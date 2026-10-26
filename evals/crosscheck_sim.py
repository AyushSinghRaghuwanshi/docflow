"""What does the deterministic layer cost when the model is perfect?

Feeds each document's *correct* answer into the pipeline as if the LLM had returned it, then counts
what the cross-check and validation still get wrong: correct values overruled, and valid documents
sent to review because the rules engine disagreed. This isolates the deterministic layer from the
model's own mistakes. It needs no LLM and runs in seconds.

Usage:  python evals/crosscheck_sim.py evals/dataset/holdout
        python evals/crosscheck_sim.py ../independent_set_1
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docflow.extractors import llm  # noqa: E402
from docflow.extractors.llm import ProviderConfig  # noqa: E402
from docflow.pipeline import process  # noqa: E402
from docflow.schema import Severity  # noqa: E402
from docflow.store import Store  # noqa: E402

FIELDS = ["supplier_name", "invoice_number", "invoice_date", "due_date", "currency", "subtotal", "vat_amount", "total"]


def load(folder: Path) -> list[tuple[Path, dict, bool]]:
    """(file, correct invoice, is_valid) in upload order, for either dataset format."""
    if (folder / "expected.csv").exists():
        rows = sorted(csv.DictReader(open(folder / "expected.csv", encoding="utf-8-sig")), key=lambda r: int(r["order"]))
        out = []
        for r in rows:
            inv = {f: (r.get(f) or None) for f in FIELDS}
            out.append((folder / r["file"], inv, r["faults"] in ("", "none")))
        return out
    out = []
    for p in sorted((folder / "labels").glob("*.json")):
        lab = json.loads(p.read_text())
        out.append((folder / "docs" / lab["file"], lab["invoice"], not lab["fault"]))
    return out


def main() -> None:
    folder = Path(sys.argv[1])
    docs = load(folder)
    answer: dict = {}
    llm._call = lambda cfg, messages: (json.dumps(answer), 0, 0)  # the "model" returns the correct answer
    cfg = ProviderConfig(provider="ollama", model="perfect", api_key="")
    store = Store(":memory:")
    overruled, reviews, codes = Counter(), [], Counter()
    for path, truth, valid in docs:
        answer.clear()
        answer.update({**truth, "line_items": truth.get("line_items", [])})
        res = process(path.name, path.read_bytes(), extractor="llm", provider=cfg, find_duplicate=store.find_duplicate,
                      today=date(2026, 10, 25))
        store.add(res)
        got = res.invoice.model_dump(mode="json")
        for f in FIELDS:
            want = truth.get(f)
            if want not in (None, "") and str(got.get(f) or "").lower() != str(want).lower():
                try:
                    if float(got.get(f)) == float(want):
                        continue
                except (TypeError, ValueError):
                    pass
                overruled[f] += 1
        errs = [i for i in res.issues if i.severity == Severity.ERROR]
        if valid and errs:
            reviews.append((path.name, [f"{i.code}:{i.field}" for i in errs]))
        for i in res.issues:
            if i.code in ("FIELD_DISAGREEMENT", "UNGROUNDED_FIELD", "NUMBER_IS_REFERENCE"):
                codes[f"{i.code}:{i.field}:{i.severity.value}"] += 1
    valid_n = sum(v for *_, v in docs)
    print(f"{folder}: {len(docs)} documents, {valid_n} valid")
    print(f"  correct values overruled by the cross-check: {dict(overruled) or 'none'}")
    print(f"  valid documents sent to review with a perfect model: {len(reviews)} of {valid_n}")
    for name, e in reviews[:12]:
        print(f"    {name}: {e}")
    print(f"  cross-check findings: {dict(codes) or 'none'}")


if __name__ == "__main__":
    main()
