"""MCP server: lets an AI agent (Claude Desktop, an agent framework, ...) use DocFlow as a tool.

The agent gets the same pipeline and the same review rules as a person, with two extra limits:

- it can only read files from one inbox folder (DOCFLOW_INBOX, default ./inbox), never an
  arbitrary path on the machine;
- it can approve a document only when no errors remain. Overriding an error with a reason is
  reserved for a person in the web review page.

Run:  python -m docflow.mcp_server          (stdio, for Claude Desktop and most agent hosts)
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .pipeline import process
from .review import decide_review
from .schema import Invoice
from .store import Store

INBOX = Path(os.getenv("DOCFLOW_INBOX", "inbox")).resolve()
FILES = Path(os.getenv("DOCFLOW_FILES", "files"))
store = Store(os.getenv("DOCFLOW_DB", "docflow.db"))
server = MCPServer(name="docflow", instructions=(
    "DocFlow extracts and checks invoices and receipts. Put files in the inbox folder, call process_document "
    "with the file name, read the decision and issues, and only approve when no errors remain. Anything with "
    "open errors must be left for a person."))


def _inbox_file(name: str) -> Path:
    path = (INBOX / name).resolve()
    if INBOX not in path.parents or not path.is_file():
        raise ToolError(f"'{name}' is not a file in the DocFlow inbox ({INBOX}).")
    return path


def _summary(doc: dict) -> dict:
    inv = doc.get("reviewed") or doc["result"]["invoice"]
    return {"id": doc["id"], "file": doc["name"], "decision": doc["decision"], "status": doc["status"],
            "supplier": inv.get("supplier_name"), "invoice_number": inv.get("invoice_number"),
            "total": inv.get("total"), "currency": inv.get("currency"),
            "issues": [f"{i['severity']}: [{i['code']}] {i['message']}" for i in doc["result"]["issues"]]}


@server.tool()
def list_inbox() -> list[str]:
    """List the files waiting in the DocFlow inbox."""
    return sorted(p.name for p in INBOX.iterdir() if p.is_file()) if INBOX.exists() else []


@server.tool()
def process_document(file_name: str) -> dict:
    """Extract, check and decide on one invoice or receipt from the inbox. Returns the decision and every issue."""
    path = _inbox_file(file_name)
    data = path.read_bytes()
    result = process(path.name, data, find_duplicate=store.find_duplicate)
    FILES.mkdir(parents=True, exist_ok=True)  # kept so the document can be reviewed in the web app too
    (FILES / f"{result.file_sha256}{path.suffix.lower()}").write_bytes(data)
    return _summary(store.get(store.add(result)))


@server.tool()
def list_documents(status: str = "pending") -> list[dict]:
    """List processed documents by status: pending (waiting for review), approved or rejected."""
    if status not in ("pending", "approved", "rejected"):
        raise ToolError("status must be pending, approved or rejected")
    return [_summary(d) for d in store.list(status)]


@server.tool()
def get_document(document_id: int) -> dict:
    """Full extracted fields, issues and review history for one document."""
    doc = store.get(document_id)
    if not doc:
        raise ToolError(f"No document {document_id}.")
    return {**_summary(doc), "fields": doc.get("reviewed") or doc["result"]["invoice"], "audit": store.audit(document_id)}


@server.tool()
def review_document(document_id: int, approve: bool, corrections: dict | None = None, note: str | None = None) -> dict:
    """Approve or reject a pending document, optionally correcting fields first.

    Approval is re-validated; if any error remains it is refused, and the agent must leave it for a person.
    """
    doc = store.get(document_id)
    if not doc:
        raise ToolError(f"No document {document_id}.")
    if doc["status"] != "pending":
        raise ToolError(f"Document {document_id} is already {doc['status']}.")
    corrected = Invoice.model_validate({**doc["result"]["invoice"], **corrections}) if corrections else None
    # reason=None: an agent can never use the override path
    out = decide_review(doc, approve, corrected, None, store.find_duplicate)
    store.record_review(document_id, out.action, out.final, f"[agent] {note}" if note else "[agent]", out.changes, out.issues)
    if out.action == "blocked":
        return {"approved": False, "status": "pending",
                "message": "Approval refused: errors remain. Leave this document for a person to review.",
                "open_errors": [f"[{i.code}] {i.message}" for i in out.blocking]}
    return {"status": store.get(document_id)["status"], "action": out.action}


if __name__ == "__main__":
    INBOX.mkdir(parents=True, exist_ok=True)
    server.run()
