"""Writes notebooks/finetune_sroie.ipynb (run: python notebooks/build_finetune_notebook.py).

The notebook is generated from this file so the code in it can be reviewed and linted like the rest
of the repository.
"""
import json
from pathlib import Path

CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("markdown", text.strip()))


def code(text: str) -> None:
    CELLS.append(("code", text.strip()))


md("""
# Fine-tuning Qwen2.5-VL 3B on SROIE receipts

Part of [DocFlow](https://github.com/AyushSinghRaghuwanshi/docflow). This notebook:

1. scores the **base** model (zero-shot) on all **347 SROIE test receipts**,
2. fine-tunes a LoRA adapter on the **626 training receipts**, with settings fixed in advance,
3. scores the **fine-tuned** model once on the same 347 test receipts,
4. saves the reports and the adapter to your Google Drive.

The test receipts are never used for training or for choosing settings. Scoring uses DocFlow's own
scorer (`evals/run_sroie.py`), so the numbers match the rest of the project.

**Before running:** Runtime → Change runtime type → **T4 GPU**. Then Runtime → **Run all**.
It takes roughly 1.5–2.5 hours. Results are saved to Drive as they go, so if Colab disconnects,
run all again and it continues where it stopped.
""")

code("""
%%capture
# 1. Install (the Colab recipe from Unsloth's own Qwen2.5-VL notebook). %%capture must stay on the first line.
!pip install sentencepiece protobuf "datasets==4.3.0" "huggingface_hub>=0.34.0" hf_transfer
!pip install --no-deps unsloth_zoo bitsandbytes accelerate peft trl triton unsloth
!unsloth install-kernels
!pip install --no-deps --upgrade "torchao>=0.16.0"
!pip install transformers==4.57.6
!pip install --no-deps trl==0.22.2
!pip install kagglehub
""")

code("""
# 2. Check the GPU and connect Google Drive (results and the adapter are kept there)
import torch, os
assert torch.cuda.is_available(), "No GPU: Runtime > Change runtime type > T4 GPU, then run all again."
print("GPU:", torch.cuda.get_device_name(0))
from google.colab import drive
drive.mount("/content/drive")
OUT = "/content/drive/MyDrive/docflow_sroie"
os.makedirs(OUT, exist_ok=True)
print("Saving to", OUT)
""")

code("""
# 3. Get DocFlow (for its scorer) and the SROIE dataset
import glob, subprocess, sys
if not os.path.exists("/content/docflow"):
    subprocess.run(["git", "clone", "-q", "https://github.com/AyushSinghRaghuwanshi/docflow", "/content/docflow"], check=True)
sys.path.insert(0, "/content/docflow"); sys.path.insert(0, "/content/docflow/evals")

def find_sroie():
    hits = glob.glob("/content/drive/MyDrive/**/SROIE2019/test/entities", recursive=True)
    if hits:
        return os.path.dirname(os.path.dirname(hits[0]))
    import kagglehub  # public dataset; if this asks for a login, upload SROIE2019 to your Drive instead
    path = kagglehub.dataset_download("urbikn/sroie-datasetv2")
    return os.path.dirname(os.path.dirname(glob.glob(f"{path}/**/test/entities", recursive=True)[0]))

ROOT = find_sroie()
print("SROIE at", ROOT)
""")

code("""
# 4. Load both splits with DocFlow's loader and check they don't overlap
from pathlib import Path
from run_sroie import load, correct, FIELDS
train, test = load(Path(ROOT) / "train"), load(Path(ROOT) / "test")
print(len(train), "train receipts,", len(test), "test receipts")
assert not {d["id"] for d in train} & {d["id"] for d in test}, "train and test overlap"
import hashlib
h = lambda d: hashlib.sha256(d["image"].read_bytes()).hexdigest()
same_image = {h(d) for d in train} & {h(d) for d in test}
print("identical images in both splits:", len(same_image))
""")

