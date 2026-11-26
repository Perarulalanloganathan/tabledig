import pytest

pytest.importorskip("reportlab")

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from tabledig import extract  # noqa: E402
from tabledig.aliases import (  # noqa: E402
    apply_memory,
    apply_packs,
    available_packs,
    load_memory,
    load_pack,
    save_memory,
)
from tabledig.cli import main  # noqa: E402
from tabledig.models import Attribute  # noqa: E402


def _pdf(tmp_path, lines):
    path = tmp_path / "d.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    for i, text in enumerate(lines):
        c.drawString(50, 780 - 15 * i, text)
    c.save()
    return str(path)


def test_packs_are_valid_yaml():
    assert {"finance", "healthcare", "sports", "government"} <= set(available_packs())
    for name in available_packs():
        pack = load_pack(name)
        assert pack and all(isinstance(v, list) and v for v in pack.values())


def test_unknown_pack_is_a_clear_error():
    with pytest.raises(ValueError, match="unknown pack"):
        load_pack("nope")


def test_pack_adds_aliases_without_adding_attributes():
    out = apply_packs([Attribute("Net profit"), Attribute("Banana")], ["finance"])
    assert "Profit for the year" in out[0].aliases and len(out) == 2
    assert out[1].aliases == []


def test_pack_makes_extraction_work(tmp_path):
    path = _pdf(tmp_path, ["Profit for the year   500   400", "Total income   900   800"])
    assert not [r for r in extract(path, ["Net profit"]) if r.status == "found"]
    got = [r.value for r in extract(path, ["Net profit"], packs=["finance"]) if r.status == "found"]
    assert got == [500, 400]


def test_memory_round_trip(tmp_path):
    mem = tmp_path / "mem.yaml"
    save_memory(mem, {"Net profit": ["Profit for the year"]})
    save_memory(mem, {"Net profit": ["Profit for the year", "PAT"]})
    assert load_memory(mem) == {"Net profit": ["Profit for the year", "PAT"]}
    applied = apply_memory([Attribute("net profit")], load_memory(mem))
    assert applied[0].aliases == ["Profit for the year", "PAT"]


def test_suggest_and_remember_via_cli(tmp_path, capsys):
    path = _pdf(tmp_path, ["Profit for the year   500   400", "Depreciation   30   20"])
    mem = tmp_path / "mem.yaml"
    main(["extract", path, "--attr", "Net profit", "--suggest", "--remember", "--memory", str(mem)])
    err = capsys.readouterr().err
    assert "Profit for the year" in err
    assert load_memory(mem) == {"Net profit": ["Profit for the year"]}
    # the next run finds it with no flags besides the memory file
    got = [r.value for r in extract(path, ["Net profit"], memory=mem) if r.status == "found"]
    assert got == [500, 400]
