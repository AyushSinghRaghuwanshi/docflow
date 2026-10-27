"""Evaluate DocFlow on SROIE, a public benchmark of real scanned receipts.

SROIE (ICDAR 2019, Task 3) has 973 real receipts, each with its image, the OCR text lines and
the correct company, date, address and total. Three ways of reading them are compared:

  rules   the rules extractor on the provided OCR text (no model)
  text    the full DocFlow pipeline on the OCR text (LLM + cross-check + validation)
  vision  the full DocFlow pipeline on the receipt image (vision-language model, no OCR)

Protocol: anything tuned is tuned on the train split; the test split is scored as it comes.
Progress is saved after every receipt, so an interrupted run carries on where it stopped.

Usage:
  python evals/run_sroie.py ..\\sroie\\SROIE2019 --mode text   --n 100
  python evals/run_sroie.py ..\\sroie\\SROIE2019 --mode vision --n 100
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from docflow.extractors import rules  # noqa: E402
from docflow.extractors.llm import resolve_provider  # noqa: E402
from docflow.parsing import parse_date  # noqa: E402
from docflow.pipeline import process  # noqa: E402

FIELDS = ["company", "date", "address", "total"]
SAMPLE_SEED = 2019


def load(split_dir: Path) -> list[dict]:
    """One record per receipt: id, OCR text (lines in reading order), image path and labels."""
    docs = []
    for ent in sorted((split_dir / "entities").glob("*.txt")):
        try:
            labels = json.loads(ent.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        lines = []
        box = split_dir / "box" / ent.name
        for raw in box.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = raw.split(",", 8)  # 8 coordinates, then the text (which may itself contain commas)
            if len(parts) == 9 and parts[8].strip():
                lines.append(parts[8].strip())
        image = next((p for p in (split_dir / "img").glob(ent.stem + ".*")), None)
        docs.append({"id": ent.stem, "text": "\n".join(lines), "image": image,
                     "labels": {k: str(labels.get(k, "")).strip() for k in FIELDS}})
    return docs


def sample(docs: list[dict], n: int | None) -> list[dict]:
    """A fixed, seeded sample, so every mode and every run scores the same receipts."""
    if not n or n >= len(docs):
        return docs
    return sorted(random.Random(SAMPLE_SEED).sample(docs, n), key=lambda d: d["id"])


# --- comparison --------------------------------------------------------------------------
def _text_key(s: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _money(s) -> Decimal | None:
    if s in (None, ""):
        return None
    m = re.search(r"-?\d[\d,]*\.?\d*", str(s).replace(" ", ""))
    try:
        return Decimal(m.group(0).replace(",", "")).quantize(Decimal("0.01")) if m else None
    except InvalidOperation:
        return None


def _date(s):
    if not s:
        return None
    s = str(s).strip()
    for cand in [s, *re.findall(r"\d{1,4}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2} ?[A-Za-z]{3,9},? ?\d{2,4}|[A-Za-z]{3,9} ?\d{1,2},? ?\d{4}", s)]:
        d = parse_date(cand)
        if d:
            return d
    return None


def correct(field: str, got, want: str) -> bool | None:
    """Exact match after normalising case, spacing and punctuation (dates and totals by value).
    None when the dataset has no usable answer for this field, so it isn't scored."""
    if not str(want or "").strip() or (field == "date" and _date(want) is None) or (field == "total" and _money(want) is None):
        return None
    if field == "date":
        return _date(want) is not None and _date(got) == _date(want)
    if field == "total":
        return _money(want) is not None and _money(got) == _money(want)
    return bool(_text_key(want)) and _text_key(got) == _text_key(want)


# --- running -----------------------------------------------------------------------------
def predict(doc: dict, mode: str) -> tuple[dict, dict]:
    started = time.perf_counter()
    if mode == "rules":
        inv, _, _ = rules.extract_with_confidence(doc["text"])
        meta = {"decision": None, "llm_calls": 0}
    elif mode == "text":
        res = process(doc["id"] + ".txt", doc["text"].encode(), extractor="llm")
        inv, meta = res.invoice, {"decision": res.decision.value, "llm_calls": res.usage.llm_calls,
                                  "issues": sorted({i.code for i in res.issues if i.severity.value == "error"})}
    else:
        res = process(doc["image"].name, doc["image"].read_bytes(), extractor="llm")
        inv, meta = res.invoice, {"decision": res.decision.value, "llm_calls": res.usage.llm_calls,
                                  "issues": sorted({i.code for i in res.issues if i.severity.value == "error"})}
    got = {"company": inv.supplier_name, "date": inv.invoice_date.isoformat() if inv.invoice_date else None,
           "address": inv.supplier_address, "total": str(inv.total) if inv.total is not None else None}
    meta["seconds"] = round(time.perf_counter() - started, 1)
    return got, meta


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    scored = {f: [r["ok"][f] for r in rows if r["ok"][f] is not None] for f in FIELDS}
    acc = {f: round(sum(v) / len(v), 3) if v else None for f, v in scored.items()}
    return {
        "receipts": n,
        "field_accuracy": acc,
        "mean_field_accuracy": round(sum(v for v in acc.values() if v is not None) / max(1, sum(v is not None for v in acc.values())), 3),
        "all_four_correct": round(sum(all(v is not False for v in r["ok"].values()) for r in rows) / n, 3),
        "unscored_fields": sum(len(rows) - len(v) for v in scored.values()),
        "avg_seconds": round(sum(r["meta"]["seconds"] for r in rows) / n, 1),
        "auto_approved": sum(r["meta"].get("decision") == "auto_approved" for r in rows),
        "auto_approved_with_a_wrong_field": sum(r["meta"].get("decision") == "auto_approved" and False in r["ok"].values()
                                                for r in rows),
    }


