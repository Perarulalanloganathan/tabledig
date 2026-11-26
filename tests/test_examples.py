"""The examples a new user copies from the README must actually work."""
from pathlib import Path

from tabledig import extract
from tabledig.config import load_config

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample_income_statement.pdf"


def test_readme_python_example_finds_values():
    net = {"name": "Net profit", "aliases": ["Profit for the year", "PAT"]}
    records = extract(str(SAMPLE), ["Revenue", net])
    found = {r.attribute for r in records if r.status == "found"}
    assert found == {"Revenue", "Net profit"}


def test_example_attribute_file_matches_sample():
    cfg = load_config(str(ROOT / "examples" / "attributes.yaml"))
    records = extract(str(SAMPLE), cfg.attributes, min_score=cfg.settings.get("min_score", 80))
    status = {}
    for r in records:
        status.setdefault(r.attribute, r.status)
    assert status.pop("Dividend paid") == "not_found"  # deliberately absent
    assert set(status.values()) == {"found"}, status


def test_demo_app_default_attributes_are_found():
    src = (ROOT / "app" / "streamlit_app.py").read_text()
    assert 'default_attrs = "Revenue\\n' in src
