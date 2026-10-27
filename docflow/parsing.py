"""Parsers for the number and date formats invoices actually use."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

_CURRENCY_SYMBOLS = {"£": "GBP", "€": "EUR", "$": "USD"}
_CURRENCY_CODES = {"GBP", "EUR", "USD"}

_DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y", "%d %b, %Y", "%d/%m/%y", "%d-%b-%Y", "%d-%B-%Y", "%d-%b-%y", "%b %d %Y",
    "%d-%m-%y", "%d.%m.%y", "%d/%b/%Y", "%d/%b/%y", "%d %b %y", "%Y/%m/%d", "%Y.%m.%d",
    # tried last: US month-first (only matches when day-first is impossible, e.g. 12/28/2017) and compact forms
    "%m/%d/%Y", "%Y%m%d", "%d%m%Y",
]


def parse_money(raw: object) -> Optional[Decimal]:
    """'£1,234.50', '1.234,50 EUR', '(12.00)' -> Decimal. Returns None if unparseable."""
    if raw is None:
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw)).quantize(Decimal("0.01"))
    s = str(raw).strip()
    negative = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s or not re.search(r"\d", s):
        return None
    # European style 1.234,56 -> 1234.56
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+,\d{2}", s) or re.fullmatch(r"-?\d+,\d{2}", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        value = Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -value if negative else value


def parse_date(raw: object) -> Optional[date]:
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", str(raw).strip())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def detect_currency(text: str) -> Optional[str]:
    for code in _CURRENCY_CODES:
        if re.search(rf"\b{code}\b", text):
            return code
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    return None
