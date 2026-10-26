"""SQLite-backed store for processed documents and the human review queue."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .duplicates import Match, number_key, same_supplier, supplier_key
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
CREATE TABLE IF NOT EXISTS review_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents (id),
    at TEXT NOT NULL,
    action TEXT NOT NULL,          -- approved | approved_with_override | rejected | blocked
    reason TEXT,
    changes_json TEXT NOT NULL,    -- {field: [extracted, final]} for every field the reviewer changed
    issues_json TEXT NOT NULL      -- validation issues of the final values at the time of the action
);
"""
_NEW_COLUMNS = {"supplier_key": "TEXT", "number_key": "TEXT", "file_sha256": "TEXT"}


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().split())


class Store:
    def __init__(self, path: str | Path = "docflow.db"):
        self._lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Add duplicate-matching columns to older databases and backfill them, keeping existing history."""
        have = {r["name"] for r in self.db.execute("PRAGMA table_info(documents)")}
        for col, typ in _NEW_COLUMNS.items():
            if col not in have:
                self.db.execute(f"ALTER TABLE documents ADD COLUMN {col} {typ}")
        for r in self.db.execute("SELECT id, result_json FROM documents WHERE number_key IS NULL").fetchall():
            inv = json.loads(r["result_json"])["invoice"]
            self.db.execute("UPDATE documents SET supplier_key = ?, number_key = ? WHERE id = ?",
                            (supplier_key(inv.get("supplier_name")), number_key(inv.get("invoice_number")), r["id"]))
        self.db.execute("CREATE INDEX IF NOT EXISTS ix_number_key ON documents (number_key)")
        self.db.commit()

    def find_duplicate(self, supplier: str | None, number: str | None, sha256: str | None = None,
                       exclude_id: int | None = None) -> Match | None:
        """Compare against every other document that was not rejected (rejected ones stay in history)."""
        other = -1 if exclude_id is None else exclude_id
        if sha256:
            if self.db.execute("SELECT 1 FROM documents WHERE file_sha256 = ? AND status != 'rejected' AND id != ? LIMIT 1",
                               (sha256, other)).fetchone():
                return Match.SAME_FILE
        nk = number_key(number)
        if not nk:
            return None
        sk = supplier_key(supplier)
        rows = self.db.execute("SELECT supplier_key FROM documents WHERE number_key = ? AND status != 'rejected' AND id != ?",
                               (nk, other)).fetchall()
        if any(same_supplier(sk, r["supplier_key"] or "") for r in rows):
            return Match.EXACT
        return Match.POSSIBLE if rows else None

    def is_duplicate(self, supplier: str | None, number: str | None) -> bool:
        return self.find_duplicate(supplier, number) == Match.EXACT

    def add(self, result: ExtractionResult, sha256: str | None = None) -> int:
        status = {"auto_approved": "approved", "needs_review": "pending", "rejected": "rejected"}[result.decision.value]
        inv = result.invoice
        with self._lock:
            cur = self.db.execute(
                "INSERT INTO documents (name, supplier, invoice_number, decision, status, result_json, created_at, "
                "supplier_key, number_key, file_sha256) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (result.document_name, _norm(inv.supplier_name), _norm(inv.invoice_number), result.decision.value, status,
                 result.model_dump_json(), datetime.now(timezone.utc).isoformat(), supplier_key(inv.supplier_name),
                 number_key(inv.invoice_number), sha256 or result.file_sha256),
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

    def record_review(self, doc_id: int, action: str, final: Invoice | None, reason: str | None,
                      changes: dict, issues: list) -> None:
        """Append to the audit log and, for a decision, update the document. Blocked attempts are logged too."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self.db.execute(
                "INSERT INTO review_log (doc_id, at, action, reason, changes_json, issues_json) VALUES (?, ?, ?, ?, ?, ?)",
                (doc_id, now, action, reason, json.dumps(changes, default=str),
                 json.dumps([i.model_dump(mode="json") for i in issues])),
            )
            if action != "blocked":
                status = "rejected" if action == "rejected" else "approved"
                if final is not None:  # keep duplicate matching in step with the values a person confirmed
                    self.db.execute(
                        "UPDATE documents SET status = ?, reviewed_json = ?, supplier = ?, invoice_number = ?, "
                        "supplier_key = ?, number_key = ? WHERE id = ?",
                        (status, final.model_dump_json(), _norm(final.supplier_name), _norm(final.invoice_number),
                         supplier_key(final.supplier_name), number_key(final.invoice_number), doc_id))
                else:
                    self.db.execute("UPDATE documents SET status = ? WHERE id = ?", (status, doc_id))
            self.db.commit()

    def audit(self, doc_id: int) -> list[dict]:
        rows = self.db.execute("SELECT * FROM review_log WHERE doc_id = ? ORDER BY id", (doc_id,)).fetchall()
        return [{"at": r["at"], "action": r["action"], "reason": r["reason"],
                 "changes": json.loads(r["changes_json"]), "issues": json.loads(r["issues_json"])} for r in rows]

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
        for col in _NEW_COLUMNS:
            d.pop(col, None)
        d["result"] = json.loads(d.pop("result_json"))
        d["reviewed"] = json.loads(d["reviewed_json"]) if d.get("reviewed_json") else None
        d.pop("reviewed_json", None)
        return d
