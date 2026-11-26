import pytest

from tabledig import Extractor
from tabledig.models import Table
from tabledig.validate import check_tables


def tbl(rows, header=("Item", "2024", "2023"), page=1, index=0):
    return Table(page=page, index=index, header=list(header), rows=rows, source="ruled")


def status(table, row_idx):
    return check_tables([table]).get((table.page, table.index, row_idx))


def test_total_equals_sum_is_verified():
    t = tbl([["Apples", "10", "5"], ["Pears", "20", "6"], ["Total", "30", "11"]])
    assert status(t, 2).status == "verified"


def test_tampered_total_is_flagged_mismatch():
    t = tbl([["Apples", "10", "5"], ["Pears", "20", "6"], ["Total", "99", "77"]])
    assert status(t, 2).status == "mismatch"


def test_one_bad_column_is_partial():
    t = tbl([["Apples", "10", "5"], ["Pears", "20", "6"], ["Total", "30", "99"]])
    res = status(t, 2)
    assert res.status == "partial" and "2023" in res.note


def test_percent_columns_are_not_summed():
    t = tbl(
        [["North", "60", "60%"], ["South", "40", "40%"], ["Total", "100", "100%"]],
        header=("Region", "Sales", "Share"),
    )
    assert status(t, 2).status == "verified"


def test_parentheses_and_absolute_sign_convention():
    t = tbl([["Rent", "(100)", "(90)"], ["Wages", "(300)", "(280)"], ["Total expenses", "400", "370"]])
    assert status(t, 2).status == "verified"


def test_subtotals_roll_up_to_grand_total():
    t = tbl(
        [
            ["A", "1", "1"], ["B", "2", "2"], ["Subtotal one", "3", "3"],
            ["C", "4", "4"], ["D", "5", "5"], ["Subtotal two", "9", "9"],
            ["Grand total", "12", "12"],
        ]
    )  # fmt: skip
    assert status(t, 2).status == "verified"
    assert status(t, 6).status == "verified"


def test_rounding_tolerance_allows_off_by_one():
    t = tbl([["A", "10", "1"], ["B", "20", "1"], ["C", "31", "1"], ["Total", "60", "3"]])
    assert status(t, 3).status == "verified"


def test_balance_sheet_identity():
    ok = tbl([["Total assets", "500", "400"], ["Total equity and liabilities", "500", "400"]])
    bad = tbl([["Total assets", "500", "400"], ["Total equity and liabilities", "480", "400"]])
    assert status(ok, 0).status == "verified"
    assert status(bad, 1).status == "mismatch"


def test_total_row_with_one_numeric_row_above_is_unchecked():
    t = tbl([["Only", "5", "5"], ["Total", "5", "5"]])
    assert status(t, 1).status == "unchecked"


def test_table_continuing_on_next_page_is_joined():
    p1 = tbl([["A", "1", "1"], ["B", "2", "2"]], page=1, index=0)
    p2 = tbl([["C", "3", "3"], ["Total", "6", "6"]], page=2, index=1)
    res = check_tables([p1, p2])
    assert res[(2, 1, 1)].status == "verified"


def test_extractor_adds_check_and_confidence(income_pdf):
    ex = Extractor(["Total income", "Revenue"], validate=True, evidence=True, explain=True)
    recs = ex.extract_file(income_pdf)
    total = [r for r in recs if r.attribute == "Total income"]
    assert all(r.check == "verified" and r.confidence == 1.0 for r in total)
    assert total[0].row_text.startswith("Total income |")
    rev = [r for r in recs if r.attribute == "Revenue"][0]
    assert rev.check == "unchecked" and rev.confidence == pytest.approx(0.8)


def test_extras_absent_by_default(income_pdf):
    recs = Extractor(["Total income"]).extract_file(income_pdf)
    assert recs[0].check is None and recs[0].confidence is None and recs[0].row_text is None
    from tabledig.models import Record

    assert Record.fields_for(recs) == list(Record.FIELDS)
