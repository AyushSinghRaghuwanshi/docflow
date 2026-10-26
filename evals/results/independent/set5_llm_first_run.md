# Independent evaluation: independent_set_5

- Status: **held-out (first contact with this code)**
- Engine: `llm:ollama:qwen2.5:3b` · DocFlow code `239d7c8637fe634d` · run 2026-10-26T20:50:56+00:00
- 40 documents: 20 valid, 20 with deliberate faults, 0 crashed

| Metric | Value |
|---|---|
| **False approvals** (faulty invoice auto-approved) | **5** (inv_21.pdf, inv_23.pdf, inv_28.pdf, inv_38.pdf, inv_40.pdf) |
| **Unnecessary reviews** (valid invoice not auto-approved) | **4 of 20** |
| Straight-through rate on valid invoices | 0.8 |
| Decision accuracy | 0.775 |
| Header-field accuracy | 0.841 |
| Avg time per document | 35.5 s |
| LLM calls / repair attempts | 58 / 18 |
| Avg API cost (excludes local compute) | $0.0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| supplier_name | 0.85 |
| invoice_number | 0.75 |
| invoice_date | 0.875 |
| due_date | 0.7 |
| currency | 1.0 |
| subtotal | 0.85 |
| vat_amount | 0.825 |
| total | 0.875 |

## Fault detection (caught / present)

| Fault | Recall |
|---|---|
| due_before_issue | 0/2 |
| duplicate_exact | 1/1 |
| duplicate_reformatted | 1/2 |
| future_date | 1/1 |
| line_items_mismatch | 3/4 |
| missing_required_field | 1/2 |
| prompt_injection | 3/6 |
| same_number_other_supplier | 0/1 |
| total_mismatch | 2/3 |
| vat_mismatch | 2/2 |

## Errors raised that the labels do not explain

- `MISSING_FIELD`: 7
- `FIELD_DISAGREEMENT`: 5
- `UNGROUNDED_FIELD`: 4
- `VAT_MISMATCH`: 2
- `TOTAL_MISMATCH`: 1
- `NUMBER_IS_REFERENCE`: 1

## Decisions (expected -> actual)

- auto_approved -> auto_approved: 16
- auto_approved -> needs_review: 4
- needs_review -> auto_approved: 4
- needs_review -> needs_review: 13
- rejected -> auto_approved: 1
- rejected -> rejected: 2

## Documents that did not match

