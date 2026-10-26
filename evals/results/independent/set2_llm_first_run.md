# Independent evaluation: independent_set_2

- Status: **held-out (first contact with this code)**
- Engine: `llm:ollama:qwen2.5:3b` · DocFlow code `95aeaf1123b86487` · run 2026-10-26T18:53:36+00:00
- 40 documents: 20 valid, 20 with deliberate faults, 0 crashed

| Metric | Value |
|---|---|
| **False approvals** (faulty invoice auto-approved) | **3** (inv_10.pdf, inv_14.pdf, inv_34.txt) |
| **Unnecessary reviews** (valid invoice not auto-approved) | **9 of 20** |
| Straight-through rate on valid invoices | 0.55 |
| Decision accuracy | 0.7 |
| Header-field accuracy | 0.938 |
| Avg time per document | 39.0 s |
| LLM calls / repair attempts | 57 / 17 |
| Avg API cost (excludes local compute) | $0.0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| supplier_name | 0.9 |
| invoice_number | 0.975 |
| invoice_date | 0.825 |
| due_date | 0.825 |
| currency | 1.0 |
| subtotal | 1.0 |
| vat_amount | 1.0 |
| total | 0.975 |

## Fault detection (caught / present)

| Fault | Recall |
|---|---|
| due_before_issue | 2/2 |
| duplicate_exact | 1/1 |
| duplicate_reformatted | 2/2 |
| future_date | 1/1 |
| line_items_mismatch | 4/4 |
| missing_required_field | 0/2 |
| prompt_injection | 2/6 |
| same_number_other_supplier | 1/1 |
| total_mismatch | 2/3 |
| vat_mismatch | 2/2 |

## Errors raised that the labels do not explain

- `FIELD_DISAGREEMENT`: 8
- `MISSING_FIELD`: 6

## Decisions (expected -> actual)

- auto_approved -> auto_approved: 11
- auto_approved -> needs_review: 9
- needs_review -> auto_approved: 3
- needs_review -> needs_review: 14
- rejected -> rejected: 3

## Documents that did not match

- **inv_05.pdf** expected auto_approved, got needs_review; errors ['MISSING_FIELD']; invoice_date: got None, expected '2026-08-14'; due_date: got None, expected '2026-09-04'
- **inv_10.pdf** expected needs_review, got auto_approved; errors []; invoice_number: got 'ACCT-71670', expected None
- **inv_11.txt** expected auto_approved, got needs_review; errors ['MISSING_FIELD']; invoice_date: got None, expected '2026-04-12'; due_date: got None, expected '2026-05-27'
- **inv_13.xlsx** expected auto_approved, got needs_review; errors ['FIELD_DISAGREEMENT']; 
- **inv_14.pdf** expected needs_review, got auto_approved; errors []; 
- **inv_15.pdf** expected auto_approved, got needs_review; errors ['FIELD_DISAGREEMENT']; 
- **inv_16.pdf** expected needs_review, got needs_review; errors ['FIELD_DISAGREEMENT', 'LINE_ITEMS_MISMATCH']; 
- **inv_17.pdf** expected auto_approved, got needs_review; errors ['MISSING_FIELD']; invoice_date: got None, expected '2026-08-10'; due_date: got None, expected '2026-08-31'
- **inv_20.pdf** expected needs_review, got needs_review; errors ['FIELD_DISAGREEMENT']; total: got '2197.51', expected '2207.51'
- **inv_23.pdf** expected auto_approved, got needs_review; errors ['MISSING_FIELD']; supplier_name: got 'INVOICE / BILLING RECORD Sundern Quay Studio', expected 'Sundern Quay Studio'; invoice_date: got None, expected '2026-04-17'; due_date: got None, expected '2026-06-01'
- **inv_29.xlsx** expected auto_approved, got needs_review; errors ['FIELD_DISAGREEMENT', 'MISSING_FIELD']; supplier_name: got 'Tansyford Scientific Ltd, address', expected 'Tansyford Scientific Ltd'; invoice_date: got None, expected '2026-08-15'; due_date: got None, expected '2026-09-05'
- **inv_31.pdf** expected auto_approved, got needs_review; errors ['FIELD_DISAGREEMENT']; supplier_name: got 'INVOICE / SUPPLY STATEMENT Hillspire Fixtures Ltd', expected 'Hillspire Fixtures Ltd'
- **inv_32.pdf** expected needs_review, got needs_review; errors ['FIELD_DISAGREEMENT']; 
- **inv_34.txt** expected needs_review, got auto_approved; errors []; invoice_date: got '2026-06-19', expected None; due_date: got None, expected '2026-06-19'
- **inv_35.pdf** expected auto_approved, got needs_review; errors ['MISSING_FIELD']; invoice_date: got None, expected '2026-04-07'; due_date: got None, expected '2026-05-22'
- **inv_36.xlsx** expected rejected, got rejected; errors ['DUPLICATE', 'FIELD_DISAGREEMENT']; supplier_name: got 'Hollowmere Logistics Ltd, 19 Copperwing Crescent, Penwold, ZZ0 7XZ, United Kingdom', expected 'Hollowmere Logistics Ltd'
