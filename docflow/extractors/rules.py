"""Deterministic regex baseline.

It needs no API key, so the project runs anywhere, and it gives the LLM extractor
an honest baseline to beat in the evaluation. It handles labelled layouts well and
struggles with unusual phrasing, which is exactly where an LLM earns its cost.
"""
from __future__ import annotations

import re
from decimal import Decimal

from ..parsing import detect_currency, parse_date, parse_money
from ..schema import Invoice, LineItem, Usage

SEP = r"\s*[:|#\-]?\s*"
_MONEY_TOKEN = re.compile(r"[-(]?[£€$]?\s?\d[\d,.]*\d\)?(?!\s*%)|[-(]?[£€$]?\s?\d\)?(?!\s*%)")
_DATE = r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)? [A-Za-z]{3,9},? \d{4}|[A-Za-z]{3,9} \d{1,2}, \d{4})"


def _find(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(m.lastindex or 0).strip()
    return None


def _amount_on_line(label: str, text: str, exclude: str | None = None) -> Decimal | None:
    """Last money value on the first line that starts with `label`."""
    for line in text.splitlines():
        s = line.strip()
        if re.match(rf"^\W*(?:{label})\b", s, re.IGNORECASE) and not (exclude and re.match(exclude, s, re.IGNORECASE)):
            tokens = _MONEY_TOKEN.findall(re.sub(rf"^\W*(?:{label})", "", s, flags=re.IGNORECASE))
            for tok in reversed(tokens):
                value = parse_money(tok)
                if value is not None:
                    return value
    return None


def _supplier(text: str) -> str | None:
    labelled = _find([rf"^(?:supplier|from|vendor|seller){SEP}([A-Za-z].+)$"], text)
    if labelled:
        return labelled.strip(" |")
    for line in text.splitlines():
        s = line.strip()
        if s and not re.search(r"invoice|tax|date|bill to|page|customer", s, re.IGNORECASE) and not re.search(r"\d{3,}", s):
            return s
    return None


def _line_items(text: str) -> list[LineItem]:
    items: list[LineItem] = []
    for line in text.splitlines():
        s = line.strip()
        parts = [p.strip() for p in s.split("|")]
        if len(parts) >= 4 and re.search(r"[A-Za-z]", parts[0]) and not re.search(r"^(description|item)$", parts[0], re.IGNORECASE):
            qty, unit, amount = parse_money(parts[1]), parse_money(parts[2]), parse_money(parts[3])
            if qty is not None and unit is not None and amount is not None:
                items.append(LineItem(description=parts[0], quantity=qty, unit_price=unit, amount=amount))
            continue
        m = (re.match(r"^(?P<d>[A-Za-z].*?)\s+(?P<q>\d+(?:\.\d+)?)\s*x\s*(?P<u>\S+(?:\s?[€])?)\s+(?P<a>\S+(?:\s?[€])?)$", s)
             or re.match(r"^-\s*(?P<d>[A-Za-z].*?):\s*(?P<q>\d+(?:\.\d+)?)\s*@\s*(?P<u>.+?)\s*=\s*(?P<a>.+)$", s))
        if m:
            unit, amount = parse_money(m["u"]), parse_money(m["a"])
            if unit is not None and amount is not None:
                items.append(LineItem(description=m["d"], quantity=Decimal(m["q"]), unit_price=unit, amount=amount))
    return items


def extract(text: str) -> tuple[Invoice, Usage]:
    inv = Invoice(
        supplier_name=_supplier(text),
        invoice_number=_find([rf"(?:invoice\s*(?:no\.?|number|#|ref(?:erence)?)|^ref(?:erence)?){SEP}([A-Z0-9][A-Z0-9\-/]+)"], text),
        invoice_date=parse_date(_find([rf"(?:invoice date|date of issue|issued|^date){SEP}{_DATE}"], text)),
        due_date=parse_date(_find([rf"(?:due date|payment due|due by|pay by){SEP}{_DATE}"], text)),
        currency=detect_currency(text),
        subtotal=_amount_on_line(r"sub[\s-]?total|net amount|net total|total net", text),
        vat_rate=parse_money(_find([r"(?:vat|tax)[^\n%]{0,12}?(\d{1,2}(?:\.\d+)?)\s*%"], text)),
        vat_amount=_amount_on_line(r"vat|tax", text, exclude=r"^\W*tax invoice"),
        total=_amount_on_line(r"total due|amount due|balance due|grand total|total payable|invoice total|amount payable|total", text,
                              exclude=r"^\W*(sub[\s-]?total|total net)"),
        line_items=_line_items(text),
    )
    return inv, Usage(model="rules-baseline")
