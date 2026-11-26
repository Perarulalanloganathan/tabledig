"""Does the optional semantic fallback help, and what does it cost in false matches?

Each case is a small table of row labels and an attribute to look up. ``expect`` is the label a person
would pick, or ``None`` when the table has no such row (the correct answer is "not found"). Labels were
chosen to be wordings the built-in synonym packs do NOT already cover, so this measures the embedding
model, not the packs. Runs offline against synthetic tables; needs ``pip install fastembed`` and a model
download on first use.

    python benchmarks/semantic_eval.py
"""
from __future__ import annotations

from tabledig import Extractor, SemanticResolver
from tabledig.models import Table

# (attribute, row labels, expected label or None)
CASES = [
    ("Revenue", ["Takings", "Staff costs", "Rent", "Interest paid"], "Takings"),
    ("Revenue", ["Income from sales", "Wages", "Postage", "Depreciation"], "Income from sales"),
    ("Net profit", ["Bottom line earnings", "Gross receipts", "Rent", "Wages"], "Bottom line earnings"),
    ("Net profit", ["Surplus for the period", "Wages", "Rent", "Insurance"], "Surplus for the period"),
    ("Total assets", ["Everything owned", "Wages", "Rent", "Insurance"], "Everything owned"),
    ("Employees", ["Headcount", "Rent", "Revenue", "Interest paid"], "Headcount"),
    ("Employees", ["Number of staff members", "Rent", "Revenue", "Interest paid"], "Number of staff members"),
    ("Cash", ["Money in the bank", "Wages", "Rent", "Insurance"], "Money in the bank"),
    ("Debt", ["Borrowings", "Wages", "Rent", "Insurance"], "Borrowings"),
    ("Debt", ["Amounts owed to lenders", "Wages", "Rent", "Insurance"], "Amounts owed to lenders"),
    ("Blood sugar", ["Glucose level", "Sodium", "Iron", "Calcium"], "Glucose level"),
    ("Heart rate", ["Pulse", "Weight", "Height", "Temperature"], "Pulse"),
    ("Goals scored", ["Strikes that went in", "Fouls", "Corners", "Offsides"], "Strikes that went in"),
    ("Population", ["Number of inhabitants", "Area", "Altitude", "Rainfall"], "Number of inhabitants"),
    ("Votes cast", ["Ballots returned", "Registered electors", "Spoiled papers", "Precincts"], "Ballots returned"),
    # no such row: any pick is a false match
    ("Revenue", ["Wages", "Rent", "Insurance", "Postage"], None),
    ("Net profit", ["Wages", "Rent", "Insurance", "Postage"], None),
    ("Employees", ["Revenue", "Rent", "Insurance", "Postage"], None),
    ("Blood sugar", ["Sodium", "Iron", "Calcium", "Potassium"], None),
    ("Heart rate", ["Weight", "Height", "Temperature", "Age"], None),
    ("Goals scored", ["Fouls", "Corners", "Offsides", "Substitutions"], None),
    ("Population", ["Area", "Altitude", "Rainfall", "Elevation"], None),
    ("Total assets", ["Total liabilities", "Wages", "Rent", "Insurance"], None),
    ("Debt", ["Equity", "Wages", "Rent", "Insurance"], None),
    ("Cash", ["Inventory", "Wages", "Rent", "Insurance"], None),
]


def run(resolver):
    ex = Extractor(["x"], fallback=resolver)
    tp = fp = fn = tn = 0
    for attr, labels, expect in CASES:
        table = Table(1, 0, ["", "2024"], [[lab, str(100 + i)] for i, lab in enumerate(labels)], "text")
        ex.attributes = Extractor([attr]).attributes
        rec = [r for r in ex.extract_tables([table], "t.pdf") if r.status == "found"]
        got = rec[0].matched_label if rec else None
        if expect is None:
            tn += got is None
            fp += got is not None
        elif got == expect:
            tp += 1
        else:
            fn += 1
            fp += got is not None
    positives = sum(1 for c in CASES if c[2])
    return tp, fp, fn, tn, positives


def main() -> None:
    base = run(None)
    print(f"lexical only: found {base[0]}/{base[4]} synonyms, {base[1]} false matches, {base[3]} correct 'not found'")
    for threshold in (0.70, 0.75, 0.80, 0.85, 0.90):
        tp, fp, fn, tn, pos = run(SemanticResolver(threshold=threshold))
        print(f"semantic >= {threshold:.2f}: found {tp}/{pos} synonyms, {fp} false matches, {tn} correct 'not found'")


if __name__ == "__main__":
    main()
