"""Duplicate detection: the same supplier using the same invoice number.

Names and numbers are normalised first ("LANTERNMOSS GRID LTD" = "Lanternmoss Grid Limited",
"LMG-260305-017" = "LMG 260305 017"). Currency, layout and file type are ignored on purpose:
a bill re-sent as a different file is still the same bill.
"""
from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from enum import Enum

_LEGAL_SUFFIX = re.compile(r"\b(ltd|limited|plc|llp|llc|inc|incorporated|corp|corporation|gmbh|sarl|sa|bv|co|company|the)\b")


class Match(str, Enum):
    EXACT = "exact"        # same supplier and same invoice number: a duplicate
    POSSIBLE = "possible"  # same invoice number, supplier differs or is unknown: a person should check
    SAME_FILE = "same_file"  # byte-for-byte the same file uploaded again


def supplier_key(name: str | None) -> str:
    if not name:
        return ""
    s = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    s = _LEGAL_SUFFIX.sub(" ", s)
    return " ".join(s.split())


def number_key(number: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (number or "").upper())


def same_supplier(a: str, b: str) -> bool:
    """True when two normalised supplier keys refer to the same company."""
    if not a or not b:
        return False
    if a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a))):
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.85


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