code("""
# 5. Prompt, image size and parsing: fixed before any result is seen, the same for base and fine-tuned
import json, re
from PIL import Image

PROMPT = ("Extract these fields from the receipt and reply with JSON only: "
          '{"company": ..., "date": ..., "address": ..., "total": ...}. '
          "company is the seller's name and address the seller's address, copied exactly as printed; "
          "date is the receipt date as printed; total is the final amount paid.")
MAX_SIDE = 1024

def open_image(path):
    img = Image.open(path).convert("RGB")
    scale = MAX_SIDE / max(img.size)
    return img.resize((round(img.width * scale), round(img.height * scale))) if scale < 1 else img

def parse(reply):
    m = re.search(r"\\{.*\\}", reply, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    return {f: (str(data.get(f)).strip() if data.get(f) not in (None, "") else None) for f in FIELDS}

def target(labels):
    return json.dumps({f: labels[f] for f in FIELDS}, ensure_ascii=False)
""")

code("""
# 6. Load the base model (4-bit, so it fits a free T4)
from unsloth import FastVisionModel, is_bf16_supported
model, tokenizer = FastVisionModel.from_pretrained(
    "unsloth/Qwen2.5-VL-3B-Instruct-bnb-4bit",
    load_in_4bit=True,
    use_gradient_checkpointing="unsloth",
)
""")

code("""
# 7. Scoring loop, saved after every receipt so a disconnect loses nothing
import time
def predict(img_path):
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
    text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    inputs = tokenizer(open_image(img_path), text, add_special_tokens=False, return_tensors="pt").to("cuda")
    out = model.generate(**inputs, max_new_tokens=256, use_cache=True, do_sample=False)
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

def evaluate(name):
    path = f"{OUT}/{name}.jsonl"
    done = {json.loads(l)["id"]: json.loads(l) for l in open(path)} if os.path.exists(path) else {}
    FastVisionModel.for_inference(model)
    with open(path, "a") as fh:
        for i, d in enumerate(test, 1):
            if d["id"] in done:
                continue
            t = time.time()
            try:
                reply = predict(d["image"])
            except Exception as e:  # scored as all wrong, never skipped
                reply = f"ERROR {e}"
            got = parse(reply)
            row = {"id": d["id"], "got": got, "want": d["labels"], "reply": reply[:500],
                   "ok": {f: correct(f, got[f], d["labels"][f]) for f in FIELDS}, "seconds": round(time.time() - t, 1)}
            fh.write(json.dumps(row) + "\\n"); fh.flush()
            done[d["id"]] = row
            if i % 10 == 0:
                print(f"{name}: {i}/{len(test)}", flush=True)
    return [done[d["id"]] for d in test]

def summary(rows):
    acc = {}
    for f in FIELDS:
        v = [r["ok"][f] for r in rows if r["ok"][f] is not None]
        acc[f] = round(sum(v) / len(v), 4)
    # SROIE-style micro precision / recall / F1 over the four entities
    tp = sum(r["ok"][f] is True for r in rows for f in FIELDS)
    predicted = sum(r["got"][f] is not None for r in rows for f in FIELDS if r["ok"][f] is not None)
    truth = sum(r["ok"][f] is not None for r in rows for f in FIELDS)
    p, rc = tp / max(1, predicted), tp / max(1, truth)
    return {"receipts": len(rows), **acc, "mean": round(sum(acc.values()) / 4, 4),
            "all_four": round(sum(all(v is not False for v in r["ok"].values()) for r in rows) / len(rows), 4),
            "precision": round(p, 4), "recall": round(rc, 4), "f1": round(2 * p * rc / max(1e-9, p + rc), 4),
            "sec_per_receipt": round(sum(r["seconds"] for r in rows) / len(rows), 1)}
""")

code("""
# 8. Zero-shot baseline: the base model on all 347 test receipts
base_rows = evaluate("test_zero_shot")
base = summary(base_rows)
print(base)
""")

