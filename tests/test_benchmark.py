import sys
from pathlib import Path

import pytest

pytest.importorskip("reportlab")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))

import run_benchmark as rb  # noqa: E402


def test_benchmark_regression_guard():
    totals, docs = rb.run(n=12, seed=3, noise=0.25, min_score=80.0)
    assert sum(docs.values()) == 12
    for layout in rb.LAYOUTS:
        tp, fp, fn = totals[("with aliases", layout)]
        assert tp > 0
        assert rb.ratio(tp, tp + fp) >= 95  # precision
        assert rb.ratio(tp, tp + fn) >= 95  # recall
