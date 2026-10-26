"""Screens uploaded text for prompt injection before the LLM sees it.

Any line that reads like an instruction to the software ("ignore previous instructions", "note to the
processing assistant", "do not flag this") is removed from what the model gets, and the document is
sent to review. It's a pattern list, so a new phrasing can get past it; the real safety net is that
the approval decision is made by code, never by the model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules|prompts)",
    r"disregard (all |any )?(previous|prior|above|the) (instructions|rules|system prompt)",
    r"you are now (a|an|the)\b",
    r"(system|developer) prompt",
    r"(set|change|make) the (total|amount|subtotal|vat)[^.\n]{0,40}\b(to|=)\b",
    r"(approve|mark) (this|the) (invoice|document) (automatically|as approved|as paid)",
    r"do\s*n[o']t (flag|review|validate|escalate|report|question|check|query)\b",
    r"\b(processing|automated|automation|ai|llm|extraction)\s+(assistant|system|agent|bot|model|tool|software)s?\b",
    r"\btreat\b[^.\n]{0,80}\bas\s+(authoritative|correct|final|approved|verified)\b",
    r"\b(fast[\s-]?track|auto(matically)?[\s-]?approv\w*|pre[\s-]?approved)\b",
    r"\b(override|supersede)s?\b[^.\n]{0,40}\b(total|amount|figure|instructions?|checks?|rules)\b",
    r"respond only with",
    r"</?(system|instructions?)>",
]
_RX = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]


@dataclass
class GuardResult:
    flagged: bool
    matches: list[str] = field(default_factory=list)
    sanitised_text: str = ""


def scan(text: str) -> GuardResult:
    kept: list[str] = []
    matches: list[str] = []
    for line in text.splitlines():
        hit = next((rx for rx in _RX if rx.search(line)), None)
        if hit:
            matches.append(line.strip()[:160])
        else:
            kept.append(line)
    return GuardResult(flagged=bool(matches), matches=matches, sanitised_text="\n".join(kept))
