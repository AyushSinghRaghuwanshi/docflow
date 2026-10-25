"""Turn PDFs, spreadsheets and text files into plain text the extractors can read.

Tables are flattened row by row with ' | ' separators so both the rules
baseline and the LLM see line items in a consistent shape.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

SUPPORTED = {".pdf", ".xlsx", ".csv", ".txt", ".md"}


class UnsupportedDocument(ValueError):
    pass


def _pdf_to_text(data: bytes) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _xlsx_to_text(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _csv_to_text(data: bytes) -> str:
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
    return "\n".join(" | ".join(c.strip() for c in row if c.strip()) for row in reader if any(row))


def document_to_text(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED:
        raise UnsupportedDocument(f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED)}")
    if suffix == ".pdf":
        text = _pdf_to_text(data)
    elif suffix == ".xlsx":
        text = _xlsx_to_text(data)
    elif suffix == ".csv":
        text = _csv_to_text(data)
    else:
        text = data.decode("utf-8", errors="replace")
    if not text.strip():
        raise UnsupportedDocument("No extractable text found (scanned image PDFs need OCR, which is out of scope).")
    return text
