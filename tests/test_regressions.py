"""Regression tests for failures found by testing on independent, AI-generated invoices.

tests/fixtures holds three fictional test invoices (marked "TEST DOCUMENT") with layouts the
project was not built against: a header split across lines, a two-column From / Bill to
block, labels above their values, and a "SUPPLIER | BILL TO" table.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from docflow.duplicates import Match, number_key, same_supplier, supplier_key
from docflow.extractors.rules import extract_with_confidence
from docflow.ingest import document_to_text
from docflow.pipeline import process
from docflow.schema import Decision
from docflow.store import Store

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 25)


def extract(name: str):
    text = document_to_text(name, (FIX / name).read_bytes())
    inv, _, conf = extract_with_confidence(text)
    return inv, conf


def codes(result) -> set[str]:
    return {i.code for i in result.issues}


# Supplier extraction
@pytest.mark.parametrize("name, supplier", [
    ("test_invoice_1.pdf", "lanternmoss grid ltd"),   # name split over two header lines
    ("test_invoice_2.pdf", "tesselmoth print room"),  # "From: | Bill to:" side by side
    ("test_invoice_3.pdf", "lanternmoss grid ltd"),   # "SUPPLIER | BILL TO" table
])
def test_supplier_is_the_seller_not_a_label_or_the_customer(name, supplier):
    inv, conf = extract(name)
    assert inv.supplier_name.lower() == supplier
    assert conf["supplier_name"] == "high"


def test_bill_to_label_is_never_the_supplier():
    text = "Bill to:\nAcme Retail Ltd\n1 High Street\nInvoice No: INV-55\nDate: 01/09/2026\nTotal: £10.00"
    inv = extract_with_confidence(text)[0]
    assert inv.supplier_name is None or inv.supplier_name.lower() not in {"bill to", "bill to:", "acme retail ltd"}


def test_label_like_supplier_from_any_extractor_is_flagged():
    from docflow.schema import Invoice
    from docflow.validate import validate

    issues = validate(Invoice(supplier_name="BILL TO", invoice_number="X1", invoice_date=date(2026, 1, 1), total=Decimal("1")), TODAY)
    assert "SUPPLIER_IS_LABEL" in {i.code for i in issues}


# Other fields across layouts
@pytest.mark.parametrize("name, number, issued, due, currency, total", [
    ("test_invoice_1.pdf", "LMG-260305-017", "2026-03-05", "2026-04-04", "GBP", "1400.00"),
    ("test_invoice_2.pdf", "TPR-0326-088", "2026-03-05", "2026-03-03", "EUR", "1025.00"),
    ("test_invoice_3.pdf", "LMG-260305-017", "2026-03-05", "2026-04-04", "USD", "1050.00"),
])
def test_fields_on_unfamiliar_layouts(name, number, issued, due, currency, total):
    inv, _ = extract(name)
    assert inv.invoice_number == number
    assert str(inv.invoice_date) == issued and str(inv.due_date) == due
    assert inv.currency == currency and str(inv.total) == total


def test_bill_hash_label_beats_our_ref():
    inv, _ = extract("test_invoice_2.pdf")
    assert inv.invoice_number == "TPR-0326-088"  # not "SPRING-PRINT-26" from "Our ref"


def test_vat_line_is_not_confused_with_total_inc_vat():
    inv, _ = extract("test_invoice_3.pdf")
    assert (inv.subtotal, inv.vat_rate, inv.vat_amount) == (Decimal("1000.00"), Decimal("5.00"), Decimal("50.00"))


def test_line_items_in_three_layouts():
    assert [str(li.amount) for li in extract("test_invoice_1.pdf")[0].line_items] == ["800.00", "150.00", "225.00"]
    assert [str(li.amount) for li in extract("test_invoice_2.pdf")[0].line_items] == ["560.00", "285.00", "190.00"]
    assert [str(li.amount) for li in extract("test_invoice_3.pdf")[0].line_items] == ["680.00", "320.00"]


# Validation, recorded independently
def run_all(store: Store):
    out = {}
    for name in ["test_invoice_1.pdf", "test_invoice_2.pdf", "test_invoice_3.pdf"]:
        r = process(name, (FIX / name).read_bytes(), extractor="rules", find_duplicate=store.find_duplicate, today=TODAY)
        store.add(r)
        out[name] = r
    return out


def test_each_failure_is_recorded_and_decisions_match():
    res = run_all(Store(":memory:"))
    r1, r2, r3 = res["test_invoice_1.pdf"], res["test_invoice_2.pdf"], res["test_invoice_3.pdf"]

    assert codes(r1) == {"TOTAL_MISMATCH"} and r1.decision == Decision.NEEDS_REVIEW
    assert {"LINE_ITEMS_MISMATCH", "DUE_BEFORE_ISSUE"} <= codes(r2) and r2.decision == Decision.NEEDS_REVIEW
    assert "TOTAL_MISMATCH" not in codes(r2) and "LINE_ITEMS_MISMATCH" not in codes(r1)
    assert {"DUPLICATE", "PROMPT_INJECTION"} <= codes(r3) and r3.decision == Decision.REJECTED
    assert not {"TOTAL_MISMATCH", "LINE_ITEMS_MISMATCH"} & codes(r3)  # invoice 3's maths is correct


def test_injection_is_removed_but_legitimate_notes_survive():
    text = document_to_text("i3.pdf", (FIX / "test_invoice_3.pdf").read_bytes())
    from docflow.guard import scan

    g = scan(text)
    assert g.flagged and "Ignore previous instructions" not in g.sanitised_text
    assert "Meter readings are estimated" in g.sanitised_text


# Duplicates
def test_normalisation():
    assert supplier_key("LANTERNMOSS GRID LTD") == supplier_key("Lanternmoss Grid Limited") == "lanternmoss grid"
    assert number_key("LMG-260305-017") == number_key("lmg 260305 017")
    assert same_supplier("lanternmoss grid", "lanternmoss grid energy")
    assert not same_supplier("kestrel it", "northgate office supplies")


def test_duplicate_across_formats_and_currencies():
    store = Store(":memory:")
    run_all(store)
    resent = ("Lanternmoss Grid Limited\nInvoice number: LMG 260305 017\nInvoice date: 2026-03-05\n"
              "Subtotal: EUR 900.00\nVAT 20%: EUR 180.00\nTotal: EUR 1,080.00").encode()
    r = process("resent.txt", resent, extractor="rules", find_duplicate=store.find_duplicate, today=TODAY)
    assert r.decision == Decision.REJECTED


def test_same_number_from_another_supplier_needs_review_not_rejection():
    store = Store(":memory:")
    run_all(store)
    other = ("Brightline Cleaning Services\nInvoice number: LMG-260305-017\nInvoice date: 2026-03-05\n"
             "Subtotal: £100.00\nVAT 20%: £20.00\nTotal: £120.00").encode()
    r = process("other.txt", other, extractor="rules", find_duplicate=store.find_duplicate, today=TODAY)
    assert "POSSIBLE_DUPLICATE" in codes(r) and r.decision == Decision.NEEDS_REVIEW


def test_reuploading_the_same_file_is_rejected():
    store = Store(":memory:")
    data = (FIX / "test_invoice_2.pdf").read_bytes()
    store.add(process("a.pdf", data, extractor="rules", find_duplicate=store.find_duplicate, today=TODAY))
    again = process("a (1).pdf", data, extractor="rules", find_duplicate=store.find_duplicate, today=TODAY)
    assert again.decision == Decision.REJECTED


def test_old_database_is_migrated_and_history_kept(tmp_path):
    import sqlite3

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript("""CREATE TABLE documents (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, supplier TEXT,
        invoice_number TEXT, decision TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, reviewed_json TEXT,
        created_at TEXT NOT NULL);""")
    first = process("test_invoice_1.pdf", (FIX / "test_invoice_1.pdf").read_bytes(), extractor="rules", today=TODAY)
    con.execute("INSERT INTO documents (name, supplier, invoice_number, decision, status, result_json, created_at) "
                "VALUES ('old.pdf', 'x', 'y', 'needs_review', 'pending', ?, '2026-01-01')", (first.model_dump_json(),))
    con.commit()
    con.close()
    store = Store(db)
    assert len(store.list()) == 1
    assert store.find_duplicate("Lanternmoss Grid Ltd", "LMG-260305-017") == Match.EXACT


# Never auto-approve unreliable data
def test_missing_required_fields_are_null_and_block_auto_approval():
    r = process("thin.txt", b"Thanks for your order!\nTotal: \xc2\xa340.00", extractor="rules", today=TODAY)
    assert r.invoice.invoice_number is None and r.invoice.invoice_date is None
    assert r.decision != Decision.AUTO_APPROVED


# LLM output is ground-checked
# The exact answer qwen2.5:3b (Ollama, CPU) gave for test_invoice_2.pdf: the tagline as the supplier and a
# due date (20 March) that is not in the document, which hid the real due-before-issue problem.
QWEN_INVOICE_2 = {
    "supplier_name": "Independent Book Printer", "invoice_number": "TPR-0326-088", "invoice_date": "2026-03-05",
    "due_date": "2026-03-20", "currency": "EUR", "subtotal": 1025, "vat_rate": 0, "vat_amount": 0, "total": 1025,
    "line_items": [{"description": "A5 printed storybooks", "quantity": 20, "unit_price": 28, "amount": 560},
                   {"description": "Pocket field guides", "quantity": 15, "unit_price": 19, "amount": 285},
                   {"description": "Gift wrap and dispatch", "quantity": 1, "unit_price": 190, "amount": 190}],
}


@pytest.fixture
def qwen(monkeypatch):
    import json

    from docflow.extractors import llm

    calls = []

    def _call(cfg, messages):
        calls.append(messages[-1]["content"])
        return json.dumps(QWEN_INVOICE_2), 900, 200  # the model repeats itself when asked to re-check

    monkeypatch.setattr(llm, "_call", _call)
    return calls


def test_hallucinated_llm_fields_are_caught_and_corrected(qwen):
    from docflow.extractors.llm import ProviderConfig

    cfg = ProviderConfig(provider="ollama", model="qwen2.5:3b", api_key="")
    r = process("test_invoice_2.pdf", (FIX / "test_invoice_2.pdf").read_bytes(), extractor="llm", provider=cfg, today=TODAY)
    assert str(r.invoice.due_date) == "2026-03-03"  # the date that is actually printed
    # The two extractors disagree on the supplier. Neither overrules the other; a person decides.
    assert r.invoice.supplier_name == "Independent Book Printer"
    supplier = [i for i in r.issues if i.code == "FIELD_DISAGREEMENT" and i.field == "supplier_name"]
    assert supplier and supplier[0].severity.value == "error" and "Tesselmoth" in supplier[0].message
    assert {"UNGROUNDED_FIELD", "DUE_BEFORE_ISSUE", "LINE_ITEMS_MISMATCH"} <= codes(r)
    assert r.repair_attempts == 1 and "isn't in the document" in qwen[1]
    assert r.decision == Decision.NEEDS_REVIEW


def test_values_both_extractors_agree_on_pass_untouched():
    from docflow.crosscheck import reconcile
    from docflow.schema import Invoice

    text = document_to_text("i1.pdf", (FIX / "test_invoice_1.pdf").read_bytes())
    rules_inv, _, _ = extract_with_confidence(text)
    inv, issues, conf = reconcile(Invoice.model_validate(rules_inv.model_dump()), rules_inv, text)
    assert issues == [] and inv == rules_inv and conf["total"] == "high"
