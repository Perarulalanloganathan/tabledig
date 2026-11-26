"""Find tables in a PDF.

Two strategies are used per page:

1. **ruled** - tables with drawn lines, via ``pdfplumber.extract_tables``.
2. **text**  - fallback for borderless tables: lines whose tail is a run of
   numbers are parsed as ``label  value  value ...`` rows.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

from .models import Table, Unit
from .normalize import detect_unit, is_year_like, parse_number

_HEADER_TOKEN = re.compile(r"(?:19|20)\d{2}|FY\s?\d{2}", re.IGNORECASE)
_HAS_LETTERS = re.compile(r"[^\W\d_]")


def _clean(cell: object) -> str:
    if cell is None:
        return ""
    return re.sub(r"\s+", " ", str(cell).replace("\n", " ")).strip()


def _numeric_non_year(cell: str) -> bool:
    return parse_number(cell) is not None and not is_year_like(cell)


def _looks_like_header(row: list[str]) -> bool:
    filled = [c for c in row[1:] if c]
    if len(filled) < 1:
        return False
    return not any(_numeric_non_year(c) for c in row)


def _merge_header_rows(top: list[str], bottom: list[str]) -> list[str]:
    width = max(len(top), len(bottom))
    top = top + [""] * (width - len(top))
    bottom = bottom + [""] * (width - len(bottom))
    carried, merged = "", []
    for t, b in zip(top, bottom):
        if t:
            carried = t  # a merged top cell spans the columns to its right
        parent = t or (carried if b else "")
        merged.append(" ".join(p for p in (parent, b) if p).strip())
    return merged


def _explode_stacked(row: list[object]) -> list[list[object]]:
    """Split a row whose cells each hold several newline-separated values into several rows.

    Some PDFs draw a whole column block as one cell ("Alabama\\nAlaska\\n..." next to
    "18,870\\n209\\n..."). We split only when every multi-line cell has the same number of
    lines and at least one of them is purely numeric, so ordinary wrapped text is left alone.
    """
    lines = [str(c).split("\n") if c else [] for c in row]
    sizes = {len(ln) for ln in lines if len(ln) > 1}
    if len(sizes) != 1:
        return [row]
    n = sizes.pop()
    numeric_block = any(
        len(ln) == n and all(parse_number(x) is not None for x in ln) for ln in lines
    )
    if not numeric_block:
        return [row]
    return [[ln[i].strip() if len(ln) == n else (str(c) if i == 0 else "") for ln, c in zip(lines, row)]
            for i in range(n)]


def _build_ruled_table(
    raw: list[list[object]], page: int, index: int, unit: Optional[Unit]
) -> Optional[Table]:
    exploded = [piece for r in raw for piece in _explode_stacked(r)]
    rows = [[_clean(c) for c in r] for r in exploded]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return None

    header: list[str] = []
    if _looks_like_header(rows[0]):
        header = rows.pop(0)
        if rows and _looks_like_header(rows[0]):
            header = _merge_header_rows(header, rows.pop(0))
    return Table(page=page, index=index, header=header, rows=rows, source="ruled", unit=unit)


def _split_numeric_tail(line: str) -> tuple[str, list[str]]:
    tokens = line.split()
    tail: list[str] = []
    while tokens and parse_number(tokens[-1]) is not None:
        tail.insert(0, tokens.pop())
    return " ".join(tokens), tail


def _build_text_tables(
    text: str, page: int, start_index: int, unit: Optional[Unit]
) -> list[Table]:
    tables: list[Table] = []
    current_rows: list[tuple[str, list[str]]] = []
    current_header: list[str] = []

    def flush() -> None:
        nonlocal current_rows, current_header
        if current_rows:
            width = len(current_header) or max(len(v) for _, v in current_rows)
            rows = []
            for label, values in current_rows:
                values = values[-width:] if current_header else values
                rows.append([label] + [""] * (width - len(values)) + values)
            header = [""] + current_header if current_header else []
            tables.append(
                Table(
                    page=page,
                    index=start_index + len(tables),
                    header=header,
                    rows=rows,
                    source="text",
                    unit=unit,
                )
            )
        current_rows, current_header = [], []

    for line in text.splitlines():
        label, tail = _split_numeric_tail(line)
        if not tail:
            continue
        if len(tail) >= 2 and all(is_year_like(t) for t in tail):
            flush()  # a header such as "Particulars  2024  2023"
            current_header = tail
            continue
        if not _HAS_LETTERS.search(label):
            continue
        current_rows.append((label, tail))
    flush()
    return tables


def _unique_header(header: list[str]) -> list[str]:
    """Make repeated column names unique ("2024", "2024 (2)") so no value is overwritten."""
    seen: dict[str, int] = {}
    out = []
    for name in header:
        n = seen.get(name, 0) + 1
        seen[name] = n
        out.append(name if n == 1 or not name else f"{name} ({n})")
    return out


def _good_rows(tables: list[Table]) -> int:
    """Rows that look like data: a text label followed by at least one number."""
    count = 0
    for table in tables:
        for row in table.rows:
            label_idx = next(
                (i for i, c in enumerate(row) if _HAS_LETTERS.search(c) and parse_number(c) is None), -1
            )
            if label_idx >= 0 and any(parse_number(c) is not None for c in row[label_idx + 1 :]):
                count += 1
    return count


def _width(table: Table) -> int:
    return max((len(r) for r in table.rows), default=0)


def read_tables(
    path: Union[str, Path], *, text_fallback: bool = True, password: Optional[str] = None
) -> list[Table]:
    """Return every table found in ``path`` (all pages).

    A ruled table with no header inherits the previous page's header when the column counts
    match (long tables usually print the header only once). Pages whose ruled tables hold
    almost no usable rows fall back to whitespace-aligned text parsing.
    """
    import pdfplumber

    tables: list[Table] = []
    previous: Optional[Table] = None
    with pdfplumber.open(str(path), password=password) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            unit = detect_unit(text)

            built: list[Table] = []
            for raw in page.extract_tables() or []:
                table = _build_ruled_table(raw, page.page_number, len(tables) + len(built), unit)
                if table:
                    same_width = previous is not None and _width(table) == len(previous.header)
                    if not table.header and previous and previous.header and same_width:
                        table.header = list(previous.header)
                    built.append(table)

            if text_fallback and _good_rows(built) < 2:
                built.extend(_build_text_tables(text, page.page_number, len(tables) + len(built), unit))
            for table in built:
                table.header = _unique_header(table.header)
            tables.extend(built)
            ruled = [t for t in built if t.source == "ruled" and t.rows]
            if ruled:
                previous = ruled[-1]
    return tables
