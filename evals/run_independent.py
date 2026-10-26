"""Score DocFlow on an independent, externally produced invoice set, and keep that set honest.

The set lives in one folder: the invoice files plus `expected.csv`, written *before* DocFlow sees them
(see docs/independent_test_brief.md for the format). Labels describe facts about each document (its
fields and its deliberate faults), not DocFlow's decision; the expected decision is derived here from
the review policy below, so the labels stay valid if the policy changes.

Freezing: the first run records a fingerprint of every file in the set and of DocFlow's code. Later
runs refuse to score a set whose files changed, and if DocFlow's code changed since the first run the
report is marked "development set": once you fix failures found here, these documents no longer
measure generalisation and a fresh set is needed.

Usage:  python evals/run_independent.py path/to/set --extractor llm
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from docflow.duplicates import supplier_key  # noqa: E402
from docflow.extractors.llm import resolve_provider  # noqa: E402
from docflow.pipeline import process  # noqa: E402
from docflow.schema import Severity  # noqa: E402
from docflow.store import Store  # noqa: E402

FIELDS = ["supplier_name", "invoice_number", "invoice_date", "due_date", "currency", "subtotal", "vat_amount", "total"]
MONEY = {"subtotal", "vat_amount", "total"}

# Fault vocabulary used in expected.csv -> the DocFlow error code(s) that count as detecting it.
FAULTS: dict[str, set[str]] = {
    "total_mismatch": {"TOTAL_MISMATCH"},
    "line_items_mismatch": {"LINE_ITEMS_MISMATCH"},
    "vat_mismatch": {"VAT_MISMATCH"},  # VAT amount != rate x subtotal; counts as caught only if raised as an error
    "due_before_issue": {"DUE_BEFORE_ISSUE"},
    "future_date": {"FUTURE_DATE"},
    "missing_required_field": {"MISSING_FIELD"},
    "duplicate_exact": {"DUPLICATE"},
    "duplicate_reformatted": {"DUPLICATE"},
    "same_number_other_supplier": {"POSSIBLE_DUPLICATE"},
    "prompt_injection": {"PROMPT_INJECTION"},
}
REJECT = {"duplicate_exact", "duplicate_reformatted"}


def expected_decision(faults: set[str]) -> str:
    """The review policy, stated once: duplicates are rejected, any other fault goes to a person."""
    if faults & REJECT:
        return "rejected"
    return "needs_review" if faults else "auto_approved"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_fingerprint() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "docflow").rglob("*")):
        if p.is_file() and p.suffix in {".py", ".html"}:
            h.update(p.relative_to(ROOT).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:16]


def load(folder: Path) -> list[dict]:
    with open(folder / "expected.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["faults"] = {x.strip() for x in (r.get("faults") or "").split(";") if x.strip() and x.strip() != "none"}
        unknown = r["faults"] - FAULTS.keys()
        if unknown:
            raise SystemExit(f"{r['file']}: unknown fault type(s) {sorted(unknown)}; allowed: {sorted(FAULTS)}")
        if not (folder / r["file"]).exists():
            raise SystemExit(f"expected.csv lists {r['file']}, which is not in {folder}")
    return sorted(rows, key=lambda r: int(r["order"]))


def check_frozen(folder: Path, rows: list[dict], allow_changed: bool) -> dict:
    files = {r["file"]: _sha(folder / r["file"]) for r in rows} | {"expected.csv": _sha(folder / "expected.csv")}
    log_path = folder / "docflow_runs.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"manifest": files, "runs": []}
    changed = sorted(k for k in files.keys() | log["manifest"].keys() if files.get(k) != log["manifest"].get(k))
    if changed and not allow_changed:
        raise SystemExit(f"The test set changed after its first run ({', '.join(changed[:5])}). A frozen set must not be "
                         "edited; use a new folder for a new set, or pass --allow-changed to score it anyway.")
    fp = code_fingerprint()
    first = log["runs"][0]["code"] if log["runs"] else fp
    return {"log": log, "path": log_path, "code": fp, "first_code": first, "set_changed": changed,
            "status": "held-out (first contact with this code)" if fp == first and not changed
            else "development set (DocFlow or the set changed since the first run; not evidence of generalisation)"}


def same(field: str, got, want: str) -> bool:
    want = (want or "").strip()
    if not want:
        return got in (None, "")
    if got in (None, ""):
        return False
    if field in MONEY:
        try:
            return Decimal(str(got)) == Decimal(want.replace(",", ""))
        except InvalidOperation:
            return False
    if field == "supplier_name":  # "Ltd" vs "Limited" and letter case are not extraction errors
        return supplier_key(str(got)) == supplier_key(want)
    if field == "invoice_number":
        return str(got).strip().upper() == want.upper()
    return str(got).strip().upper() == want.upper()


def run(folder: Path, extractor: str, today: date) -> dict:
    rows = load(folder)
    store = Store(":memory:")
    hits: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    confusion: Counter = Counter()
    fault_seen: Counter = Counter()
    fault_caught: Counter = Counter()
    false_errors: Counter = Counter()
    per_doc, cost, latency, calls, repairs, crashed = [], 0.0, 0.0, 0, 0, 0

    for i, r in enumerate(rows, 1):
        want_decision = expected_decision(r["faults"])
        try:
            res = process(r["file"], (folder / r["file"]).read_bytes(), extractor=extractor,
                          find_duplicate=store.find_duplicate, today=today)
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the run; it is scored as a miss
            crashed += 1
            confusion[(want_decision, "crashed")] += 1
            per_doc.append({"file": r["file"], "expected": want_decision, "got": "crashed", "error": str(e)[:200]})
            print(f"  {i}/{len(rows)} {r['file']}: CRASH {e}", flush=True)
            continue
        store.add(res)
        got = res.invoice.model_dump(mode="json")
        wrong = []
        for f in FIELDS:
            ok = same(f, got.get(f), r.get(f, ""))
            hits[f][0] += ok
            hits[f][1] += 1
            if not ok:
                wrong.append(f"{f}: got {got.get(f)!r}, expected {r.get(f) or None!r}")
        errors = {x.code for x in res.issues if x.severity == Severity.ERROR}
        explained = set().union(*(FAULTS[f] for f in r["faults"])) if r["faults"] else set()
        for f in r["faults"]:
            fault_seen[f] += 1
            fault_caught[f] += bool(FAULTS[f] & errors)
        for code in errors - explained:
            false_errors[code] += 1
        confusion[(want_decision, res.decision.value)] += 1
        cost += res.usage.cost_usd
        latency += res.usage.latency_ms
        calls += res.usage.llm_calls
        repairs += res.repair_attempts
        per_doc.append({"file": r["file"], "faults": sorted(r["faults"]), "expected": want_decision,
                        "got": res.decision.value, "errors": sorted(errors), "unexplained_errors": sorted(errors - explained),
                        "wrong_fields": wrong})
        print(f"  {i}/{len(rows)} {r['file']}: expected {want_decision}, got {res.decision.value}", flush=True)

    n = len(rows)
    valid = [d for d in per_doc if d["expected"] == "auto_approved"]
    risky = [d for d in per_doc if d["expected"] != "auto_approved"]
    return {
        "documents": n, "valid": len(valid), "with_faults": len(risky), "crashed": crashed,
        "field_accuracy": {f: round(h[0] / h[1], 3) for f, h in hits.items()},
        "field_accuracy_overall": round(sum(h[0] for h in hits.values()) / max(1, sum(h[1] for h in hits.values())), 3),
        "decision_accuracy": round(sum(d["expected"] == d["got"] for d in per_doc) / n, 3),
        # The two errors that matter most, kept separate:
        "false_approvals": [d["file"] for d in risky if d["got"] == "auto_approved"],
        "unnecessary_reviews": [d["file"] for d in valid if d["got"] != "auto_approved"],
        "straight_through_on_valid": round(sum(d["got"] == "auto_approved" for d in valid) / len(valid), 3) if valid else None,
        "fault_recall": {f: f"{fault_caught[f]}/{fault_seen[f]}" for f in sorted(fault_seen)},
        "errors_not_explained_by_labels": dict(false_errors.most_common()),
        "confusion": {f"{a} -> {b}": c for (a, b), c in sorted(confusion.items())},
        "avg_latency_s": round(latency / n / 1000, 1), "llm_calls": calls, "repair_attempts": repairs,
        "avg_api_cost_usd": round(cost / n, 6),
        "documents_detail": per_doc,
    }


def to_markdown(r: dict, meta: dict) -> str:
    fa = r["false_approvals"]
    out = [f"# Independent evaluation: {meta['set']}", "",
           f"- Status: **{meta['status']}**",
           f"- Engine: `{meta['engine']}` · DocFlow code `{meta['code']}` · run {meta['at']}",
           f"- {r['documents']} documents: {r['valid']} valid, {r['with_faults']} with deliberate faults, {r['crashed']} crashed", "",
           "| Metric | Value |", "|---|---|",
           f"| **False approvals** (faulty invoice auto-approved) | **{len(fa)}** {'(' + ', '.join(fa) + ')' if fa else ''} |",
           f"| **Unnecessary reviews** (valid invoice not auto-approved) | **{len(r['unnecessary_reviews'])} of {r['valid']}** |",
           f"| Straight-through rate on valid invoices | {r['straight_through_on_valid']} |",
           f"| Decision accuracy | {r['decision_accuracy']} |",
           f"| Header-field accuracy | {r['field_accuracy_overall']} |",
           f"| Avg time per document | {r['avg_latency_s']} s |",
           f"| LLM calls / repair attempts | {r['llm_calls']} / {r['repair_attempts']} |",
           f"| Avg API cost (excludes local compute) | ${r['avg_api_cost_usd']} |", "",
           "## Field accuracy", "", "| Field | Accuracy |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in r["field_accuracy"].items()]
    out += ["", "## Fault detection (caught / present)", "", "| Fault | Recall |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in r["fault_recall"].items()]
    out += ["", "## Errors raised that the labels do not explain", ""]
    out += [f"- `{k}`: {v}" for k, v in r["errors_not_explained_by_labels"].items()] or ["- none"]
    out += ["", "## Decisions (expected -> actual)", ""] + [f"- {k}: {v}" for k, v in r["confusion"].items()]
    out += ["", "## Documents that did not match", ""]
    for d in r["documents_detail"]:
        if d["expected"] != d["got"] or d.get("wrong_fields") or d.get("unexplained_errors"):
            out.append(f"- **{d['file']}** expected {d['expected']}, got {d['got']}; errors {d.get('errors')}; "
                       + "; ".join(d.get("wrong_fields", [])) + (f" {d['error']}" if d.get("error") else ""))
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--extractor", choices=["rules", "llm"], default="llm")
    ap.add_argument("--today", default=None, help="date the set treats as today, YYYY-MM-DD (default: real today)")
    ap.add_argument("--allow-changed", action="store_true")
    a = ap.parse_args()
    rows = load(a.folder)
    frozen = check_frozen(a.folder, rows, a.allow_changed)
    cfg = resolve_provider() if a.extractor == "llm" else None
    if a.extractor == "llm" and cfg is None:
        raise SystemExit("No LLM configured: set DOCFLOW_PROVIDER / DOCFLOW_MODEL (or an API key) first.")
    today = date.fromisoformat(a.today) if a.today else date.today()
    res = run(a.folder, a.extractor, today)
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta = {"set": a.folder.name, "status": frozen["status"], "code": frozen["code"], "at": at,
            "engine": f"llm:{cfg.provider}:{cfg.model}" if cfg else "rules"}
    frozen["log"]["runs"].append({"at": at, "code": frozen["code"], "engine": meta["engine"],
                                  "false_approvals": len(res["false_approvals"]),
                                  "unnecessary_reviews": len(res["unnecessary_reviews"])})
    frozen["path"].write_text(json.dumps(frozen["log"], indent=2))
    out = a.folder / "results"
    out.mkdir(exist_ok=True)
    stem = f"{meta['engine'].replace(':', '_')}_{at[:19].replace(':', '')}"
    (out / f"{stem}.json").write_text(json.dumps({**meta, **res}, indent=2, default=str))
    (out / f"{stem}.md").write_text(to_markdown(res, meta))
    print(to_markdown(res, meta))
    print(f"Saved to {out / stem}.md")


if __name__ == "__main__":
    main()
