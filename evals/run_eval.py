"""Score DocFlow extractors against the labelled dataset.

Metrics
- field accuracy: share of the 9 header fields extracted exactly right
- document exact match: every header field right on the same document
- line-item accuracy: same number of items and same amounts
- fault detection recall: faulty documents where the expected error was raised
- false-alarm rate: clean documents wrongly given an error
- decision accuracy: auto-approve / review / reject matched the label
- injection recall: documents with hidden instructions that were caught
- cost and latency per document

Usage:  python evals/run_eval.py --extractor rules
        python evals/run_eval.py --extractor llm      # needs an API key or Ollama
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docflow.pipeline import process  # noqa: E402
from docflow.schema import FIELDS, Severity  # noqa: E402
from docflow.store import Store  # noqa: E402

TODAY = date(2026, 10, 25)
NUMERIC = {"subtotal", "vat_rate", "vat_amount", "total"}


def same(field: str, got, want) -> bool:
    if want is None:
        return got in (None, "")
    if got in (None, ""):
        return False
    if field in NUMERIC:
        return Decimal(str(got)) == Decimal(str(want))
    if field in {"invoice_date", "due_date"}:
        return str(got) == str(want)
    return " ".join(str(got).lower().split()) == " ".join(str(want).lower().split())


def run(extractor: str, dataset: Path) -> dict:
    labels = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((dataset / "labels").glob("*.json"))]
    store = Store(":memory:")
    field_hits: dict[str, int] = defaultdict(int)
    per_layout: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    exact = items_ok = decision_ok = 0
    faults = detected = clean = false_alarm = inj = inj_caught = clean_inj_flag = 0
    cost = latency = 0.0
    failures: list[dict] = []
    errors = processed = 0

    for lab in labels:
        data = (dataset / "docs" / lab["file"]).read_bytes()
        try:
            res = process(lab["file"], data, extractor=extractor, find_duplicate=store.find_duplicate, today=TODAY)
        except Exception as e:  # one bad document should not stop the whole evaluation
            errors += 1
            print(f"  ! {lab['id']}: {type(e).__name__}: {str(e)[:300]}", flush=True)
            if errors == 3 and processed == 0:
                raise SystemExit("Stopping: the first 3 documents all failed. Fix the error above and re-run.") from e
            failures.append({"id": lab["id"], "layout": lab["layout"], "fault": lab["fault"], "error": str(e)[:300]})
            continue
        processed += 1
        print(f"  {processed + errors}/{len(labels)} {lab['id']}: {res.decision.value}", flush=True)
        store.add(res)
        got = res.invoice.model_dump(mode="json")
        want = lab["invoice"]

        hits = {f: same(f, got.get(f), want.get(f)) for f in FIELDS}
        for f, ok in hits.items():
            field_hits[f] += ok
        per_layout[lab["layout"]][0] += sum(hits.values())
        per_layout[lab["layout"]][1] += len(FIELDS)
        exact += all(hits.values())
        items_ok += sorted(Decimal(i["amount"]) for i in got["line_items"]) == sorted(Decimal(i["amount"]) for i in want["line_items"])

        codes = {i.code for i in res.issues if i.severity == Severity.ERROR}
        if lab["fault"]:
            faults += 1
            detected += set(lab["expected_error_codes"]) <= codes
        else:
            clean += 1
            false_alarm += bool(codes)
        if lab["fault"] == "prompt_injection":
            inj += 1
            inj_caught += res.injection_detected
        elif res.injection_detected:
            clean_inj_flag += 1
        decision_ok += res.decision.value == lab["expected_decision"]
        cost += res.usage.cost_usd
        latency += res.usage.latency_ms
        if not all(hits.values()) or res.decision.value != lab["expected_decision"]:
            failures.append({"id": lab["id"], "layout": lab["layout"], "fault": lab["fault"],
                             "wrong_fields": [f for f, ok in hits.items() if not ok],
                             "decision": res.decision.value, "expected": lab["expected_decision"],
                             "errors": sorted(codes)})

    n = len(labels)
    return {
        "extractor": extractor, "documents": n,
        "field_accuracy": round(sum(field_hits.values()) / (n * len(FIELDS)), 3),
        "per_field_accuracy": {f: round(field_hits[f] / n, 3) for f in FIELDS},
        "per_layout_field_accuracy": {k: round(v[0] / v[1], 3) for k, v in sorted(per_layout.items())},
        "document_exact_match": round(exact / n, 3),
        "line_item_accuracy": round(items_ok / n, 3),
        "fault_detection_recall": round(detected / faults, 3) if faults else None,
        "false_alarm_rate": round(false_alarm / clean, 3) if clean else None,
        "decision_accuracy": round(decision_ok / n, 3),
        "injection_recall": round(inj_caught / inj, 3) if inj else None,
        "injection_false_positives": clean_inj_flag,
        "avg_cost_usd": round(cost / n, 6),
        "avg_latency_ms": round(latency / n, 1),
        "processing_errors": errors,
        "failures": failures,
    }


def to_markdown(r: dict) -> str:
    rows = [
        ("Header-field accuracy", r["field_accuracy"]), ("Document exact match", r["document_exact_match"]),
        ("Line-item accuracy", r["line_item_accuracy"]), ("Fault detection recall", r["fault_detection_recall"]),
        ("False-alarm rate (lower is better)", r["false_alarm_rate"]), ("Decision accuracy", r["decision_accuracy"]),
        ("Prompt-injection recall", r["injection_recall"]), ("Injection false positives", r["injection_false_positives"]),
        ("Avg cost per document (USD)", r["avg_cost_usd"]), ("Avg latency per document (ms)", r["avg_latency_ms"]),
    ]
    out = [f"### Extractor: `{r['extractor']}` ({r['documents']} documents)", "", "| Metric | Value |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in rows]
    out += ["", "| Layout | Field accuracy |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in r["per_layout_field_accuracy"].items()]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", choices=["rules", "llm"], default="rules")
    ap.add_argument("--split", choices=["dev", "holdout"], default="dev")
    ap.add_argument("--out", default=str(Path(__file__).parent / "results"))
    args = ap.parse_args()
    res = run(args.extractor, Path(__file__).parent / "dataset" / args.split)
    res["split"] = args.split
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{args.extractor}_{args.split}"
    (out / f"{stem}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    (out / f"{stem}.md").write_text(to_markdown(res), encoding="utf-8")
    print(f"[{args.split}] " + to_markdown(res))


if __name__ == "__main__":
    main()
