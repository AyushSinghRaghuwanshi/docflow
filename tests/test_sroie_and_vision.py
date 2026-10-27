"""SROIE loading and scoring, receipt date formats, and the image (vision-model) path."""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

from docflow.extractors import llm
from docflow.extractors.llm import ProviderConfig
from docflow.parsing import parse_date
from docflow.pipeline import process
from docflow.schema import Decision

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from run_sroie import correct, load, sample  # noqa: E402

BOX = """98,26,321,26,321,66,98,66,TAN CHAY YEE
80,119,329,119,329,140,80,140,OJC MARKETING SDN BHD
104,163,306,163,306,182,104,182,NO 2 & 4, JALAN BAYU 4,
10,300,60,300,60,320,10,320,DATE: 15/01/2019
10,330,60,330,60,350,10,350,TOTAL: 193.00
"""
LABELS = {"company": "OJC MARKETING SDN BHD", "date": "15/01/2019", "address": "NO 2 & 4, JALAN BAYU 4", "total": "193.00"}


@pytest.fixture
def sroie(tmp_path):
    for sub in ("box", "entities", "img"):
        (tmp_path / "test" / sub).mkdir(parents=True)
    (tmp_path / "test" / "box" / "X1.txt").write_text(BOX)
    (tmp_path / "test" / "entities" / "X1.txt").write_text(json.dumps(LABELS))
    (tmp_path / "test" / "img" / "X1.jpg").write_bytes(b"\xff\xd8fakejpeg")
    return tmp_path


def test_loader_keeps_text_with_commas_and_finds_the_image(sroie):
    [doc] = load(sroie / "test")
    assert "NO 2 & 4, JALAN BAYU 4," in doc["text"] and doc["image"].name == "X1.jpg"
    assert doc["labels"]["company"] == "OJC MARKETING SDN BHD"


def test_sample_is_fixed():
    docs = [{"id": f"X{i:03d}"} for i in range(50)]
    assert sample(docs, 10) == sample(docs, 10) and len(sample(docs, 10)) == 10


@pytest.mark.parametrize("field, got, want, ok", [
    ("company", "OJC Marketing Sdn. Bhd.", "OJC MARKETING SDN BHD", True),
    ("company", "TAN CHAY YEE", "OJC MARKETING SDN BHD", False),
    ("date", "2019-01-15", "15/01/2019", True),
    ("date", "2019-01-16", "15/01/2019", False),
    ("total", "193.0", "193.00", True),
    ("total", "1,193.00", "193.00", False),
    ("address", "no 2 & 4 jalan bayu 4", "NO 2 & 4, JALAN BAYU 4", True),
    ("total", "10.00", "", None),  # no usable answer in the dataset: not scored
])
def test_scoring(field, got, want, ok):
    assert correct(field, got, want) is ok


@pytest.mark.parametrize("raw, expected", [
    ("28-01-18", date(2018, 1, 28)), ("15/APR/2017", date(2017, 4, 15)), ("28 MAR 18", date(2018, 3, 28)),
    ("2018/02/22", date(2018, 2, 22)), ("11.02.18", date(2018, 2, 11)), ("12/28/2017", date(2017, 12, 28)),
    ("20180304", date(2018, 3, 4)), ("05/04/2018", date(2018, 4, 5)),  # day first when both are possible
])
def test_receipt_date_formats(raw, expected):
    assert parse_date(raw) == expected


ANSWER = {"supplier_name": "OJC MARKETING SDN BHD", "supplier_address": "NO 2 & 4, JALAN BAYU 4", "invoice_number": "R-1",
          "invoice_date": "2019-01-15", "currency": "MYR", "subtotal": 193, "vat_amount": 0, "total": 193, "line_items": []}


@pytest.fixture
def seen(monkeypatch):
    calls = []

    def _call(cfg, messages):
        calls.append(messages)
        return json.dumps(ANSWER), 800, 100

    monkeypatch.setattr(llm, "_call", _call)
    return calls


@pytest.mark.parametrize("provider, check", [
    ("ollama", lambda m: m["images"] and m["content"]),
    ("anthropic", lambda m: m["content"][0]["type"] == "image" and m["content"][0]["source"]["media_type"] == "image/jpeg"),
    ("openai", lambda m: m["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")),
])
def test_image_is_sent_in_each_providers_format(seen, provider, check):
    cfg = ProviderConfig(provider=provider, model="m", api_key="k")
    r = process("receipt.jpg", b"\xff\xd8fakejpeg", extractor="llm", provider=cfg, today=date(2026, 10, 25))
    assert check(seen[0][0])  # the request (the reply is appended to the same history)
    assert r.invoice.supplier_address == "NO 2 & 4, JALAN BAYU 4" and r.extractor == f"vision:{provider}"


def test_images_always_go_to_a_person(seen):
    cfg = ProviderConfig(provider="ollama", model="qwen2.5vl:3b", api_key="")
    r = process("receipt.png", b"\x89PNGfake", extractor="llm", provider=cfg, today=date(2026, 10, 25))
    assert r.decision == Decision.NEEDS_REVIEW and "IMAGE_UNVERIFIED" in {i.code for i in r.issues}


def test_images_need_a_model():
    with pytest.raises(RuntimeError):
        process("receipt.jpg", b"\xff\xd8", extractor="rules")


def test_supplier_name_missing_from_text_is_kept_but_flagged():
    from docflow.crosscheck import reconcile
    from docflow.schema import Invoice

    text = "TAN WOON YANN\nNO 2, JALAN BAYU\nTOTAL 10.00\n"  # the company name is only in the logo
    model = Invoice(supplier_name="MR D.I.Y. (JOHOR) SDN BHD", total=10)
    inv, issues, _ = reconcile(model, Invoice(supplier_name="TAN WOON YANN", total=10), text)
    assert inv.supplier_name == "MR D.I.Y. (JOHOR) SDN BHD"
    assert any(i.code == "UNGROUNDED_FIELD" and i.field == "supplier_name" for i in issues)
