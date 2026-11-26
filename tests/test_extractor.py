import pytest

from tabledig import Attribute, Extractor, extract, read_tables
from tabledig.output import records_to_wide


def by_column(records, attribute):
    return {r.column: r.value for r in records if r.attribute == attribute and r.status == "found"}


def test_reads_ruled_table_with_header_and_unit(income_pdf):
    tables = read_tables(income_pdf)
    assert len(tables) == 1
    table = tables[0]
    assert table.source == "ruled"
    assert table.header == ["Particulars", "Note", "FY 2024", "FY 2023"]
    assert table.unit is not None and table.unit.name == "thousands"


def test_extracts_values_and_skips_note_column(income_pdf):
    records = extract(income_pdf, ["Revenue from operations", "Finance costs"])
    assert by_column(records, "Revenue from operations") == {"FY 2024": 12450.0, "FY 2023": 10980.0}
    assert by_column(records, "Finance costs") == {"FY 2024": -180.0, "FY 2023": -210.0}
    assert all(r.column != "Note" for r in records)


def test_aliases_and_modes(income_pdf):
    attrs = [
        Attribute("Net profit", aliases=["Profit for the year"]),
        Attribute("Profit", mode="exact"),  # nothing is exactly "Profit"
        {"name": "tax", "mode": "contains"},
    ]
    records = Extractor(attrs).extract_file(income_pdf)
    assert by_column(records, "Net profit")["FY 2024"] == 3630.0
    assert [r.status for r in records if r.attribute == "Profit"] == ["not_found"]
    assert by_column(records, "tax")["FY 2023"] == -960.0


def test_normalize_units(income_pdf):
    records = extract(income_pdf, ["Revenue from operations"], normalize_units=True)
    assert by_column(records, "Revenue from operations")["FY 2024"] == 12_450_000.0


def test_missing_attribute_reported_and_optional(income_pdf):
    records = extract(income_pdf, ["Dividend paid"])
    assert [r.status for r in records] == ["not_found"]
    assert extract(income_pdf, ["Dividend paid"], include_missing=False) == []


def test_top_k_returns_multiple_rows(income_pdf):
    records = extract(income_pdf, ["Profit"], top_k=2, min_score=50)
    labels = {r.matched_label for r in records}
    assert len(labels) == 2


def test_text_table_fallback_on_borderless_pdf(invoice_pdf):
    tables = read_tables(invoice_pdf)
    assert tables and tables[0].source == "text"
    records = extract(invoice_pdf, ["Subtotal", "Total due", "Sales tax", "Postage"])
    values = {r.attribute: r.value for r in records if r.status == "found"}
    assert values["Subtotal"] == 2011.97
    assert values["Total due"] == 2217.93
    assert values["Sales tax"] == 160.96  # "(8%)" in the label is not a value
    assert [r.status for r in records if r.attribute == "Postage"] == ["not_found"]


def test_wide_pivot(income_pdf):
    records = extract(income_pdf, ["Revenue from operations", "Finance costs"])
    fieldnames, rows = records_to_wide(records)
    assert "FY 2024" in fieldnames and "FY 2023" in fieldnames
    assert len(rows) == 2


def test_bad_pdf_does_not_stop_batch(tmp_path, income_pdf):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf")
    records = Extractor(["Finance costs"]).extract_many([bad, income_pdf])
    statuses = {(r.file, r.status) for r in records}
    assert ("broken.pdf", "error") in statuses
    assert (income_pdf.name, "found") in statuses


def test_requires_attributes():
    with pytest.raises(ValueError):
        Extractor([])
