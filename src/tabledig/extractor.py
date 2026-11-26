"""Core engine: look attributes up in the tables of one or many PDFs."""
from __future__ import annotations

import re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

from .config import coerce_attributes
from .matcher import score_label
from .models import Attribute, Record, Table
from .normalize import parse_number
from .reader import read_tables
from .validate import check_tables

DEFAULT_SKIP_COLUMNS = re.compile(
    r"^(?:notes?|note\s*no\.?|ref\.?|sl\.?\s*no\.?|s\.?\s*no\.?|sr\.?\s*no\.?)$", re.IGNORECASE
)
_HAS_LETTERS = re.compile(r"[^\W\d_]")

AttributeLike = Union[str, dict, Attribute]


@dataclass
class _Candidate:
    score: float
    method: str
    table: Table
    label: str
    values: list[tuple[str, str, float]]  # (column, raw, number)
    row_idx: int = -1
    row: Optional[list[str]] = None

    @property
    def key(self) -> tuple:
        # best score first; on ties prefer the tighter (shorter) label, then richer rows
        return (self.score, -len(self.label.split()), len(self.values), -self.table.page, -self.table.index)


def _split_row(row: list[str]) -> tuple[Optional[str], int]:
    """Return (label, index of label cell). The label is the first text cell."""
    for i, cell in enumerate(row):
        if _HAS_LETTERS.search(cell) and parse_number(cell) is None:
            return cell, i
    return None, -1


def _describe_error(exc: Exception) -> str:
    text = str(exc).strip()
    name = type(exc).__name__
    if "password" in name.lower() or "password" in text.lower() or (name == "PdfminerException" and not text):
        return f"{name}: PDF is password-protected or encrypted; pass password=... (CLI: --password)"
    return f"{name}: {text}" if text else name


def _confidence(score: float, check_status: Optional[str]) -> float:
    """Heuristic 0-1 confidence: the match score, nudged by what validation found."""
    base = score / 100.0
    if check_status == "verified":
        base = min(1.0, base + 0.1)
    elif check_status == "partial":
        base *= 0.85
    elif check_status == "mismatch":
        base *= 0.5
    return round(base, 3)


def _alternatives(chosen: _Candidate, candidates: list[_Candidate], limit: int = 3) -> Optional[str]:
    others = [
        f"{c.label} ({c.score:.0f}, p.{c.table.page})"
        for c in candidates
        if c is not chosen and c.label != chosen.label
    ]
    return "; ".join(others[:limit]) or None


