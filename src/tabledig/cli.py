"""Command line interface: ``tabledig extract`` and ``tabledig inspect``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .config import coerce_attributes, load_config, parse_attribute_lines
from .extractor import Extractor
from .fallback import SemanticResolver
from .output import write_records
from .reader import read_tables


def _collect_pdfs(paths: Sequence[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found.extend(sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() == ".pdf"))
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
    ex.add_argument(
        "--attr",
        action="append",
        default=[],
        help='attribute, optionally with aliases: "Net profit=PAT|Profit after tax" (repeatable)',
    )
    ex.add_argument("-o", "--output", help="output file (.csv, .json, .xlsx); default: CSV to stdout")
    ex.add_argument("--format", choices=["csv", "json", "xlsx"], help="override format from extension")
    ex.add_argument("--wide", action="store_true", help="one row per attribute, one column per table column")
    ex.add_argument("--min-score", type=float, help="minimum match score 0-100 (default 80)")
    ex.add_argument("--top-k", type=int, help="best-matching rows to keep per attribute (default 1)")
    ex.add_argument("--normalize-units", action="store_true", help="convert lakhs/millions/... to base units")
    ex.add_argument(
        "--pack",
        action="append",
        metavar="NAME",
        help="synonym pack: finance, healthcare, sports, government, all, or a .yaml path (repeatable)",
    )
    ex.add_argument(
        "--cache",
        metavar="DIR",
        help="cache results per file+settings in DIR; re-running a big batch skips finished files",
    )
    ex.add_argument(
        "--semantic",
        action="store_true",
        help="for attributes the matcher cannot find, try a local embedding model (tabledig[semantic])",
    )
    ex.add_argument("--memory", metavar="FILE", help="YAML file of remembered aliases to load")
    ex.add_argument(
        "--suggest",
        action="store_true",
        help="for attributes not found, print near-miss row labels to try as aliases",
    )
    ex.add_argument(
        "--remember",
        action="store_true",
        help="with --suggest and --memory: save the best suggestion per missing attribute to the memory file",
    )
    ex.add_argument(
        "--column",
        action="append",
        metavar="NAME",
        help="keep only columns whose header matches NAME, e.g. 'Q2 Budget' (repeatable)",
    )
    ex.add_argument(
        "--decimal",
        choices=["auto", "dot", "comma"],
        default="auto",
        help="decimal mark: auto-detect (default), or force dot (1,234.5) / comma (1.234,5)",
    )
    ex.add_argument(
        "--validate", action="store_true", help="check totals/subtotals add up; adds check + confidence"
    )
    ex.add_argument("--evidence", action="store_true", help="include the full source row text")
    ex.add_argument("--explain", action="store_true", help="include runner-up labels that were not chosen")
    ex.add_argument(
        "--ocr", choices=["auto", "on", "force", "off"], default="auto",
        help="OCR for scanned pages: auto (if installed, default), on (required), force (ignore any "
        "existing text layer), off",
    )
    ex.add_argument("--ocr-lang", default="eng", help="Tesseract language code(s), e.g. eng or eng+deu")
    ex.add_argument("--password", default=None, help="password for encrypted PDFs")
    ex.add_argument("--no-missing", action="store_true", help="omit attributes that were not found")
    ex.add_argument("-j", "--workers", type=int, default=1, help="parallel processes for many PDFs")

    sub.add_parser("schema", help="print the JSON Schema of the json output")

    ins = sub.add_parser("inspect", help="show the tables detected in a PDF (to pick attribute names)")
    ins.add_argument("pdf")
    ins.add_argument("--page", type=int, help="only this page (1-based)")
    ins.add_argument("--rows", type=int, default=8, help="rows to preview per table")
    ins.add_argument("--password", default=None, help="password for encrypted PDFs")
    return parser


def _cmd_extract(args: argparse.Namespace) -> int:
    attributes = []
    settings: dict = {}
    if args.attrs:
        config = load_config(args.attrs)
        attributes.extend(config.attributes)
        settings = config.settings
    if args.attr:
        attributes.extend(coerce_attributes(parse_attribute_lines("\n".join(args.attr))))
    if not attributes:
        print("error: give attributes with --attrs FILE and/or --attr NAME", file=sys.stderr)
        return 2

    extractor = Extractor(
        attributes,
        min_score=args.min_score if args.min_score is not None else settings.get("min_score", 80.0),
        top_k=args.top_k if args.top_k is not None else settings.get("top_k", 1),
        normalize_units=args.normalize_units or bool(settings.get("normalize_units", False)),
        include_missing=not args.no_missing,
        password=args.password,
        ocr=args.ocr,
        ocr_lang=args.ocr_lang,
        validate=args.validate,
        evidence=args.evidence,
        explain=args.explain,
        columns=args.column,
        packs=args.pack,
        memory=args.memory,
        cache_dir=args.cache,
        fallback=SemanticResolver() if args.semantic else None,
        decimal={"auto": None, "dot": ".", "comma": ","}[args.decimal],
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
    if args.suggest:
        _print_suggestions(extractor, pdfs, args)
    return 1 if errors else 0


def _print_suggestions(extractor: Extractor, pdfs: Sequence[Path], args: argparse.Namespace) -> None:
    learned: dict[str, list[str]] = {}
    for pdf in pdfs:
        for name, hits in extractor.suggest(pdf).items():
            shown = ", ".join(f"{label!r} ({score:.0f})" for label, score in hits)
            print(f"  ? {pdf.name}: {name!r} not found; closest rows: {shown}", file=sys.stderr)
            learned.setdefault(name, []).append(hits[0][0])
    if args.remember and args.memory and learned:
        from .aliases import save_memory

        save_memory(args.memory, {k: sorted(set(v)) for k, v in learned.items()})
        print(f"  saved {len(learned)} alias suggestion(s) to {args.memory}", file=sys.stderr)


def _cmd_inspect(args: argparse.Namespace) -> int:
    tables = read_tables(args.pdf, password=args.password)
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
        if args.command == "schema":
            import json

            from .output import result_schema

            print(json.dumps(result_schema(), indent=2))
            return 0
        return _cmd_extract(args) if args.command == "extract" else _cmd_inspect(args)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
