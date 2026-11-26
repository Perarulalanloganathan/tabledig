# Changelog

## 0.2.0
- Streamlit demo app (`app/streamlit_app.py`): upload or pick a sample PDF, list attributes, see results,
  detected tables and JSON, download CSV.
- Alias syntax everywhere: `--attr "Net profit=Profit for the year|PAT"`, plus
  `parse_attribute_line` / `parse_attribute_lines`.
- Reproducible synthetic benchmark (`benchmarks/run_benchmark.py`) and a regression test for it.
- Hosted demo: https://tabledig.streamlit.app
- Packaging: `app` extra, `requirements.txt` for hosting the demo.

## 0.1.0
- Initial version: table detection (ruled + text fallback), exact/contains/fuzzy attribute
  matching with aliases, number and unit normalisation, CSV/JSON/XLSX output, CLI and Python API.
