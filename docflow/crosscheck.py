"""Check the LLM's answer against the document text and against the rules extractor.

Arithmetic checks can't see two kinds of LLM mistake: a value that isn't in the document at all
(a made-up due date), and a real value in the wrong field (the subtotal read as the total). So for
each field:

- If the model's value doesn't appear in the text, it's replaced with the rules value (or left
  empty) and flagged UNGROUNDED_FIELD.
- If both extractors found a value and they disagree, the model's value is kept but the document
  goes to review (FIELD_DISAGREEMENT). Neither reader is trusted to overrule the other: on the
  independent test set the rules extractor's "high confidence" supplier names were wrong 15 times
  out of 40.
- A purchase-order or bank reference is never accepted as the invoice number.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .duplicates import number_key, supplier_key
from .extractors.rules import DATE_RX, MONEY_RX
from .parsing import parse_date, parse_money
from .schema import Invoice, Issue, Severity

CHECKED = ["supplier_name", "invoice_number", "invoice_date", "due_date", "currency",
           "subtotal", "vat_rate", "vat_amount", "total"]
# A disagreement on these fields could mean paying the wrong company or the wrong amount.
MUST_AGREE = {"supplier_name", "invoice_number", "invoice_date", "due_date", "subtotal", "vat_amount", "total"}

SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$"}
NUMBER = re.compile(r"\d[\d,.]*")
ANY_DATE = re.compile(f"(?=({DATE_RX.pattern}))")  # overlapping, so "INV-05 Raised 2026-08-15" still finds the date
REFERENCE_LABEL = re.compile(r"(\bP\.?O\.?|purchase\s*order|order\s*(no\.?|number|#)|bank|account|payment\s*ref(erence)?)"
                             r"[\s:#.\-]*$", re.I)


class Evidence:
    """What the document text can back up, worked out once per document."""

    def __init__(self, text: str):
        self.text = text
        self.dates: set[date] = {d for m in ANY_DATE.finditer(text) if (d := parse_date(m.group(1)))}
        self.amounts: set[Decimal] = {a for m in MONEY_RX.finditer(text) if (a := parse_money(m.group(0))) is not None}
        self.numbers: set[Decimal] = {n for m in NUMBER.finditer(text) if (n := parse_money(m.group(0))) is not None}
        self.words = set(re.findall(r"[a-z0-9]+", text.lower()))
        self.alnum = number_key(text)

    def contains(self, field: str, value: object) -> bool:
        if value is None:
            return True
        if field in ("invoice_date", "due_date"):
            return value in self.dates
        if field in ("subtotal", "vat_amount", "total"):
            return value == 0 or value in self.amounts or value in self.numbers
        if field == "vat_rate":
            return value == 0 or value in self.numbers
        if field == "currency":
            return bool(re.search(rf"\b{value}\b", self.text)) or SYMBOLS.get(str(value), "\0") in self.text
        if field == "supplier_name":
            # word by word, because layouts often split a name over two lines
            words = supplier_key(str(value)).split()
            return bool(words) and all(w in self.words for w in words)
        if field == "invoice_number":
            key = number_key(str(value))
            return len(key) >= 3 and key in self.alnum
        return True

    def is_reference(self, number: str) -> bool:
        """True if every place the number appears, it's labelled as a PO, order or bank reference."""
        spots = [m.start() for m in re.finditer(re.escape(number), self.text)]
        if not spots:
            return False
        for pos in spots:
            line_start = self.text.rfind("\n", 0, pos) + 1
            if not REFERENCE_LABEL.search(self.text[max(line_start, pos - 30):pos]):
                return False
        return True


def same_value(field: str, a: object, b: object) -> bool:
    if field == "supplier_name":
        return supplier_key(str(a)) == supplier_key(str(b))
    if field == "invoice_number":
        return number_key(str(a)) == number_key(str(b))
    return a == b


def reference_as_number(inv: Invoice, text: str) -> tuple[Invoice, list[Issue]]:
    """Blank out an invoice number that is really a PO or bank reference (used for every extractor)."""
    if inv.invoice_number and Evidence(text).is_reference(inv.invoice_number):
        issue = Issue(code="NUMBER_IS_REFERENCE", severity=Severity.ERROR, field="invoice_number",
                      message=f"'{inv.invoice_number}' is a purchase-order or payment reference, not the invoice number.")
        return inv.model_copy(update={"invoice_number": None}), [issue]
    return inv, []


def reconcile(llm: Invoice, rules: Invoice, text: str) -> tuple[Invoice, list[Issue], dict[str, str]]:
    """Return the checked invoice, any issues, and how sure we are of each field (high/medium/low)."""
    ev = Evidence(text)
    values = llm.model_dump()
    issues: list[Issue] = []
    confidence: dict[str, str] = {}

    for f in CHECKED:
        ours, theirs = getattr(llm, f), getattr(rules, f)
        if f == "invoice_number":
            if ours and ev.is_reference(ours):
                issues.append(Issue(code="NUMBER_IS_REFERENCE", severity=Severity.ERROR, field=f,
                                    message=f"The model gave '{ours}' as the invoice number, but it's a purchase-order "
                                            "or payment reference."))
                ours = values[f] = None
            if theirs and ev.is_reference(theirs):
                theirs = None
        theirs_found = theirs is not None and ev.contains(f, theirs)

        if ours is None:
            if theirs_found:
                values[f], confidence[f] = theirs, "medium"
            continue

        if not ev.contains(f, ours):
            values[f] = theirs if theirs_found else None
            confidence[f] = "medium" if theirs_found else "low"
            instead = f"used '{theirs}' from the rules extractor instead" if theirs_found else "left it empty"
            issues.append(Issue(code="UNGROUNDED_FIELD", severity=Severity.ERROR, field=f,
                                message=f"The model read {f} as '{ours}', which isn't in the document; {instead}."))
            continue

        if not theirs_found or same_value(f, ours, theirs):
            confidence[f] = "high" if theirs_found else "medium"
            continue

        confidence[f] = "low"
        severity = Severity.ERROR if f in MUST_AGREE else Severity.WARNING
        issues.append(Issue(code="FIELD_DISAGREEMENT", severity=severity, field=f,
                            message=f"The model read {f} as '{ours}' but the rules extractor read '{theirs}'. "
                                    "Please check which is right."))

    return Invoice.model_validate(values), issues, confidence
