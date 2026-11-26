"""Reproducible synthetic benchmark for tabledig.

Generates a seeded corpus of fictional PDFs in several layouts, with known answers, and
measures value-level precision and recall. Two query styles are compared:

* ``name only``  - the user asks for one canonical name per concept ("Net profit")
* ``with aliases`` - the user also lists the wording variants they expect

    pip install -e ".[dev]"
    python benchmarks/run_benchmark.py --n 60 --seed 7

IMPORTANT: this corpus is synthetic. It measures how well the matcher and table reader handle
controlled layout, wording, typo and unit variations - not accuracy on arbitrary real documents.
"""
from __future__ import annotations

import argparse
import random
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from tabledig import Attribute, Extractor

STYLES = getSampleStyleSheet()

# canonical concept -> wording variants a document might use
CONCEPTS = {
    "Revenue": ["Revenue from operations", "Total revenue", "Net sales", "Turnover"],
    "Cost of goods": ["Cost of materials consumed", "Cost of goods sold", "Cost of sales"],
    "Staff cost": ["Employee benefits expense", "Employee benefit expenses", "Personnel costs"],
    "Finance costs": ["Finance costs", "Interest expense", "Borrowing costs"],
    "Depreciation": ["Depreciation and amortisation", "Depreciation and amortization"],
    "Pre-tax profit": ["Profit before tax", "Earnings before tax", "Income before taxes"],
    "Tax": ["Tax expense", "Income tax expense", "Provision for taxation"],
    "Net profit": ["Profit for the year", "Net income", "Profit after tax"],
}
# present in some documents on purpose, to catch look-alike mistakes
DISTRACTORS = ["Finance income", "Total expenses", "Other income", "Tax paid", "Total income"]
ABSENT = ["Dividend paid", "Goodwill impairment"]  # never in any document

UNIT_LINES = [None, "(Amounts in thousands)", "(INR in lakhs)", "(USD in millions)"]
LAYOUTS = ("bordered", "borderless", "invoice")


def typo(text: str, rng: random.Random) -> str:
    """Swap two adjacent letters inside a longer word."""
    words = text.split(" ")
    idx = [i for i, w in enumerate(words) if len(w) > 5]
    if not idx:
        return text
    i = rng.choice(idx)
    w = words[i]
    j = rng.randrange(1, len(w) - 2)
    words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2 :]
    return " ".join(words)


