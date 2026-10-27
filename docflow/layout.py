"""Rows of positioned cells, so extractors can ask what's right of or below a label.

PDF text comes out with its layout kept, so columns are separated by runs of spaces. Each line is
split into cells on 3+ spaces or a " | ", " · " or " • " separator, and each cell keeps its column.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_DATE = re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?[ \-][A-Za-z]{3,9},?[ \-]\d{4}"
                   r"|[A-Za-z]{3,9} \d{1,2}(?:st|nd|rd|th)?,? \d{4}"
                   r"|\d{4}[/.]\d{2}[/.]\d{2}|\d{1,2}[/\-][A-Za-z]{3}[/\-]\d{2,4}|\d{1,2} [A-Za-z]{3} \d{2}(?!\d)")
_CELL = re.compile(r"(?:(?!\s{3,}|\s[|·•]\s).)+")  # cells are split by wide gaps or " | ", " · ", " • "


@dataclass(frozen=True)
class Cell:
    row: int
    start: int
    end: int
    text: str

    def overlaps(self, other: "Cell", slack: int = 6) -> bool:
        return self.start <= other.end + slack and other.start <= self.end + slack and abs(self.start - other.start) <= 25


class Grid:
    def __init__(self, text: str):
        self.rows: list[list[Cell]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            r = len(self.rows)
            cells = []
            for m in _CELL.finditer(line):
                raw = m.group(0)
                stripped = raw.strip(" |")
                if not stripped:
                    continue
                lead = len(raw) - len(raw.lstrip(" |"))
                start = m.start() + lead
                dates = list(_DATE.finditer(stripped))
                # only a run of values ("Jun 05, 2026 Jul 20, 2026  EUR"), never a sentence with labels in it
                if len(dates) >= 2 and not re.search(r"[a-z]{2}", _DATE.sub("", stripped)):
                    # several dates squeezed into one cell under several labels: keep each piece at its own column
                    cells += [Cell(r, start + x.start(), start + x.end(), x.group(0))
                              for x in re.finditer(rf"{_DATE.pattern}|\S+", stripped)]
                else:
                    cells.append(Cell(r, start, start + len(stripped), " ".join(stripped.split())))
            if cells:
                self.rows.append(cells)

    def cells(self):
        for row in self.rows:
            yield from row

    def right_of(self, cell: Cell) -> list[Cell]:
        return [c for c in self.rows[cell.row] if c.start > cell.start]

    def below(self, cell: Cell, depth: int = 2) -> list[Cell]:
        """Cells in the next `depth` rows that sit in the same column as `cell`."""
        out = []
        for r in range(cell.row + 1, min(cell.row + 1 + depth, len(self.rows))):
            # nearest column first, so a wide value in the next column doesn't win
            out += sorted((c for c in self.rows[r] if cell.overlaps(c)), key=lambda c: abs(c.start - cell.start))
        return out

    def column_block(self, cell: Cell, max_rows: int = 5) -> list[Cell]:
        """The run of cells directly under `cell` in the same column (an address block)."""
        out, anchor = [], cell
        for r in range(cell.row + 1, min(cell.row + 1 + max_rows, len(self.rows))):
            match = [c for c in self.rows[r] if anchor.overlaps(c, slack=2)]
            if not match:
                break
            out.append(match[0])
        return out
