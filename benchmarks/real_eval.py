"""Evaluate tabledig on REAL public PDFs with hand-checked expected values.

The PDFs come from the MIT-licensed test suite of jsvine/pdfplumber, cloned at a pinned commit into a
cache folder (they are not stored in this repository). Every expected value below was read off the
printed page (cross-checked with ``pdftotext -layout``), not produced by tabledig.

    python benchmarks/real_eval.py            # prints a per-case table, exits 1 if score < --min-pass

Cases marked ``known_limit`` document layouts tabledig cannot handle yet; they stay in the score so
the number is honest.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from tabledig import extract

REPO = "https://github.com/jsvine/pdfplumber.git"
COMMIT = "af4c1b149d736e876197c345a6b0378d17b3d189"
CACHE = Path.home() / ".cache" / "tabledig-eval" / "pdfplumber"

NICS = "nics-background-checks-2015-11.pdf"
# first six numeric columns: Permit, Handgun, Long Gun, *Other, **Multiple, Admin
NICS_CASES = {
    "Alabama": [18870, 23022, 22650, 859, 1178, 0],
    "Texas": [21550, 56941, 51670, 2532, 3048, 0],
    "California": [98452, 41181, 35007, 4559, 0, 0],
    "District of Columbia": [8, 54, 2, 0, 0, 0],
    "Guam": [0, 100, 55, 12, 3, 0],
}

# (pdf, attribute, expected values (prefix), optional column filter, extractor options, known_limit)
CASES: list[dict] = [
    *[
        {"pdf": NICS, "attr": name, "expect": vals, "opts": {"min_score": 90}}
        for name, vals in NICS_CASES.items()
    ],
    {"pdf": "WARN-Report-for-7-1-2015-to-03-25-2016.pdf", "attr": "Boeing Company",
     "column": "No. Of", "expect": [56, 65, 113, 66], "opts": {"min_score": 95, "top_k": 4}},
    {"pdf": "WARN-Report-for-7-1-2015-to-03-25-2016.pdf", "attr": "Maxim Integrated Product",
     "column": "No. Of", "expect": [150, 20, 11], "opts": {"min_score": 95, "top_k": 4}},
    {"pdf": "issue-336-example.pdf", "attr": "高速公路", "column": "用地指标基准值",
     "expect": [2.5], "opts": {"min_score": 80}},
    {"pdf": "issue-336-example.pdf", "attr": "一级公路", "column": "用地指标基准值",
     "expect": [1.3333], "opts": {"min_score": 80}},
    {"pdf": "issue-67-example.pdf", "attr": "应付股利", "expect": [40017.86, 40017.86],
     "opts": {"min_score": 90}},
    {"pdf": "issue-67-example.pdf", "attr": "其他应付款", "expect": [365680984.80, 365420737.42],
     "opts": {"min_score": 90}},
    {"pdf": "issue-67-example.pdf", "attr": "应付职工薪酬", "expect": [2402389.91, 3022542.03],
     "opts": {"min_score": 90}},
    {"pdf": "pr-138-example.pdf", "attr": "Standard Variable Rate", "expect": [5.37, 5.51, 4.87, 5.27],
     "opts": {"min_score": 90}},
    {"pdf": "pr-138-example.pdf", "attr": "1 Year Fixed Rate", "expect": [4.04, 5.38, 3.89, 5.18],
     "opts": {"min_score": 90}},
    {"pdf": "issue-90-example.pdf", "attr": "Ekaterina PUSHKASH / Jonathan GUERREIRO",
     "expect": [49.88], "opts": {"min_score": 90}},
    {"pdf": "la-precinct-bulletin-2014-p1.pdf", "attr": "BALLOTS CAST", "expect": [327],
     "opts": {"min_score": 80}, "known_limit": "number printed before its label"},
    {"pdf": "federal-register-2020-17221.pdf", "attr": "Stabilizer wiring change",
     "expect": [766865], "opts": {"min_score": 85},
     "known_limit": "newspaper-style multi-column layout"},
]


def ensure_corpus(cache: Path) -> Path:
    if not (cache / ".git").exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", REPO, str(cache)], check=True)
    subprocess.run(["git", "-C", str(cache), "checkout", "-q", COMMIT], check=True)
    return cache / "tests" / "pdfs"


def run_case(case: dict, pdf_dir: Path) -> tuple[bool, list[float]]:
    records = extract(str(pdf_dir / case["pdf"]), [case["attr"]], **case.get("opts", {}))
    found = [r for r in records if r.status == "found"]
    col = case.get("column")
    if col:
        found = [r for r in found if r.column and col in r.column]
    values = [r.value for r in found]
    want = case["expect"]
    ok = len(values) >= len(want) and all(abs(v - w) < 1e-6 for v, w in zip(values, want))
    return ok, values[: len(want)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=CACHE)
    ap.add_argument("--min-pass", type=float, default=0.85, help="minimum pass rate (0-1)")
    args = ap.parse_args()
    pdf_dir = ensure_corpus(args.cache)

    passed = 0
    for case in CASES:
        ok, got = run_case(case, pdf_dir)
        passed += ok
        note = f"  [known limit: {case['known_limit']}]" if case.get("known_limit") else ""
        print(f"{'PASS' if ok else 'FAIL'}  {case['pdf'][:34]:34} {case['attr'][:30]:30} "
              f"expected={case['expect'][:4]} got={got[:4]}{note}")
    rate = passed / len(CASES)
    print(f"\n{passed}/{len(CASES)} cases passed ({rate:.0%}) on real public PDFs")
    return 0 if rate >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())