code("""
# 9. LoRA fine-tuning on the 626 training receipts (settings fixed in advance, no test data involved)
from unsloth.trainer import UnslothVisionDataCollator
from trl import SFTTrainer, SFTConfig

ADAPTER = f"{OUT}/qwen25vl3b_sroie_lora"
if os.path.exists(f"{ADAPTER}/adapter_config.json"):
    print("Adapter already trained; loading it instead of training again.")
    model, tokenizer = FastVisionModel.from_pretrained(ADAPTER, load_in_4bit=True)
else:
    model = FastVisionModel.get_peft_model(
        model, finetune_vision_layers=True, finetune_language_layers=True,
        finetune_attention_modules=True, finetune_mlp_modules=True,
        r=16, lora_alpha=16, lora_dropout=0, bias="none", random_state=3407,
    )
    data = [{"messages": [
        {"role": "user", "content": [{"type": "image", "image": open_image(d["image"])}, {"type": "text", "text": PROMPT}]},
        {"role": "assistant", "content": [{"type": "text", "text": target(d["labels"])}]},
    ]} for d in train]
    FastVisionModel.for_training(model)
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        data_collator=UnslothVisionDataCollator(model, tokenizer),
        train_dataset=data,
        args=SFTConfig(
            per_device_train_batch_size=2, gradient_accumulation_steps=4, num_train_epochs=2,
            warmup_steps=5, learning_rate=2e-4, optim="adamw_8bit", weight_decay=0.001,
            lr_scheduler_type="linear", seed=3407, logging_steps=10, output_dir="outputs", report_to="none",
            fp16=not is_bf16_supported(), bf16=is_bf16_supported(),
            remove_unused_columns=False, dataset_text_field="", dataset_kwargs={"skip_prepare_dataset": True},
            max_length=2048,
        ),
    )
    stats = trainer.train()
    print(f"Trained in {stats.metrics['train_runtime'] / 60:.1f} minutes")
    model.save_pretrained(ADAPTER); tokenizer.save_pretrained(ADAPTER)
""")

code("""
# 10. The fine-tuned model on the same 347 test receipts, once
tuned_rows = evaluate("test_fine_tuned")
tuned = summary(tuned_rows)
print(tuned)
""")

code("""
# 11. Results table, saved to Drive
rows = [("Company", "company"), ("Date", "date"), ("Address", "address"), ("Total", "total"),
        ("**Mean of the four**", "mean"), ("All four right on a receipt", "all_four"),
        ("Precision (SROIE-style, micro)", "precision"), ("Recall", "recall"), ("**F1**", "f1"),
        ("Seconds per receipt (T4)", "sec_per_receipt")]
lines = ["# Qwen2.5-VL 3B on SROIE: zero-shot vs LoRA fine-tuned", "",
         f"All {len(test)} test receipts. Trained on the {len(train)} training receipts only; settings fixed before training.",
         "Correct = exact match after normalising case, spacing and punctuation; dates and totals compared by value.", "",
         "| | Zero-shot | Fine-tuned |", "|---|---|---|"]
lines += [f"| {label} | {base[key]} | {tuned[key]} |" for label, key in rows]
report = "\\n".join(lines) + "\\n"
open(f"{OUT}/sroie_finetune_results.md", "w").write(report)
json.dump({"zero_shot": base, "fine_tuned": tuned}, open(f"{OUT}/sroie_finetune_results.json", "w"), indent=2)
print(report)
print("Saved to Google Drive → docflow_sroie")
""")


def build(path: Path) -> None:
    nb = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
                     "kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "cells": [],
    }
    for kind, src in CELLS:
        cell = {"cell_type": kind, "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update(outputs=[], execution_count=None)
        nb["cells"].append(cell)
    path.write_text(json.dumps(nb, indent=1), encoding="utf-8")


if __name__ == "__main__":
    out = Path(__file__).with_name("finetune_sroie.ipynb")
    build(out)
    print(f"wrote {out} ({len(CELLS)} cells)")
