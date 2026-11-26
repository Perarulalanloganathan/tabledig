"""Core engine: look attributes up in the tables of one or many PDFs."""
from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

from . import __version__
from .aliases import apply_memory, apply_packs, load_memory, suggest_aliases
from .config import coerce_attributes
from .matcher import score_label
from .models import Attribute, Record, Table
from .normalize import is_labelish, parse_number
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
        if is_labelish(cell) and parse_number(cell) is None:
            return cell, i
    return None, -1


def _describe_error(exc: Exception) -> str:
    text = str(exc).strip()
    name = type(exc).__name__
    if "password" in name.lower() or "password" in text.lower() or (name == "PdfminerException" and not text):
        return f"{name}: PDF is password-protected or encrypted; pass password=... (CLI: --password)"
    return f"{name}: {text}" if text else name


def _confidence(score: float, check_status: Optional[str], source: Optional[str] = None) -> float:
    """Heuristic 0-1 confidence: the match score, nudged by what validation found."""
    base = score / 100.0
    if source in ("ocr", "kv"):
        base *= 0.9  # OCR can misread digits; key-value rows have no table structure to confirm them
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
    ocr:
        ``"auto"`` (default) reads scanned pages with OCR if the ``ocr`` extra and Tesseract are
        installed; ``"on"`` requires it; ``"force"`` re-reads image pages even when they already have a text
        layer (useful when a scanner's built-in OCR is poor); ``"off"`` never uses it.
    ocr_lang:
        Tesseract language code(s), e.g. ``"eng"`` or ``"eng+deu"``.
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
        ocr: object = "auto",
        ocr_lang: str = "eng",
        validate: bool = False,
        evidence: bool = False,
        explain: bool = False,
        skip_columns: re.Pattern = DEFAULT_SKIP_COLUMNS,
        columns: Optional[Sequence[str]] = None,
        packs: Optional[Sequence[str]] = None,
        memory: Optional[Union[str, Path]] = None,
        cache_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.attributes = coerce_attributes(attributes)
        if packs:
            self.attributes = apply_packs(self.attributes, packs)
        if memory:
            self.attributes = apply_memory(self.attributes, load_memory(memory))
        self.min_score = min_score
        self.top_k = max(1, top_k)
        self.normalize_units = normalize_units
        self.include_missing = include_missing
        self.decimal = decimal
        self.password = password
        self.ocr = ocr
        self.ocr_lang = ocr_lang
        self.validate = validate
        self.evidence = evidence
        self.explain = explain
        self.skip_columns = skip_columns
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.columns = [columns] if isinstance(columns, str) else list(columns or [])
        self._latest = [c.lower() for c in self.columns] == ["latest"]

    def suggest(self, path: Union[str, Path]) -> dict[str, list[tuple[str, float]]]:
        """For attributes not found in ``path``: near-miss row labels worth trying as aliases."""
        found = {r.attribute for r in self.extract_file(path) if r.status == "found"}
        tables = read_tables(path, password=self.password, ocr=self.ocr, ocr_lang=self.ocr_lang)
        out = {}
        for attr in self.attributes:
            if attr.name not in found:
                hits = suggest_aliases(tables, attr, ceiling=attr.min_score or self.min_score)
                if hits:
                    out[attr.name] = hits
        return out

    # -- single file --------------------------------------------------------
    def extract_file(self, path: Union[str, Path]) -> list[Record]:
        report: list[str] = []
        tables = read_tables(
            path,
            password=self.password,
            ocr=self.ocr,
            ocr_lang=self.ocr_lang,
            report=report,
            key_values=True,
        )
        records = self.extract_tables(tables, Path(path).name)
        if report:
            for record in records:
                if record.status == "not_found" and not record.note:
                    record.note = "; ".join(report[:2])
        return records

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
        """Best-first candidates; key-value rows are consulted only when real tables have no match."""
        real = [t for t in tables if t.source != "kv"]
        found = self._scan(attribute, real)
        if not found:
            found = self._scan(attribute, [t for t in tables if t.source == "kv"])
        return found

    def _scan(self, attribute: Attribute, tables: list[Table]) -> list[_Candidate]:
        threshold = attribute.min_score if attribute.min_score is not None else self.min_score
        found: list[_Candidate] = []
        seen: set[tuple] = set()

        for table in tables:
            for row_idx, row in enumerate(table.rows):
                label, label_idx = _split_row(row)
                if label is None:
                    continue

                if attribute.section and not self._in_section(table, row_idx, attribute.section):
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
                    if self.columns and not self._latest and not self._column_wanted(column):
                        continue
                    number = parse_number(row[j], self.decimal)
                    if number is not None:
                        values.append((column, row[j], number))
                if self._latest:
                    values = _latest_only(values)
                if not values:
                    continue  # a heading row, not a data row

                dedupe = (table.page, label, tuple(v[1] for v in values))
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                found.append(_Candidate(best_score, best_method, table, label, values, row_idx, row))

        found.sort(key=lambda c: c.key, reverse=True)
        return found

    @staticmethod
    def _in_section(table: Table, row_idx: int, section: str) -> bool:
        if row_idx >= len(table.sections):
            return False
        heading = table.sections[row_idx]
        if not heading:
            return False
        return score_label(section, heading, "contains")[0] >= 90 or score_label(section, heading)[0] >= 80

    def _column_wanted(self, column: str) -> bool:
        """True if ``column`` matches one of the requested column names (word-wise, or fuzzy)."""
        for wanted in self.columns:
            if score_label(wanted, column, "contains")[0] >= 90 or score_label(wanted, column)[0] >= 85:
                return True
        return False

    def _to_records(
        self, file_name: str, attribute: Attribute, cand: _Candidate, checks: Optional[dict] = None
    ) -> list[Record]:
        unit = cand.table.unit
        scale = unit.scale if (unit and self.normalize_units) else 1.0
        check = (checks or {}).get((cand.table.page, cand.table.index, cand.row_idx))
        confidence = None
        if self.validate:
            confidence = _confidence(cand.score, check.status if check else None, cand.table.source)
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
        cached = self._cache_load(path)
        if cached is not None:
            return cached
        try:
            records = self.extract_file(path)
        except Exception as exc:  # one bad PDF must not stop a batch
            return [Record(path.name, "*", "error", note=_describe_error(exc))]
        self._cache_store(path, records)
        return records

    # -- resumable batches: results cached per (file content, settings) ----------
    def _cache_key(self, path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        settings = (self.attributes, self.min_score, self.top_k, self.normalize_units, self.include_missing,
                    self.decimal, self.ocr, self.ocr_lang, self.validate, self.evidence, self.explain,
                    self.columns, __version__)
        h.update(repr(settings).encode())
        return h.hexdigest()

    def _cache_load(self, path: Path) -> Optional[list[Record]]:
        if not self.cache_dir:
            return None
        entry = self.cache_dir / f"{self._cache_key(path)}.json"
        try:
            rows = json.loads(entry.read_text(encoding="utf-8"))
            return [Record(**{**r, "file": path.name}) for r in rows]
        except (OSError, ValueError, TypeError):
            return None

    def _cache_store(self, path: Path, records: list[Record]) -> None:
        if not self.cache_dir:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        entry = self.cache_dir / f"{self._cache_key(path)}.json"
        tmp = entry.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(r) for r in records]), encoding="utf-8")
        tmp.replace(entry)  # atomic: an interrupted run never leaves a half-written entry


_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?:\s*[-/\u2013]\s*(\d{2}))?(?!\d)")


def _period_key(column: str) -> Optional[int]:
    """Latest year named in a column header (``2023-24`` counts as 2024), or None."""
    best = None
    for m in _YEAR.finditer(column):
        year = int(m.group(1))
        if m.group(2):
            year = year // 100 * 100 + int(m.group(2))
        best = year if best is None else max(best, year)
    return best


def _latest_only(values: list) -> list:
    """Keep the values in the column(s) naming the most recent period; all if none is dated."""
    keys = [_period_key(v[0]) for v in values]
    dated = [k for k in keys if k is not None]
    if not dated:
        return values
    top = max(dated)
    return [v for v, k in zip(values, keys) if k == top]


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
