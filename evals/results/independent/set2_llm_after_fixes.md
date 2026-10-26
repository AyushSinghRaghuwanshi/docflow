# Independent evaluation: independent_set_2

- Status: **development set (DocFlow or the set changed since the first run; not evidence of generalisation)**
- Engine: `llm:ollama:qwen2.5:3b` · DocFlow code `239d7c8637fe634d` · run 2026-10-26T20:15:34+00:00
- 40 documents: 20 valid, 20 with deliberate faults, 0 crashed

| Metric | Value |
|---|---|
| **False approvals** (faulty invoice auto-approved) | **0**  |
| **Unnecessary reviews** (valid invoice not auto-approved) | **0 of 20** |
| Straight-through rate on valid invoices | 1.0 |
| Decision accuracy | 1.0 |
| Header-field accuracy | 0.994 |
| Avg time per document | 32.5 s |
| LLM calls / repair attempts | 46 / 6 |
| Avg API cost (excludes local compute) | $0.0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| supplier_name | 1.0 |
| invoice_number | 1.0 |
| invoice_date | 0.975 |
| due_date | 1.0 |
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
| missing_required_field | 1/2 |
| prompt_injection | 6/6 |
| same_number_other_supplier | 1/1 |
| total_mismatch | 2/3 |
| vat_mismatch | 2/2 |

## Errors raised that the labels do not explain

- `FIELD_DISAGREEMENT`: 2
- `NUMBER_IS_REFERENCE`: 1
- `LINE_ITEMS_MISMATCH`: 1

## Decisions (expected -> actual)

- auto_approved -> auto_approved: 20
- needs_review -> needs_review: 17
- rejected -> rejected: 3

## Documents that did not match

- **inv_10.pdf** expected needs_review, got needs_review; errors ['MISSING_FIELD', 'NUMBER_IS_REFERENCE']; 
- **inv_20.pdf** expected needs_review, got needs_review; errors ['FIELD_DISAGREEMENT']; total: got '2197.51', expected '2207.51'
- **inv_32.pdf** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH', 'PROMPT_INJECTION']; 
- **inv_34.txt** expected needs_review, got needs_review; errors ['FIELD_DISAGREEMENT']; invoice_date: got '2026-06-19', expected None
