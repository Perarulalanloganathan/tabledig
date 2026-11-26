"""Arithmetic sanity checks for extracted tables.

A value that is *read* correctly can still be the *wrong* value (a neighbouring row, a different
column). Tables usually contain their own proof: a "Total" row should equal the rows above it, and a
balance sheet should balance. :func:`check_tables` looks for those relationships and reports, per row:

* ``verified``  - every additive column reproduces from the rows above (strong evidence of a correct read)
* ``partial``   - some columns reproduce and some do not (e.g. a ratio column, or one misread cell)
* ``mismatch``  - the row looks like a total but none of its columns add up (misread, or a genuine error)
* ``unchecked`` - nothing to compare against (most rows)

The checks are conservative: only rows labelled like a total are examined, at least two numeric rows
must sit above them, tables that continue across pages are joined, and columns that are not additive
(percentages, rates, ratios, averages) are skipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .matcher import normalize_label
from .models import Table
from .normalize import parse_number

TOTAL_PREFIXES = ("total", "subtotal", "sub total", "grand total", "sum of")
ASSETS = ("total assets",)
LIABILITIES_AND_EQUITY = ("total equity and liabilities", "total liabilities and equity")


NON_ADDITIVE = ("%", "percent", "pct", "rate", "ratio", "avg", "average", "per ", "share", "margin", "mean")


@dataclass(frozen=True)
class Check:
    status: str  # "verified" | "partial" | "mismatch" | "unchecked"
    note: Optional[str] = None


UNCHECKED = Check("unchecked")


def _is_total(label: str) -> bool:
    norm = normalize_label(label)
    return norm.startswith(TOTAL_PREFIXES)


def _label_of(row: list[str]) -> Optional[str]:
    for cell in row:
        if cell and parse_number(cell) is None and any(ch.isalpha() for ch in cell):
            return cell
    return None


def _numbers(row: list[str]) -> dict[int, float]:
    """Numeric cells keyed by column position, ignoring the label cell."""
    label = _label_of(row)
    out: dict[int, float] = {}
    seen_label = False
    for j, cell in enumerate(row):
        if cell == label and not seen_label:
            seen_label = True
            continue
        if not seen_label:
            continue
        number = parse_number(cell)
        if number is not None:
            out[j] = number
    return out


def _tolerance(value: float, n_terms: int, integers: bool) -> float:
    unit = 1.0 if integers else 0.01
    return max(0.002 * abs(value), unit * 0.5 * (n_terms + 1))


def _sum_reproduces(target: float, terms: list[float], integers: bool) -> bool:
    """True if ``terms`` add up to ``target``, allowing rounding and sign convention."""
    tol = _tolerance(target, len(terms), integers)
    return abs(sum(terms) - target) <= tol or abs(sum(abs(t) for t in terms) - abs(target)) <= tol


def _check_total_row(
    rows: list[dict[int, float]],
    labels: list[Optional[str]],
    i: int,
    skip: set[int],
    names: list[str],
) -> Check:
    own = rows[i]
    if not own:
        return UNCHECKED
    above = [k for k in range(i) if rows[k]]
    if len(above) < 2:
        return UNCHECKED

    verified_cols, failed_cols = 0, 0
    failed_names: list[str] = []
    for col, target in own.items():
        if target == 0 or col in skip:
            continue
        integers = float(target).is_integer()
        matched = False
        # candidate blocks: the last n numeric rows above, for every n >= 2 that has a value in `col`
        chain = [k for k in above if col in rows[k]]
        for start in range(len(chain) - 1, -1, -1):
            block = chain[start:]
            if len(block) < 2:
                continue
            terms_all = [rows[k][col] for k in block]
            terms_detail = [rows[k][col] for k in block if not (labels[k] and _is_total(labels[k]))]
            terms_subtotals = [rows[k][col] for k in block if labels[k] and _is_total(labels[k])]
            for terms in (terms_all, terms_detail, terms_subtotals):
                if len(terms) >= 2 and _sum_reproduces(target, terms, integers):
                    matched = True
                    break
            if matched:
                break
        if matched:
            verified_cols += 1
        else:
            failed_cols += 1
            failed_names.append(names[col] if col < len(names) and names[col] else f"col_{col + 1}")

    if verified_cols and not failed_cols:
        return Check("verified", f"{verified_cols} column(s) equal the sum of the rows above")
    if failed_cols and not verified_cols:
        return Check("mismatch", "does not equal the sum of the rows above: " + ", ".join(failed_names))
    if failed_cols:
        return Check("partial", f"{verified_cols} column(s) add up; not: " + ", ".join(failed_names))
    return UNCHECKED


def _logical_tables(tables: list[Table]) -> list[list[Table]]:
    """Group consecutive tables that are continuations of each other (same header, same width)."""
    groups: list[list[Table]] = []
    for table in tables:
        prev = groups[-1][-1] if groups else None
        width = max((len(r) for r in table.rows), default=0)
        prev_width = max((len(r) for r in prev.rows), default=0) if prev else -1
        if (
            prev is not None
            and table.header
            and table.header == prev.header
            and table.page == prev.page + 1
            and width == prev_width
        ):
            groups[-1].append(table)
        else:
            groups.append([table])
    return groups


def check_tables(tables: list[Table]) -> dict[tuple[int, int, int], Check]:
    """Check every table. Keys are ``(page, table index, row index)``."""
    results: dict[tuple[int, int, int], Check] = {}
    asset_rows: list[tuple[tuple[int, int, int], dict[int, float]]] = []
    liability_rows: list[tuple[tuple[int, int, int], dict[int, float]]] = []

    for group in _logical_tables(tables):
        rows_text: list[list[str]] = []
        origin: list[tuple[int, int, int]] = []
        for table in group:
            for i, row in enumerate(table.rows):
                rows_text.append(row)
                origin.append((table.page, table.index, i))
        header = group[0].header
        names = list(header)
        skip = {
            j
            for j, name in enumerate(names)
            if any(word in name.lower() for word in NON_ADDITIVE)
        }
        rows = [_numbers(r) for r in rows_text]
        # a "%" in the cell itself also marks a non-additive column
        for r_text in rows_text:
            for j, cell in enumerate(r_text):
                if "%" in cell:
                    skip.add(j)
        labels = [_label_of(r) for r in rows_text]
        for i, label in enumerate(labels):
            if label is None:
                continue
            key = origin[i]
            norm = normalize_label(label)
            if _is_total(label):
                results[key] = _check_total_row(rows, labels, i, skip, names)
            if norm in ASSETS and rows[i]:
                asset_rows.append((key, rows[i]))
            if norm in LIABILITIES_AND_EQUITY and rows[i]:
                liability_rows.append((key, rows[i]))

    # accounting identity: total assets == total equity and liabilities (same column count, in order)
    for (akey, avals), (lkey, lvals) in zip(asset_rows, liability_rows):
        a, b = list(avals.values()), list(lvals.values())
        if len(a) != len(b) or not a:
            continue
        ok = all(abs(x - y) <= max(0.002 * abs(x), 1.0) for x, y in zip(a, b))
        note = (
            "total assets equal total equity and liabilities"
            if ok
            else "total assets differ from equity and liabilities"
        )
        status = "verified" if ok else "mismatch"
        for key in (akey, lkey):
            previous = results.get(key)
            if previous is None or previous.status == "unchecked" or status == "mismatch":
                results[key] = Check(status, note)
    return results
