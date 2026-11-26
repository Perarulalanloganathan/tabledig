from pathlib import Path

import pytest

from tabledig import Extractor
from tabledig.ocr import ocr_available, resolve_mode, words_to_text

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
needs_ocr = pytest.mark.skipif(not ocr_available(), reason="pytesseract/tesseract not installed")


def _scan(tmp_path, name):
    """Render a sample PDF to an image-only PDF (a stand-in for a scanner)."""
    pdfium = pytest.importorskip("pypdfium2")
    pdf = pdfium.PdfDocument(str(EXAMPLES / name))
    image = pdf[0].render(scale=300 / 72).to_pil().convert("RGB")
    out = tmp_path / ("scan_" + name)
    image.save(out, resolution=300)
    return str(out)


def _w(text, left, line=0, width=None):
    return {"text": text, "left": left, "top": line * 40, "width": width or len(text) * 10,
            "height": 30, "line": (1, 1, line)}  # fmt: skip


def test_words_to_text_separates_columns_by_wide_gaps():
    words = [_w("Total", 0), _w("income", 60), _w("12,770", 400), _w("11,255", 520)]
    line = words_to_text(words)
    assert line.startswith("Total income  ")  # narrow gap -> single space, wide gap -> run of spaces
    assert "12,770" in line and "  " in line.split("income", 1)[1]


def test_words_to_text_orders_lines_top_to_bottom():
    words = [_w("second", 0, line=2), _w("first", 0, line=1)]
    assert words_to_text(words).splitlines() == ["first", "second"]


def test_resolve_mode():
    modes = [resolve_mode(v) for v in ("auto", None, True, "off", False)]
    assert modes == ["auto", "auto", "on", "off", "off"]
    with pytest.raises(ValueError):
        resolve_mode("maybe")


def test_scanned_pdf_without_ocr_explains_why(tmp_path):
    pytest.importorskip("pypdfium2")
    recs = Extractor(["Total income"], ocr="off").extract_file(_scan(tmp_path, "sample_income_statement.pdf"))
    assert recs[0].status == "not_found" and "scanned page" in recs[0].note


def test_ocr_on_without_engine_raises(tmp_path, monkeypatch):
    pytest.importorskip("pypdfium2")
    import tabledig.ocr as ocr_module

    monkeypatch.setattr(ocr_module, "ocr_available", lambda: False)
    path = _scan(tmp_path, "sample_income_statement.pdf")
    with pytest.raises(RuntimeError, match="OCR requested"):
        Extractor(["Total income"], ocr="on").extract_file(path)
    recs = Extractor(["Total income"], ocr="on").extract_many([path])  # batch mode reports, not raises
    assert recs[0].status == "error" and "OCR" in recs[0].note


@needs_ocr
def test_ocr_reads_scanned_bordered_statement(tmp_path):
    path = _scan(tmp_path, "sample_income_statement.pdf")
    ex = Extractor(["Total income", "Profit for the year", "Employee benefits expense"], validate=True)
    recs = ex.extract_file(path)
    got = {(r.attribute, r.column): r.value for r in recs if r.status == "found"}
    assert got[("Total income", "FY 2024")] == 12770
    assert got[("Total income", "FY 2023")] == 11255
    assert got[("Profit for the year", "FY 2024")] == 3630
    assert got[("Employee benefits expense", "FY 2024")] == -2140
    assert all(r.source == "ocr" for r in recs if r.status == "found")
    assert [r.check for r in recs if r.attribute == "Total income"] == ["verified", "verified"]


@needs_ocr
def test_ocr_reads_scanned_borderless_invoice(tmp_path):
    path = _scan(tmp_path, "sample_invoice.pdf")
    recs = Extractor(["Subtotal", "Total due"], validate=True).extract_file(path)
    got = {r.attribute: r.value for r in recs if r.status == "found"}
    assert got == {"Subtotal": 2011.97, "Total due": 2217.93}
