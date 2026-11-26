"""Prose-plus-table documents from several unrelated domains.

Each document mixes narrative paragraphs (containing numbers that must NOT be picked up)
with one or more tables, sometimes continuing across pages without a repeated header.
"""
import pytest

pytest.importorskip("reportlab")

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from tabledig import extract  # noqa: E402

S = getSampleStyleSheet()
GRID = TableStyle(
    [("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]
)


def _build(path, story):
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return str(path)


def _p(text):
    return [Paragraph(text, S["BodyText"]), Spacer(1, 8)]


def _bordered(rows):
    return [Table(rows, style=GRID), Spacer(1, 12)]


def _values(records, attr):
    return [r.value for r in records if r.attribute == attr and r.status == "found"]


def test_lab_results_report(tmp_path):
    story = _p("Patient 4471 was admitted on 12 March. Hemoglobin was reported as 9.1 in the referral note, "
               "but the confirmed laboratory values are tabulated below.")
    story += _bordered([["Test", "Result", "Unit", "Reference range"],
                        ["Hemoglobin", "13.8", "g/dL", "12.0-16.0"],
                        ["White cell count", "6,200", "cells/uL", "4,000-11,000"],
                        ["Glucose (fasting)", "(5.4)", "mmol/L", "3.9-5.6"],
                        ["Platelets", "245,000", "cells/uL", "150,000-400,000"]])
    story += _p("A follow-up in 6 weeks is advised; creatinine was 1.1 at the last visit.")
    recs = extract(_build(tmp_path / "lab.pdf", story), ["Hemoglobin", "White cell count", "Platelets"])
    assert _values(recs, "Hemoglobin")[0] == 13.8
    assert _values(recs, "White cell count")[0] == 6200
    assert _values(recs, "Platelets")[0] == 245000


def test_sales_report_table_spans_pages_without_header(tmp_path):
    header = ["Region", "Q1", "Q2", "Q3", "Q4"]
    page1 = [header, ["North", "1,200", "1,350", "1,500", "1,720"],
             ["South", "980", "1,010", "1,100", "1,230"]]
    page2 = [["East", "2,050", "2,100", "2,260", "2,480"], ["West", "1,400", "1,390", "1,460", "1,610"]]
    story = _p("Sales grew 14% year on year to 7,500 units across 4 regions; Q4 was the strongest quarter.")
    story += _bordered(page1) + [PageBreak()]
    story += _p("Regional detail continues on this page.") + _bordered(page2)
    recs = extract(_build(tmp_path / "sales.pdf", story), ["East", "West", "North"])
    east = [r for r in recs if r.attribute == "East" and r.status == "found"]
    assert [r.value for r in east] == [2050, 2100, 2260, 2480]
    assert [r.column for r in east] == ["Q1", "Q2", "Q3", "Q4"]  # header carried from page 1
    assert _values(recs, "North")[0] == 1200


def test_price_list_with_currency_and_percent(tmp_path):
    story = _p("Prices include a 18% levy. The previous list priced the Standard plan at $19.00.")
    story += _bordered([["Plan", "Monthly price", "Discount"],
                        ["Standard plan", "$24.50", "5%"],
                        ["Premium plan", "$1,299.00", "10%"]])
    recs = extract(_build(tmp_path / "prices.pdf", story), ["Premium plan", "Standard plan"])
    assert _values(recs, "Standard plan")[:1] == [24.5]
    assert _values(recs, "Premium plan")[:1] == [1299.0]


def test_european_number_format(tmp_path):
    story = _p("Alle Beträge in Euro.")
    story += _bordered([["Posten", "2024", "2023"], ["Umsatzerlöse", "1.234.567,89", "1.100.000,00"],
                        ["Jahresüberschuss", "98.765,43", "-45.000,50"]])
    recs = extract(_build(tmp_path / "de.pdf", story), ["Umsatzerlöse", "Jahresüberschuss"])
    assert _values(recs, "Umsatzerlöse") == [1234567.89, 1100000.0]
    assert _values(recs, "Jahresüberschuss") == [98765.43, -45000.5]


def test_prose_number_is_not_returned_as_a_table_value(tmp_path):
    story = _p("Total revenue was 9,999 according to the press release.")
    story += _bordered([["Item", "Amount"], ["Total revenue", "5,000"]])
    recs = extract(_build(tmp_path / "prose.pdf", story), ["Total revenue"])
    assert _values(recs, "Total revenue") == [5000]


def test_missing_attribute_reports_not_found(tmp_path):
    story = _p("Narrative only mentions Dividend of 7.") + _bordered([["Item", "Amount"], ["Revenue", "10"]])
    recs = extract(_build(tmp_path / "miss.pdf", story), ["Dividend paid"])
    assert recs[0].status == "not_found"
