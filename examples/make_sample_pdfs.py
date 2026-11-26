"""Generate small, fully fictional sample PDFs used by the tests and README.

    pip install reportlab
    python examples/make_sample_pdfs.py

Creates in ``examples/``:
  * sample_income_statement.pdf  - bordered table, "in thousands", notes column
  * sample_invoice.pdf           - borderless, whitespace-aligned table
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).parent
styles = getSampleStyleSheet()


def income_statement(path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    data = [
        ["Particulars", "Note", "FY 2024", "FY 2023"],
        ["Revenue from operations", "1", "12,450", "10,980"],
        ["Other income", "2", "320", "275"],
        ["Total income", "", "12,770", "11,255"],
        ["Cost of materials consumed", "3", "(5,200)", "(4,810)"],
        ["Employee benefits expense", "4", "(2,140)", "(1,990)"],
        ["Finance costs", "5", "(180)", "(210)"],
        ["Depreciation and amortisation", "6", "(410)", "(395)"],
        ["Profit before tax", "", "4,840", "3,850"],
        ["Tax expense", "7", "(1,210)", "(960)"],
        ["Profit for the year", "", "3,630", "2,890"],
    ]
    table = Table(data, colWidths=[230, 40, 90, 90])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    doc.build(
        [
            Paragraph("Acme Widgets Ltd (fictional)", styles["Title"]),
            Paragraph("Statement of Profit and Loss for the year ended 31 March 2024", styles["Heading3"]),
            Paragraph("(Amounts in thousands)", styles["Normal"]),
            Spacer(1, 12),
            table,
        ]
    )


def invoice(path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    data = [
        ["Description", "Qty", "Unit price", "Amount"],
        ["Standing desk", "2", "450.00", "900.00"],
        ["Ergonomic chair", "4", "210.50", "842.00"],
        ["USB-C dock", "3", "89.99", "269.97"],
        ["Subtotal", "", "", "2,011.97"],
        ["Sales tax (8%)", "", "", "160.96"],
        ["Shipping", "", "", "45.00"],
        ["Total due", "", "", "2,217.93"],
    ]
    table = Table(data, colWidths=[200, 60, 90, 90])  # no GRID: borderless
    table.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    doc.build(
        [
            Paragraph("INVOICE #A-1042 - Example Supplies Co. (fictional)", styles["Title"]),
            Spacer(1, 12),
            table,
        ]
    )


if __name__ == "__main__":
    income_statement(OUT / "sample_income_statement.pdf")
    invoice(OUT / "sample_invoice.pdf")
    print("wrote sample PDFs to", OUT)
