# tabledig

Give it table-style PDFs and the names of the things you want ("Revenue", "Hemoglobin", "Ballots cast").
It finds those rows and returns their values with the page, column, match score, a validation verdict
(do the totals add up?) and a confidence, so you know which values to double-check.

```bash
pip install "git+https://github.com/Perarulalanloganathan/tabledig.git"   # PyPI release planned for 1.0
tabledig extract report.pdf --attr "Revenue" --validate --evidence
```

```python
from tabledig import extract
rows = extract("report.pdf", ["Revenue", "Net profit"], validate=True, packs=["finance"])
```

* Ruled tables, whitespace-aligned tables, key-value forms, scanned pages (OCR) and multi-column pages.
* Merged and multi-row headers, column selection (`--column latest`), section scoping (`Revenue @ Segment`).
* Synonym packs, alias suggestions, resumable batches, an MCP server and a published JSON schema.

Try the [live demo](https://tabledig.streamlit.app), see the [gallery](gallery.md) of real documents, or
read [what to do when something does not match](troubleshooting.md).
