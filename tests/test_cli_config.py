import csv
import json
from pathlib import Path

import pytest

from tabledig.cli import main
from tabledig.config import load_config


def test_yaml_config_with_settings(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text(
        "min_score: 70\nattributes:\n  - Revenue\n  - name: Net profit\n"
        "    aliases: [PAT, Profit after tax]\n    mode: contains\n"
    )
    cfg = load_config(f)
    assert cfg.settings == {"min_score": 70}
    assert [a.name for a in cfg.attributes] == ["Revenue", "Net profit"]
    assert cfg.attributes[1].aliases == ["PAT", "Profit after tax"]
    assert cfg.attributes[1].mode == "contains"


def test_csv_config_variants(tmp_path):
    with_header = tmp_path / "a.csv"
    with_header.write_text("attribute,aliases,mode\nNet profit,PAT|Profit after tax,exact\n")
    attr = load_config(with_header).attributes[0]
    assert (attr.name, attr.aliases, attr.mode) == ("Net profit", ["PAT", "Profit after tax"], "exact")

    headerless = tmp_path / "b.csv"
    headerless.write_text("Revenue\nFinance costs\n")
    assert [a.name for a in load_config(headerless).attributes] == ["Revenue", "Finance costs"]


def test_invalid_mode_rejected(tmp_path):
    f = tmp_path / "a.json"
    f.write_text(json.dumps([{"name": "x", "mode": "magic"}]))
    with pytest.raises(ValueError):
        load_config(f)


def test_cli_extract_csv_and_json(tmp_path, income_pdf):
    out_csv = tmp_path / "out.csv"
    code = main(["extract", str(income_pdf), "--attr", "Finance costs", "-o", str(out_csv)])
    assert code == 0
    rows = list(csv.DictReader(out_csv.open()))
    assert {r["column"] for r in rows} == {"FY 2024", "FY 2023"}

    out_json = tmp_path / "out.json"
    assert main(["extract", str(income_pdf.parent), "--attr", "Finance costs", "-o", str(out_json)]) == 0
    assert json.loads(out_json.read_text())[0]["attribute"] == "Finance costs"


def test_cli_requires_attributes(income_pdf, capsys):
    assert main(["extract", str(income_pdf)]) == 2
    assert "attrs" in capsys.readouterr().err


def test_cli_missing_path(capsys):
    assert main(["extract", "nope.pdf", "--attr", "x"]) == 2
    assert "no such file" in capsys.readouterr().err


def test_cli_inspect(income_pdf, capsys):
    assert main(["inspect", str(income_pdf)]) == 0
    assert "Revenue from operations" in capsys.readouterr().out


def test_parse_attribute_lines():
    from tabledig import parse_attribute_line, parse_attribute_lines

    attr = parse_attribute_line("Net profit = Profit for the year | PAT")
    assert (attr.name, attr.aliases) == ("Net profit", ["Profit for the year", "PAT"])
    assert parse_attribute_line("  # comment") is None
    assert parse_attribute_line("") is None
    names = [a.name for a in parse_attribute_lines("Revenue\n\n# skip\nFinance costs=Interest")]
    assert names == ["Revenue", "Finance costs"]


def test_cli_attr_alias_syntax(tmp_path, income_pdf):
    out = tmp_path / "o.csv"
    code = main(["extract", str(income_pdf), "--attr", "Net profit=Profit for the year|PAT", "-o", str(out)])
    assert code == 0
    rows = list(csv.DictReader(out.open()))
    assert rows[0]["matched_label"] == "Profit for the year"


def test_directory_scan_is_case_insensitive_and_recursive(tmp_path):
    import shutil

    from tabledig.cli import _collect_pdfs

    src = next(Path(__file__).resolve().parent.parent.joinpath("examples").glob("sample_income*.pdf"))
    (tmp_path / "sub").mkdir()
    shutil.copy(src, tmp_path / "A.PDF")
    shutil.copy(src, tmp_path / "sub" / "b.pdf")
    (tmp_path / "notes.txt").write_text("x")
    assert sorted(p.name for p in _collect_pdfs([str(tmp_path)])) == ["A.PDF", "b.pdf"]
