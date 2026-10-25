"""FastAPI service: upload documents, see decisions, and work the human review queue.

Run:  uvicorn docflow.api:app --reload    then open http://localhost:8000
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .extractors.llm import resolve_provider
from .ingest import UnsupportedDocument
from .pipeline import process
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
        result = process(file.filename or "upload", data, extractor=extractor, is_duplicate=store.is_duplicate)
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
    return doc


@app.post("/documents/{doc_id}/review")
def review(doc_id: int, body: ReviewRequest) -> dict:
    if not store.get(doc_id):
        raise HTTPException(404, "Document not found.")
    return store.review(doc_id, body.approve, body.corrected)


@app.get("/metrics")
def metrics() -> dict:
    return store.metrics()
