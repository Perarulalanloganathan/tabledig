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

# name -> (git url, pinned commit, folder holding the PDFs). All three are MIT-licensed test suites.
CORPORA = {
    "pdfplumber": ("https://github.com/jsvine/pdfplumber.git", "af4c1b149d736e876197c345a6b0378d17b3d189", "tests/pdfs"),
    "camelot": ("https://github.com/camelot-dev/camelot.git", "de07faedfecd55937ec88532d8aeb940fd025f24", "docs/benchmark"),
    "tabula": (
        "https://github.com/tabulapdf/tabula-java.git",
        "2cdf3b4fd3f7e921dca8cc6814cdd9316be40f0f",
        "src/test/resources/technology/tabula",
    ),
}
CACHE = Path.home() / ".cache" / "tabledig-eval"

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
    {"pdf": NICS, "attr": "Totals", "expect": [804006, 671330, 636903, 26597], "opts": {"min_score": 90},
     "check": "verified"},
    {"pdf": "WARN-Report-for-7-1-2015-to-03-25-2016.pdf", "attr": "Total", "column": "Notices",
     "expect": [632], "opts": {"min_score": 100}, "check": "verified"},
    {"pdf": "la-precinct-bulletin-2014-p1.pdf", "attr": "BALLOTS CAST", "expect": [327],
     "opts": {"min_score": 80}},
    {"pdf": "la-precinct-bulletin-2014-p1.pdf", "attr": "REGISTERED VOTERS", "expect": [1100],
     "opts": {"min_score": 80}},
    {"pdf": "federal-register-2020-17221.pdf", "attr": "Stabilizer wiring change",
     "expect": [3790, 10505, 766865], "opts": {"min_score": 85}},
    # ---- held-out round 1: drawn at random (seed 2026) from camelot + tabula-java; first blind run scored 3/7,
    #      the failures were then fixed, so these now act as regression cases ----
    {"corpus": "tabula", "group": "heldout round 1", "pdf": "icdar2013-dataset/competition-dataset-us/us-033.pdf",
     "attr": "12-19", "expect": [9795497, 9208607, 2191327, 2218406, 1180160], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 1", "pdf": "icdar2013-dataset/competition-dataset-us/us-033.pdf",
     "attr": "6-11", "expect": [7808033, 7401349, 1770525, 1732954, 998192], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 1", "pdf": "icdar2013-dataset/competition-dataset-us/us-002.pdf",
     "attr": "Total", "expect": [44.8, 33200, 23.2, 10.3, 27.0, 20.1, 19.4], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 1", "pdf": "spanning_cells.pdf", "attr": "Server closets",
     "expect": [1505, 1580, 1643, 1673, 1689], "opts": {"min_score": 90}},
    {"corpus": "camelot", "group": "heldout round 1", "pdf": "stream/superscript/superscript.pdf",
     "attr": "Assam", "expect": [12.69, 10.02, 0, 2.41, 0.26, 0.08, 0, -0.06, 0.01, 0.24],
     "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 1", "pdf": "puertos1.pdf", "attr": "MOA pesquero",
     "expect": [232, 0.9, 241, 0.9, 267, 0.9], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 1", "pdf": "argentina_diputados_voting_record.pdf",
     "attr": "Presentes", "expect": [217, 0, 217], "opts": {"min_score": 90}},
    # ---- held-out round 2: fresh draw, expected values written down BEFORE running; first run scored 7/9 ----
    {"corpus": "camelot", "group": "heldout round 2", "pdf": "stream/missing_values/missing_values.pdf",
     "attr": "Children (6-59 months) having anaemia", "expect": [68.5, 71.9], "opts": {"min_score": 90}},
    {"corpus": "camelot", "group": "heldout round 2", "pdf": "stream/missing_values/missing_values.pdf",
     "attr": "Disease of respiratory system", "expect": [11.7, 15.0], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 2", "pdf": "12s0324.pdf", "attr": "Robbery",
     "expect": [102.1, 25.5, 76.6, 90.0, 22.9, 67.1, 12.1, 2.5, 9.5], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 2", "pdf": "12s0324.pdf", "attr": "Forcible rape",
     "expect": [17.5, 2.6, 14.9, 17.2, 2.5, 14.7, 0, 0, 0], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 2", "pdf": "spreadsheet_no_bounding_frame.pdf",
     "attr": "COTTON", "expect": [1393.4, 886.7, 894.9, -35.8, -498.5], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 2", "pdf": "spreadsheet_no_bounding_frame.pdf",
     "attr": "TOTAL PEANUT", "expect": [93.9, 100.6, 100.2, 6.7, 6.3], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 2", "pdf": "eu-002.pdf", "attr": "Social skills and abilities",
     "expect": [0.3416, 0.3369, 0.4303], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 2", "pdf": "eu-002.pdf", "attr": "Self competence",
     "expect": [0.3791, 0.3320, 0.4617], "opts": {"min_score": 90}},
    {"corpus": "tabula", "group": "heldout round 2", "pdf": "20.pdf", "attr": "Saar Creek @ Vye Road",
     "expect": [5429665, 559270], "opts": {"min_score": 90}},
]


def ensure_corpora(cache: Path) -> dict[str, Path]:
    """Clone each corpus at its pinned commit (shallow) and return the folder holding its PDFs."""
    folders = {}
    for name, (url, commit, subdir) in CORPORA.items():
        repo = cache / name
        if not (repo / ".git").exists():
            repo.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)
        have = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", commit], capture_output=True)
        if have.returncode != 0:
            subprocess.run(["git", "-C", str(repo), "fetch", "-q", "--depth", "1", "origin", commit], check=True)
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-f", commit], check=True)
        folders[name] = repo / subdir
    return folders


def run_case(case: dict, folders: dict[str, Path]) -> tuple[bool, list[float]]:
    opts = dict(case.get("opts", {}), validate="check" in case)
    pdf = folders[case.get("corpus", "pdfplumber")] / case["pdf"]
    records = extract(str(pdf), [case["attr"]], **opts)
    found = [r for r in records if r.status == "found"]
    col = case.get("column")
    if col:
        found = [r for r in found if r.column and col in r.column]
    values = [r.value for r in found]
    want = case["expect"]
    ok = len(values) >= len(want) and all(abs(v - w) < 1e-6 for v, w in zip(values, want))
    if ok and "check" in case:
        ok = bool(found) and all(r.check == case["check"] for r in found)  # validation verdict must agree
    return ok, values[: len(want)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=CACHE, help="where corpora are cloned")
    ap.add_argument("--min-pass", type=float, default=0.85, help="minimum pass rate (0-1)")
    args = ap.parse_args()
    folders = ensure_corpora(args.cache)

    passed = 0
    by_group: dict[str, list[int]] = {}
    for case in CASES:
        ok, got = run_case(case, folders)
        passed += ok
        group = case.get("group", "tuned")
        by_group.setdefault(group, [0, 0])
        by_group[group][0] += ok
        by_group[group][1] += 1
        note = f"  [known limit: {case['known_limit']}]" if case.get("known_limit") else ""
        print(f"{'PASS' if ok else 'FAIL'}  {case['pdf'][:34]:34} {case['attr'][:30]:30} "
              f"expected={case['expect'][:4]} got={got[:4]}{note}")
    rate = passed / len(CASES)
    for group, (ok, total) in by_group.items():
        print(f"  {group:<22} {ok}/{total}")
    print(f"\n{passed}/{len(CASES)} cases passed ({rate:.0%}) on real public PDFs")
    return 0 if rate >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())
