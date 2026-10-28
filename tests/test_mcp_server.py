"""The MCP server gives an agent the pipeline, but not a way round the rules."""
import asyncio
import importlib
import json

import pytest

pytest.importorskip("mcp")

GOOD = """Kestrel IT Solutions Ltd
Invoice Number: INV-5001
Invoice Date: 01/09/2026
Due Date: 01/10/2026
Toner cartridge 2 x £50.00 £100.00
Subtotal: £100.00
VAT (20%): £20.00
Total Due: £120.00
"""


@pytest.fixture
def srv(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "good.txt").write_text(GOOD, encoding="utf-8")
    (inbox / "bad.txt").write_text(GOOD.replace("£120.00", "£150.00").replace("INV-5001", "INV-5002"), encoding="utf-8")
    (tmp_path / "secret.txt").write_text("not an invoice", encoding="utf-8")
    monkeypatch.setenv("DOCFLOW_INBOX", str(inbox))
    monkeypatch.setenv("DOCFLOW_DB", str(tmp_path / "mcp.db"))
    monkeypatch.setenv("DOCFLOW_FILES", str(tmp_path / "files"))
    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DOCFLOW_PROVIDER"]:
        monkeypatch.delenv(var, raising=False)
    import docflow.mcp_server as m
    return importlib.reload(m)


def call(m, name, **args):
    """Call a tool the way an MCP client would; tool errors come back as errors, not crashes."""
    try:
        result = asyncio.run(m.server.call_tool(name, args))
    except Exception as e:  # noqa: BLE001
        raise ToolFailed(str(e)) from e
    if getattr(result, "is_error", False):
        raise ToolFailed(" ".join(getattr(c, "text", "") for c in result.content))
    data = result.structured_content
    if data is None:  # plain dicts come back as JSON text content
        data = json.loads(result.content[0].text)
    return data["result"] if isinstance(data, dict) and set(data) == {"result"} else data


class ToolFailed(Exception):
    pass


def test_tools_are_listed(srv):
    names = {t.name for t in asyncio.run(srv.server.list_tools())}
    assert {"list_inbox", "process_document", "list_documents", "get_document", "review_document"} <= names


def test_agent_processes_a_clean_invoice(srv):
    assert call(srv, "list_inbox") == ["bad.txt", "good.txt"]
    out = call(srv, "process_document", file_name="good.txt")
    assert out["decision"] == "auto_approved" and out["total"] == "120.00"


def test_agent_cannot_read_outside_the_inbox(srv):
    with pytest.raises(ToolFailed):
        call(srv, "process_document", file_name="../secret.txt")
    with pytest.raises(ToolFailed):
        call(srv, "process_document", file_name=str(srv.INBOX.parent / "secret.txt"))


def test_agent_cannot_approve_while_errors_remain(srv):
    doc = call(srv, "process_document", file_name="bad.txt")
    assert doc["decision"] == "needs_review"
    out = call(srv, "review_document", document_id=doc["id"], approve=True, note="looks fine to me")
    assert out["approved"] is False and any("TOTAL_MISMATCH" in e for e in out["open_errors"])
    assert call(srv, "get_document", document_id=doc["id"])["status"] == "pending"


def test_agent_can_approve_after_a_real_fix_and_it_is_audited(srv):
    doc = call(srv, "process_document", file_name="bad.txt")
    out = call(srv, "review_document", document_id=doc["id"], approve=True, corrections={"total": "120.00"}, note="total misread")
    assert out["status"] == "approved"
    audit = call(srv, "get_document", document_id=doc["id"])["audit"]
    assert audit[-1]["reason"].startswith("[agent]") and audit[-1]["changes"]["total"] == ["150.00", "120.00"]