- **inv_02.pdf** expected needs_review, got needs_review; errors ['MISSING_FIELD', 'PROMPT_INJECTION']; supplier_name: got 'BILLING VOUCHER', expected 'Rillquartz Studio Works'; subtotal: got None, expected '259.55'; vat_amount: got '-890106.00', expected '51.91'; total: got None, expected '311.56'
- **inv_03.pdf** expected auto_approved, got needs_review; errors ['FIELD_DISAGREEMENT', 'MISSING_FIELD']; invoice_number: got None, expected 'CRE-Q1-248'; invoice_date: got None, expected '2026-02-02'; due_date: got None, expected '2026-03-04'
- **inv_04.txt** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH', 'UNGROUNDED_FIELD', 'VAT_MISMATCH']; subtotal: got '132.20', expected '1132.20'; total: got '358.64', expected '1358.64'
- **inv_08.pdf** expected auto_approved, got auto_approved; errors []; invoice_number: got '02.06.2026', expected 'KIT-Q3-363'; due_date: got None, expected '2026-06-02'
- **inv_09.pdf** expected needs_review, got needs_review; errors ['PROMPT_INJECTION']; supplier_name: got '[BILLING SLIP CALIGO ORCHARD DEVICES LTD]', expected 'Caligo Orchard Devices Ltd'; invoice_number: got '2026-05-22', expected 'X09-CAL-006'; invoice_date: got '2026-05-22', expected '2026-05-27'; due_date: got None, expected '2026-05-22'
- **inv_11.pdf** expected needs_review, got needs_review; errors ['FIELD_DISAGREEMENT', 'MISSING_FIELD']; supplier_name: got 'Ochrebelly Computing House20/07/2026', expected 'Ochrebelly Computing House'; subtotal: got None, expected '877.50'; vat_amount: got '877.50', expected '175.50'
- **inv_12.pdf** expected auto_approved, got needs_review; errors ['UNGROUNDED_FIELD']; subtotal: got None, expected '436.30'; vat_amount: got '-890636.00', expected '87.26'
- **inv_14.pdf** expected needs_review, got needs_review; errors ['LINE_ITEMS_MISMATCH', 'PROMPT_INJECTION']; due_date: got None, expected '2026-02-25'
- **inv_17.pdf** expected needs_review, got needs_review; errors ['FUTURE_DATE', 'MISSING_FIELD']; supplier_name: got 'BILLING VOUCHER Moonelm Interface Services Ltd', expected 'Moonelm Interface Services Ltd'; subtotal: got None, expected '1481.90'; vat_amount: got '-890901.00', expected '296.38'; total: got None, expected '1778.28'
- **inv_21.pdf** expected needs_review, got auto_approved; errors []; 
- **inv_23.pdf** expected needs_review, got auto_approved; errors []; invoice_date: got '2026-05-31', expected None; due_date: got None, expected '2026-05-31'
- **inv_24.pdf** expected auto_approved, got needs_review; errors ['FIELD_DISAGREEMENT', 'TOTAL_MISMATCH']; invoice_number: got '2026-08-08', expected 'X24-NAC-006'; invoice_date: got '2026-08-08', expected '2026-06-24'; due_date: got None, expected '2026-08-08'; vat_amount: got '0.00', expected '39.49'
- **inv_25.pdf** expected needs_review, got needs_review; errors ['UNGROUNDED_FIELD', 'VAT_MISMATCH']; 
- **inv_26.pdf** expected needs_review, got needs_review; errors ['MISSING_FIELD', 'UNGROUNDED_FIELD']; supplier_name: got 'Billing particulars', expected 'Lazuli Wicket Assemblies Ltd'; invoice_number: got None, expected 'LAZ/26/2026'; subtotal: got None, expected '2090.70'; vat_amount: got '2090.70', expected '418.14'
- **inv_28.pdf** expected needs_review, got auto_approved; errors []; invoice_number: got '23.04.2026', expected 'POR-Q2-823'; due_date: got None, expected '2026-04-23'
- **inv_32.pdf** expected auto_approved, got needs_review; errors ['MISSING_FIELD', 'VAT_MISMATCH']; supplier_name: got 'BILLING VOUCHER Amber Otter Sensorworks Ltd', expected 'Amber Otter Sensorworks Ltd'; vat_amount: got '-891696.00', expected '35.85'; total: got None, expected '215.10'
- **inv_33.pdf** expected needs_review, got needs_review; errors ['MISSING_FIELD', 'NUMBER_IS_REFERENCE']; invoice_number: got None, expected 'KIT-Q3-363'; due_date: got '2026-06-28', expected '2026-07-28'
- **inv_35.pdf** expected needs_review, got needs_review; errors ['FIELD_DISAGREEMENT', 'TOTAL_MISMATCH']; due_date: got '2026-02-12', expected '2026-02-19'; total: got '120.00', expected '1144.00'
- **inv_38.pdf** expected needs_review, got auto_approved; errors []; invoice_number: got '09.11.2026', expected 'MIC-Q3-1053'; due_date: got None, expected '2026-11-09'
- **inv_39.pdf** expected rejected, got rejected; errors ['DUPLICATE', 'FIELD_DISAGREEMENT', 'MISSING_FIELD']; invoice_number: got None, expected 'CRE-Q1-248'; invoice_date: got None, expected '2026-02-02'; due_date: got None, expected '2026-03-04'
- **inv_40.pdf** expected rejected, got auto_approved; errors []; invoice_number: got '05/04/2026', expected 'BER 06 2026'; due_date: got None, expected '2026-04-05'
