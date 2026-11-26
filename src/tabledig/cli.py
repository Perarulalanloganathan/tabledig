"""Command line interface: ``tabledig extract`` and ``tabledig inspect``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .config import coerce_attributes, load_config
from .extractor import Extractor
from .output import write_records
from .reader import read_tables


def _collect_pdfs(paths: Sequence[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found.extend(sorted(p.rglob("*.pdf")))
        elif p.is_file():
            found.append(p)
        else:
            raise FileNotFoundError(f"no such file or folder: {raw}")
    if not found:
        raise FileNotFoundError("no PDF files found")
    return found


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tabledig",
        description="Pull named attributes (row labels) out of table-style PDFs.",
    )
    parser.add_argument("--version", action="version", version=f"tabledig {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    ex = sub.add_parser("extract", help="extract attribute values from PDFs")
    ex.add_argument("paths", nargs="+", help="PDF files and/or folders")
    ex.add_argument("-a", "--attrs", help="attribute file (.yaml, .json or .csv)")
    ex.add_argument("--attr", action="append", default=[], help="attribute name (repeatable)")
    ex.add_argument("-o", "--output", help="output file (.csv, .json, .xlsx); default: CSV to stdout")
    ex.add_argument("--format", choices=["csv", "json", "xlsx"], help="override format from extension")
    ex.add_argument("--wide", action="store_true", help="one row per attribute, one column per table column")
    ex.add_argument("--min-score", type=float, help="minimum match score 0-100 (default 80)")
    ex.add_argument("--top-k", type=int, help="best-matching rows to keep per attribute (default 1)")
    ex.add_argument("--normalize-units", action="store_true", help="convert lakhs/millions/... to base units")
    ex.add_argument("--no-missing", action="store_true", help="omit attributes that were not found")
    ex.add_argument("-j", "--workers", type=int, default=1, help="parallel processes for many PDFs")

    ins = sub.add_parser("inspect", help="show the tables detected in a PDF (to pick attribute names)")
    ins.add_argument("pdf")
    ins.add_argument("--page", type=int, help="only this page (1-based)")
    ins.add_argument("--rows", type=int, default=8, help="rows to preview per table")
    return parser


def _cmd_extract(args: argparse.Namespace) -> int:
    attributes = []
    settings: dict = {}
    if args.attrs:
        config = load_config(args.attrs)
        attributes.extend(config.attributes)
        settings = config.settings
    if args.attr:
        attributes.extend(coerce_attributes(args.attr))
    if not attributes:
        print("error: give attributes with --attrs FILE and/or --attr NAME", file=sys.stderr)
        return 2

    extractor = Extractor(
        attributes,
        min_score=args.min_score if args.min_score is not None else settings.get("min_score", 80.0),
        top_k=args.top_k if args.top_k is not None else settings.get("top_k", 1),
        normalize_units=args.normalize_units or bool(settings.get("normalize_units", False)),
        include_missing=not args.no_missing,
    )
    pdfs = _collect_pdfs(args.paths)
    records = extractor.extract_many(pdfs, workers=args.workers)
    write_records(records, args.output, fmt=args.format, wide=args.wide)

    found = sum(1 for r in records if r.status == "found")
    missing = sum(1 for r in records if r.status == "not_found")
    errors = [r for r in records if r.status == "error"]
    print(
        f"{len(pdfs)} file(s): {found} value(s) found, {missing} attribute(s) not found, "
        f"{len(errors)} error(s)" + (f" -> {args.output}" if args.output else ""),
        file=sys.stderr,
    )
    for r in errors:
        print(f"  ! {r.file}: {r.note}", file=sys.stderr)
    return 1 if errors else 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    tables = read_tables(args.pdf)
    if args.page:
        tables = [t for t in tables if t.page == args.page]
    if not tables:
        print("no tables detected")
        return 1
    for t in tables:
        unit = f", unit={t.unit.name}" if t.unit else ""
        print(f"\n[page {t.page} | table {t.index} | {t.source}{unit}] {len(t.rows)} rows")
        if t.header:
            print("  header:", " | ".join(t.header))
        for row in t.rows[: args.rows]:
            print("  ", " | ".join(row))
        if len(t.rows) > args.rows:
            print(f"   ... {len(t.rows) - args.rows} more")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return _cmd_extract(args) if args.command == "extract" else _cmd_inspect(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
