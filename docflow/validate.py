"""Business-rule validation: the layer that decides whether a person must check a record.

LLMs are good readers but are not accountants. Every extraction, from any extractor,
is checked against arithmetic and common-sense rules before it can be auto-approved.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from .schema import Invoice, Issue, Severity

TOLERANCE = Decimal("0.02")
STANDARD_UK_VAT = {Decimal("0"), Decimal("5"), Decimal("20")}
REQUIRED = ["supplier_name", "invoice_number", "invoice_date", "total"]


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def validate(inv: Invoice, today: date | None = None) -> list[Issue]:
    today = today or date.today()
    issues: list[Issue] = []

    for f in REQUIRED:
        if getattr(inv, f) in (None, ""):
            issues.append(Issue(code="MISSING_FIELD", severity=Severity.ERROR, field=f,
                                message=f"Required field '{f}' could not be found."))

    if inv.line_items and inv.subtotal is not None:
        line_sum = sum((li.amount for li in inv.line_items), Decimal("0"))
        if not _close(line_sum, inv.subtotal):
            issues.append(Issue(code="LINE_ITEMS_MISMATCH", severity=Severity.ERROR, field="subtotal",
                                message=f"Line items add up to {line_sum}, but the subtotal says {inv.subtotal}."))

    for li in inv.line_items:
        if not _close(li.quantity * li.unit_price, li.amount):
            issues.append(Issue(code="LINE_ARITHMETIC", severity=Severity.WARNING, field="line_items",
                                message=f"'{li.description}': {li.quantity} x {li.unit_price} is not {li.amount}."))

    if None not in (inv.subtotal, inv.vat_amount, inv.total):
        if not _close(inv.subtotal + inv.vat_amount, inv.total):
            issues.append(Issue(code="TOTAL_MISMATCH", severity=Severity.ERROR, field="total",
                                message=f"Subtotal {inv.subtotal} + VAT {inv.vat_amount} is not the total {inv.total}."))

    if None not in (inv.subtotal, inv.vat_rate, inv.vat_amount):
        expected = (inv.subtotal * inv.vat_rate / 100).quantize(Decimal("0.01"))
        if not _close(expected, inv.vat_amount):
            issues.append(Issue(code="VAT_MISMATCH", severity=Severity.WARNING, field="vat_amount",
                                message=f"{inv.vat_rate}% of {inv.subtotal} is {expected}, not {inv.vat_amount}."))

    if inv.currency == "GBP" and inv.vat_rate is not None and inv.vat_rate not in STANDARD_UK_VAT:
        issues.append(Issue(code="UNUSUAL_VAT_RATE", severity=Severity.WARNING, field="vat_rate",
                            message=f"{inv.vat_rate}% is not a standard UK VAT rate."))

    if inv.invoice_date and inv.due_date and inv.due_date < inv.invoice_date:
        issues.append(Issue(code="DUE_BEFORE_ISSUE", severity=Severity.ERROR, field="due_date",
                            message="The due date is before the invoice date."))
    if inv.invoice_date and inv.invoice_date > today:
        issues.append(Issue(code="FUTURE_DATE", severity=Severity.WARNING, field="invoice_date",
                            message="The invoice date is in the future."))
    if inv.total is not None and inv.total <= 0:
        issues.append(Issue(code="NON_POSITIVE_TOTAL", severity=Severity.ERROR, field="total",
                            message="The total is zero or negative."))
    if not inv.currency:
        issues.append(Issue(code="MISSING_CURRENCY", severity=Severity.WARNING, field="currency",
                            message="No currency could be identified."))
    return issues
