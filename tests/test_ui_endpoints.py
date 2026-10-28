"""Endpoints the review screen relies on: the original file, evidence locations, metrics and benchmarks."""
import importlib
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from docflow.evidence import locate
from docflow.schema import Invoice

DOC = """Kestrel IT Solutions Ltd
Invoice Number: INV-8001
Invoice Date: 5th March 2026
Due Date: 04/04/2026
Toner cartridge 2 x £50.00 £100.00
Subtotal: £100.00
VAT (20%): £20.00
Total Due: £1,120.00
"""


def test_evidence_finds_values_by_meaning_not_just_spelling():
    inv = Invoice(supplier_name="KESTREL IT SOLUTIONS LTD", invoice_number="INV 8001", invoice_date=date(2026, 3, 5),
                  due_date=date(2026, 4, 4), subtotal=Decimal("100.00"), vat_amount=Decimal("20.00"), total=Decimal("1120.00"))
    spans = locate(inv, DOC)
    shown = {f: [DOC[s:e] for s, e in v] for f, v in spans.items()}
    assert shown["supplier_name"] == ["Kestrel IT Solutions Ltd"]
    assert shown["invoice_number"] == ["INV-8001"]
    assert shown["invoice_date"] == ["5th March 2026"] and shown["due_date"] == ["04/04/2026"]
    assert "£1,120.00" in shown["total"][0] and "£20.00" in shown["vat_amount"][0]


def test_vat_rate_and_currency_are_located():
    spans = locate(Invoice(vat_rate=Decimal("20"), currency="GBP"), DOC)
    assert [DOC[s:e] for s, e in spans["vat_rate"]] == ["20%"]
    assert DOC[slice(*spans["currency"][0])] == "£"


def test_value_not_in_the_document_has_no_evidence():
    assert "total" not in locate(Invoice(total=Decimal("999.99")), DOC)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCFLOW_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("DOCFLOW_FILES", str(tmp_path / "files"))
    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DOCFLOW_PROVIDER"]:
        monkeypatch.delenv(var, raising=False)
    import docflow.api as api
    importlib.reload(api)
    return TestClient(api.app)


def test_original_file_and_evidence_are_served(client):
    doc = client.post("/documents", files={"file": ("k.txt", DOC.encode(), "text/plain")}).json()
    f = client.get(f"/documents/{doc['id']}/file")
    assert f.status_code == 200 and f.content == DOC.encode() and "inline" in f.headers["content-disposition"]
    ev = client.get(f"/documents/{doc['id']}/evidence").json()
    assert ev["text"].startswith("Kestrel") and "supplier_name" in ev["spans"]


def test_metrics_report_status_and_issues(client):
    client.post("/documents", files={"file": ("a.txt", DOC.encode(), "text/plain")})
    m = client.get("/metrics").json()
    assert m["documents"] == 1 and set(m["by_status"]) == {"pending", "approved", "rejected"}
    assert any(i["code"] == "TOTAL_MISMATCH" for i in m["issues"])


def test_ui_and_static_files_load(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.css").status_code == 200 and client.get("/static/app.js").status_code == 200


def test_benchmarks_summary(client):
    b = client.get("/benchmarks").json()
    assert b["sroie_finetune"]["receipts"] == 347 and b["published"]
