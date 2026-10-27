"""Turn PDF, XLSX, CSV and text files into plain text.

Spreadsheet rows are joined with " | " so the extractors see tables the same way whatever the format.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

SUPPORTED = {".pdf", ".xlsx", ".csv", ".txt", ".md"}
IMAGES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def image_type(name: str) -> str | None:
    """The media type if the file is a photo or scan that has to be read by a vision model."""
    return IMAGES.get(Path(name).suffix.lower())


class UnsupportedDocument(ValueError):
    pass


def _pdf_to_text(data: bytes) -> str:
    """Extract text with its layout kept, so columns stay separated by runs of spaces.

    Plain extraction merges side-by-side columns ("From:  Bill to:" becomes one phrase),
    which is the main reason two-column invoices were misread.
    """
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            raw = page.extract_text(layout=True) or ""
            lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
            indent = min((len(ln) - len(ln.lstrip()) for ln in lines), default=0)
            pages.append("\n".join(ln[indent:] for ln in lines))
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
