"""Write results as CSV, JSON, Excel, or a wide pivot table."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Optional, Union

from .models import Record

WIDE_KEYS = ("file", "attribute", "matched_label", "page", "unit", "score")


def records_to_wide(records: Iterable[Record]) -> tuple[list[str], list[dict]]:
    """Pivot to one row per (file, attribute) with one column per table column."""
    rows: dict[tuple, dict] = {}
    columns: list[str] = []
    for r in records:
        key = (r.file, r.attribute, r.matched_label, r.page)
        row = rows.setdefault(
            key,
            {
                "file": r.file,
                "attribute": r.attribute,
                "matched_label": r.matched_label,
                "page": r.page,
                "unit": r.unit,
                "score": r.score,
                "status": r.status,
            },
        )
        if r.column is not None:
            if r.column not in columns:
                columns.append(r.column)
            row[r.column] = r.value
        elif r.note:
            row["note"] = r.note
    fieldnames = [*WIDE_KEYS, "status", *columns]
    if any("note" in row for row in rows.values()):
        fieldnames.append("note")
    return fieldnames, list(rows.values())


def to_dataframe(records: Iterable[Record], wide: bool = False):
    """Return a pandas DataFrame (pandas is an optional dependency)."""
    import pandas as pd

    if wide:
        fieldnames, rows = records_to_wide(records)
        return pd.DataFrame(rows, columns=fieldnames)
    return pd.DataFrame([r.as_dict() for r in records], columns=list(Record.FIELDS))


def write_csv(records: Iterable[Record], path: Optional[Union[str, Path]], wide: bool = False) -> None:
    import sys

    records = list(records)
    if wide:
        fieldnames, rows = records_to_wide(records)
    else:
        fieldnames, rows = list(Record.FIELDS), [r.as_dict() for r in records]

    handle = open(path, "w", newline="", encoding="utf-8") if path else sys.stdout
    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if path:
            handle.close()


def write_json(records: Iterable[Record], path: Optional[Union[str, Path]]) -> None:
    import sys

    payload = json.dumps([r.as_dict() for r in records], indent=2, ensure_ascii=False)
    if path:
        Path(path).write_text(payload + "\n", encoding="utf-8")
    else:
        sys.stdout.write(payload + "\n")


def write_excel(records: Iterable[Record], path: Union[str, Path], wide: bool = False) -> None:
    to_dataframe(records, wide=wide).to_excel(path, index=False)


def write_records(
    records: Iterable[Record],
    path: Optional[Union[str, Path]],
    fmt: Optional[str] = None,
    wide: bool = False,
) -> None:
    """Pick the format from ``fmt`` or the file extension (default CSV)."""
    records = list(records)
    fmt = (fmt or (Path(path).suffix.lstrip(".").lower() if path else "csv")) or "csv"
    if fmt == "json":
        write_json(records, path)
    elif fmt in {"xlsx", "excel"}:
        if not path:
            raise ValueError("Excel output needs an output file path")
        write_excel(records, path, wide=wide)
    elif fmt == "csv":
        write_csv(records, path, wide=wide)
    else:
        raise ValueError(f"unsupported output format: {fmt!r}")
