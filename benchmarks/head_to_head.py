"""tabledig vs. the obvious alternatives on the same real documents and the same expected values.

Baselines are what someone would write by hand with a table library: extract the tables, find the row whose
first non-empty cell equals the attribute (ignoring case and spacing), and read the numbers after it.
They are given tabledig's own number parser, so they are never penalised for "1,234" or "(5)".

  pdfplumber        page.extract_tables(), then the lookup
  pdfplumber+text   the same, then a regex over page text lines when no table row matches
  camelot           lattice, then stream, over all pages, then the lookup (needs: pip install camelot-py)
  tabledig          the library itself, default options except min_score as in the case list

Cases with a column filter are left out (a lookup cannot express them). Pass = the returned values start
with the expected values, exactly as in real_eval.py.

    python benchmarks/head_to_head.py
"""
from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pdfplumber  # noqa: E402
from real_eval import CACHE, CASES, ensure_corpora  # noqa: E402

from tabledig import extract  # noqa: E402
from tabledig.normalize import parse_number  # noqa: E402


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def _row_lookup(rows, attr):
    for row in rows:
        cells = [c for c in row if c not in (None, "")]
        if cells and _key(cells[0]) == _key(attr):
            nums = [parse_number(c) for c in cells[1:]]
            nums = [n for n in nums if n is not None]
            if nums:
                return nums
    return None


@lru_cache(maxsize=None)
def _plumber_tables(pdf: str):
    with pdfplumber.open(pdf) as doc:
        return [row for page in doc.pages for t in (page.extract_tables() or []) for row in t]


@lru_cache(maxsize=None)
def _plumber_lines(pdf: str):
    with pdfplumber.open(pdf) as doc:
        return [ln for page in doc.pages for ln in (page.extract_text() or "").splitlines()]


@lru_cache(maxsize=None)
def _camelot_rows(pdf: str):
    import camelot

    rows = []
    for flavor in ("lattice", "stream"):
        try:
            for t in camelot.read_pdf(pdf, pages="all", flavor=flavor):
                rows += t.df.values.tolist()
        except Exception:
            pass
    return rows


def pdfplumber_only(pdf, attr):
    return _row_lookup(_plumber_tables(pdf), attr)


def pdfplumber_text(pdf, attr):
    found = _row_lookup(_plumber_tables(pdf), attr)
    if found:
        return found
    for line in _plumber_lines(pdf):
        if _key(line).startswith(_key(attr) + " "):
            nums = [parse_number(tok) for tok in line[len(attr):].split()]
            nums = [n for n in nums if n is not None]
            if nums:
                return nums
    return None


def camelot_lookup(pdf, attr):
    return _row_lookup(_camelot_rows(pdf), attr)


def tabledig_lookup(pdf, attr, opts):
    rows = [r for r in extract(pdf, [attr], **opts) if r.status == "found"]
    return [r.value for r in rows] or None


def passes(values, want):
    return bool(values) and len(values) >= len(want) and all(abs(v - w) < 1e-6 for v, w in zip(values, want))


def main() -> None:
    try:
        import camelot  # noqa: F401
        have_camelot = True
    except ImportError:
        have_camelot = False
    folders = ensure_corpora(CACHE)
    cases = [c for c in CASES if not c.get("column")]
    tools = {"pdfplumber": pdfplumber_only, "pdfplumber+text": pdfplumber_text}
    if have_camelot:
        tools["camelot"] = camelot_lookup
    names = [*tools, "tabledig"]
    score: dict[str, dict[str, int]] = {}
    total: dict[str, int] = {}
    for case in cases:
        group = "tuned" if case.get("group", "tuned") == "tuned" else "held-out"
        total[group] = total.get(group, 0) + 1
        pdf = str(folders[case.get("corpus", "pdfplumber")] / case["pdf"])
        row = score.setdefault(group, {n: 0 for n in names})
        for name, fn in tools.items():
            try:
                row[name] += passes(fn(pdf, case["attr"]), case["expect"])
            except Exception:
                pass
        row["tabledig"] += passes(tabledig_lookup(pdf, case["attr"], case.get("opts", {})), case["expect"])
    print(f"{len(cases)} real-document cases (column-filter cases excluded)\n")
    print(f"{'tool':18}" + "".join(f"{g + f' (n={total[g]})':>22}" for g in total))
    for name in names:
        print(f"{name:18}" + "".join(f"{score[g][name]:>14}/{total[g]:<3} {score[g][name] / total[g]:>4.0%}" for g in total))
    print("\n'tuned' cases were looked at while building tabledig; 'held-out' ones were written down before the first run.")
    if not have_camelot:
        print("(camelot not installed; pip install camelot-py to include it)")


if __name__ == "__main__":
    main()
