# SROIE evaluation: `vision` on the test split

- Engine: `llm:ollama:qwen2.5vl:3b` · 100 receipts (seeded sample) · run 2026-10-27T19:25:03+00:00
- **Receipts that crashed in the first run were re-run after a fix; all other results are unchanged.**
- Correct = exact match after normalising case, spacing and punctuation; dates and totals compared by value.

| Field | Accuracy |
|---|---|
| company | 0.86 |
| date | 0.9 |
| address | 0.84 |
| total | 0.89 |
| **mean of the four** | **0.873** |
| all four correct on a receipt | 0.62 |

- Average time per receipt: 130.0 s
- Auto-approved by DocFlow: 0 of 100; of those, **0 had at least one wrong field**

## Wrong fields (first 40)

- X51005288570 date: got None, expected '23.03.18'
- X51005361908 company: got 'TED HENG STATIONERY & BOOKS', expected 'TEO HENG STATIONERY & BOOKS'
- X51005361908 address: got 'NO. 53, JALAN BESAR, 45600 BATANG BERJUNTA SELANGOR DARUL EHSAN', expected 'NO. 53, JALAN BESAR, 45600 BATANG BERJUNTAI SELANGOR DARUL EHSAN'
- X51005361923 total: got '50.20', expected '4.20'
- X51005433548 address: got '379, JALAN PERMAS SATU, BANDAR BARU PERMAS JAVA 81750 PLENTONG, JOHOR.', expected '379, JALAN PERMAS SATU, BANDAR BARU PERMAS JAYA 81750 PLENTONG, JOHOR.'
- X51005442334 address: got '12, Jalan Tampoi 7/4,Kawasan Perindustrian Tampoi,81200 Johor Bahru,Johor', expected '12, JALAN TAMPOI 7/4,KAWASAN PARINDUSTRIAN TAMPOI,81200 JOHOR BAHRU,JOHOR'
- X51005444041 company: got 'Bens Independent Grocer', expected 'BENS INDEPENDENT GROCER SDN. BHD'
- X51005447844 address: got '13, JLN IASIK UTAMA 8 MEDAN NIAGA DAMAI SG BESI 57000 KL', expected '13, JLN TASIK UTAMA 8 MEDAN NIAGA DAMAI SG BESI'
- X51005568887 date: got '2017-04-28', expected '26/04/2017'
- X51005605287 total: got '12.95', expected '12.25'
- X51005705784 company: got 'EDAI BUKU NEW ACHEIVERS', expected 'KEDAI BUKU NEW ACHEIVERS'
- X51005719889 company: got 'HENG KEE DELIGHTS', expected 'HENG KEE DELIGHTS BAK KUT TEH.'
- X51005741929 address: got 'No 13, 15, 17 & 19 Jalan Nova Q U5/0, Seksyen U5, Subang Bestari 40150 Shah Ala Selangor Darul Ehsan', expected 'NO 13, 15, 17 & 19 JALAN NOVA Q U5/Q, SEKSYEN U5, SUBANG BESTARI 40150 SHAH ALA SELANGOR DARUL EHSAN'
- X51005741929 total: got '5.81', expected '5.50'
- X51005745213 address: got 'No.52, Jalan Bulan USJ/8T, Bandar Pinggiran Subang, Sungai Buloh, 40150 Shah Alam, Sel.', expected 'NO.52, JALAN BULAN U5/BT, BANDAR PINGGLRAN SUBANG, SUNGAL BULOH, 40150 SHAH ALAM, SEL.'
- X51005806695 company: got 'Juwita Weddings', expected 'SAYANG YOU STATION SDN BHD'
- X51005806696 total: got '7.65', expected '7.20'
- X51006008092 date: got '2018-03-08', expected '06/03/18'
- X51006328937 company: got 'LIVE9 PHARMACY SDN BHD', expected 'OLIVE9 PHARMACY SDN BHD'
- X51006328937 address: got '69 JALAN NOVA U5/N, BERKSYEN U5 SUBANG BE', expected '69 JALAN NOVA U5/N, SEKSYEN U5 SUBANG BE'
- X51006349083 company: got 'CHÀ FOR TEA', expected 'CHA FOR TEA'
- X51006349083 address: got '1-1, CENTRAL PARK, JALAN PJUS/13, DATARAN SUNWAY, 47810 KUTA DAMANSARA, SELANGOR', expected '1-1, CENTRAL PARK , JALAN PJU5/13, DATARAN SUNWAY, 47810 KOTA DAMANSARA, SELANGOR'
- X51006387660 date: got '2017-02-02', expected '02/04/2017'
- X51006387660 address: got 'LOT F15, GIANT BANDAR PUTERI JALAN PUTERI 1/1, BDR PUTERI 47160 PUCHONG, SELANGOR', expected 'LOT F15, GIANT BANDAR PUTERI JALAN PUTERI 1/1, BDR PUTERI 47100 PUCHONG, SELANGOR'
- X51006389898 company: got 'RESTORAN WAN SHF', expected 'RESTORAN WAN SHE'
- X51006414702 total: got '160.00', expected '157.90'
- X51006438346 date: got None, expected '05/04/18'
- X51006466070 total: got '42.90', expected 'RM42.88'
- X51006554841 company: got 'WISMA YAP TIEH (TAG)', expected 'NSK TRADE CITY-SELAYANG'
- X51006557208 address: got '1 Lot 3, Jalan Pelabur 23/1, 40300 Shah Alam, Selangor.', expected 'LOT 3, JALAN PELABUR 23/1, 40300 SHAH ALAM, SELANGOR.'
- X51006619569 date: got None, expected '01-02-16'
- X51006619569 total: got '27.89', expected 'RM 26.40'
- X51006619700 date: got None, expected '10-01-16'
- X51006619700 total: got '8.56', expected 'RM 8.10'
- X51006619790 total: got '15.50', expected '14.50'
- X51006620175 total: got '28.21', expected 'RM 26.70'
- X51006620437 total: got '15.00', expected '14.20'
- X51006647984 company: got 'Kechara Oasis', expected 'KECHARA VEGETARIAN RESTAURANT S/B'
- X51006647984 address: got '63&67-P1, Block D, The Suite, Jaya One, No.72A, Jalan Universiti, 46200, Petaling Jaya, Selangor.', expected 'NO. 72A, JALAN UNIVERSITI, 46200, PETALING JAYA, SELANGOR.'
- X51006828200 company: got 'YIM Mid Valley', expected 'YHM MID VALLEY'
