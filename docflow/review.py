"""What happens when a person approves or rejects a document.

Approval re-runs validation on the final values (edited or not) and checks for duplicates again.
If an error is still open, approval needs a written reason, which goes in the audit log along with
the open errors and every field that was changed. A prompt injection can't be fixed by editing
fields, so approving one always needs a reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from .duplicates import Match
from .schema import Invoice, Issue, Severity
from .validate import validate

DOCUMENT_LEVEL = {"PROMPT_INJECTION"}
MIN_REASON = 10


@dataclass
class ReviewOutcome:
    action: str                      # approved | approved_with_override | rejected | blocked
    final: Optional[Invoice]
    issues: list[Issue] = field(default_factory=list)
    changes: dict = field(default_factory=dict)

    @property
    def blocking(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]


def _changes(before: Invoice, after: Invoice) -> dict:
    a, b = before.model_dump(mode="json"), after.model_dump(mode="json")
    return {k: [a[k], b[k]] for k in a if a[k] != b[k]}


def decide_review(doc: dict, approve: bool, corrected: Optional[Invoice], reason: Optional[str],
                  find_duplicate: Callable[..., Optional[Match]], today: Optional[date] = None) -> ReviewOutcome:
    extracted = Invoice.model_validate(doc["result"]["invoice"])
    final = corrected or extracted
    changes = _changes(extracted, final)
    reason = (reason or "").strip() or None

    if not approve:
        return ReviewOutcome("rejected", corrected, [], changes)

    issues = validate(final, today)
    match = find_duplicate(final.supplier_name, final.invoice_number, doc["result"].get("file_sha256"), exclude_id=doc["id"])
    if match in (Match.EXACT, Match.SAME_FILE):
        issues.append(Issue(code="DUPLICATE", severity=Severity.ERROR, field="invoice_number",
                            message="Another accepted document has the same supplier and invoice number."
                            if match == Match.EXACT else "This exact file was already accepted."))
    elif match == Match.POSSIBLE:
        issues.append(Issue(code="POSSIBLE_DUPLICATE", severity=Severity.ERROR, field="invoice_number",
                            message="Another document uses this invoice number with a different supplier."))
    issues += [Issue.model_validate(x) for x in doc["result"]["issues"] if x["code"] in DOCUMENT_LEVEL]

    if not any(i.severity == Severity.ERROR for i in issues):
        return ReviewOutcome("approved", final, issues, changes)
    if reason and len(reason) >= MIN_REASON:
        return ReviewOutcome("approved_with_override", final, issues, changes)
    return ReviewOutcome("blocked", final, issues, changes)