def to_markdown(s: dict, meta: dict, rows: list[dict]) -> str:
    out = [f"# SROIE evaluation: `{meta['mode']}` on the {meta['split']} split", "",
           f"- Engine: `{meta['engine']}` · {s['receipts']} receipts (seeded sample) · run {meta['at']}",
           *(["- **Receipts that crashed in the first run were re-run after a fix; all other results are unchanged.**"]
             if meta.get("retried_errors") else []),
           "- Correct = exact match after normalising case, spacing and punctuation; dates and totals compared by value.", "",
           "| Field | Accuracy |", "|---|---|"]
    out += [f"| {f} | {v} |" for f, v in s["field_accuracy"].items()]
    out += [f"| **mean of the four** | **{s['mean_field_accuracy']}** |", f"| all four correct on a receipt | {s['all_four_correct']} |",
            "", f"- Average time per receipt: {s['avg_seconds']} s"]
    if meta["mode"] != "rules":
        out += [f"- Auto-approved by DocFlow: {s['auto_approved']} of {s['receipts']}; of those, "
                f"**{s['auto_approved_with_a_wrong_field']} had at least one wrong field**"]
    out += ["", "## Wrong fields (first 40)", ""]
    shown = 0
    for r in rows:
        for f in FIELDS:
            if r["ok"][f] is False and shown < 40:
                out.append(f"- {r['id']} {f}: got {r['got'][f]!r}, expected {r['want'][f]!r}")
                shown += 1
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", type=Path, help="the SROIE2019 folder (contains train/ and test/)")
    ap.add_argument("--mode", choices=["rules", "text", "vision"], required=True)
    ap.add_argument("--split", choices=["train", "test"], default="test")
    ap.add_argument("--n", type=int, default=100, help="receipts to score (seeded sample; 0 = all)")
    ap.add_argument("--retry-errors", action="store_true",
                    help="re-run only the receipts that crashed in an earlier run (written to a separate *_errors_retried report)")
    a = ap.parse_args()

    docs = sample(load(a.root / a.split), a.n)
    cfg = resolve_provider() if a.mode != "rules" else None
    if a.mode != "rules" and cfg is None:
        raise SystemExit("No model configured: set DOCFLOW_PROVIDER and DOCFLOW_MODEL first.")
    engine = f"llm:{cfg.provider}:{cfg.model}" if cfg else "rules"
    out = ROOT / "evals" / "results" / "sroie"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{a.split}_{a.mode}_{engine.replace(':', '_').replace('/', '_')}_n{len(docs)}"
    progress = out / f"{stem}.progress.jsonl"
    if a.retry_errors:
        # Keep every receipt that ran, drop the ones that crashed, and score those again in a new report;
        # the original report is left exactly as it was.
        earlier = out / f"{stem}.json"
        if not earlier.exists():
            raise SystemExit(f"No earlier run to retry: {earlier}")
        stem += "_errors_retried"
        progress = out / f"{stem}.progress.jsonl"
        if not progress.exists():
            kept = [r for r in json.loads(earlier.read_text(encoding="utf-8"))["rows"] if "error" not in r["meta"]]
            progress.write_text("".join(json.dumps(r) + "\n" for r in kept), encoding="utf-8")
    done = {}
    if progress.exists():
        for line in progress.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["id"]] = r
        print(f"Resuming: {len(done)} of {len(docs)} already scored.", flush=True)

    rows = []
    with open(progress, "a", encoding="utf-8") as fh:
        for i, doc in enumerate(docs, 1):
            if doc["id"] in done:
                rows.append(done[doc["id"]])
                continue
            try:
                got, meta = predict(doc, a.mode)
            except Exception as e:  # noqa: BLE001 - a failed receipt is scored as all wrong, not skipped
                got, meta = {f: None for f in FIELDS}, {"error": str(e)[:200], "seconds": 0.0}
            ok = {f: correct(f, got[f], doc["labels"][f]) for f in FIELDS}
            row = {"id": doc["id"], "got": got, "want": doc["labels"], "ok": ok, "meta": meta}
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            rows.append(row)
            print(f"  {i}/{len(docs)} {doc['id']}: {sum(v is True for v in ok.values())}/4 fields right ({meta['seconds']} s)", flush=True)

    s = summarise(rows)
    meta = {"mode": a.mode, "split": a.split, "engine": engine, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "retried_errors": a.retry_errors}
    (out / f"{stem}.json").write_text(json.dumps({**meta, **s, "rows": rows}, indent=2, default=str), encoding="utf-8")
    (out / f"{stem}.md").write_text(to_markdown(s, meta, rows), encoding="utf-8")
    print(to_markdown(s, meta, rows))
    print(f"Saved to {out / stem}.md")


if __name__ == "__main__":
    main()
