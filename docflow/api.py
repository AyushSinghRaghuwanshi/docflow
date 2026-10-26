"""FastAPI service: upload documents, see decisions, and work the human review queue.

Run:  uvicorn docflow.api:app --reload    then open http://localhost:8000
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .extractors.llm import resolve_provider
from .ingest import UnsupportedDocument
from .pipeline import process
from .review import MIN_REASON, decide_review
from .schema import Invoice
from .store import Store

MAX_BYTES = 5 * 1024 * 1024
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="DocFlow", version="0.1.0",
              description="AI agent that turns messy invoices into validated, structured data.")
store = Store(os.getenv("DOCFLOW_DB", "docflow.db"))


class ReviewRequest(BaseModel):
    approve: bool
    corrected: Invoice | None = None
    reason: str | None = None  # required to approve while errors remain; stored in the audit log


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    cfg = resolve_provider()
    return {"status": "ok", "extractor": f"llm:{cfg.provider}:{cfg.model}" if cfg else "rules (no LLM key set)"}


@app.post("/documents", status_code=201)
async def upload(file: UploadFile = File(...), extractor: str = Query("auto", pattern="^(auto|rules|llm)$")) -> dict:
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File larger than 5 MB.")
    try:
        # Run in a worker thread: an LLM call can take a minute on CPU and must not freeze the rest of the API.
        result = await run_in_threadpool(process, file.filename or "upload", data, extractor=extractor,
                                         find_duplicate=store.find_duplicate)
    except UnsupportedDocument as e:
        raise HTTPException(415, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    doc_id = store.add(result)
    return store.get(doc_id)


@app.get("/documents")
def list_documents(status: str | None = Query(None, pattern="^(pending|approved|rejected)$")) -> list[dict]:
    return store.list(status)


@app.get("/documents/{doc_id}")
def get_document(doc_id: int) -> dict:
    doc = store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return {**doc, "audit": store.audit(doc_id)}


@app.post("/documents/{doc_id}/review")
def review(doc_id: int, body: ReviewRequest) -> dict:
    """Approve or reject a pending document. Approval re-validates the final values on the server."""
    doc = store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    if doc["status"] != "pending":
        raise HTTPException(409, f"Only pending documents can be reviewed; this one is {doc['status']}.")
    out = decide_review(doc, body.approve, body.corrected, body.reason, store.find_duplicate)
    store.record_review(doc_id, out.action, out.final, body.reason, out.changes, out.issues)
    if out.action == "blocked":
        raise HTTPException(409, {
            "message": f"Approval blocked: {len(out.blocking)} error(s) remain in the final values. Fix them, or give an "
                       f"override reason of at least {MIN_REASON} characters.",
            "issues": [i.model_dump(mode="json") for i in out.blocking]})
    return get_document(doc_id)


@app.get("/metrics")
def metrics() -> dict:
    return store.metrics()
