from tabledig.matcher import normalize_label, score_label


def test_normalize_label_strips_numbering_and_punctuation():
    assert normalize_label("1. Revenue from Operations") == "revenue from operations"
    assert normalize_label("(a) Salaries & Wages") == "salaries and wages"


def test_exact_and_normalized():
    assert score_label("Finance costs", "Finance Costs") == (100.0, "exact")
    score, method = score_label("Employee benefit expense", "Employee benefits expenses")
    assert score >= 99 and method == "normalized"


def test_exact_mode_rejects_partial():
    assert score_label("Revenue", "Revenue from operations", "exact")[0] == 0


def test_contains_mode():
    assert score_label("Revenue", "Total revenue from operations", "contains") == (90.0, "contains")
    assert score_label("Revenue operations", "Revenue from operations", "contains")[0] == 0


def test_fuzzy_tolerates_typos_and_word_order():
    assert score_label("Reveneu from operations", "Revenue from operations")[0] >= 90
    assert score_label("Operations revenue", "Revenue from operations")[0] >= 80


def test_fuzzy_does_not_confuse_related_labels():
    assert score_label("Finance costs", "Finance income")[0] < 80
    assert score_label("Total revenue", "Total expenses")[0] < 80
