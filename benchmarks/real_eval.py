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

# ---- held-out round 3: three fresh documents, expected values read from `pdftotext -layout` BEFORE running ----
_US018 = "icdar2013-dataset/competition-dataset-us/us-018.pdf"  # graduates by state, ten school years
_R3 = [
    ("tabula", _US018, "Connecticut", [34573, 35515, 36222, 37541, 38419, 34968]),
    ("tabula", _US018, "Maine", [13278, 13077, 12950, 13151, 14350, 14093]),
    ("tabula", _US018, "Georgia", [68550, 70834, 73498, 77829, 83505, 88003]),
    ("tabula", _US018, "Alabama", [36464, 37453, 37918, 38912, 41346, 42082]),
    ("tabula", _US018, "Indiana", [56008, 55444, 57920, 59887, 61901, 63663]),
    ("tabula", _US018, "Wisconsin", [62784, 63229, 63003, 63968, 65183, 65410]),
    ("tabula", _US018, "New Jersey", [83826, 86502, 90049, 93013, 94994, 95085]),
    ("tabula", _US018, "Delaware", [6951, 6934, 7275, 7205, 7388, 7839]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Assam", [34.98, 34.95, 23.36, 24.24, 18.92, 16.93]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Bihar", [19.79, 20.91, 24.16, 23.38, 28.62, 25.07]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Chandigarh", [394.13, 114.59, 75.55, 42.16, 40.28, 17.10]),
    ("camelot", "stream/population_growth/population_growth.pdf", "NCT of Delhi", [52.44, 52.93, 53.00, 51.45, 47.02, 20.96]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Daman and Diu", [-24.56, 70.85, 26.07, 28.62, 55.73, 53.54]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Chhattisgarh", [22.77, 27.12, 20.39, 25.73, 18.27, 22.59]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Andhra Pradesh", [15.65, 20.90, 23.10, 24.20, 14.59, 11.10]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Arunachal Pradesh", [0, 38.91, 35.15, 36.83, 27.00, 25.92]),
    ("camelot", "stream/budget/budget.pdf", "DEPARTMENT OF ATOMIC ENERGY", [1779.00, 4101.00, 5880.00]),
    ("camelot", "stream/budget/budget.pdf", "Atomic Energy", [1483.00, 3427.00, 4910.00]),
    ("camelot", "stream/budget/budget.pdf", "Nuclear Power Schemes", [296.00, 674.00, 970.00]),
    ("camelot", "stream/budget/budget.pdf", "Department of Agriculture and Cooperation", [22260.55, 48.45, 22309.00]),
    ("camelot", "stream/budget/budget.pdf", "Department of Animal Husbandry, Dairying and Fisheries", [2154.93, 19.07, 2174.00]),
    # ---- round 4: same method, further rows and three more documents (health, twotables_2, budget) ----
    ("tabula", _US018, "Illinois", [124763, 123615, 126817, 130220, 135143, 131670]),
    ("tabula", _US018, "Florida", [131418, 133318, 134686, 142284, 149046, 153461]),
    ("tabula", _US018, "Ohio", [119029, 116702, 117356, 117658, 120758, 122203]),
    ("tabula", _US018, "Minnesota", [59096, 58391, 58898, 59497, 60409, 59729]),
    ("tabula", _US018, "Massachusetts", [58326, 59665, 61272, 63903, 65197, 65258]),
    ("tabula", _US018, "Kentucky", [37787, 38399, 38449, 39099, 39339, 41851]),
    ("tabula", _US018, "Louisiana", [37019, 36009, 33275, 34274, 34401, 35622]),
    ("tabula", _US018, "Maryland", [52870, 54170, 55536, 57564, 59171, 58304]),
    ("tabula", _US018, "Mississippi", [23735, 23523, 23848, 24186, 24795, 24505]),
    ("tabula", _US018, "North Carolina", [72126, 75010, 76710, 76031, 83307, 86712]),
    ("camelot", "stream/health/health.pdf", "Andhra Pradesh", [47824589, 9967837, 1275000, 15000, 59082426, 14898243, 73980669]),
    ("camelot", "stream/health/health.pdf", "Arunachal Pradesh", [2241609, 107549, 23000, 0, 2372158, 86336, 2458494]),
    ("camelot", "stream/health/health.pdf", "Assam", [14874821, 2554197, 161600, 0, 17590618, 4408505, 21999123]),
    ("camelot", "stream/health/health.pdf", "Bihar", [21016708, 4332141, 5329000, 0, 30677849, 2251571, 32929420]),
    ("camelot", "lattice/twotables_2/twotables_2.pdf", "Kerala", [2400, 7.2, 0.5, 25.3, 20.1, 41.5, 5.5]),
    ("camelot", "lattice/twotables_2/twotables_2.pdf", "Tamil Nadu", [2400, 21.4, 2.3, 8.8, 35.5, 25.8, 6.2]),
    ("camelot", "lattice/twotables_2/twotables_2.pdf", "Karnataka", [2399, 37.4, 2.8, 12.5, 18.3, 23.1, 5.8]),
    ("camelot", "lattice/twotables_2/twotables_2.pdf", "Maharashtra", [2400, 22.0, 0.9, 17.3, 20.3, 32.6, 7.0]),
    ("camelot", "lattice/twotables_2/twotables_2.pdf", "Gujarat", [2390, 28.6, 0.1, 14.4, 23.1, 26.9, 6.8]),
    ("camelot", "stream/budget/budget.pdf", "MINISTRY OF AGRICULTURE", [28130.48, 67.52, 28198.00, 2863.09]),
    ("camelot", "stream/budget/budget.pdf", "MINISTRY OF CORPORATE AFFAIRS", [22.76, 1.24, 24.00, 208.75, 22.50, 231.25, 255.25]),
    ("camelot", "stream/budget/budget.pdf", "MINISTRY OF COMMUNICATIONS AND INFORMATION TECHNOLOGY", [7704.70, 4410.30, 12115.00, 13953.92, 101.00, 14054.92, 26169.92]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Andaman and Nicobar Islands", [105.19, 81.17, 63.93, 48.70, 26.90, 6.68]),
    ("camelot", "stream/population_growth/population_growth.pdf", "Dadra and Nagar Haveli", [39.56, 27.96, 39.78, 33.57, 59.22, 55.50]),
]
CASES += [
    {"corpus": c, "group": "heldout round 3+4", "pdf": pdf, "attr": attr, "expect": vals, "opts": {"min_score": 90}}
    for c, pdf, attr, vals in _R3
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
