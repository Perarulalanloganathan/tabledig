# Changelog

## 0.3.1
- Fixed: repeated column names in one table (e.g. two "2024" columns) silently overwrote each other
  in wide output; they are now `2024` and `2024 (2)`.
- Fixed: directory scan skipped upper-case `.PDF` files.
- Added: `--password` / `password=` for encrypted PDFs; clearer error message when a password is needed.
- Fixed: README, example attribute file and demo defaults used "Total revenue", which never matches the
  sample PDF; examples are now covered by tests so they cannot drift.

## 0.3.0
- International number formats (`1.234,56`, `1 234,56`, `1'234.50`) and `--decimal auto|dot|comma`.
- Unicode-aware labels and matching (accents folded; Chinese, Cyrillic, Greek labels work).
- Header carry-over for tables continuing on later pages without a header.
- Stacked-cell tables split into rows; text-line fallback when ruled tables are nearly empty.
- Tests on mixed prose + table documents from other domains.
- Demo: result columns reordered so values appear first; README now has a demo GIF
  (`scripts/make_demo_gif.py` regenerates it from the real app).

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
