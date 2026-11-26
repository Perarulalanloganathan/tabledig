"""Evaluate OCR on REAL scanned receipts with hand-read expected totals.

The receipts come from the CC0 repository JensWalter/my-receipts, fetched at a pinned commit into a
cache folder (the PDFs are not stored here). Each expected value was read off the rendered page image by
a person, not produced by tabledig. Every receipt is a scanner image with a (poor) embedded text layer,
so OCR is forced; the score without OCR is reported for comparison.

    python benchmarks/scan_eval.py            # needs Tesseract; exits 1 if the OCR score < --min-pass

Groups: ``tuned`` receipts were looked at while improving OCR (so they flatter the score); ``heldout``
receipts were sampled and read only after the code was frozen.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from tabledig import extract
from tabledig.ocr import ocr_available

REPO = "https://github.com/JensWalter/my-receipts.git"
COMMIT = "0b875ba0d5e50b9dda57c33dceb253a3503b9241"
CACHE = Path.home() / ".cache" / "tabledig-eval" / "my-receipts"

TOTAL = {"name": "Total", "aliases": ["Grand Total", "Amount Due"]}

# (group, path in the repo, attribute, expected total)
CASES = [
    ("tuned", "2019/us/restaurant/roxanne-596018.pdf", TOTAL, 19.88),
    ("tuned", "2023/us/redwood_20231005_007.pdf", TOTAL, 10.00),
    ("tuned", "2023/us/grandlux_20231209_018.pdf", TOTAL, 63.35),
    ("tuned", "2019/us/restaurant/dennys-20190420_009.pdf", TOTAL, 30.37),
    ("tuned", "2024/us/wholefood_20240528_003.pdf", TOTAL, 14.52),
    ("tuned", "2023/us/snacks_20231209_013.pdf", TOTAL, 30.84),
    ("tuned", "2021/us/wholefoods_20211211_005.pdf", TOTAL, 13.16),
    ("tuned", "2022/us/snacks_20221210_001.pdf", TOTAL, 31.59),
    ("tuned", "2023/us/snacks_20231209_016.pdf", TOTAL, 71.56),
    ("tuned", "2018/us/restaurant/sw_20181208_3630.pdf", TOTAL, 968.84),
    ("tuned", "2024/ca/timhorton_20240918_011.pdf", TOTAL, 6.30),
    ("tuned", "2021/us/inout_20211211_001.pdf", TOTAL, 10.57),
    ("heldout", "2024/ca/uniqlo_20240715.pdf", TOTAL, 101.37),
    ("heldout", "2022/us/fiveguys_20221016_011.pdf", TOTAL, 22.09),
    ("heldout", "2019/us/restaurant/superduper_20355.pdf", TOTAL, 14.92),
    ("heldout", "2024/us/spaceneedle_20240528_005.pdf", TOTAL, 39.38),
    ("heldout", "2018/us/restaurant/applebees_8267120140431.pdf", {"name": "Total Due"}, 125.23),
    ("heldout", "2024/ca/oldnavy_20240918_013.pdf", TOTAL, 74.52),
    ("heldout", "2019/us/tourist attraction/topgold-20191203.pdf", TOTAL, 117.64),
]


def ensure_corpus() -> Path:
    if not (CACHE / ".git").exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", REPO, str(CACHE)], check=True)
    files = sorted({c[1] for c in CASES})
    subprocess.run(["git", "-C", str(CACHE), "checkout", "-q", COMMIT, "--", *files], check=True)
    return CACHE


def first_value(path: Path, attr, **options):
    rows = [r for r in extract(str(path), [attr], top_k=1, **options) if r.status == "found"]
    return rows[0].value if rows else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-pass", type=float, default=0.7, help="minimum OCR pass rate (default 0.7)")
    args = parser.parse_args()
    if not ocr_available():
        print("Tesseract is not installed; install it (and pip install 'tabledig[ocr]') to run this.")
        return 2
    root = ensure_corpus()
    tally: dict[str, list[int]] = {}
    for group, rel, attr, expected in CASES:
        ocr = first_value(root / rel, attr, ocr="force")
        layer = first_value(root / rel, attr, ocr="off")
        ok_ocr = ocr is not None and abs(ocr - expected) < 0.005
        ok_layer = layer is not None and abs(layer - expected) < 0.005
        t = tally.setdefault(group, [0, 0, 0])
        t[0] += ok_ocr
        t[1] += ok_layer
        t[2] += 1
        print(f"{'PASS' if ok_ocr else 'FAIL'}  {Path(rel).name:36} expected={expected:<8} ocr={ocr} layer={layer}")
    print()
    total = [sum(t[i] for t in tally.values()) for i in range(3)]
    for group, (o, lyr, n) in tally.items():
        print(f"  {group:8} OCR {o}/{n}   scanner text layer {lyr}/{n}")
    print(f"\nOCR {total[0]}/{total[2]} ({total[0] / total[2]:.0%});  scanner text layer {total[1]}/{total[2]}")
    return 0 if total[0] / total[2] >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())
