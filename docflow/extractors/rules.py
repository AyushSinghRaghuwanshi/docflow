"""Rules-based extractor: no LLM, no API key.

Finds each field by its label and then looks for the value after the label, in the cell to the
right, or in the cell below (for "label above value" layouts). The LLM path also runs it as a
second, independent reading to check the model against.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Callable, Optional

from ..layout import Cell, Grid
from ..parsing import detect_currency, parse_date, parse_money
from ..schema import Invoice, LineItem, Usage

# Value patterns
NOT_A_RATE = r"(?![\d,.]|\s*(?:%|per\s?cent))"  # "20%" and "20 percent" are rates, not amounts
MONEY_RX = re.compile(rf"(?:[A-Z]{{3}}\s?)?[-(]?[£€$]?\s?\d[\d,.]*\d(?:\s?[£€$])?\)?{NOT_A_RATE}|[£€$]\s?\d{NOT_A_RATE}")
DATE_RX = re.compile(
    r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?[ \-][A-Za-z]{3,9},?[ \-]\d{4}"
    r"|[A-Za-z]{3,9} \d{1,2}(?:st|nd|rd|th)?,? \d{4}"
    r"|\d{4}[/.]\d{2}[/.]\d{2}|\d{1,2}[/\-][A-Za-z]{3}[/\-]\d{2,4}|\d{1,2} [A-Za-z]{3} \d{2}(?!\d)"
)
ID_RX = re.compile(r"\b(?=[A-Z0-9\-/.]*\d)[A-Z0-9][A-Z0-9\-/.]{2,}[A-Z0-9]\b")

# Label vocabularies
INVOICE_NO = [r"invoice\s*(?:no\.?|number|#|id|ref(?:erence)?)", r"bill\s*(?:#|no\.?|number)", r"document\s*(?:no\.?|number|#)",
              r"doc(?:ument)?\s*no\.?", r"inv\s*(?:#|no\.?)", r"(?:our|your|supplier)\s*ref(?:erence)?"]
# A bare "Ref:" is a last resort: on many invoices it is the bank or payment reference instead.
BARE_REF = [r"ref(?:erence)?(?:\s*no\.?)?"]
PAYMENT_LINE = re.compile(r"\b(bank|account|acct|iban|swift|bic|sort\s*code|payment|remittance)\b", re.I)
INVOICE_DATE = [r"invoice\s*date", r"date\s*of\s*issue", r"issue\s*date", r"issued(?:\s*on)?", r"tax\s*point", r"date(?!\s*of\s*supply)"]
DUE_DATE = [r"due\s*date", r"payment\s*due", r"due\s*(?:by|on)?", r"pay(?:able)?\s*by", r"settle(?:ment)?\s*(?:date|by)", r"please\s*settle\s*by"]
TOTAL = [r"grand\s*total(?:\s*\(?inc[^)]*\)?)?", r"total\s*(?:due|payable|to\s*pay)", r"amount\s*(?:due|payable|to\s*pay)",
         r"balance\s*(?:due|to\s*pay)", r"invoice\s*total", r"total\s*(?:\(?inc(?:l|luding)?\.?\s*vat\)?)", r"total(?!\s*(?:excl|ex\b|net))"]
SUBTOTAL = [r"sub[\s-]?total", r"net\s*(?:amount|total|value)", r"total\s*(?:net|excl(?:uding)?\.?\s*vat|ex\.?\s*vat)"]
VAT = [r"(?:uk\s*)?vat(?!\s*(?:id|reg|registration|number|no\b|#))", r"tax(?!\s*(?:invoice|point|breakdown|id|reg))"]
SUPPLIER_LABEL = [r"supplier(?!\s*(?:address|ref|no|number|vat|id|code|account|reg))", r"from", r"vendor", r"seller", r"issued\s*by", r"sold\s*by", r"payee"]
BUYER_LABEL = re.compile(r"^\W*(bill(?:ed)?\s*to|invoice\s*to|sold\s*to|ship\s*to|deliver\s*to|customer(?!\s*account)|client|buyer)\b", re.I)

LABEL_WORDS = re.compile(
    r"^\W*(bill(ed)?\s*to|invoice\s*to|ship\s*to|sold\s*to|customer|client|buyer|supplier|from|vendor|seller|invoice|tax\s*invoice|"
    r"statement|description|payment|summary|date|due|total|subtotal|vat|tax|page|purchase\s*order|account|details|notes|terms)\b\W*$", re.I)
HEADING = re.compile(r"^(=+.*=+|(tax\s*)?invoice\s*\d*|bill|receipt|statement|customer\s*billing\s*document)$", re.I)
ADDRESS = re.compile(r"(^\d+\s+\w)|(\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b)|(\b(street|st|road|rd|lane|avenue|ave|wharf|crescent|gardens|"
                     r"place|square|way|drive|court|united kingdom|uk)\b)|@|www\.|https?://|\+?\d[\d\s]{8,}", re.I)
# Words that make up document titles such as "STATEMENT / INVOICE" or "BILLING DOCUMENT".
TITLE_WORDS = {"invoice", "invoices", "tax", "vat", "statement", "account", "accounts", "services", "billing", "bill", "document",
               "receipt", "sales", "customer", "copy", "original", "of", "and", "for", "pro", "forma", "proforma", "commercial",
               "client", "note", "charges", "service", "goods", "record", "supply", "summary", "advice", "request",
               "payment", "remittance"}
COMPANY_SUFFIX = re.compile(r"\b(ltd|limited|plc|llp|llc|inc|corp|gmbh|sarl|s\.?a\.?|b\.?v\.?|co\.?|company|group|studio|room|"
                            r"services|solutions|consulting|partners|associates|collective|trust)\b\.?$", re.I)


def _label_rx(alts: list[str]) -> re.Pattern:
    return re.compile(rf"(?:^|(?<=[\s|;:,(]))(?P<label>{'|'.join(alts)})(?![A-Za-z])\s*[.:#\-]*\s*(?P<rest>.*)$", re.I)


INCLUSIVE = re.compile(r"(\(|\binc\.?|\bincl\.?|\bincluding|\bexcl\.?|\bexcluding|\bex\.?|\bplus)\s*$", re.I)


def _find(grid: Grid, alts: list[str], value: Callable[[str], Optional[object]], anywhere: bool = True):
    """Try each label (in priority order) and return the first value found next to it."""
    for alt in alts:
        rx = _label_rx([alt])
        for cell in grid.cells():
            m = rx.search(cell.text) if anywhere else rx.match(cell.text)
            if not m or (not anywhere and m.start() > 0):
                continue
            if INCLUSIVE.search(cell.text[: m.start()]) and not INCLUSIVE.search(cell.text[: m.start()]).group(1).lower().startswith("plus"):
                continue  # "Grand total (inc. VAT)" is a total, not a VAT line
            # a label part-way along a cell ("Invoice date Due date") sits in its own column
            anchor = Cell(cell.row, cell.start + m.start("label"), cell.end, cell.text) if m.start("label") else cell
            neighbours = [c.text for c in grid.right_of(cell)[:1]] + [c.text for c in grid.below(anchor, 1)]
            if value is _money:  # a neighbouring cell only counts if it is a bare amount, not another labelled line
                neighbours = [t for t in neighbours if not re.search(r"[a-z]", t)]
            for candidate in [m["rest"], *neighbours]:
                v = value(candidate)
                if v is not None:
                    return v
    return None


def _bare_ref(grid: Grid) -> Optional[str]:
    rx = _label_rx(BARE_REF)
    for cell in grid.cells():
        if PAYMENT_LINE.search(" ".join(c.text for c in grid.rows[cell.row])):
            continue
        m = rx.search(cell.text)
        if m and (v := _ident(m["rest"])):
            return v
    return None


def _money(s: str) -> Optional[Decimal]:
    if re.fullmatch(r"\s*\d+\s*", s):  # a bare whole number in its own cell, e.g. "0" in a spreadsheet
        return parse_money(s)
    for tok in MONEY_RX.findall(s):
        v = parse_money(tok)
        if v is not None:
            return v
    return None


def _date(s: str):
    m = DATE_RX.search(s)
    return parse_date(m.group(0)) if m else None


def _ident(s: str) -> Optional[str]:
    """An invoice identifier at the start of `s`: 'LMG-260305-017', 'SI-20781' or a spaced form like 'LMG 260305 017'."""
    parts: list[str] = []
    for tok in s.strip().split()[:4]:
        tok = tok.strip(".,;:")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-/.]*", tok) or (parts and not re.fullmatch(r"[A-Z0-9\-/.]+", tok)):
            break
        parts.append(tok)
        if not re.fullmatch(r"[A-Z]+", tok) and not re.fullmatch(r"\d+", tok):  # a complete id like 'TPR-0326-088'
            break
    candidate = " ".join(parts)
    return candidate if parts and re.search(r"\d", candidate) and len(candidate) >= 3 else None


def _rate(s: str) -> Optional[Decimal]:
    m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*(?:%|percent)", s, re.I)
    return Decimal(m.group(1)).quantize(Decimal("0.01")) if m else None


# Supplier
def _clean_name(s: str) -> str:
    return tidy_supplier(" ".join(s.replace("—", " ").strip(" -–—:|·•").split()))


def tidy_supplier(name: str) -> str:
    """Drop a document title stuck to the front ("INVOICE / BILLING RECORD Sundern Quay Studio")
    and an address stuck to the end ("Hollowmere Logistics Ltd, 19 Copperwing Crescent")."""
    words = name.split()
    i = 0
    while i < len(words) and (words[i] in {"/", "&", "-", "|"} or (words[i].isupper() and words[i].lower() in TITLE_WORDS)):
        i += 1
    if 0 < i < len(words) and re.match(r"[A-Z][a-z]", words[i]):
        name = " ".join(words[i:])
    head, sep, tail = name.partition(",")
    if sep and head.strip() and (ADDRESS.search(tail) or re.fullmatch(r"\s*address\s*", tail, re.I)):
        name = head.strip()
    return name


def _name_like(s: str) -> bool:
    s = _clean_name(s)
    return (bool(re.search(r"[A-Za-z]{2}", s)) and len(s) <= 80 and not LABEL_WORDS.match(s) and not HEADING.match(s)
            and not ADDRESS.search(s) and not re.search(r"\d{3,}|[:#]", s) and not BUYER_LABEL.match(s))


def _continuation(grid: Grid, header: list[Cell], cell: Cell) -> Optional[Cell]:
    """A name split over lines: the next name-like cell starting in the same column, at most two rows down,
    with nothing else in that column in between; or the next cell on the same row."""
    for c in header:
        if c.row in (cell.row + 1, cell.row + 2) and abs(c.start - cell.start) <= 3:
            between = [x for r in range(cell.row + 1, c.row) for x in grid.rows[r] if abs(x.start - cell.start) <= 3]
            if not between:
                return c
    same_row = [c for c in header if c.row == cell.row and c.start > cell.start]
    return same_row[0] if same_row else None


def _is_title(row: list[Cell]) -> bool:
    words = re.findall(r"[a-z]+", " ".join(c.text for c in row).lower())
    return bool(words) and all(w in TITLE_WORDS for w in words)


def _join_spaced(cells) -> list[Cell]:
    """Join pieces of one name that a wide, letter-spaced header split into cells ("Mosswhistle   Consulting  Studio")."""
    out: list[Cell] = []
    for c in cells:
        prev = out[-1] if out else None
        if prev and prev.row == c.row and c.start - prev.end <= 8:
            out[-1] = Cell(prev.row, prev.start, c.end, f"{prev.text} {c.text}")
        else:
            out.append(c)
    return out


def _supplier(grid: Grid) -> tuple[Optional[str], str]:
    """Return (name, confidence) where confidence is 'high', 'medium' or 'low'."""
    buyer_cells: set[tuple[int, int]] = set()
    for cell in grid.cells():
        if BUYER_LABEL.match(cell.text):
            for c in [*grid.below(cell, 1), *grid.column_block(cell)]:
                if any(_label_rx([alt]).match(c.text) for alt in SUPPLIER_LABEL):
                    break
                buyer_cells.add((c.row, c.start))
            rest = BUYER_LABEL.sub("", cell.text).strip(" :")
            if rest:
                buyer_cells.add((cell.row, cell.start))

    # 1. An explicit supplier label with a company-like value next to or under it.
    for alt in SUPPLIER_LABEL:
        rx = _label_rx([alt])
        for cell in grid.cells():
            m = rx.match(cell.text)
            if not m:
                continue
            for c, text in [(cell, m["rest"]), *[(c, c.text) for c in grid.right_of(cell)[:1]], *[(c, c.text) for c in grid.below(cell, 1)]]:
                if text and _name_like(text) and (c.row, c.start) not in buyer_cells:
                    return _clean_name(text), "high"

    # 2. The document header: name-like lines before the first labelled field, merged when
    #    a name is split across lines ("LANTERNMOSS" / "GRID LTD").
    header: list[Cell] = []
    for row in grid.rows[:12]:
        if any(BUYER_LABEL.match(c.text) for c in row):
            break
        if _is_title(row):
            continue
        header += _join_spaced(c for c in row if _name_like(c.text) and (c.row, c.start) not in buyer_cells)
    best: tuple[Optional[str], str] = (None, "low")
    for cell in header:
        name = _clean_name(cell.text)
        if not COMPANY_SUFFIX.search(name):
            nxt = _continuation(grid, header, cell)
            if nxt and (COMPANY_SUFFIX.search(nxt.text) or (len(name.split()) == 1 and len(nxt.text.split()) <= 3)):
                name = f"{name} {_clean_name(nxt.text)}"
        # One word on its own ("Services") is not enough to be sure it is a company name.
        confidence = "high" if COMPANY_SUFFIX.search(name) and len(name.split()) >= 2 else "medium"
        # Corroborate: the same name appearing again (e.g. "Account: Tesselmoth Print Room") raises confidence
        # and supplies the properly-cased full name.
        for other in grid.cells():
            if other.row != cell.row and name.lower() in other.text.lower() and len(other.text) > len(name) - 1:
                m = re.search(re.escape(name), other.text, re.I)
                if m:
                    name, confidence = other.text[m.start():m.end()], "high"
                    break
        if best[0] is None or (confidence == "high" and best[1] != "high"):
            best = (name, confidence)
        if confidence == "high":
            break
    return best


# Line items
QTY_AT = re.compile(r"^(?P<q>\d+(?:\.\d+)?)\s*(?:copies|units?|items?|hours?|hrs?|pcs|days?|x|×)?\s*(?:@|at|x|×)\s*(?P<u>.+?)(?:\s*each|/unit)?$", re.I)
SUMMARY_LABEL = re.compile(r"^\W*(sub[\s-]?total|total|vat|tax|net|grand|amount|balance)\b", re.I)
ITEMS_HEADER = re.compile(r"\b(description|item|particulars|services|qty|quantity)\b", re.I)


def _is_num(s: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", s.strip()))


def _desc_like(row: list[Cell]) -> bool:
    text = re.sub(r"^\d{1,3}[.)]\s+", "", " ".join(c.text for c in row))  # "01. Workshop tool hire"
    return (bool(re.search(r"[A-Za-z]{3}", text)) and _money(text) is None and not SUMMARY_LABEL.match(text)
            and not ITEMS_HEADER.fullmatch(text) and len(row) == 1)


# A quantity line under its description: "Qty 2 | Price £145.25 | Line amount £290.50", "4 × £310.25 = £1,241.00",
# "4 units x 120,75 € 483,00 €" or "Quantity 3 · Rate £425.50" (amount on the line above).
QTY_LINE = re.compile(
    r"^(?:qty|quantity)?\s*(?P<q>\d+(?:\.\d+)?)\s*(?:units?|pcs|hours?|hrs?|days?|items?|copies)?\s*"
    r"[|·•,]?\s*(?:[x×@]|(?:unit\s*)?(?:price|rate)\b:?)\s*(?P<u>(?:[A-Z]{3}\s?)?-?[£€$]?\s?-?\d[\d.,]*(?:\s?[£€$])?)"
    r"(?:\s*(?:each|/unit))?\s*(?:=|(?:line\s*)?amount:?)?\s*(?P<a>.*)$", re.I)


def _split_amounts(texts: list[str]) -> list[str]:
    """Narrow columns can leave two amounts in one cell ("GBP 110.50  GBP 552.50"); split them."""
    out = []
    for t in texts:
        amounts = [a.strip() for a in MONEY_RX.findall(t)]
        if len(amounts) >= 2 and not DATE_RX.search(t) and not MONEY_RX.sub("", t).strip() \
                and all(re.search(r"[£€$]|[A-Z]{3}|[.,]\d{2}$", a) for a in amounts):
            out += amounts
        else:
            out.append(t)
    return out


def _line_items(grid: Grid) -> list[LineItem]:
    items: list[LineItem] = []
    used: set[int] = set()  # description rows already turned into an item
    rows = grid.rows
    for i, row in enumerate(rows):
        texts = _split_amounts([c.text for c in row])
        joined = " ".join(texts)
        if SUMMARY_LABEL.match(joined):
            continue
        # a) one row with description, qty, unit price, amount in separate cells
        if len(texts) >= 4 and re.search(r"[A-Za-z]{2}", texts[0]) and _is_num(texts[-3]):
            unit, amount = _money(texts[-2]), _money(texts[-1])
            if unit is not None and amount is not None:
                items.append(LineItem(description=texts[0], quantity=Decimal(texts[-3]), unit_price=unit, amount=amount))
                continue
        # b) "desc 3 x £12.00 £36.00" or "- desc: 3 @ £12.00 = £36.00" or "3 × desc (£12.00/unit) £36.00"
        m = (re.match(r"^(?P<d>[A-Za-z].*?)\s+(?P<q>\d+(?:\.\d+)?)\s*x\s*(?P<u>\S+(?:\s?[€])?)\s+(?P<a>\S+(?:\s?[€])?)$", joined)
             or re.match(r"^-\s*(?P<d>[A-Za-z].*?):\s*(?P<q>\d+(?:\.\d+)?)\s*@\s*(?P<u>.+?)\s*=\s*(?P<a>.+)$", joined)
             )
        if m:
            unit, amount = _money(m["u"]), _money(m["a"])
            if unit is not None and amount is not None:
                items.append(LineItem(description=m["d"].strip(), quantity=Decimal(m["q"]), unit_price=unit, amount=amount))
            continue
        # c) qty / unit / amount on a row of their own, description on the row above
        if len(texts) == 3 and _is_num(texts[0]) and i > 0 and _desc_like(rows[i - 1]):
            unit, amount = _money(texts[1]), _money(texts[2])
            if unit is not None and amount is not None:
                items.append(LineItem(description=rows[i - 1][0].text, quantity=Decimal(texts[0]), unit_price=unit, amount=amount))
                continue
        # e) description, then a quantity line (with the amount at its end, or alone on the line between)
        q = QTY_LINE.match(joined)
        if q and i > 0 and _money(q["u"]) is not None:
            amount = _money(q["a"]) if q["a"].strip() else None
            desc_row = i - 1
            if amount is None and i > 1 and len(rows[i - 1]) == 1 and _money(rows[i - 1][0].text) is not None:
                amount, desc_row = _money(rows[i - 1][0].text), i - 2
            if amount is not None and _desc_like(rows[desc_row]) and desc_row not in used:
                items.append(LineItem(description=rows[desc_row][0].text, quantity=Decimal(q["q"]),
                                      unit_price=_money(q["u"]), amount=amount))
                continue
        # d) description, then the amount alone, then "20 copies @ 28,00 € each"
        if len(texts) == 1 and _money(texts[0]) is not None and re.fullmatch(r"[^A-Za-z]*(?:[A-Z]{3})?[^A-Za-z]*", texts[0]) \
                and i > 0 and _desc_like(rows[i - 1]) and i + 1 < len(rows):
            q = QTY_AT.match(" ".join(c.text for c in rows[i + 1]))
            unit = _money(q["u"]) if q else None
            if q and unit is not None:
                items.append(LineItem(description=rows[i - 1][0].text, quantity=Decimal(q["q"]), unit_price=unit, amount=_money(texts[0])))
                used.add(i - 1)
    return items


# Public API
def extract(text: str) -> tuple[Invoice, Usage]:
    inv, usage, _ = extract_with_confidence(text)
    return inv, usage


def extract_with_confidence(text: str) -> tuple[Invoice, Usage, dict[str, str]]:
    grid = Grid(text)
    supplier, supplier_conf = _supplier(grid)
    vat_amount = _find(grid, VAT, _money)
    vat_rate = _find(grid, VAT, _rate)
    inv = Invoice(
        supplier_name=supplier,
        invoice_number=_find(grid, INVOICE_NO, _ident, anywhere=False) or _find(grid, INVOICE_NO, _ident) or _bare_ref(grid),
        # the generic "date" label is only trusted at the start of a cell, or it would match "Due date"
        invoice_date=_find(grid, INVOICE_DATE, _date, anywhere=False) or _find(grid, INVOICE_DATE[:-1], _date),
        due_date=_find(grid, DUE_DATE, _date),
        currency=detect_currency(text),
        subtotal=_find(grid, SUBTOTAL, _money),
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        total=_find(grid, TOTAL, _money, anywhere=False) or _find(grid, TOTAL, _money),
        line_items=_line_items(grid),
    )
    confidence = {"supplier_name": supplier_conf if supplier else "low"}
    return inv, Usage(model="rules-baseline"), confidence