def fmt(value: int, rng_style: str, negative: bool) -> str:
    if rng_style == "indian":
        s = f"{value:,}"
        digits = str(value)
        if len(digits) > 3:
            head, tail = digits[:-3], digits[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            s = ",".join(groups + [tail])
    else:
        s = f"{value:,}"
    return f"({s})" if negative else s


def build_statement(path: Path, layout: str, rng: random.Random, noise: float):
    """Return gold: {concept: [values...]} and the label used per concept."""
    unit = rng.choice(UNIT_LINES)
    style = rng.choice(["western", "indian"])
    with_note = rng.random() < 0.5
    years = ["2024", "2023"]
    header = (["Particulars"] + (["Note"] if with_note else []) + [f"FY {y}" for y in years]
              if layout == "bordered"
              else ["Particulars"] + (["Note"] if with_note else []) + years)

    concepts = list(CONCEPTS)
    rng.shuffle(concepts)
    rows, gold, labels = [], {}, {}
    for n, concept in enumerate(concepts, 1):
        label = rng.choice(CONCEPTS[concept])
        if rng.random() < noise:
            label = typo(label, rng)
        labels[concept] = label
        negative = concept in {"Cost of goods", "Staff cost", "Finance costs", "Depreciation", "Tax"}
        vals = [rng.randint(100, 9_999_999) for _ in years]
        gold[concept] = [-v if negative else v for v in vals]
        row = [label] + ([str(n)] if with_note else []) + [fmt(v, style, negative) for v in vals]
        rows.append(row)
    for label in rng.sample(DISTRACTORS, k=3):
        vals = [rng.randint(100, 9_999_999) for _ in years]
        rows.append([label] + (["9"] if with_note else []) + [fmt(v, style, False) for v in vals])
    rng.shuffle(rows)

    doc = SimpleDocTemplate(str(path), pagesize=A4)
    table = Table([header] + rows)
    cmds = [("ALIGN", (1, 0), (-1, -1), "RIGHT")]
    if layout == "bordered":
        cmds.append(("GRID", (0, 0), (-1, -1), 0.5, colors.black))
    table.setStyle(TableStyle(cmds))
    story = [Paragraph("Fictional Co (benchmark)", STYLES["Title"])]
    if unit:
        story.append(Paragraph(unit, STYLES["Normal"]))
    story += [Spacer(1, 12), table]
    doc.build(story)
    return gold, labels


def build_invoice(path: Path, rng: random.Random):
    subtotal = rng.randint(500, 50_000)
    tax = round(subtotal * 0.08, 2)
    shipping = round(rng.uniform(5, 80), 2)
    total = round(subtotal + tax + shipping, 2)
    items = [
        [f"Item {i}", str(rng.randint(1, 9)), f"{rng.uniform(5, 500):.2f}", f"{rng.uniform(5, 3000):.2f}"]
        for i in range(rng.randint(2, 5))
    ]
    rows = [["Description", "Qty", "Unit price", "Amount"], *items,
            ["Subtotal", "", "", f"{subtotal:,.2f}"],
            ["Sales tax (8%)", "", "", f"{tax:,.2f}"],
            ["Shipping", "", "", f"{shipping:,.2f}"],
            ["Total due", "", "", f"{total:,.2f}"]]
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    table = Table(rows)
    table.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    doc.build([Paragraph("Invoice (benchmark)", STYLES["Title"]), Spacer(1, 12), table])
    gold = {"Subtotal": [float(subtotal)], "Tax": [tax], "Shipping": [shipping], "Total": [total]}
    labels = {"Subtotal": "Subtotal", "Tax": "Sales tax (8%)", "Shipping": "Shipping", "Total": "Total due"}
    return gold, labels


INVOICE_ALIASES = {"Subtotal": [], "Tax": ["Sales tax"], "Shipping": [], "Total": ["Total due"]}


def attributes_for(concepts, with_aliases: bool, invoice: bool):
    attrs = []
    for concept in concepts:
        if invoice:
            aliases = INVOICE_ALIASES[concept] if with_aliases else []
        else:
            aliases = list(CONCEPTS[concept]) if with_aliases else []
        attrs.append(Attribute(concept, aliases=aliases))
    return attrs


def close(a: float, b: float) -> bool:
    return abs(a - b) < 0.005


def score_document(records, gold, queried, absent):
    """Return (tp, fp, fn) at value level for one document."""
    tp = fp = fn = 0
    by_attr = defaultdict(list)
    for r in records:
        if r.status == "found":
            by_attr[r.attribute].append(r.value)
    for concept in queried:
        got, want = by_attr.get(concept, []), gold[concept]
        hits = sum(1 for g, w in zip(got, want) if close(g, w))
        tp += hits
        fp += max(len(got), 0) - hits
        fn += len(want) - hits
    for name in absent:
        fp += len(by_attr.get(name, []))
    return tp, fp, fn


def run(n: int, seed: int, noise: float, min_score: float):
    rng = random.Random(seed)
    totals = {(mode, layout): [0, 0, 0] for mode in ("name only", "with aliases") for layout in LAYOUTS}
    docs = {layout: 0 for layout in LAYOUTS}
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n):
            layout = LAYOUTS[i % len(LAYOUTS)]
            path = Path(tmp) / f"doc_{i:03d}.pdf"
            if layout == "invoice":
                gold, _ = build_invoice(path, rng)
            else:
                gold, _ = build_statement(path, layout, rng, noise)
            docs[layout] += 1
            for mode in ("name only", "with aliases"):
                attrs = attributes_for(list(gold), mode == "with aliases", layout == "invoice")
                attrs += [Attribute(name) for name in ABSENT]
                records = Extractor(attrs, min_score=min_score).extract_file(path)
                tp, fp, fn = score_document(records, gold, list(gold), ABSENT)
                t = totals[(mode, layout)]
                t[0] += tp
                t[1] += fp
                t[2] += fn
    return totals, docs


def ratio(a: int, b: int) -> float:
    return 100.0 * a / b if b else 0.0


def report(totals, docs, args) -> str:
    lines = [
        f"tabledig synthetic benchmark - {args.n} documents, seed {args.seed}, "
        f"typo rate {args.noise:.0%}, min_score {args.min_score:g}",
        "",
        "| Queries | Layout | Docs | Precision | Recall |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for mode in ("name only", "with aliases"):
        agg = [0, 0, 0]
        for layout in LAYOUTS:
            tp, fp, fn = totals[(mode, layout)]
            agg = [agg[0] + tp, agg[1] + fp, agg[2] + fn]
            p_, r_ = ratio(tp, tp + fp), ratio(tp, tp + fn)
            lines.append(f"| {mode} | {layout} | {docs[layout]} | {p_:.1f}% | {r_:.1f}% |")
        lines.append(
            f"| **{mode}** | **all** | **{sum(docs.values())}** | **{ratio(agg[0], agg[0] + agg[1]):.1f}%** "
            f"| **{ratio(agg[0], agg[0] + agg[2]):.1f}%** |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--n", type=int, default=60, help="number of documents (default 60)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--noise", type=float, default=0.25, help="typo rate in labels (default 0.25)")
    parser.add_argument("--min-score", type=float, default=80.0)
    args = parser.parse_args()
    totals, docs = run(args.n, args.seed, args.noise, args.min_score)
    print(report(totals, docs, args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
