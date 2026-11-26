"""Layouts beyond a plain ruled table: value-before-label, side-by-side blocks, leaders, numeric labels."""
import pytest

pytest.importorskip("reportlab")

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from tabledig import extract  # noqa: E402
from tabledig.normalize import is_labelish  # noqa: E402
from tabledig.reader import _kv_rows, _strip_leaders  # noqa: E402


def _pdf(tmp_path, lines, name="doc.pdf"):
    """Draw each (x, y, text) at an absolute position, like a form or multi-column page."""
    path = tmp_path / name
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica", 10)
    for x, y, text in lines:
        c.drawString(x, y, text)
    c.save()
    return str(path)


def _values(records, attr):
    return [r.value for r in records if r.attribute == attr and r.status == "found"]


def test_value_before_label(tmp_path):
    path = _pdf(tmp_path, [(50, 780, "327 BALLOTS CAST"), (50, 765, "1100 REGISTERED VOTERS")])
    recs = extract(path, ["Ballots cast", "Registered voters"])
    assert _values(recs, "Ballots cast") == [327]
    assert _values(recs, "Registered voters") == [1100]
    assert all(r.source == "kv" for r in recs if r.status == "found")


def test_two_blocks_on_one_line_are_separate_rows():
    rows = _kv_rows("Presentes   217       0           217 Votos Afirmativos 129 0      0    129")
    assert ["Presentes", "217", "0", "217"] in rows
    assert ["Votos Afirmativos", "129", "0", "0", "129"] in rows


def test_dot_leader_row_with_qualifiers():
    line = "Stabilizer wiring change........ Up to 79 work-hours x $85 = Up to $3,790....... Up to $766,865."
    assert _kv_rows(line) == [["Stabilizer wiring change", "$3,790", "$766,865"]]
    assert _strip_leaders("Total . . . . . 5") == "Total   5"


def test_bracket_spacing_in_negatives():
    assert _kv_rows("COTTON   1.393,4   886,7   ( 498,5)") == [["COTTON", "1.393,4", "886,7", "(498,5)"]]


def test_numeric_range_labels_are_rows(tmp_path):
    rows = ["Age (years)      Male      Female", "12-19      9,795      9,208", "20-29     13,340     14,032"]
    path = _pdf(tmp_path, [(50, 780 - 15 * i, text) for i, text in enumerate(rows)])
    recs = extract(path, ["20-29"])
    assert _values(recs, "20-29") == [13340, 14032]


def test_is_labelish():
    assert is_labelish("Revenue") and is_labelish("12-19") and is_labelish("65+") and is_labelish("<18")
    assert not is_labelish("1,234") and not is_labelish("") and not is_labelish("2024")


def test_real_table_wins_over_key_value_fallback(tmp_path):
    rows = ["Item           2024      2023", "Revenue        100       90"]
    path = _pdf(tmp_path, [(50, 780 - 15 * i, text) for i, text in enumerate(rows)])
    recs = extract(path, ["Revenue"])
    assert _values(recs, "Revenue") == [100, 90]
    assert all(r.source != "kv" for r in recs if r.status == "found")


def test_absent_attribute_is_not_invented_from_key_values(tmp_path):
    path = _pdf(tmp_path, [(50, 780, "327 BALLOTS CAST"), (50, 765, "Revenue   100")])
    assert extract(path, ["Dividend paid"])[0].status == "not_found"


def test_multi_value_per_period_header_keeps_all_values():
    from tabledig.reader import _build_text_tables

    text = "Class   2001   2002\nPrimary   663 2.5%   478 1.9%\nOther   232 0.9%   241 0.9%"
    table = _build_text_tables(text, 1, 0, None)[0]
    assert table.rows[0][1:] == ["663", "2.5%", "478", "1.9%"]
    assert len(table.header) == 5  # label + 2 periods x 2 values


def test_title_mentioning_years_does_not_trim_values():
    from tabledig.reader import _build_text_tables

    text = "2011/2012 AND 2012/2013 CROPS\nCOTTON   1,393   886   894   35   498"
    table = _build_text_tables(text, 1, 0, None)[0]
    assert table.rows[0][1:] == ["1,393", "886", "894", "35", "498"]
