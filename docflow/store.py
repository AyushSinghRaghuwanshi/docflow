"""SQLite-backed store for processed documents and the human review queue."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .schema import Decision, ExtractionResult, Invoice

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    supplier TEXT,
    invoice_number TEXT,
    decision TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL,
    reviewed_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_dupe ON documents (supplier, invoice_number);
"""


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().split())


class Store:
    def __init__(self, path: str | Path = "docflow.db"):
        self._lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)

    def is_duplicate(self, supplier: str | None, number: str | None) -> bool:
        if not supplier or not number:
            return False
        row = self.db.execute(
            "SELECT 1 FROM documents WHERE supplier = ? AND invoice_number = ? AND status != 'rejected' LIMIT 1",
            (_norm(supplier), _norm(number)),
        ).fetchone()
        return row is not None

    def add(self, result: ExtractionResult) -> int:
        status = {"auto_approved": "approved", "needs_review": "pending", "rejected": "rejected"}[result.decision.value]
        with self._lock:
            cur = self.db.execute(
                "INSERT INTO documents (name, supplier, invoice_number, decision, status, result_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (result.document_name, _norm(result.invoice.supplier_name), _norm(result.invoice.invoice_number),
                 result.decision.value, status, result.model_dump_json(), datetime.now(timezone.utc).isoformat()),
            )
            self.db.commit()
            return int(cur.lastrowid)

    def get(self, doc_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return self._row(row) if row else None

    def list(self, status: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM documents", ()
        if status:
            q, args = q + " WHERE status = ?", (status,)
        return [self._row(r) for r in self.db.execute(q + " ORDER BY id DESC", args).fetchall()]

    def review(self, doc_id: int, approve: bool, corrected: Invoice | None) -> dict | None:
        with self._lock:
            self.db.execute(
                "UPDATE documents SET status = ?, reviewed_json = ? WHERE id = ?",
                ("approved" if approve else "rejected", corrected.model_dump_json() if corrected else None, doc_id),
            )
            self.db.commit()
        return self.get(doc_id)

    def metrics(self) -> dict:
        rows = [self._row(r) for r in self.db.execute("SELECT * FROM documents").fetchall()]
        n = len(rows)
        cost = sum(r["result"]["usage"]["cost_usd"] for r in rows)
        by_decision = {d.value: sum(1 for r in rows if r["decision"] == d.value) for d in Decision}
        return {
            "documents": n,
            "by_decision": by_decision,
            "straight_through_rate": round(by_decision["auto_approved"] / n, 3) if n else 0.0,
            "injections_blocked": sum(1 for r in rows if r["result"]["injection_detected"]),
            "total_cost_usd": round(cost, 6),
            "avg_cost_per_document_usd": round(cost / n, 6) if n else 0.0,
        }

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json"))
        d["reviewed"] = json.loads(d["reviewed_json"]) if d.get("reviewed_json") else None
        d.pop("reviewed_json", None)
        return d
