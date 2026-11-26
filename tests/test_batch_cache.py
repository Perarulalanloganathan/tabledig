import pytest

pytest.importorskip("reportlab")

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from tabledig import Extractor  # noqa: E402


def _pdf(path, text):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawString(50, 780, text)
    c.save()
    return path


def test_cache_skips_finished_files_and_respects_settings(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path / "a.pdf", "Revenue   100   90")
    cache = tmp_path / "cache"
    first = Extractor(["Revenue"], cache_dir=cache).extract_many([pdf])
    assert [r.value for r in first] == [100, 90] and len(list(cache.glob("*.json"))) == 1

    calls = []
    original = Extractor.extract_file
    monkeypatch.setattr(Extractor, "extract_file", lambda self, p: calls.append(p) or original(self, p))
    again = Extractor(["Revenue"], cache_dir=cache).extract_many([pdf])
    assert calls == [] and [r.value for r in again] == [100, 90]

    Extractor(["Revenue"], cache_dir=cache, min_score=95).extract_many([pdf])  # new settings: recompute
    assert len(calls) == 1


def test_cache_invalidated_when_file_changes(tmp_path):
    pdf = _pdf(tmp_path / "a.pdf", "Revenue   100   90")
    cache = tmp_path / "cache"
    Extractor(["Revenue"], cache_dir=cache).extract_many([pdf])
    _pdf(pdf, "Revenue   555   90")
    got = Extractor(["Revenue"], cache_dir=cache).extract_many([pdf])
    assert [r.value for r in got] == [555, 90]