class Extractor:
    """Find named attributes (row labels) and return their values.

    Parameters
    ----------
    attributes:
        Names (``"Total revenue"``), dicts (``{"name":..., "aliases":[...]}``)
        or :class:`Attribute` objects.
    min_score:
        Default minimum match score (0-100) for fuzzy matching.
    top_k:
        How many best-matching rows to keep per attribute and file.
    normalize_units:
        Multiply values by the table's declared unit (lakhs, millions, ...)
        so results are in base units.
    include_missing:
        Emit a ``not_found`` record for attributes with no match.
    password:
        Password for encrypted PDFs.
    validate:
        Check totals/subtotals and balance-sheet identities; adds ``check``, ``check_note`` and a
        heuristic ``confidence`` to each record.
    evidence:
        Add ``row_text`` (the full source row) to each record.
    explain:
        Add ``alternatives`` (runner-up labels that were not chosen).
    decimal:
        ``"."`` or ``","`` to force the decimal mark (default: auto-detect, so ``1.234,56`` works).
    """

    def __init__(
        self,
        attributes: Sequence[AttributeLike],
        *,
        min_score: float = 80.0,
        top_k: int = 1,
        normalize_units: bool = False,
        include_missing: bool = True,
        decimal: Optional[str] = None,
        password: Optional[str] = None,
        validate: bool = False,
        evidence: bool = False,
        explain: bool = False,
        skip_columns: re.Pattern = DEFAULT_SKIP_COLUMNS,
    ) -> None:
        self.attributes = coerce_attributes(attributes)
        self.min_score = min_score
        self.top_k = max(1, top_k)
        self.normalize_units = normalize_units
        self.include_missing = include_missing
        self.decimal = decimal
        self.password = password
        self.validate = validate
        self.evidence = evidence
        self.explain = explain
        self.skip_columns = skip_columns

    # -- single file --------------------------------------------------------
    def extract_file(self, path: Union[str, Path]) -> list[Record]:
        tables = read_tables(path, password=self.password)
        return self.extract_tables(tables, Path(path).name)

    def extract_tables(self, tables: Iterable[Table], file_name: str = "") -> list[Record]:
        tables = list(tables)
        records: list[Record] = []
        checks = check_tables(tables) if self.validate else {}
        for attribute in self.attributes:
            candidates = self._candidates(attribute, tables)
            if not candidates:
                if self.include_missing:
                    records.append(Record(file_name, attribute.name, "not_found"))
                continue
            for cand in candidates[: self.top_k]:
                new = self._to_records(file_name, attribute, cand, checks)
                if self.explain:
                    alts = _alternatives(cand, candidates)
                    for r in new:
                        r.alternatives = alts
                records.extend(new)
        return records

    # -- internals ----------------------------------------------------------
    def _candidates(self, attribute: Attribute, tables: list[Table]) -> list[_Candidate]:
        threshold = attribute.min_score if attribute.min_score is not None else self.min_score
        found: list[_Candidate] = []
        seen: set[tuple] = set()

        for table in tables:
            for row_idx, row in enumerate(table.rows):
                label, label_idx = _split_row(row)
                if label is None:
                    continue

                best_score, best_method = 0.0, "none"
                for name in attribute.names:
                    score, method = score_label(name, label, attribute.mode)
                    if score > best_score:
                        best_score, best_method = score, method
                if best_score < threshold:
                    continue

                values = []
                for j in range(label_idx + 1, len(row)):
                    column = table.header[j] if j < len(table.header) and table.header[j] else f"col_{j + 1}"
                    if self.skip_columns.match(column):
                        continue
                    number = parse_number(row[j], self.decimal)
                    if number is not None:
                        values.append((column, row[j], number))
                if not values:
                    continue  # a heading row, not a data row

                dedupe = (table.page, label, tuple(v[1] for v in values))
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                found.append(_Candidate(best_score, best_method, table, label, values, row_idx, row))

        found.sort(key=lambda c: c.key, reverse=True)
        return found

    def _to_records(
        self, file_name: str, attribute: Attribute, cand: _Candidate, checks: Optional[dict] = None
    ) -> list[Record]:
        unit = cand.table.unit
        scale = unit.scale if (unit and self.normalize_units) else 1.0
        check = (checks or {}).get((cand.table.page, cand.table.index, cand.row_idx))
        confidence = _confidence(cand.score, check.status if check else None) if self.validate else None
        out = []
        for column, raw, number in cand.values:
            out.append(
                Record(
                    file=file_name,
                    attribute=attribute.name,
                    status="found",
                    matched_label=cand.label,
                    page=cand.table.page,
                    column=column,
                    raw_value=raw,
                    value=number * scale,
                    unit="base" if scale != 1.0 else (unit.name if unit else None),
                    score=cand.score,
                    method=cand.method,
                    source=cand.table.source,
                    confidence=confidence,
                    check=(check.status if check else "unchecked") if self.validate else None,
                    check_note=check.note if check else None,
                    row_text=" | ".join(c for c in (cand.row or []) if c) if self.evidence else None,
                )
            )
        return out

    # -- many files ---------------------------------------------------------
    def extract_many(self, paths: Iterable[Union[str, Path]], workers: int = 1) -> list[Record]:
        paths = [Path(p) for p in paths]
        if workers > 1 and len(paths) > 1:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                chunks = list(pool.map(self._safe_file, paths))
        else:
            chunks = [self._safe_file(p) for p in paths]
        return [record for chunk in chunks for record in chunk]

    def _safe_file(self, path: Path) -> list[Record]:
        try:
            return self.extract_file(path)
        except Exception as exc:  # one bad PDF must not stop a batch
            return [Record(path.name, "*", "error", note=_describe_error(exc))]


def extract(
    paths: Union[str, Path, Iterable[Union[str, Path]]],
    attributes: Sequence[AttributeLike],
    *,
    workers: int = 1,
    **options,
) -> list[Record]:
    """One-call API: ``extract("report.pdf", ["Revenue", "Net profit"])``."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    return Extractor(attributes, **options).extract_many(paths, workers=workers)
