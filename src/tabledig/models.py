"""Plain data containers shared across the package."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Unit:
    """A unit/scale declared in a document, e.g. ``thousands`` -> 1_000."""

    name: str
    scale: float


@dataclass
class Table:
    """A table found in a PDF page.

    ``header`` is aligned with the cells of each row (it may be empty when the
    table has no recognisable header row).
    """

    page: int
    index: int
    header: list[str]
    rows: list[list[str]]
    source: str  # "ruled" (drawn grid) or "text" (whitespace-aligned lines)
    unit: Optional[Unit] = None
    sections: list[str] = field(default_factory=list)  # heading above each row (may be empty)


@dataclass
class Attribute:
    """Something to look up: a row label, optional aliases and match mode."""

    name: str
    aliases: list[str] = field(default_factory=list)
    mode: str = "fuzzy"  # "fuzzy" | "exact" | "contains"
    min_score: Optional[float] = None
    section: Optional[str] = None  # only rows under a heading matching this text

    @property
    def names(self) -> list[str]:
        return [self.name, *self.aliases]


@dataclass
class Record:
    """One extracted value (long format: one record per attribute x column)."""

    file: str
    attribute: str
    status: str  # "found" | "not_found" | "error"
    matched_label: Optional[str] = None
    page: Optional[int] = None
    column: Optional[str] = None
    raw_value: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    score: Optional[float] = None
    method: Optional[str] = None
    source: Optional[str] = None
    note: Optional[str] = None
    # optional extras (only written when something sets them)
    confidence: Optional[float] = None  # heuristic 0-1: match score, adjusted by validation
    check: Optional[str] = None  # "verified" | "mismatch" | "unchecked" (validate=True)
    check_note: Optional[str] = None
    row_text: Optional[str] = None  # the whole source row, for evidence (evidence=True)
    alternatives: Optional[str] = None  # runner-up labels (explain=True)

    FIELDS = (
        "file",
        "attribute",
        "status",
        "matched_label",
        "page",
        "column",
        "raw_value",
        "value",
        "unit",
        "score",
        "method",
        "source",
        "note",
    )
    EXTRA_FIELDS = ("confidence", "check", "check_note", "row_text", "alternatives")

    @classmethod
    def fields_for(cls, records) -> list[str]:
        """Base fields plus any extra field that at least one record actually uses."""
        extras = [f for f in cls.EXTRA_FIELDS if any(getattr(r, f) is not None for r in records)]
        return [*cls.FIELDS, *extras]

    def as_dict(self, fields=None) -> dict:
        return {name: getattr(self, name) for name in (fields or self.FIELDS)}
