# Train-split experiment: image only vs image + OCR text

Stopped after 23 of 50 receipts to move on to fine-tuning. Both modes on the same 23 training receipts:

| Field | Image only | Image + OCR text |
|---|---|---|
| company | 0.913 | 0.783 |
| date | 0.87 | 0.913 |
| address | 0.783 | 0.826 |
| total | 0.87 | 0.87 |
| **mean** | **0.859** | **0.848** |
| seconds per receipt (RTX 2050) | 34.3 | 72.0 |

On the same receipts the two are nearly tied overall. With the OCR text in the prompt, the 3B model more often took a place or cashier name from the text as the company, but read dates and addresses slightly better, and it was twice as slow. 23 receipts is too few to separate them, so this is recorded as inconclusive. Hybrid mode stays available because it lets DocFlow check values against the text, which image-only can't.
