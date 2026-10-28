"""Where each extracted value is printed in the document text, so the review screen can show it.

Values are matched the way the cross-check matches them: amounts and dates by value (so "£1,234.50"
matches 1234.50 and "5th March 2026" matches 2026-03-05), names and numbers by their characters.
"""
from __future__ import annotations

import re

from .crosscheck import ANY_DATE
from .duplicates import number_key
from .extractors.rules import MONEY_RX
from .parsing import parse_date, parse_money
from .schema import Invoice

TEXT_FIELDS = ("supplier_name", "supplier_address", "invoice_number")
DATE_FIELDS = ("invoice_date", "due_date")
MONEY_FIELDS = ("subtotal", "vat_amount", "total")
SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$", "JPY": "¥", "INR": "₹"}
PERCENT = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")


def _loose(value: str) -> re.Pattern:
    """A pattern that matches the value with any spacing, punctuation or line breaks between its words."""
    words = re.findall(r"[A-Za-z0-9]+", value)
    return re.compile(r"[^A-Za-z0-9]{0,6}".join(map(re.escape, words)), re.I) if words else re.compile(r"(?!x)x")


def locate(inv: Invoice, text: str) -> dict[str, list[list[int]]]:
    """{field: [[start, end], ...]} for every field whose value can be found in the text."""
    spans: dict[str, list[list[int]]] = {}
    for f in TEXT_FIELDS:
        value = getattr(inv, f)
        if not value:
            continue
        found = [[m.start(), m.end()] for m in _loose(str(value)).finditer(text)]
        if not found and f == "invoice_number" and len(number_key(value)) >= 3:
            found = [[m.start(), m.end()] for m in re.finditer(r"[A-Z0-9][A-Z0-9 \-/.]*[A-Z0-9]", text, re.I)
                     if number_key(m.group(0)) == number_key(value)]
        if found:
            spans[f] = found
    for f in DATE_FIELDS:
        value = getattr(inv, f)
        if value:
            found = [[m.start(1), m.start(1) + len(m.group(1))] for m in ANY_DATE.finditer(text) if parse_date(m.group(1)) == value]
            if found:
                spans[f] = _dedupe(found)
    for f in MONEY_FIELDS:
        value = getattr(inv, f)
        if value is not None:
            found = [[m.start(), m.end()] for m in MONEY_RX.finditer(text) if parse_money(m.group(0)) == value]
            if found:
                spans[f] = found
    if inv.vat_rate is not None:
        found = [[m.start(), m.end()] for m in PERCENT.finditer(text) if parse_money(m.group(1)) == inv.vat_rate]
        if found:
            spans["vat_rate"] = found
    if inv.currency:
        code = inv.currency.upper()
        alts = [re.escape(code)] + ([re.escape(SYMBOLS[code])] if code in SYMBOLS else [])
        found = [[m.start(), m.end()] for m in re.finditer(rf"(?<![A-Za-z])(?:{'|'.join(alts)})(?![A-Za-z])", text)]
        if found:
            spans["currency"] = found[:12]  # a symbol can appear on every line; a handful is enough to show
    return spans


def _dedupe(spans: list[list[int]]) -> list[list[int]]:
    """Overlapping date matches ("05 Mar 2026" and "5 Mar 2026") collapse to the longest one."""
    out: list[list[int]] = []
    for s, e in sorted(spans, key=lambda x: (x[0], -x[1])):
        if out and s < out[-1][1]:
            continue
        out.append([s, e])
    return out
