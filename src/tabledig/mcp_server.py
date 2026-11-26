"""MCP server: lets an assistant call tabledig as an extraction tool.

    pip install "tabledig[mcp]"
    tabledig-mcp                         # stdio server; add it to your MCP client's configuration
    TABLEDIG_MCP_ROOT=/data/pdfs tabledig-mcp   # only allow files under this folder

Every value comes back with its page, column, matched label, score and a validation verdict, so the
assistant can say how far to trust it instead of guessing.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .extractor import Extractor
from .reader import read_tables


def _resolve(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    root = os.environ.get("TABLEDIG_MCP_ROOT")
    if root and Path(root).resolve() not in (p, *p.parents):
        raise ValueError(f"{path!r} is outside the allowed folder (TABLEDIG_MCP_ROOT)")
    if not p.is_file():
        raise ValueError(f"no such file: {path}")
    return p


def extract_attributes(
    path: str,
    attributes: list[str],
    min_score: float = 80.0,
    column: Optional[str] = None,
    pack: Optional[str] = None,
) -> list[dict]:
    """Find rows named by ``attributes`` in a PDF and return their values.

    Each record has attribute, status (found / not_found / error), matched_label, page, column,
    value, score, check (verified / partial / mismatch / unchecked) and confidence (0-1). Treat a
    check of "mismatch" or a low confidence as a reason to look at the page, not as a fact.
    Attribute names may carry aliases: "Net profit=PAT|Profit for the year".
    """
    from .config import coerce_attributes, parse_attribute_lines

    attrs = coerce_attributes(parse_attribute_lines("\n".join(attributes)))
    extractor = Extractor(
        attrs,
        min_score=min_score,
        validate=True,
        evidence=True,
        columns=[column] if column else None,
        packs=[pack] if pack else None,
    )
    records = extractor.extract_file(_resolve(path))
    fields = records[0].FIELDS if not records else records[0].fields_for(records)
    return [r.as_dict(fields) for r in records]


def inspect_tables(path: str, page: Optional[int] = None, max_rows: int = 15) -> list[dict]:
    """List the tables tabledig detects in a PDF, to choose attribute names from."""
    out = []
    for t in read_tables(str(_resolve(path))):
        if t.source == "kv" or (page and t.page != page):
            continue
        out.append(
            {
                "page": t.page,
                "source": t.source,
                "header": t.header,
                "rows": t.rows[:max_rows],
                "more_rows": max(0, len(t.rows) - max_rows),
            }
        )
    return out


def suggest_aliases(path: str, attributes: list[str]) -> dict:
    """For attributes not found in the PDF, list near-miss row labels to try as aliases."""
    from .config import coerce_attributes, parse_attribute_lines

    attrs = coerce_attributes(parse_attribute_lines("\n".join(attributes)))
    hits = Extractor(attrs).suggest(_resolve(path))
    return {
        name: [{"label": label, "score": round(score)} for label, score in found]
        for name, found in hits.items()
    }


def build_server():
    try:
        try:  # mcp 2.x
            from mcp.server.mcpserver import MCPServer as Server
        except ImportError:  # mcp 1.x
            from mcp.server.fastmcp import FastMCP as Server
    except ImportError as exc:  # pragma: no cover
        raise SystemExit('the MCP server needs the "mcp" package: pip install "tabledig[mcp]"') from exc
    server = Server("tabledig")
    for fn in (extract_attributes, inspect_tables, suggest_aliases):
        server.tool()(fn)
    return server


def main() -> None:  # pragma: no cover
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
