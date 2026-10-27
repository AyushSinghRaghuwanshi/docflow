"""Processing one document: read it, screen it, extract fields, check them, decide what happens next."""
from __future__ import annotations

import time
from datetime import date
from typing import Callable

from .crosscheck import reconcile, reference_as_number
from .duplicates import Match, file_hash
from .extractors import rules
from .extractors.llm import LLMExtractor, ProviderConfig, resolve_provider
from .guard import scan
from .ingest import document_to_text, image_type
from .schema import Decision, ExtractionResult, Invoice, Issue, Severity
from .validate import validate

MAX_REPAIRS = 1
# Asking the model to read again only helps when we're unsure what the document says...
EXTRACTION_DOUBTS = {"MISSING_FIELD", "UNGROUNDED_FIELD", "FIELD_DISAGREEMENT", "NUMBER_IS_REFERENCE"}
# ...not when both extractors agree on figures that simply don't add up.
ARITHMETIC = {"LINE_ITEMS_MISMATCH", "TOTAL_MISMATCH", "VAT_MISMATCH"}
MONEY_FIELDS = ("subtotal", "vat_amount", "total")

DuplicateCheck = Callable[[str | None, str | None], bool]
DuplicateFinder = Callable[..., "Match | None"]


def worth_retrying(issues: list[Issue], confidence: dict[str, str]) -> bool:
    errors = {i.code for i in issues if i.severity == Severity.ERROR}
    if errors & EXTRACTION_DOUBTS:
        return True
    figures_agreed = all(confidence.get(f) == "high" for f in MONEY_FIELDS)
    return bool(errors & ARITHMETIC) and not figures_agreed


def duplicate_issues(match: Match | None) -> list[Issue]:
    if match == Match.SAME_FILE:
        return [Issue(code="DUPLICATE", severity=Severity.ERROR, field="invoice_number",
                      message="This exact file has already been uploaded.")]
    if match == Match.EXACT:
        return [Issue(code="DUPLICATE", severity=Severity.ERROR, field="invoice_number",
                      message="This supplier and invoice number have already been processed.")]
    if match == Match.POSSIBLE:
        return [Issue(code="POSSIBLE_DUPLICATE", severity=Severity.ERROR, field="invoice_number",
                      message="This invoice number was already used by a different or unrecognised supplier; "
                              "check it isn't a duplicate.")]
    return []


def process(
    name: str,
    data: bytes,
    *,
    extractor: str = "auto",
    provider: ProviderConfig | None = None,
    is_duplicate: DuplicateCheck | None = None,
    find_duplicate: DuplicateFinder | None = None,
    today: date | None = None,
) -> ExtractionResult:
    started = time.perf_counter()
    sha = file_hash(data)
    cfg = provider or (resolve_provider() if extractor in ("auto", "llm") else None)
    if extractor == "llm" and cfg is None:
        raise RuntimeError("extractor='llm' was requested but no LLM provider is configured (see .env.example).")

    media = image_type(name)
    if media:
        return _process_image(name, data, media, sha, cfg, find_duplicate, today)

    guard = scan(document_to_text(name, data))
    text = guard.sanitised_text  # the model never sees the lines the guard removed

    repairs = 0
    if cfg is not None and extractor != "rules":
        agent = LLMExtractor(cfg)
        baseline, _, _ = rules.extract_with_confidence(text)

        def check(answer: Invoice):
            inv, issues, confidence = reconcile(answer, baseline, text)
            return inv, issues + validate(inv, today), confidence

        invoice, issues, confidence = check(agent.extract(text))
        while repairs < MAX_REPAIRS and worth_retrying(issues, confidence):
            repairs += 1
            invoice, issues, confidence = check(agent.repair([i.message for i in issues if i.severity == Severity.ERROR]))
        usage, used = agent.usage, f"llm:{cfg.provider}"
    else:
        invoice, usage, confidence = rules.extract_with_confidence(text)
        invoice, issues = reference_as_number(invoice, text)
        issues += validate(invoice, today)
        if invoice.supplier_name and confidence.get("supplier_name") == "low":
            issues.append(Issue(code="UNCERTAIN_FIELD", severity=Severity.ERROR, field="supplier_name",
                                message=f"'{invoice.supplier_name}' is only a guess at the supplier name; please confirm it."))
        usage.latency_ms = (time.perf_counter() - started) * 1000
        used = "rules"

    if guard.flagged:
        issues.append(Issue(code="PROMPT_INJECTION", severity=Severity.ERROR,
                            message="Text that tries to instruct the software was found and removed: "
                                    + " / ".join(guard.matches[:3])))

    if find_duplicate:
        match = find_duplicate(invoice.supplier_name, invoice.invoice_number, sha)
    else:
        match = Match.EXACT if is_duplicate and is_duplicate(invoice.supplier_name, invoice.invoice_number) else None
    issues += duplicate_issues(match)

    if any(i.code == "DUPLICATE" for i in issues):
        decision = Decision.REJECTED
    elif any(i.severity == Severity.ERROR for i in issues):
        decision = Decision.NEEDS_REVIEW
    else:
        decision = Decision.AUTO_APPROVED

    return ExtractionResult(document_name=name, extractor=used, invoice=invoice, issues=issues,
                            injection_detected=guard.flagged, repair_attempts=repairs,
                            field_confidence=confidence, file_sha256=sha, decision=decision, usage=usage)


def _process_image(name, data, media, sha, cfg, find_duplicate, today) -> ExtractionResult:
    """A photo or scan, read directly by a vision-language model.

    There is no text layer, so the guard can't screen for injected instructions and the values
    can't be checked against the document text. The arithmetic and duplicate checks still run,
    but the result always goes to a person.
    """
    if cfg is None:
        raise RuntimeError("Images need a vision-capable model; set DOCFLOW_PROVIDER and DOCFLOW_MODEL.")
    agent = LLMExtractor(cfg)
    invoice = agent.extract_image(data, media)
    issues = validate(invoice, today)
    issues.append(Issue(code="IMAGE_UNVERIFIED", severity=Severity.ERROR,
                        message="Read from an image: values couldn't be checked against document text and the "
                                "image couldn't be screened for injected instructions. Please check it."))
    if find_duplicate:
        issues += duplicate_issues(find_duplicate(invoice.supplier_name, invoice.invoice_number, sha))
    decision = Decision.REJECTED if any(i.code == "DUPLICATE" for i in issues) else Decision.NEEDS_REVIEW
    return ExtractionResult(document_name=name, extractor=f"vision:{cfg.provider}", invoice=invoice, issues=issues,
                            injection_detected=False, repair_attempts=0, field_confidence={}, file_sha256=sha,
                            decision=decision, usage=agent.usage)
