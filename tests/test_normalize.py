import pytest

from tabledig.normalize import detect_unit, parse_number


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1,234", 1234.0),
        ("12,34,567.50", 1234567.5),
        ("(1,200)", -1200.0),
        ("-45.5", -45.5),
        ("45-", -45.0),
        ("₹ 3,000", 3000.0),
        ("$1,000.00", 1000.0),
        ("12%", 12.0),
        ("-", 0.0),
        ("—", 0.0),
        ("0", 0.0),
    ],
)
def test_parse_number_valid(text, expected):
    assert parse_number(text) == expected


@pytest.mark.parametrize("text", ["", None, "abc", "Note 3", "(8%)", "1.2.3", "2024 2023"])
def test_parse_number_invalid(text):
    assert parse_number(text) is None


@pytest.mark.parametrize(
    "text,name,scale",
    [
        ("(Amounts in thousands)", "thousands", 1e3),
        ("(INR in lakhs)", "lakhs", 1e5),
        ("All figures in Rs. crores", "crores", 1e7),
        ("USD in millions", "millions", 1e6),
        ("($ in billions)", "billions", 1e9),
        ("Amount in '000", "thousands", 1e3),
    ],
)
def test_detect_unit(text, name, scale):
    unit = detect_unit(text)
    assert unit is not None
    assert (unit.name, unit.scale) == (name, scale)


def test_detect_unit_none():
    assert detect_unit("Revenue was strong in the quarter") is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("1 234,56", 1234.56),
        ("1'234.50", 1234.5),
        ("12,5", 12.5),
        ("1.234.567", 1234567.0),
        ("98 452", 98452.0),
    ],
)
def test_parse_number_international_formats(text, expected):
    assert parse_number(text) == expected


def test_parse_number_forced_decimal_mark():
    assert parse_number("1,234", decimal=",") == 1.234
    assert parse_number("1,234", decimal=".") == 1234.0


def test_ocr_specks_around_numbers_are_ignored():
    assert parse_number("‘19.88") == 19.88
    assert parse_number("'30.37'") == 30.37
    assert parse_number("1'234.50") == 1234.50  # Swiss grouping unaffected
