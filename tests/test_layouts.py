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


def _ruled_pdf(tmp_path, data, col_x, name="grid.pdf", merges=()):
    """Draw a ruled grid; ``merges`` = (row, first_col, last_col) spans drawn without inner lines."""
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    path = tmp_path / name
    t = Table(data, colWidths=col_x)
    style = [("GRID", (0, 0), (-1, -1), 0.5, "black")]
    style += [("SPAN", (c0, r), (c1, r)) for r, c0, c1 in merges]
    t.setStyle(TableStyle(style))
    SimpleDocTemplate(str(path)).build([t])
    return str(path)


def test_three_row_merged_header(tmp_path):
    data = [
        ["", "2024", "", "", ""],
        ["", "Q1", "", "Q2", ""],
        ["Item", "Actual", "Budget", "Actual", "Budget"],
        ["Revenue", "100", "90", "120", "110"],
        ["Costs", "60", "55", "70", "65"],
    ]
    path = _ruled_pdf(tmp_path, data, [90, 70, 70, 70, 70], merges=[(0, 1, 4), (1, 1, 2), (1, 3, 4)])
    from tabledig import read_tables

    header = read_tables(path)[0].header
    assert header[1:] == ["2024 Q1 Actual", "2024 Q1 Budget", "2024 Q2 Actual", "2024 Q2 Budget"]
    vals = [r.value for r in extract(path, ["Revenue"]) if r.status == "found"]
    assert vals == [100, 90, 120, 110]


def test_column_selection_with_merged_header(tmp_path):
    data = [
        ["", "2024", "", "", ""],
        ["", "Q1", "", "Q2", ""],
        ["Item", "Actual", "Budget", "Actual", "Budget"],
        ["Revenue", "100", "90", "120", "110"],
    ]
    path = _ruled_pdf(tmp_path, data, [90, 70, 70, 70, 70], merges=[(0, 1, 4), (1, 1, 2), (1, 3, 4)])
    recs = extract(path, ["Revenue"], columns=["Q2 Budget"])
    got = {r.column: r.value for r in recs if r.status == "found"}
    assert got == {"2024 Q2 Budget": 110}
    both = [r.value for r in extract(path, ["Revenue"], columns=["Q1"]) if r.status == "found"]
    assert both == [100, 90]


def test_section_scoping_and_latest_period(tmp_path):
    lines = [
        (50, 780, "Segment information"),
        (50, 765, "Revenue            1,000    900"),
        (50, 740, "Group totals"),
        (50, 725, "Revenue            5,000    4,500"),
    ]
    path = _pdf(tmp_path, [(x, y, t) for x, y, t in lines])
    from tabledig.config import parse_attribute_line

    attr = parse_attribute_line("Revenue @ Group totals")
    assert attr.section == "Group totals"
    got = [r.value for r in extract(path, [attr]) if r.status == "found"]
    assert got == [5000, 4500]
    seg = parse_attribute_line("Revenue @ Segment")
    other = [r.value for r in extract(path, [seg]) if r.status == "found"]
    assert other == [1000, 900]


def test_latest_column(tmp_path):
    data = [["Item", "FY 2023", "FY 2024"], ["Revenue", "90", "100"]]
    path = _ruled_pdf(tmp_path, data, [90, 80, 80])
    got = [r.value for r in extract(path, ["Revenue"], columns=["latest"]) if r.status == "found"]
    assert got == [100]


def test_wrapped_label_in_borderless_table(tmp_path):
    path = _pdf(
        tmp_path,
        [
            (50, 780, "Cash flow statement"),
            (50, 765, "Net cash used in investing"),
            (50, 752, "activities            (1,200)    (900)"),
            (50, 735, "Net cash from operations   3,000   2,500"),
        ],
    )
    recs = [r for r in extract(path, ["Net cash used in investing activities"]) if r.status == "found"]
    assert [r.value for r in recs] == [-1200, -900]


def _prose(prefix, n):
    return [f"{prefix} line {i} words that make up a sentence of ordinary prose text" for i in range(n)]


def test_two_column_page_reads_each_column_separately(tmp_path):
    left = [(50, 780 - 13 * i, t[:40]) for i, t in enumerate(_prose("left", 12))]
    right = [(320, 780 - 13 * i, t[:40]) for i, t in enumerate(_prose("right", 12))]
    left += [(50, 600, "Ballots cast   1,200   1,100")]
    right += [(320, 600, "Registered voters   5,000   4,900")]
    path = _pdf(tmp_path, left + right)
    from tabledig import read_tables

    assert [r.value for r in extract(path, ["Ballots cast"]) if r.status == "found"] == [1200, 1100]
    assert [r.value for r in extract(path, ["Registered voters"]) if r.status == "found"] == [5000, 4900]
    assert read_tables(path)  # no crash
    import pdfplumber

    from tabledig.reader import _split_columns

    with pdfplumber.open(path) as pdf:
        assert len(_split_columns(pdf.pages[0]) or []) == 2


def test_label_number_table_is_not_split_into_columns(tmp_path):
    lines = [(50, 780 - 13 * i, f"Item number {i} of the long ledger") for i in range(45)]
    lines += [(400, 780 - 13 * i, f"{i * 1000 + 17}") for i in range(45)]
    path = _pdf(tmp_path, lines)
    import pdfplumber

    from tabledig.reader import _split_columns

    with pdfplumber.open(path) as pdf:
        assert _split_columns(pdf.pages[0]) is None


def test_numbered_rows_with_page_reference(tmp_path):
    path = _pdf(
        tmp_path,
        [
            (50, 780, "Ministry   Revenue   Capital   Total   Page"),
            (50, 765, "4. Atomic Energy   1483.00   3427.00   4910.00   20-25"),
            (50, 750, "5. Nuclear Power Schemes   296.00   674.00   970.00   26-27"),
        ],
    )
    got = [r.value for r in extract(path, ["Nuclear Power Schemes"]) if r.status == "found"]
    assert got == [296.0, 674.0, 970.0]
