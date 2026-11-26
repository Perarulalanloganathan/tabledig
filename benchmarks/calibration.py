"""How well does ``confidence`` predict correctness on the real-document evaluation sets?

Runs every real-PDF case and every real-scan case with validation on, takes the lowest confidence among
the values a case returned, and reports the share of correct cases per confidence band. The sample is
small (about 55 cases), so treat the bands as a sanity check, not a calibrated probability.

    python benchmarks/calibration.py        # needs Tesseract for the scan cases
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from real_eval import CACHE, CASES, ensure_corpora  # noqa: E402
from scan_eval import CASES as SCANS  # noqa: E402
from scan_eval import ensure_corpus

from tabledig import extract  # noqa: E402
from tabledig.ocr import ocr_available  # noqa: E402

BANDS = [(0.0, 0.6), (0.6, 0.8), (0.8, 0.95), (0.95, 1.01)]


def collect() -> list[tuple[float, bool]]:
    points: list[tuple[float, bool]] = []
    folders = ensure_corpora(CACHE)
    for case in CASES:
        opts = dict(case.get("opts", {}), validate=True)
        pdf = folders[case.get("corpus", "pdfplumber")] / case["pdf"]
        found = [r for r in extract(str(pdf), [case["attr"]], **opts) if r.status == "found"]
        col = case.get("column")
        if col:
            found = [r for r in found if r.column and col in r.column]
        want = case["expect"]
        values = [r.value for r in found][: len(want)]
        ok = len(values) == len(want) and all(abs(v - w) < 1e-6 for v, w in zip(values, want))
        if found:
            points.append((min(r.confidence or 0.0 for r in found), ok))
    if ocr_available():
        root = ensure_corpus()
        for _group, rel, attr, expected in SCANS:
            rows = [r for r in extract(str(root / rel), [attr], top_k=1, ocr="force", validate=True) if r.status == "found"]
            if rows:
                points.append((rows[0].confidence or 0.0, abs((rows[0].value or 0) - expected) < 0.005))
    return points


def main() -> None:
    points = collect()
    print(f"{len(points)} cases with a value\n")
    print(f"{'confidence':>12} {'cases':>6} {'correct':>8}")
    for lo, hi in BANDS:
        sel = [ok for c, ok in points if lo <= c < hi]
        if sel:
            print(f"{lo:>5.2f}-{min(hi, 1.0):<5.2f} {len(sel):>6} {sum(sel) / len(sel):>8.0%}")


if __name__ == "__main__":
    main()
