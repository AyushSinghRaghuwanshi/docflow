"""Collect the published evaluation results into evals/results/dashboard.json for the Benchmarks page.

Everything here is read from result files already in the repository; nothing is re-run or adjusted.

Usage:  python evals/build_dashboard_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

from analyse_finetune import FIELDS, OVERLAP, bootstrap, metrics, rows

RESULTS = Path(__file__).resolve().parent / "results"


def _strict(d: dict[str, dict]) -> dict[str, float]:
    out = {}
    for f in FIELDS:
        v = [(r["got"][f] or "").strip() == r["want"][f].strip() for r in d.values() if r["ok"][f] is not None]
        out[f] = round(sum(v) / len(v), 4)
    out["mean"] = round(sum(out.values()) / 4, 4)
    return out


def finetune() -> dict:
    zs, ft = rows("test_zero_shot"), rows("test_fine_tuned")
    clean = [r for i, r in ft.items() if i not in OVERLAP]
    pick = ["company", "date", "address", "total", "mean", "all_four"]
    return {
        "model": "Qwen2.5-VL 3B (4-bit) + LoRA",
        "receipts": len(ft), "train_receipts": 626, "training_minutes": 45.9, "trained_share": 0.0108,
        "hardware": "Google Colab, NVIDIA T4",
        "zero_shot": {k: round(v, 4) for k, v in metrics(list(zs.values())).items() if k in pick},
        "fine_tuned": {k: round(v, 4) for k, v in metrics(list(ft.values())).items() if k in pick},
        "fine_tuned_without_overlap": round(metrics(clean)["mean"], 4),
        "strict": {"zero_shot": _strict(zs), "fine_tuned": _strict(ft)},
        "ci95": {"zero_shot": [round(x, 4) for x in bootstrap([zs[i] for i in zs if i not in OVERLAP], "mean")],
                 "fine_tuned": [round(x, 4) for x in bootstrap(clean, "mean")]},
        "seconds_per_receipt": {"zero_shot": 8.7, "fine_tuned": 13.2},
    }


PUBLISHED = [  # field-level F1 on SROIE, image only (no OCR input); from the STNet paper's comparison table
    {"model": "Donut", "year": 2022, "f1": 0.832},
    {"model": "SeRum", "year": 2023, "f1": 0.858},
    {"model": "OmniParser V2", "year": 2025, "f1": 0.858},
    {"model": "STNet", "year": 2024, "f1": 0.878},
]


def local_zero_shot() -> list[dict]:
    files = [("Rules only", "test_rules_rules_n100.json"),
             ("Qwen2.5 3B on OCR text", "test_text_llm_ollama_qwen2.5_3b_n100.json"),
             ("Qwen2.5-VL 3B on the image", "test_vision_llm_ollama_qwen2.5vl_3b_n100_errors_retried.json")]
    out = []
    for label, name in files:
        j = json.loads((RESULTS / "sroie" / name).read_text(encoding="utf-8"))
        out.append({"label": label, "mean": j["mean_field_accuracy"], "all_four": j["all_four_correct"],
                    "fields": j["field_accuracy"], "seconds": j["avg_seconds"]})
    return out


def independent() -> list[dict]:
    runs = [("Set 1, first run", "set1_llm_first_run.json"), ("Set 2, first run", "set2_llm_first_run.json"),
            ("Set 2, after fixes", "set2_llm_after_fixes.json"), ("Set 5, unseen", "set5_llm_first_run.json")]
    out = []
    for label, name in runs:
        j = json.loads((RESULTS / "independent" / name).read_text(encoding="utf-8"))
        out.append({"label": label, "documents": j["documents"], "decision_accuracy": j["decision_accuracy"],
                    "false_approvals": len(j["false_approvals"]), "unnecessary_reviews": len(j["unnecessary_reviews"]),
                    "faulty": j["with_faults"], "valid": j["valid"]})
    return out


def main() -> None:
    data = {"sroie_finetune": finetune(), "published": PUBLISHED, "sroie_local": local_zero_shot(),
            "independent": independent()}
    out = RESULTS / "dashboard.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
