import pytest

pytest.importorskip("streamlit")
from pathlib import Path  # noqa: E402

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")


def test_app_runs_with_sample_and_shows_results():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Tables detected"] == "1"
    assert metrics["Attributes found"] == "4 / 5"  # "Dividend paid" is absent on purpose
    assert len(at.dataframe) >= 2  # results + detected table


def test_app_invoice_sample_and_min_score():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.selectbox[0].select("Invoice (borderless table)").run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Attributes found"] == "4 / 5"  # "Postage" is absent on purpose


def test_app_warns_without_attributes():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_area[0].set_value("  \n").run()
    assert not at.exception
    assert any("at least one attribute" in w.value for w in at.warning)
