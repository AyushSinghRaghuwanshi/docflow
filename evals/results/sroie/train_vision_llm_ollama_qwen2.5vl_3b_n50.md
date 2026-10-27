# SROIE evaluation: `vision` on the train split

- Engine: `llm:ollama:qwen2.5vl:3b` · 50 receipts (seeded sample) · run 2026-10-27T20:22:28+00:00
- Correct = exact match after normalising case, spacing and punctuation; dates and totals compared by value.

| Field | Accuracy |
|---|---|
| company | 0.92 |
| date | 0.94 |
| address | 0.86 |
| total | 0.88 |
| **mean of the four** | **0.9** |
| all four correct on a receipt | 0.66 |

- Average time per receipt: 36.0 s
- Auto-approved by DocFlow: 0 of 50; of those, **0 had at least one wrong field**

## Wrong fields (first 40)

- X51005442327 address: got '12, Jalan Tampol 7/4,Kawasan Perindustrian Tampol,81200 Johor Bahru, Johor', expected '12, JALAN TAMPOI 7/4,KAWASAN PARINDUSTRIAN TAMPOI,81200 JOHOR BAHRU,JOHOR'
- X51005719873 company: got 'tealive', expected 'CT281 - TEALIVE SHELL KEPONG OTTOGO ENTERPRISE'
- X51005719873 address: got 'CT281 - Tealive Shell Kepong Otto go Enterprise SHELL STATION PT15944, Mukim Batu, Jln Besar Kepong', expected 'SHELL STATION PT15944, MUKIM BATU, JLN BESAR KEPONG'
- X51005745249 date: got None, expected '27/02/2018'
- X51005745249 total: got '24.00', expected 'RM22.65'
- X51005749895 date: got '2023-03-02', expected '02-03-18'
- X51005749895 address: got 'LOT 1851-A & 1351-B, JALAN KPB 6, KAWASAN PERINDUSTRIAN BALAKONG, 43300 SERI KEMBANGAN, SELANGOR', expected 'LOT 1851-A & 1851-B, JALAN KPB 6, KAWASAN PERINDUSTRIAN BALAKONG, 43300 SERI KEMBANGAN, SELANGOR'
- X51005757353 date: got None, expected '24-03-18'
- X51006335314 address: got 'NO 2, JALAN BULAN 6M U5/BM, SEKSYEN U5, 40150 SHAH ALAM, SELANGOR', expected 'NO 2, JALAN BULAN BM U5/BM, SEKSYEN U5, 40150 SHAH ALAM, SELANGOR'
- X51006349086 company: got 'First City Parking Sdn Bhd', expected 'AMPANG 210 FIRST CITY PARKING SDN BHD'
- X51006387850 address: got '8, JALAN SUBANG JASA 3, 40150 SHAH ALAM, SELANGOR.', expected '9, JALAN SUBANG JASA 3, 40150 SHAH ALAM, SELANGOR.'
- X51006401723 total: got '76.08', expected '72.00'
- X51006414599 total: got '13.00', expected '12.30'
- X51006414675 total: got '22.68', expected '21.60'
- X51006414679 address: got '1241045-D Blk 2, Unit G1 & G2, Bestari Terrace, Lot PTD 182908 & PTD 143216, Jalan Danga, Taman Nusa Bestari, 81300', expected 'BLK 2, UNIT G1 & G2, BESTARI TERRACE, LOT PTD 182908 & PTD 143216, JALAN DANGA, TAMAN NUSA BESTARI, 81300'
- X51006414700 company: got 'AEON CO. (M) BHD', expected 'AEON CO. (M) SDN BHD'
- X51006679216 company: got 'FACE TO FACE NOODLE HOUSE', expected 'FTOF NOODLE HOUSE'
- X51006912960 address: got '1241045-D\nBlk 2, Unit G1 & G2, Bestari Terrace,\nLot PTD 182908 & PTD 143216,\nJalan Danga, Taman Nusa Bestari, 81300', expected 'BLK 2, UNIT G1 & G2, BESTARI TERRACE, LOT PTD 182908 & PTD 143216, JALAN DANGA, TAMAN NUSA BESTARI, 81300'
- X51007135037 total: got '76.08', expected '72.00'
- X51008114260 total: got '24.00', expected '23.60'
