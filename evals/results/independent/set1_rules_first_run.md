# Independent evaluation: independent_set_1

- Status: **held-out (first contact with this code)**
- Engine: `rules` · DocFlow code `9d36dbc341e44a34` · run 2026-10-26T01:13:54+00:00
- 40 documents: 20 valid, 20 with deliberate faults, 0 crashed

| Metric | Value |
|---|---|
| **False approvals** (faulty invoice auto-approved) | **6** (invoice_006.pdf, invoice_018.pdf, invoice_028.pdf, invoice_030.pdf, invoice_034.pdf, invoice_035.pdf) |
| **Unnecessary reviews** (valid invoice not auto-approved) | **7 of 20** |
| Straight-through rate on valid invoices | 0.65 |
| Decision accuracy | 0.65 |
| Header-field accuracy | 0.903 |
| Avg time per document | 0.0 s |
| LLM calls / repair attempts | 0 / 0 |
| Avg API cost (excludes local compute) | $0.0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| supplier_name | 0.625 |
| invoice_number | 0.75 |
| invoice_date | 0.875 |
| due_date | 0.975 |
| currency | 1.0 |
| subtotal | 1.0 |
| vat_amount | 1.0 |
| total | 1.0 |

## Fault detection (caught / present)

| Fault | Recall |
|---|---|
| due_before_issue | 1/3 |
| duplicate_reformatted | 1/2 |
| line_items_mismatch | 3/4 |
| missing_required_field | 0/1 |
| prompt_injection | 1/2 |
| total_mismatch | 5/5 |
| vat_mismatch | 0/3 |

## Errors raised that the labels do not explain

- `MISSING_FIELD`: 5
- `LINE_ITEMS_MISMATCH`: 5
- `POSSIBLE_DUPLICATE`: 1

## Decisions (expected -> actual)

- auto_approved -> auto_approved: 13
- auto_approved -> needs_review: 7
- needs_review -> auto_approved: 6
- needs_review -> needs_review: 12
- rejected -> needs_review: 1
- rejected -> rejected: 1

## Documents that did not match

- **invoice_003.pdf** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH']; invoice_number: got 'SAMPLE-000003', expected 'LAR-2604-0703'
- **invoice_004.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'Consulting Studio', expected 'Mosswhistle Consulting Studio'
- **invoice_005.pdf** expected needs_review, got needs_review; errors ['MISSING_FIELD']; invoice_date: got None, expected '2026-06-16'
- **invoice_006.pdf** expected needs_review, got auto_approved; errors []; supplier_name: got 'SERVICES', expected 'Silverhusk Workshop Supplies'
- **invoice_007.pdf** expected auto_approved, got auto_approved; errors []; invoice_number: got 'SAMPLE-000007', expected 'TAT-2608-0707'
- **invoice_008.pdf** expected needs_review, got needs_review; errors ['TOTAL_MISMATCH']; supplier_name: got 'BILLING Pineharbor Supply Collective', expected 'Pineharbor Supply Collective'
- **invoice_011.pdf** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH']; invoice_number: got 'SAMPLE-000011', expected None
- **invoice_012.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'STATEMENT / INVOICE Kestrelwick Research Services', expected 'Kestrelwick Research Services'
- **invoice_013.pdf** expected auto_approved, got needs_review; errors ['MISSING_FIELD']; invoice_date: got None, expected '2026-05-15'
- **invoice_014.pdf** expected needs_review, got needs_review; errors ['PROMPT_INJECTION']; supplier_name: got 'Services', expected 'Pebbleford Industrial Services Ltd'
- **invoice_015.pdf** expected auto_approved, got needs_review; errors ['LINE_ITEMS_MISMATCH']; invoice_number: got 'SAMPLE-000015', expected 'WRE-2607-0715'
- **invoice_016.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'BILLING Northstarling Lighting Partners', expected 'Northstarling Lighting Partners'
- **invoice_018.pdf** expected needs_review, got auto_approved; errors []; 
- **invoice_019.pdf** expected auto_approved, got auto_approved; errors []; invoice_number: got 'SAMPLE-000019', expected 'CLO-2602-0719'
- **invoice_020.pdf** expected needs_review, got needs_review; errors ['DUE_BEFORE_ISSUE']; supplier_name: got 'Design Studio', expected 'Willowquay Design Studio'
- **invoice_021.pdf** expected auto_approved, got needs_review; errors ['MISSING_FIELD']; invoice_date: got None, expected '2026-04-14'
- **invoice_022.pdf** expected needs_review, got needs_review; errors ['TOTAL_MISMATCH']; supplier_name: got 'SERVICES', expected 'Copperreed Print Workshop'
- **invoice_023.pdf** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH']; invoice_number: got 'SAMPLE-000023', expected 'HOL-2606-0723'
- **invoice_024.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'BILLING Rainburrow Consulting Studio', expected 'Rainburrow Consulting Studio'
- **invoice_027.pdf** expected auto_approved, got needs_review; errors ['LINE_ITEMS_MISMATCH']; invoice_number: got 'SAMPLE-000027', expected 'OTT-2601-0727'
- **invoice_028.pdf** expected needs_review, got auto_approved; errors []; supplier_name: got 'Supply Collective', expected 'Cricketmere Supply Collective'; due_date: got '2026-02-10', expected '2026-02-06'
- **invoice_029.pdf** expected auto_approved, got needs_review; errors ['LINE_ITEMS_MISMATCH', 'MISSING_FIELD']; invoice_date: got None, expected '2026-03-13'
- **invoice_030.pdf** expected needs_review, got auto_approved; errors []; supplier_name: got 'SERVICES', expected 'Sageharbour Distribution Ltd'
- **invoice_031.pdf** expected needs_review, got needs_review; errors ['TOTAL_MISMATCH']; invoice_number: got 'SAMPLE-000031', expected 'BIR-2605-0731'
- **invoice_032.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'BILLING Parchmentwick Research Services', expected 'Parchmentwick Research Services'
- **invoice_033.pdf** expected auto_approved, got needs_review; errors ['LINE_ITEMS_MISMATCH']; 
- **invoice_034.pdf** expected needs_review, got auto_approved; errors []; 
- **invoice_035.pdf** expected needs_review, got auto_approved; errors []; invoice_number: got 'SAMPLE-000035', expected 'HED-2609-0735'
- **invoice_036.pdf** expected auto_approved, got auto_approved; errors []; supplier_name: got 'Lighting Partners', expected 'Duskberry Lighting Partners'
- **invoice_037.pdf** expected auto_approved, got needs_review; errors ['MISSING_FIELD']; invoice_date: got None, expected '2026-02-12'
- **invoice_038.pdf** expected rejected, got needs_review; errors ['POSSIBLE_DUPLICATE']; supplier_name: got 'SERVICES', expected 'Foxgrove Analytics Limited'
- **invoice_039.pdf** expected auto_approved, got auto_approved; errors []; invoice_number: got 'SAMPLE-000039', expected 'CRE-2604-0739'
- **invoice_040.pdf** expected needs_review, got needs_review; errors ['TOTAL_MISMATCH']; supplier_name: got 'BILLING Paperhaven Design Studio', expected 'Paperhaven Design Studio'
