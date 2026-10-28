# Fine-tuning analysis (SROIE test set)

## Headline, with and without the 7 receipts that also appear in training

| | Zero-shot, all 347 | Fine-tuned, all 347 | Zero-shot, 340 clean | **Fine-tuned, 340 clean** |
|---|---|---|---|---|
| company | 0.879 | 0.934 | 0.879 | **0.932** |
| date | 0.939 | 0.960 | 0.938 | **0.959** |
| address | 0.674 | 0.798 | 0.674 | **0.797** |
| total | 0.928 | 0.960 | 0.926 | **0.959** |
| mean | 0.855 | 0.913 | 0.854 | **0.912** |
| all_four | 0.556 | 0.703 | 0.553 | **0.700** |

## 95% bootstrap confidence intervals (340 clean receipts, 2,000 resamples)

| | Zero-shot | Fine-tuned |
|---|---|---|
| mean | 0.833–0.874 | 0.897–0.928 |
| all_four | 0.500–0.606 | 0.653–0.750 |
| address | 0.624–0.724 | 0.753–0.841 |

## Receipt by receipt (340 clean): which model got each field right

| Field | Only fine-tuned right | Only zero-shot right | Both right | Both wrong | McNemar p |
|---|---|---|---|---|---|
| company | 20 | 2 | 297 | 21 | 0.00012 |
| date | 8 | 1 | 318 | 13 | 0.039 |
| address | 54 | 12 | 217 | 57 | 1.7e-07 |
| total | 12 | 1 | 314 | 13 | 0.0034 |

## Strict scoring (closer to how papers score SROIE)

Our scorer ignores case and punctuation and compares dates and totals by value. Papers usually require the
exact string. Both strict rules below use all 347 receipts.

| Rule | Zero-shot mean | Fine-tuned mean | Fine-tuned address |
|---|---|---|---|
| exact string (outer spaces trimmed) | 0.760 | **0.864** | 0.669 |
| exact, ignoring case and repeated spaces | 0.786 | **0.865** | 0.669 |

## Remaining address errors after fine-tuning (69 of 340)

- one or two words differ (spelling / OCR-like): 43
- substantially different: 18
- extra text (phone, tax number, company name): 4
- incomplete (a line or part missing): 4

Examples:

- X00016469670: got `NO 2 & 4, JALAN BAYU 4, BANDAR SERI ALAM, 81750 MASAI, JOHOR` | expected `NO 2 & 4, JALAN BAYU 4, BANDAR SERI ALAM, B1750 MASAI, JOHOR`
- X51005230621: got `LOT 13, JALAN IPOH, KG BATU 30, JLU YAM LAMA 44300 BTG KALI, SELANGOR.` | expected `LOT 13, JALAN IPOH, KG BATU 30, ULU YAM LAMA 44300 BTG KALI, SELANGOR.`
- X51005230659: got `NO. 5-7, JALAN MAHAGONI 7/1, SEKSYEN 4, BANDAR UTAMA, 44300 BATANG KALI, SELANGOR.` | expected `NO. 5-7, JALAN MAHAGONI 7/1, SEKYSEN 4, BANDAR UTAMA, 44300 BATANG KALI, SELANGOR.`
- X51005268275: got `NO. 28, JALAN ASTANA 1C, BANDAR BUKIT RAJAH, 41050 KLANG SELANGOR D.E., MALAYSIA` | expected `NO: 28, JALAN ASTANA 1C, BANDAR BUKIT RAJA, 41050 KLANG SELANGOR D.E, MALAYSIA`
- X51005301666: got `NO. 28, JALAN ASTANA 1C, BANDAR BUKIT RAJAH, 41050 KLANG SELANGOR D.E., MALAYSIA` | expected `NO: 28, JALAN ASTANA 1C, BANDAR BUKIT RAJA, 41050 KLANG SELANGOR D.E, MALAYSIA`
- X51005361906: got `NO. 53, JALAN BESAR, 81600 BATANG BERJUNTAI SELANGOR DARUL EHSAN.` | expected `NO. 53, JALAN BESAR, 45600 BATANG BERJUNTAI SELANGOR DARUL EHSAN`
- X51005361908: got `NO. 53, JALAN MESAR, 45000 BATANG BERJIMBAR SELANGOR DARUL EHSAN` | expected `NO. 53, JALAN BESAR, 45600 BATANG BERJUNTAI SELANGOR DARUL EHSAN`
- X51005433548: got `579, JALAN PERMAS SATU, BANDAR BARU PERMAS JAYA 81750 PLENTONG, JOHOR.` | expected `379, JALAN PERMAS SATU, BANDAR BARU PERMAS JAYA 81750 PLENTONG, JOHOR.`

## Other remaining errors (examples)

- **company** (23 wrong): got `ALSERKAM ENTERPRISE`, expected `PETRON BKT LANJAN SB`; got `OLD TOWN WHITE COFFEE OLD TOWN KOPITIAM SDN BHD`, expected `OLD TOWN KOPITAM SND BHD`; got `TEO HENG STATIONERY & BOOKS`, expected `TED HENG STATIONERY & BOOKS`; got `CONTENTO (M)0761170-8J`, expected `CONTENTO`
- **date** (14 wrong): got `03 MAR 18`, expected `03 MAR 19`; got `28 MAR 2018`, expected `26 MAR 2018`; got `28/04/2017`, expected `26/04/2017`; got `10/1/2017`, expected `10/11/2017`
- **total** (14 wrong): got `30.24`, expected `30.25`; got `$8.60`, expected `$6.60`; got `7.65`, expected `7.20`; got `6.04`, expected `6.40`

Replies that couldn't be parsed at all: zero-shot 0, fine-tuned 0.
