"""Analyse the Colab fine-tuning run (evals/results/sroie_finetune/*.jsonl).

Reports the result with and without the 7 test receipts whose image also appears in the training set,
95% bootstrap confidence intervals, a receipt-by-receipt comparison of the two models (with McNemar's
exact test), and a breakdown of the remaining errors.

Usage:  python evals/analyse_finetune.py
"""
from __future__ import annotations

import json
import random
import re
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent / "results" / "sroie_finetune"
FIELDS = ["company", "date", "address", "total"]
# Test receipts whose image is byte-identical to a training receipt (found by SHA-256 of the image files).
OVERLAP = {"X51006328937", "X51006328967", "X51006329388", "X51006401853", "X51009008095", "X51009453729", "X51009568881"}


def rows(name: str) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, (HERE / f"{name}.jsonl").read_text(encoding="utf-8").splitlines())}


def metrics(rs: list[dict]) -> dict:
    out = {}
    for f in FIELDS:
        v = [r["ok"][f] for r in rs if r["ok"][f] is not None]
        out[f] = sum(v) / len(v)
    out["mean"] = sum(out[f] for f in FIELDS) / 4
    out["all_four"] = sum(all(v is not False for v in r["ok"].values()) for r in rs) / len(rs)
    return out


def bootstrap(rs: list[dict], key: str, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    rnd = random.Random(seed)
    vals = sorted(metrics([rs[rnd.randrange(len(rs))] for _ in rs])[key] for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value for b wins vs c losses."""
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def address_error(got: str | None, want: str) -> str:
    g = re.sub(r"[^A-Z0-9 ]", " ", (got or "").upper()).split()
    w = re.sub(r"[^A-Z0-9 ]", " ", want.upper()).split()
    if not got:
        return "missing"
    if set(w) < set(g):
        return "extra text (phone, tax number, company name)"
    if set(g) < set(w):
        return "incomplete (a line or part missing)"
    diff = len(set(g) ^ set(w))
    return "one or two words differ (spelling / OCR-like)" if diff <= 3 else "substantially different"


def main() -> None:
    zs, ft = rows("test_zero_shot"), rows("test_fine_tuned")
    ids = sorted(zs)
    assert ids == sorted(ft) and len(ids) == 347
    clean = [i for i in ids if i not in OVERLAP]
    out = ["# Fine-tuning analysis (SROIE test set)", ""]

    out += ["## Headline, with and without the 7 receipts that also appear in training", "",
            "| | Zero-shot, all 347 | Fine-tuned, all 347 | Zero-shot, 340 clean | **Fine-tuned, 340 clean** |",
            "|---|---|---|---|---|"]
    M = {k: metrics([d[i] for i in s]) for k, d, s in
         [("za", zs, ids), ("fa", ft, ids), ("zc", zs, clean), ("fc", ft, clean)]}
    for key in FIELDS + ["mean", "all_four"]:
        out.append(f"| {key} | {M['za'][key]:.3f} | {M['fa'][key]:.3f} | {M['zc'][key]:.3f} | **{M['fc'][key]:.3f}** |")

    out += ["", "## 95% bootstrap confidence intervals (340 clean receipts, 2,000 resamples)", "",
            "| | Zero-shot | Fine-tuned |", "|---|---|---|"]
    for key in ["mean", "all_four", "address"]:
        a, b = bootstrap([zs[i] for i in clean], key), bootstrap([ft[i] for i in clean], key)
        out.append(f"| {key} | {a[0]:.3f}–{a[1]:.3f} | {b[0]:.3f}–{b[1]:.3f} |")

    out += ["", "## Receipt by receipt (340 clean): which model got each field right", "",
            "| Field | Only fine-tuned right | Only zero-shot right | Both right | Both wrong | McNemar p |",
            "|---|---|---|---|---|---|"]
    for f in FIELDS:
        pairs = [(zs[i]["ok"][f], ft[i]["ok"][f]) for i in clean if zs[i]["ok"][f] is not None]
        win = sum(not a and b for a, b in pairs)
        loss = sum(a and not b for a, b in pairs)
        both = sum(a and b for a, b in pairs)
        none = sum(not a and not b for a, b in pairs)
        out.append(f"| {f} | {win} | {loss} | {both} | {none} | {mcnemar(win, loss):.2g} |")

    out += ["", "## Strict scoring (closer to how papers score SROIE)", "",
            "Our scorer ignores case and punctuation and compares dates and totals by value. Papers usually require the",
            "exact string. Both strict rules below use all 347 receipts.", "",
            "| Rule | Zero-shot mean | Fine-tuned mean | Fine-tuned address |", "|---|---|---|---|"]
    strict = {"exact string (outer spaces trimmed)": lambda g, w: (g or "").strip() == w.strip(),
              "exact, ignoring case and repeated spaces": lambda g, w: " ".join((g or "").split()).upper() == " ".join(w.split()).upper()}
    for label, fn in strict.items():
        def score(d, fields=FIELDS, fn=fn):
            accs = []
            for f in fields:
                v = [fn(d[i]["got"][f], d[i]["want"][f]) for i in ids if d[i]["ok"][f] is not None]
                accs.append(sum(v) / len(v))
            return sum(accs) / len(accs)
        out.append(f"| {label} | {score(zs):.3f} | **{score(ft):.3f}** | {score(ft, ['address']):.3f} |")

    errs = [(i, ft[i]) for i in clean if ft[i]["ok"]["address"] is False]
    kinds: dict[str, int] = {}
    for _, r in errs:
        k = address_error(r["got"]["address"], r["want"]["address"])
        kinds[k] = kinds.get(k, 0) + 1
    out += ["", f"## Remaining address errors after fine-tuning ({len(errs)} of {len(clean)})", ""]
    out += [f"- {k}: {v}" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])]
    out += ["", "Examples:", ""]
    for i, r in errs[:8]:
        out.append(f"- {i}: got `{r['got']['address']}` | expected `{r['want']['address']}`")

    other = {f: [(i, ft[i]) for i in clean if ft[i]["ok"][f] is False] for f in ["company", "date", "total"]}
    out += ["", "## Other remaining errors (examples)", ""]
    for f, es in other.items():
        out.append(f"- **{f}** ({len(es)} wrong): " + "; ".join(f"got `{r['got'][f]}`, expected `{r['want'][f]}`" for _, r in es[:4]))
    bad_json = sum(all(v is None for v in r["got"].values()) for r in ft.values())
    out += ["", f"Replies that couldn't be parsed at all: zero-shot {sum(all(v is None for v in r['got'].values()) for r in zs.values())}, "
            f"fine-tuned {bad_json}."]
    report = "\n".join(out) + "\n"
    (HERE / "analysis.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
