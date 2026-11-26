"""Synonym packs, alias suggestions and a small alias memory file.

A *pack* is a YAML file mapping a canonical label to other wordings. Packs only add aliases to the
attributes you asked for; they never add attributes. Matching stays lexical and explainable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence, Union

import yaml

from .matcher import normalize_label, score_label
from .models import Attribute, Table
from .normalize import parse_number

PACK_DIR = Path(__file__).parent / "packs"


def available_packs() -> list[str]:
    return sorted(p.stem for p in PACK_DIR.glob("*.yaml"))


def load_pack(name_or_path: Union[str, Path]) -> dict[str, list[str]]:
    """Load a built-in pack by name (``finance``) or a user pack by file path."""
    path = Path(name_or_path)
    if not path.suffix:
        path = PACK_DIR / f"{name_or_path}.yaml"
        if not path.exists():
            raise ValueError(f"unknown pack {name_or_path!r}; built-in packs: {', '.join(available_packs())}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: a pack must map labels to lists of aliases")
    return {str(k): [str(a) for a in (v or [])] for k, v in data.items()}


def apply_packs(attributes: Sequence[Attribute], packs: Iterable[Union[str, Path]]) -> list[Attribute]:
    """Add pack aliases to every attribute whose name (or alias) is a pack entry's wording."""
    entries: list[tuple[str, list[str]]] = []
    for pack in packs:
        names = available_packs() if str(pack) == "all" else [pack]
        for name in names:
            entries.extend(load_pack(name).items())
    out = []
    for attr in attributes:
        known = {normalize_label(n) for n in attr.names}
        aliases = list(attr.aliases)
        for canonical, others in entries:
            group = [canonical, *others]
            if known & {normalize_label(g) for g in group}:
                for g in group:
                    if normalize_label(g) not in known:
                        aliases.append(g)
                        known.add(normalize_label(g))
        out.append(
            Attribute(attr.name, aliases, attr.mode, attr.min_score, attr.section)
        )
    return out


def load_memory(path: Union[str, Path]) -> dict[str, list[str]]:
    p = Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {str(k): [str(a) for a in (v or [])] for k, v in data.items()}


def apply_memory(attributes: Sequence[Attribute], memory: dict[str, list[str]]) -> list[Attribute]:
    """Add aliases remembered from earlier runs (keyed by attribute name)."""
    by_name = {normalize_label(k): v for k, v in memory.items()}
    out = []
    for attr in attributes:
        extra = [a for a in by_name.get(normalize_label(attr.name), []) if a not in attr.aliases]
        out.append(Attribute(attr.name, [*attr.aliases, *extra], attr.mode, attr.min_score, attr.section))
    return out


def save_memory(path: Union[str, Path], additions: dict[str, Sequence[str]]) -> None:
    memory = load_memory(path)
    for name, aliases in additions.items():
        current = memory.setdefault(name, [])
        current.extend(a for a in aliases if a not in current)
    Path(path).write_text(yaml.safe_dump(memory, allow_unicode=True, sort_keys=True), encoding="utf-8")


def suggest_aliases(
    tables: Sequence[Table],
    attribute: Attribute,
    *,
    floor: float = 35.0,
    ceiling: float = 80.0,
    limit: int = 3,
) -> list[tuple[str, float]]:
    """Row labels that nearly matched ``attribute`` (score between ``floor`` and ``ceiling``).

    Only rows with a number are offered. Use them as candidate aliases; a person decides.
    """
    best: dict[str, float] = {}
    for table in tables:
        if table.source == "kv":
            continue
        for row in table.rows:
            label = next((c for c in row if c and parse_number(c) is None), None)
            if not label or not any(parse_number(c) is not None for c in row):
                continue
            score = max(score_label(n, label)[0] for n in attribute.names)
            if floor <= score < ceiling:
                best[label] = max(score, best.get(label, 0.0))
    return sorted(best.items(), key=lambda kv: -kv[1])[:limit]

