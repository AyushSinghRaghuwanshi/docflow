"""The independent-evaluation scorer: policy-derived expectations, separate error types, and freezing."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"
VALID = """Kestrel IT Solutions Ltd
Invoice Number: INV-4001
Invoice Date: 01/09/2026
Due Date: 01/10/2026
Toner cartridge 2 x £50.00 £100.00
Subtotal: £100.00
VAT (20%): £20.00
Total Due: £120.00
"""
CSV = """order,file,faults,supplier_name,invoice_number,invoice_date,due_date,currency,subtotal,vat_amount,total
1,test_invoice_1.pdf,total_mismatch,Lanternmoss Grid Ltd,LMG-260305-017,2026-03-05,2026-04-04,GBP,1175.00,235.00,1400.00
2,test_invoice_2.pdf,line_items_mismatch;due_before_issue,Tesselmoth Print Room,TPR-0326-088,2026-03-05,2026-03-03,EUR,1025.00,0.00,1025.00
3,test_invoice_3.pdf,duplicate_reformatted;prompt_injection,Lanternmoss Grid Ltd,LMG-260305-017,2026-03-05,2026-04-04,USD,1000.00,50.00,1050.00
4,valid.txt,none,Kestrel IT Solutions Ltd,INV-4001,2026-09-01,2026-10-01,GBP,100.00,20.00,120.00
"""


def make_set(tmp_path: Path) -> Path:
    s = tmp_path / "set"
    s.mkdir()
    for i in (1, 2, 3):
        shutil.copy(FIX / f"test_invoice_{i}.pdf", s)
    (s / "valid.txt").write_text(VALID, encoding="utf-8")
    (s / "expected.csv").write_text(CSV, encoding="utf-8")
    return s


def score(folder: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "evals" / "run_independent.py"), str(folder), "--extractor", "rules",
                           "--today", "2026-10-25", *extra], capture_output=True, text=True, cwd=ROOT)


def test_scores_and_freezes(tmp_path):
    s = make_set(tmp_path)
    r = score(s)
    assert r.returncode == 0, r.stderr
    assert "False approvals** (faulty invoice auto-approved) | **0**" in r.stdout
    assert "Unnecessary reviews** (valid invoice not auto-approved) | **0 of 1**" in r.stdout
    assert "held-out" in r.stdout and "| Decision accuracy | 1.0 |" in r.stdout
    assert (s / "docflow_runs.json").exists()

    (s / "valid.txt").write_text(VALID.replace("120.00", "121.00"), encoding="utf-8")  # editing a frozen set
    r = score(s)
    assert r.returncode != 0 and "changed after its first run" in r.stdout + r.stderr
