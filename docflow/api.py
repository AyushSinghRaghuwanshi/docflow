"""FastAPI service: upload documents, see decisions, and work the human review queue.

Run:  uvicorn docflow.api:app --reload    then open http://localhost:8000
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .evidence import locate
from .extractors.llm import for_images, resolve_provider
from .ingest import IMAGES, UnsupportedDocument, document_to_text
from .pipeline import process
from .review import MIN_REASON, decide_review
from .schema import Invoice
from .store import Store

MAX_BYTES = 5 * 1024 * 1024
STATIC = Path(__file__).parent / "static"
FILES = Path(os.getenv("DOCFLOW_FILES", "files"))  # originals, kept so a reviewer can see what was read
BENCHMARKS = Path(__file__).resolve().parents[1] / "evals" / "results" / "dashboard.json"
MEDIA = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
         ".csv": "text/plain; charset=utf-8", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         **IMAGES}

app = FastAPI(title="DocFlow", version="0.1.0",
              description="AI agent that turns messy invoices into validated, structured data.")
store = Store(os.getenv("DOCFLOW_DB", "docflow.db"))
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _original(doc: dict) -> Path | None:
    sha, name = doc["result"].get("file_sha256"), doc["name"]
    path = FILES / f"{sha}{Path(name).suffix.lower()}" if sha else None
    return path if path and path.exists() else None


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
    return {"status": "ok", "extractor": f"llm:{cfg.provider}:{cfg.model}" if cfg else "rules (no LLM key set)",
            "provider": cfg.provider if cfg else None, "model": cfg.model if cfg else None,
            "vision_model": for_images(cfg).model if cfg else None,
            "images_supported": cfg is not None, "max_upload_mb": MAX_BYTES // (1024 * 1024)}


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
    FILES.mkdir(parents=True, exist_ok=True)
    (FILES / f"{result.file_sha256}{Path(file.filename or '').suffix.lower()}").write_bytes(data)
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


@app.get("/documents/{doc_id}/file", include_in_schema=False)
def original_file(doc_id: int) -> FileResponse:
    """The uploaded file, shown inline next to the extracted fields."""
    doc = store.get(doc_id)
    path = _original(doc) if doc else None
    if not path:
        raise HTTPException(404, "The original file wasn't kept for this document.")
    return FileResponse(path, media_type=MEDIA.get(path.suffix, "application/octet-stream"),
                        headers={"Content-Disposition": f'inline; filename="{doc["name"]}"'})


@app.get("/documents/{doc_id}/evidence")
def evidence(doc_id: int) -> dict:
    """The document text DocFlow read, and where each extracted value appears in it."""
    doc = store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    path = _original(doc)
    if not path or path.suffix in IMAGES:
        return {"text": None, "spans": {}}
    text = document_to_text(doc["name"], path.read_bytes())
    inv = Invoice.model_validate(doc.get("reviewed") or doc["result"]["invoice"])
    return {"text": text, "spans": locate(inv, text)}


@app.get("/benchmarks")
def benchmarks() -> dict:
    """Published evaluation results (built by evals/build_dashboard_data.py)."""
    if not BENCHMARKS.exists():
        raise HTTPException(404, "No benchmark summary yet: run python evals/build_dashboard_data.py")
    import json

    return json.loads(BENCHMARKS.read_text(encoding="utf-8"))


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
