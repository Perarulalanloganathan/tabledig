# tabledig roadmap

## Vision

> **Name the rows you want. Get the numbers back, with page, column, unit and a confidence you can check.**

General table extractors (Camelot, Tabula, pdfplumber, Docling) return whole tables and leave the
"find my row" step to you. Hosted AI services do that step but are paid, opaque and send your documents
away. tabledig aims to be the **best open-source, local, explainable layer for pulling named values out of
table-style PDFs**: small, deterministic, honest about its mistakes.

**Principles**

1. **Measure first.** No feature ships without real-PDF cases in `benchmarks/real_eval.py`. The score
   is published, including failures.
2. **Never silently wrong.** A value is returned with evidence and confidence, or reported `not_found`.
3. **Local by default.** No API keys. Heavy features (OCR, embeddings) are optional extras.
4. **Generic.** Finance is one use case, not the design centre.

## How we know we are "best in segment"

| Metric | Today (v0.5.0) | v1.0 target |
|---|---|---|
| Real-PDF eval cases | 36 (36 pass; blind first runs 43% and 78%) | 100+, >= 90% pass |
| Document types covered | statements, invoices, government/lab/sports tables | + scans, multi-column, merged-header tables |
| Wrong value returned without a warning | not measured | < 2% of returned values (measured) |
| Published head-to-head vs raw pdfplumber / Camelot + hand-written lookup | none | yes, fair methodology, reproducible |
| Install | from GitHub | `pip install tabledig` |

## Milestones

### v0.4 - Trust (validation and evidence)
The feature no free library does well: *tell the user when to doubt a value.*
- [x] **`validate` mode** (shipped in 0.4.0): arithmetic checks (total = sum of parts, subtotal chains, balance sheet
  assets = liabilities + equity, year-over-year column sanity). Each failed check is a flagged record.
- [x] **Evidence output**: original row text per value (0.4.0). Still to do: bounding box and a cropped
  page image in the demo so a person can verify in one glance.
- [~] **Confidence**: heuristic `confidence` shipped (0.4.0). Still to do: calibrate it on a larger eval set.
- [x] `--explain`: why this row won and which runners-up were rejected.
- [ ] Grow real eval to 40 cases (add insurance, utilities, lab, sports, government).

### v0.5 - Layout coverage
Fix the failures we already know about, then the next ones the eval exposes.
- [x] Value-before-label rows ("327 BALLOTS CAST") and key-value lists (0.5.0).
- [~] Side-by-side blocks on one page: handled for `label value` pairs (0.5.0). Still to do: true newspaper
  columns of prose and per-column table detection.
- [ ] Wrapped row labels in borderless tables.
- [x] Multi-row and merged headers (up to three rows); column selection (`--column`).
- [ ] **Column selection**: ask for "FY 2024" only, or "latest period", instead of every column.
- [ ] **Section scoping**: "Revenue" *within* "Segment information"; disambiguate repeated labels.

### v0.6 - Scanned documents
- [x] Optional `tabledig[ocr]` extra (Tesseract; shipped in 0.4.0, pulled forward). Same API; OCR confidence feeds the value
  confidence. Clear warning when a page has no text layer instead of silent `not_found`.
- [~] Table structure for images (lines and whitespace) with the same evidence output.
- [ ] 10+ *real* scanned cases in the eval, tracked separately (current OCR tests use synthetic scans).

### v0.7 - Smarter matching
- [ ] Built-in **synonym packs** (finance, healthcare labs, sports, government) as plain YAML, user-extensible.
- [ ] Optional `tabledig[semantic]` extra: small local embedding model for "turnover" ~ "revenue".
  Off by default; the lexical matcher stays the baseline and the eval compares both.
- [ ] Alias suggestions: after a run, propose aliases from near-misses ("Net profit" -> "Profit for the year").
- [ ] Learned alias memory file so repeat users stop re-typing aliases.

### v0.8 - Integrations and developer experience
- [ ] Stable JSON schema for results (published, versioned) and typed Python API.
- [ ] **MCP server / LLM tool wrapper** so assistants can call tabledig as a trustworthy extraction tool.
- [ ] Docker image; batch mode with caching and resumable runs for thousands of PDFs.
- [ ] Docs site with a gallery of real examples and a "why did it not match" troubleshooting guide.
- [ ] Optional LLM fallback hook (bring-your-own model) for rows the rules cannot resolve, always marked as such.

### v1.0 - Credible and stable
- [ ] Published on **PyPI** with trusted publishing from CI.
- [ ] Real eval >= 100 cases, >= 90% pass; synthetic benchmark retained as a regression guard.
- [ ] Public head-to-head write-up (method, data, code) against raw pdfplumber/Camelot + hand-written lookup.
- [ ] Semantic versioning promise, deprecation policy, security policy, citation file.
- [ ] Windows, macOS, Linux and Python 3.9-3.14 green in CI (Windows/macOS already added).

## Non-goals
- Not a general PDF-to-Markdown converter or layout-analysis toolkit (use Docling or pdfplumber for that).
- No hosted service and no uploading of user documents.
- No claim of 100% accuracy; the claim is *measured* accuracy plus visible doubt.

## Working rules for every milestone
1. Add failing real-PDF cases first; the milestone is done when they pass.
2. Update the README score and CHANGELOG in the same change.
3. Third-party PDFs are referenced by pinned URL or commit, never committed.
4. Anything that can return a wrong number must say how sure it is.

## Contributing
Real documents that break tabledig are the most valuable contribution. Open an issue with a
public PDF (or a redacted one), the attribute you asked for, and the value printed on the page.
