# SROIE evaluation: `rules` on the test split

- Engine: `rules` · 100 receipts (seeded sample) · run 2026-10-26T21:34:37+00:00
- Correct = exact match after normalising case, spacing and punctuation; dates and totals compared by value.

| Field | Accuracy |
|---|---|
| company | 0.49 |
| date | 0.44 |
| address | 0.0 |
| total | 0.45 |
| **mean of the four** | **0.345** |
| all four correct on a receipt | 0.0 |

- Average time per receipt: 0.0 s

## Wrong fields (first 40)

- X00016469671 company: got 'TAN CHAY YEE', expected 'OJC MARKETING SDN BHD'
- X00016469671 address: got None, expected 'NO 2 & 4, JALAN BAYU 4, BANDAR SERI ALAM, 81750 MASAI, JOHOR'
- X51005288570 company: got 'SECURE PARKING', expected 'SECURE PARKING CORPORATION S/B'
- X51005288570 date: got None, expected '23.03.18'
- X51005288570 address: got None, expected 'RIVERWALK VILLAGE BATU 3, JALAN IPOH 51200 KL.'
- X51005288570 total: got None, expected '1.00'
- X51005361908 company: got 'CASH', expected 'TEO HENG STATIONERY & BOOKS'
- X51005361908 address: got None, expected 'NO. 53, JALAN BESAR, 45600 BATANG BERJUNTAI SELANGOR DARUL EHSAN'
- X51005361908 total: got '48.00', expected '127.20'
- X51005361923 date: got None, expected '02/01/2018'
- X51005361923 address: got None, expected '8 & 10, JALAN IJOK PERMAI 1, PUSAT NIAGA IJOK PERMAI, 48000 IJOK, SELANGOR.'
- X51005361923 total: got '1.00', expected '4.20'
- X51005433548 company: got 'VEGETABLES', expected 'PASAR MINI JIN SENG'
- X51005433548 date: got None, expected '03/03/18'
- X51005433548 address: got None, expected '379, JALAN PERMAS SATU, BANDAR BARU PERMAS JAYA 81750 PLENTONG, JOHOR.'
- X51005433548 total: got None, expected '33.80'
- X51005442334 company: got 'TAMPOI', expected 'UNIHAKKA INTERNATIONAL SDN BHD'
- X51005442334 date: got None, expected '26 MAR 2018'
- X51005442334 address: got None, expected '12, JALAN TAMPOI 7/4,KAWASAN PARINDUSTRIAN TAMPOI,81200 JOHOR BAHRU,JOHOR'
- X51005442334 total: got '100000035.00', expected '$8.20'
- X51005442343 address: got None, expected 'NO 4,JALAN PERJIRANAN 10, TAMAN AIR BIRU, 81700 PASIR GUDANG, JOHOR.'
- X51005442343 total: got '1.00', expected '72.00'
- X51005444041 company: got "BEN'S INDEPENDENT GROCER", expected 'BENS INDEPENDENT GROCER SDN. BHD'
- X51005444041 date: got None, expected '08/03/18'
- X51005444041 address: got None, expected 'LOT 6, JALAN BATAI, PLAZA BATAI, DAMANSARA HEIGHTS 50490, KUALA LUMPUR'
- X51005447842 company: got 'SDN BHD', expected 'PASARAYA BORONG PINTAR SDN BHD'
- X51005447842 date: got None, expected '14/03/2018'
- X51005447842 address: got None, expected 'NO 19-G& 19-1& 19-2 JALAN TASIK UTAMA 4, MEDAN NIAGA TASIK DAMAI'
- X51005447844 company: got 'RESTAURANT JIAWEI', expected 'RESTAURANT JIAWEI JIAWEI HOUSE'
- X51005447844 address: got None, expected '13, JLN TASIK UTAMA 8 MEDAN NIAGA DAMAI SG BESI'
- X51005568887 date: got None, expected '26/04/2017'
- X51005568887 address: got None, expected 'NO 37, JALAN MANIS 7, TAMAN SEGAR, 56100 CHERAS, KUALA LUMPUR.'
- X51005568887 total: got '1.20', expected '7.20'
- X51005568894 company: got 'PROMOTER', expected 'VIVOPAC MARKETING SDN BHD'
- X51005568894 address: got None, expected '14 JALAN MANIS 4 TAMAN SEGAR 56100 KL'
- X51005568894 total: got '44.00', expected '46.65'
- X51005605287 company: got '3RD FLR, AEON TAMAN MALURI SC', expected 'AEON CO. (M) BHD'
- X51005605287 date: got None, expected '14/03/2018'
- X51005605287 address: got None, expected '3RD FLR, AEON TAMAN MALURI SC JLN JEJAKA, TAMAN MALURI CHERAS, 55100 KUALA LUMPUR'
- X51005605332 company: got 'POPULAR BOOK', expected 'POPULAR BOOK CO. (M) SDN BHD'
