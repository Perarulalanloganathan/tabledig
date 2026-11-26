import pytest

pytest.importorskip("reportlab")

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from tabledig import SemanticResolver, extract  # noqa: E402
from tabledig.cli import main  # noqa: E402


def _pdf(tmp_path, lines):
    path = tmp_path / "d.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    for i, t in enumerate(lines):
        c.drawString(50, 780 - 15 * i, t)
    c.save()
    return str(path)


DOC = ["Turnover   900   800", "Staff costs   300   280", "Depreciation   30   20"]


def test_no_fallback_means_no_guess(tmp_path):
    assert not [r for r in extract(_pdf(tmp_path, DOC), ["Revenue"]) if r.status == "found"]


def test_bring_your_own_resolver_picks_a_row_but_never_a_value(tmp_path):
    seen = {}

    def llm(attribute, labels):
        seen["labels"] = list(labels)
        return labels.index("Turnover"), 99.0  # score is capped by tabledig

    llm.method = "llm"
    found = extract(_pdf(tmp_path, DOC), ["Revenue"], fallback=llm, validate=True)
    rows = [r for r in found if r.status == "found"]
    assert [r.value for r in rows] == [900, 800]  # numbers come from the PDF row
    assert rows[0].method == "llm" and rows[0].score <= 75 and rows[0].confidence < 0.7
    assert "Turnover" in seen["labels"]


def test_resolver_is_not_called_when_lexical_match_exists(tmp_path):
    def boom(attribute, labels):
        raise AssertionError("must not be called")

    rows = extract(_pdf(tmp_path, DOC), ["Depreciation"], fallback=boom)
    assert [r.value for r in rows if r.status == "found"] == [30, 20]


@pytest.mark.parametrize("bad", [None, (99, 80.0), (-1, 80.0)])
def test_resolver_answers_that_do_not_point_at_a_row_are_ignored(tmp_path, bad):
    rows = extract(_pdf(tmp_path, DOC), ["Revenue"], fallback=lambda a, labels: bad)
    assert [r.status for r in rows] == ["not_found"]


def test_semantic_resolver_with_injected_embedder(tmp_path):
    vocab = {"revenue": [1, 0], "turnover": [0.95, 0.1], "staff costs": [0, 1], "depreciation": [0.1, 0.9]}
    embed = lambda texts: [vocab[t.lower()] for t in texts]  # noqa: E731
    resolver = SemanticResolver(threshold=0.9, embedder=embed)
    rows = [r for r in extract(_pdf(tmp_path, DOC), ["Revenue"], fallback=resolver) if r.status == "found"]
    assert [r.value for r in rows] == [900, 800] and rows[0].method == "semantic"
    strict = SemanticResolver(threshold=0.999, embedder=embed)
    assert not [r for r in extract(_pdf(tmp_path, DOC), ["Revenue"], fallback=strict) if r.status == "found"]


def test_semantic_flag_without_the_extra_gives_a_clear_error(tmp_path, capsys, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_fastembed(name, *a, **k):
        if name == "fastembed":
            raise ImportError("no")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_fastembed)
    code = main(["extract", _pdf(tmp_path, DOC), "--attr", "Revenue", "--semantic"])
    assert code != 0 and "tabledig[semantic]" in capsys.readouterr().err
