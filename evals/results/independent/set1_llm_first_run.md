# Independent evaluation: independent_set_1

- Status: **held-out (first contact with this code)**
- Engine: `llm:ollama:qwen2.5:3b` · DocFlow code `9d36dbc341e44a34` · run 2026-10-26T01:46:20+00:00
- 40 documents: 20 valid, 20 with deliberate faults, 0 crashed

| Metric | Value |
|---|---|
| **False approvals** (faulty invoice auto-approved) | **6** (invoice_002.pdf, invoice_006.pdf, invoice_011.pdf, invoice_018.pdf, invoice_030.pdf, invoice_034.pdf) |
| **Unnecessary reviews** (valid invoice not auto-approved) | **0 of 20** |
| Straight-through rate on valid invoices | 1.0 |
| Decision accuracy | 0.825 |
| Header-field accuracy | 0.944 |
| Avg time per document | 40.0 s |
| LLM calls / repair attempts | 49 / 9 |
| Avg API cost (excludes local compute) | $0.0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| supplier_name | 0.625 |
| invoice_number | 0.95 |
| invoice_date | 1.0 |
| due_date | 1.0 |
| currency | 1.0 |
| subtotal | 1.0 |
| vat_amount | 1.0 |
| total | 0.975 |

## Fault detection (caught / present)

| Fault | Recall |
|---|---|
| due_before_issue | 3/3 |
| duplicate_reformatted | 1/2 |
| line_items_mismatch | 4/4 |
| missing_required_field | 0/1 |
| prompt_injection | 1/2 |
| total_mismatch | 4/5 |
| vat_mismatch | 0/3 |

## Errors raised that the labels do not explain

- `UNGROUNDED_FIELD`: 4
- `POSSIBLE_DUPLICATE`: 1

## Decisions (expected -> actual)

- auto_approved -> auto_approved: 20
- needs_review -> auto_approved: 6
- needs_review -> needs_review: 12
- rejected -> needs_review: 1
- rejected -> rejected: 1

## Documents that did not match

- **invoice_002.pdf** expected needs_review, got auto_approved; errors []; total: got '687.25', expected '698.25'
- **invoice_004.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'Consulting Studio', expected 'Mosswhistle Consulting Studio'
- **invoice_006.pdf** expected needs_review, got auto_approved; errors []; supplier_name: got 'SERVICES', expected 'Silverhusk Workshop Supplies'
- **invoice_008.pdf** expected needs_review, got needs_review; errors ['TOTAL_MISMATCH']; supplier_name: got 'BILLING Pineharbor Supply Collective', expected 'Pineharbor Supply Collective'
- **invoice_011.pdf** expected needs_review, got auto_approved; errors []; invoice_number: got 'PO-19913', expected None
- **invoice_012.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'STATEMENT / INVOICE Kestrelwick Research Services', expected 'Kestrelwick Research Services'
- **invoice_014.pdf** expected needs_review, got needs_review; errors ['PROMPT_INJECTION']; supplier_name: got 'Services', expected 'Pebbleford Industrial Services Ltd'
- **invoice_016.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'BILLING Northstarling Lighting Partners', expected 'Northstarling Lighting Partners'
- **invoice_017.pdf** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH', 'UNGROUNDED_FIELD']; 
- **invoice_018.pdf** expected needs_review, got auto_approved; errors []; 
- **invoice_020.pdf** expected needs_review, got needs_review; errors ['DUE_BEFORE_ISSUE']; supplier_name: got 'Design Studio', expected 'Willowquay Design Studio'
- **invoice_022.pdf** expected needs_review, got needs_review; errors ['TOTAL_MISMATCH']; supplier_name: got 'SERVICES', expected 'Copperreed Print Workshop'
- **invoice_023.pdf** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH', 'UNGROUNDED_FIELD']; 
- **invoice_024.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'BILLING Rainburrow Consulting Studio', expected 'Rainburrow Consulting Studio'
- **invoice_028.pdf** expected needs_review, got needs_review; errors ['DUE_BEFORE_ISSUE']; supplier_name: got 'Supply Collective', expected 'Cricketmere Supply Collective'
- **invoice_030.pdf** expected needs_review, got auto_approved; errors []; supplier_name: got 'SERVICES', expected 'Sageharbour Distribution Ltd'
- **invoice_031.pdf** expected needs_review, got needs_review; errors ['TOTAL_MISMATCH', 'UNGROUNDED_FIELD']; 
- **invoice_032.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'BILLING Parchmentwick Research Services', expected 'Parchmentwick Research Services'
- **invoice_034.pdf** expected needs_review, got auto_approved; errors []; 
- **invoice_035.pdf** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH', 'UNGROUNDED_FIELD']; 
- **invoice_036.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'Lighting Partners', expected 'Duskberry Lighting Partners'
- **invoice_038.pdf** expected rejected, got needs_review; errors ['POSSIBLE_DUPLICATE']; supplier_name: got 'SERVICES', expected 'Foxgrove Analytics Limited'
- **invoice_039.pdf** expected auto_approved, got auto_approved; errors []; invoice_number: got 'PO-22237', expected 'CRE-2604-0739'
- **invoice_040.pdf** expected needs_review, got needs_review; errors ['TOTAL_MISMATCH']; supplier_name: got 'BILLING Paperhaven Design Studio', expected 'Paperhaven Design Studio'
