import asyncio
import json

import pytest

pytest.importorskip("reportlab")

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from tabledig import extract, result_schema  # noqa: E402
from tabledig.cli import main  # noqa: E402
from tabledig.output import write_records  # noqa: E402


def _pdf(tmp_path):
    path = tmp_path / "d.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    lines = ["Item   2024   2023", "Revenue   100   90", "Costs   60   55", "Total   160   145"]
    for i, t in enumerate(lines):
        c.drawString(50, 780 - 15 * i, t)
    c.save()
    return str(path)


def test_json_output_validates_against_published_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    pdf = _pdf(tmp_path)
    out = tmp_path / "o.json"
    recs = extract(pdf, ["Revenue", "Nope"], validate=True, evidence=True, explain=True)
    write_records(recs, out, fmt="json")
    jsonschema.validate(json.loads(out.read_text()), result_schema())


def test_schema_command(capsys):
    assert main(["schema"]) == 0
    assert json.loads(capsys.readouterr().out)["title"].startswith("tabledig result")


def test_mcp_tool_functions_and_root_restriction(tmp_path, monkeypatch):
    from tabledig import mcp_server

    pdf = _pdf(tmp_path)
    rows = mcp_server.extract_attributes(pdf, ["Revenue"])
    assert [r["value"] for r in rows if r["status"] == "found"] == [100, 90]
    assert "check" in rows[0] and "confidence" in rows[0]
    assert mcp_server.inspect_tables(pdf)[0]["rows"]
    monkeypatch.setenv("TABLEDIG_MCP_ROOT", str(tmp_path / "elsewhere"))
    with pytest.raises(ValueError, match="outside"):
        mcp_server.extract_attributes(pdf, ["Revenue"])


def test_mcp_server_lists_tools_over_the_protocol(tmp_path):
    pytest.importorskip("mcp")
    from tabledig import mcp_server

    async def run():
        tools = await mcp_server.build_server().list_tools()
        return {t.name for t in tools}

    assert asyncio.run(run()) == {"extract_attributes", "inspect_tables", "suggest_aliases"}
