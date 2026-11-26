"""Load attribute definitions from YAML, JSON or CSV."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Union

from .models import Attribute

VALID_MODES = {"fuzzy", "exact", "contains"}


@dataclass
class Config:
    attributes: list[Attribute]
    settings: dict[str, Any] = field(default_factory=dict)


def _split_aliases(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [p.strip() for p in re.split(r"[|;]", str(value)) if p.strip()]


def _one(item: Any) -> Attribute:
    if isinstance(item, Attribute):
        return item
    if isinstance(item, str):
        return Attribute(name=item.strip())
    if isinstance(item, dict):
        name = item.get("name") or item.get("attribute")
        if not name:
            raise ValueError(f"attribute entry needs a 'name': {item!r}")
        mode = str(item.get("mode") or "fuzzy").lower()
        if mode not in VALID_MODES:
            raise ValueError(f"unknown mode {mode!r} for {name!r}; use one of {sorted(VALID_MODES)}")
        min_score = item.get("min_score")
        return Attribute(
            name=str(name).strip(),
            aliases=_split_aliases(item.get("aliases")),
            mode=mode,
            min_score=float(min_score) if min_score not in (None, "") else None,
            section=str(item["section"]).strip() if item.get("section") else None,
        )
    raise TypeError(f"cannot build an attribute from {type(item).__name__}")


def parse_attribute_line(line: str) -> Optional[Attribute]:
    """Parse ``"Net profit = Profit for the year | PAT"`` (aliases after ``=``).

    Blank lines and ``#`` comments return ``None``.
    """
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    name, _, rest = text.partition("=")
    if not name.strip():
        return None
    name, _, section = name.partition("@")  # "Revenue @ Segment information"
    return Attribute(
        name=name.strip(), aliases=_split_aliases(rest), section=section.strip() or None
    )


def parse_attribute_lines(text: str) -> list[Attribute]:
    """Parse several lines with :func:`parse_attribute_line`."""
    parsed = (parse_attribute_line(line) for line in text.splitlines())
    return [a for a in parsed if a is not None]


def coerce_attributes(items: Iterable[Any]) -> list[Attribute]:
    attributes = [_one(i) for i in items]
    attributes = [a for a in attributes if a.name]
    if not attributes:
        raise ValueError("at least one attribute is required")
    return attributes


def load_config(path: Union[str, Path]) -> Config:
    """Read attributes (and optional default settings) from a file.

    YAML/JSON may be a plain list, or a mapping with ``attributes`` plus the
    optional settings ``min_score``, ``top_k`` and ``normalize_units``.
    CSV needs an ``attribute`` (or ``name``) column and may have ``aliases``
    (separated by ``|``), ``mode`` and ``min_score``.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return Config(_load_csv(path))

    text = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        import yaml

        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"unsupported attribute file type: {suffix} (use .yaml, .json or .csv)")

    if isinstance(data, dict):
        items = data.get("attributes")
        if items is None:
            raise ValueError("config mapping needs an 'attributes' list")
        settings = {k: v for k, v in data.items() if k in {"min_score", "top_k", "normalize_units"}}
        return Config(coerce_attributes(items), settings)
    return Config(coerce_attributes(data))


def load_attributes(path: Union[str, Path]) -> list[Attribute]:
    return load_config(path).attributes


def _load_csv(path: Path) -> list[Attribute]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError(f"{path} is empty")

    header = [h.strip().lower() for h in rows[0]]
    key = next((k for k in ("attribute", "name") if k in header), None)
    if key is None:  # headerless: first column holds the names
        return coerce_attributes(r[0] for r in rows if r and r[0].strip())

    entries = []
    for row in rows[1:]:
        entry = {h: (row[i].strip() if i < len(row) else "") for i, h in enumerate(header)}
        if entry.get(key):
            entries.append({**entry, "name": entry[key]})
    return coerce_attributes(entries)
