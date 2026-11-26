# Changelog

## Unreleased

- Headers: up to three stacked header rows are merged, with merged cells spanning their columns
  (`2024 Q1 Actual`).
- New `columns=[...]` option / `--column NAME` flag keeps only matching columns (`Q2 Budget`).
- Demo: pinned to a release tag (a stale unpinned install broke it) and OCR enabled.

## 0.5.1

- OCR: `--ocr force` re-reads pages that already have a text layer (e.g. scanner output).
- OCR: a second Tesseract layout pass recovers lines the first pass loses (large-print totals).
- Numbers: stray quote marks left by OCR (`'19.88`) no longer break parsing.
- Tested on 12 real scanned receipts (CC0 `JensWalter/my-receipts`): 10/12 totals correct
  with forced OCR vs 7/12 from the scanners' own text layers. The misses were a garbled
  digit and white-on-black print. Small sample; treat as indicative, not a benchmark.

## 0.5.0
- **Key-value fallback** (`source = kv`): value-before-label rows, several blocks on one line / side-by-side
  page columns, dot-leader rows with qualifiers like "Up to $3,790". Used only when no real table row matches.
- Row labels can be ranges/bands (`12-19`, `65+`, `<18`) instead of requiring letters.
- Text tables: a cell-sized block of text mis-detected as one table cell no longer suppresses the page's
  text fallback; several values per period (`2001 Mill. | Part.`) are kept; a title that mentions two years
  is no longer mistaken for a 2-column header (it used to cut values); `( 498,5)` negatives with inner spaces.
- Real-PDF evaluation now spans three pinned corpora, 36 cases, with honestly reported blind first-run scores.

## 0.4.0
- **Validation** (`--validate` / `validate=True`): checks that Total/Subtotal rows equal the rows above and
  that total assets equal total equity and liabilities; joins tables continuing across pages; skips
  percentage/ratio columns. Adds `check`, `check_note` and a heuristic `confidence`.
- `--evidence` (`row_text`) and `--explain` (`alternatives`: runner-up labels).
- **OCR** for scanned pages (`pip install "tabledig[ocr]"` + Tesseract): rule-line removal, layout-preserving
  text rebuild, `--ocr off|auto|on`, `--ocr-lang`. A scanned file without OCR now says why it returned nothing.
- Header detection now understands `FY 2024`, `Q1 2024`, `2023-24` style column headers in text tables.
- Demo app: "Validate totals" option. CI installs Tesseract so OCR tests run.
- Real-PDF evaluation: 19 cases (17 pass), including validation verdicts on real totals.

## 0.3.2
- Fixed: the Streamlit demo failed to read uploaded/sample PDFs on Windows (temp file reopened while open).
- `benchmarks/real_eval.py`: 17 hand-checked cases on real public PDFs (15 pass; 2 documented limits), run in CI.
- CI now also runs the test suite on Windows and macOS.

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
