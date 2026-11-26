# Changelog

## 0.10.0

- **Fallback resolvers**: `fallback=` hook for rows the lexical matcher cannot find. Built-in
  `SemanticResolver` (`--semantic`, `pip install "tabledig[semantic]"`) and bring-your-own model (e.g. an LLM).
  A resolver only picks a row; the value always comes from the PDF. Results are marked (`method`),
  score-capped (75) and lower-confidence. See docs/fallback.md.
- Measured in CI (`benchmarks/semantic_eval.py`, 25 synthetic cases): at threshold 0.80 (default) 2 of 15
  unlisted synonyms found with 0 false matches; at 0.75, 6 of 15 with 1 false match; at 0.70, 9 of 15 with 6
  false matches. A modest gain, so it is opt-in.
- **Confidence check** (`benchmarks/calibration.py`, 55 real cases): confidence >= 0.95 was right in 38 of 38
  cases; 0.80-0.95 in 9 of 10. The "mismatch" verdict is noisy on receipts (total vs. net sales rows), which
  lowers confidence on some correct values. Still a ranking aid, not a probability.
- Not built: free-form prose extraction ("revenue rose 12% to $4.2m"). A sentence has no row structure, so
  there is no way to say which number is the value; guessing would break the "know when to doubt" promise.

## 0.9.0

- **Multi-column pages**: a page set in two or more columns of words is also read column by column
  (gutter detection that refuses to split label|number tables), in addition to whole-page reading.
  Real-PDF evaluation unchanged at 36/36; 0 false matches on absent attributes across 361 PDFs.
- **Typed package**: `py.typed` shipped, `mypy` clean and checked in CI.
- **Docs site** (MkDocs): home, real-document gallery, CLI reference, troubleshooting, roadmap, changelog.
  Built with `--strict` in CI; publishing needs Pages enabled once (see the workflow comment).

## 0.8.0

- **MCP server** (`tabledig-mcp`, `pip install "tabledig[mcp]"`): tools `extract_attributes`,
  `inspect_tables`, `suggest_aliases`. `TABLEDIG_MCP_ROOT` limits which folder it may read. Tested over
  stdio and with both mcp 1.x and 2.x.
- **Published result schema** (`tabledig schema`, `tabledig.result_schema()`), version 1; the JSON output is
  validated against it in tests.
- **Resumable batches**: `--cache DIR` stores results per file content and settings; re-running skips
  finished files.
- **Dockerfile** (with Tesseract). Built and smoke-tested in CI; I could not run Docker in my sandbox.
- `docs/troubleshooting.md`: "why did it not match" guide.
- Not shipped: a hosted docs site and the bring-your-own-LLM fallback hook.

## 0.7.0

- Synonym packs (`--pack finance|healthcare|sports|government|all` or your own `.yaml`): only add aliases
  to attributes you asked for. Plain YAML in `src/tabledig/packs/`.
- `--suggest` lists near-miss row labels for attributes not found; `--memory FILE` loads remembered aliases;
  `--suggest --remember --memory FILE` saves the best suggestion per missing attribute (review the file).
- Fix: one- and two-letter names/aliases ("P", "TO") now match whole words only; they used to fuzzy-match
  names such as "Brinderson, L.P.".
- Not shipped: the optional embedding matcher (`tabledig[semantic]`). It needs a model download I could not
  evaluate here, and an untested matcher would undermine the point of the project.

## 0.6.0

- `benchmarks/scan_eval.py`: OCR evaluated on 19 real scanned receipts (CC0, pinned commit, not stored
  in the repo), hand-read expected totals, run in CI. Forced OCR 16/19 (tuned 10/12, held-out 6/7) vs 9/19
  from the scanners' own text layers. Known misses: a garbled digit, white-on-black print, and a
  "Sub Total" vs "Order Total" tie (both score alike for the query "Total").

## 0.5.2

- Headers: up to three stacked header rows are merged, with merged cells spanning their columns
  (`2024 Q1 Actual`).
- New `columns=[...]` option / `--column NAME` flag keeps only matching columns (`Q2 Budget`).
- Wrapped row labels in borderless tables are joined ("Net cash used in investing" + "activities ...").
- Section scoping: `Revenue @ Segment information` (or `section:` in YAML/CSV) matches only rows
  under a heading containing that text.
- `--column latest` keeps only the most recent period's column(s).
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
