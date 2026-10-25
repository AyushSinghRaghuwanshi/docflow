"""The DocFlow agent loop: ingest -> guard -> extract -> validate -> self-repair -> decide."""
from __future__ import annotations

import time
from datetime import date
from typing import Callable

from .extractors import rules
from .extractors.llm import LLMExtractor, ProviderConfig, resolve_provider
from .guard import scan
from .ingest import document_to_text
from .schema import Decision, ExtractionResult, Issue, Severity
from .validate import validate

# Only arithmetic / missing-field errors are worth a second look by the model;
# a real duplicate or a genuinely wrong document will not be "fixed" by re-reading.
REPAIRABLE = {"MISSING_FIELD", "LINE_ITEMS_MISMATCH", "TOTAL_MISMATCH"}
MAX_REPAIRS = 1

DuplicateCheck = Callable[[str | None, str | None], bool]


def process(
    name: str,
    data: bytes,
    *,
    extractor: str = "auto",
    provider: ProviderConfig | None = None,
    is_duplicate: DuplicateCheck | None = None,
    today: date | None = None,
) -> ExtractionResult:
    started = time.perf_counter()
    text = document_to_text(name, data)
    guard = scan(text)

    cfg = provider or (resolve_provider() if extractor in ("auto", "llm") else None)
    if extractor == "llm" and cfg is None:
        raise RuntimeError("extractor='llm' requested but no LLM provider is configured (see .env.example).")
    use_llm = cfg is not None and extractor != "rules"

    repairs = 0
    if use_llm:
        agent = LLMExtractor(cfg)
        invoice = agent.extract(guard.sanitised_text)
        issues = validate(invoice, today)
        while repairs < MAX_REPAIRS and any(i.severity == Severity.ERROR and i.code in REPAIRABLE for i in issues):
            repairs += 1
            invoice = agent.repair([i.message for i in issues if i.severity == Severity.ERROR])
            issues = validate(invoice, today)
        usage, used = agent.usage, f"llm:{cfg.provider}"
    else:
        invoice, usage = rules.extract(guard.sanitised_text)
        issues, used = validate(invoice, today), "rules"
        usage.latency_ms = (time.perf_counter() - started) * 1000

    if guard.flagged:
        issues.append(Issue(code="PROMPT_INJECTION", severity=Severity.ERROR,
                            message="Instruction-like text was found in the document and removed: "
                                    + " / ".join(guard.matches[:3])))
    if is_duplicate and is_duplicate(invoice.supplier_name, invoice.invoice_number):
        issues.append(Issue(code="DUPLICATE", severity=Severity.ERROR, field="invoice_number",
                            message="This supplier and invoice number have already been processed."))

    codes = {i.code for i in issues}
    if "DUPLICATE" in codes:
        decision = Decision.REJECTED
    elif any(i.severity == Severity.ERROR for i in issues):
        decision = Decision.NEEDS_REVIEW
    else:
        decision = Decision.AUTO_APPROVED

    return ExtractionResult(document_name=name, extractor=used, invoice=invoice, issues=issues,
                            injection_detected=guard.flagged, repair_attempts=repairs,
                            decision=decision, usage=usage)
