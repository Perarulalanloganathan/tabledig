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

DEFAULT_SKIP_COLUMNS = re.compile(
    r"^(?:notes?|note\s*no\.?|ref\.?|sl\.?\s*no\.?|s\.?\s*no\.?|sr\.?\s*no\.?)$", re.IGNORECASE
)
_HAS_LETTERS = re.compile(r"[A-Za-z]")

AttributeLike = Union[str, dict, Attribute]


@dataclass
class _Candidate:
    score: float
    method: str
    table: Table
    label: str
    values: list[tuple[str, str, float]]  # (column, raw, number)

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
    """

    def __init__(
        self,
        attributes: Sequence[AttributeLike],
        *,
        min_score: float = 80.0,
        top_k: int = 1,
        normalize_units: bool = False,
        include_missing: bool = True,
        skip_columns: re.Pattern = DEFAULT_SKIP_COLUMNS,
    ) -> None:
        self.attributes = coerce_attributes(attributes)
        self.min_score = min_score
        self.top_k = max(1, top_k)
        self.normalize_units = normalize_units
        self.include_missing = include_missing
        self.skip_columns = skip_columns

    # -- single file --------------------------------------------------------
    def extract_file(self, path: Union[str, Path]) -> list[Record]:
        tables = read_tables(path)
        return self.extract_tables(tables, Path(path).name)

    def extract_tables(self, tables: Iterable[Table], file_name: str = "") -> list[Record]:
        tables = list(tables)
        records: list[Record] = []
        for attribute in self.attributes:
            candidates = self._candidates(attribute, tables)
            if not candidates:
                if self.include_missing:
                    records.append(Record(file_name, attribute.name, "not_found"))
                continue
            for cand in candidates[: self.top_k]:
                records.extend(self._to_records(file_name, attribute, cand))
        return records

    # -- internals ----------------------------------------------------------
    def _candidates(self, attribute: Attribute, tables: list[Table]) -> list[_Candidate]:
        threshold = attribute.min_score if attribute.min_score is not None else self.min_score
        found: list[_Candidate] = []
        seen: set[tuple] = set()

        for table in tables:
            for row in table.rows:
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
                    number = parse_number(row[j])
                    if number is not None:
                        values.append((column, row[j], number))
                if not values:
                    continue  # a heading row, not a data row

                dedupe = (table.page, label, tuple(v[1] for v in values))
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                found.append(_Candidate(best_score, best_method, table, label, values))

        found.sort(key=lambda c: c.key, reverse=True)
        return found

    def _to_records(self, file_name: str, attribute: Attribute, cand: _Candidate) -> list[Record]:
        unit = cand.table.unit
        scale = unit.scale if (unit and self.normalize_units) else 1.0
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
            return [Record(path.name, "*", "error", note=f"{type(exc).__name__}: {exc}")]


def extract(
    paths: Union[str, Path, Iterable[Union[str, Path]]],
    attributes: Sequence[AttributeLike],
    *,
    workers: int = 1,
    **options,
) -> list[Record]:
    """One-call API: ``extract("report.pdf", ["Total revenue", "Net profit"])``."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    return Extractor(attributes, **options).extract_many(paths, workers=workers)
