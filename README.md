# tabledig

[![CI](https://github.com/Perarulalanloganathan/tabledig/actions/workflows/ci.yml/badge.svg)](https://github.com/Perarulalanloganathan/tabledig/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
[![Live demo](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://tabledig.streamlit.app)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Give it a PDF and the names of the things you want. Get back their values.

`tabledig` finds tables in table-style PDFs (financial statements, invoices, reports,
price lists, lab results...) and looks up **named attributes** - row labels such as
*"Total revenue"* or *"Subtotal"* - returning every value on that row, with the column it
came from, the page, and how confident the match was.

![tabledig demo: pick a PDF, list attributes, get values](docs/demo.gif)

*The [live demo](https://tabledig.streamlit.app) in action.*

Docs: <https://perarulalanloganathan.github.io/tabledig/> (gallery of real documents, CLI reference, troubleshooting).

```text
$ tabledig extract examples/sample_income_statement.pdf \
      --attr "Revenue from operations" --attr "Net profit" --attr "Dividend paid" --wide

file,attribute,matched_label,page,unit,score,status,FY 2024,FY 2023
sample_income_statement.pdf,Revenue from operations,Revenue from operations,1,thousands,100.0,found,12450.0,10980.0
sample_income_statement.pdf,Net profit,,,,,not_found,,
sample_income_statement.pdf,Dividend paid,,,,,not_found,,
```

"Net profit" is *not* found there because the document says "Profit for the year".
Tell the tool that once with an alias and it is found:

```yaml
- name: Net profit
  aliases: [Profit for the year, Profit after tax, PAT]
```

## Try it in the browser

**Live demo: https://tabledig.streamlit.app** (no install needed).

A Streamlit app lets you upload a PDF (or pick a sample), list the attributes you want, and see
the results, every detected table, and a CSV download:

```bash
pip install -e ".[app]"
streamlit run app/streamlit_app.py
```

## Why it is useful

- **Any table-style PDF.** Not tied to one country, form or taxonomy.
- **Ask in your own words.** Exact, "contains" and typo-tolerant fuzzy matching, plus aliases.
- **Bordered or borderless tables.** Uses drawn grid lines when present and falls back to
  whitespace-aligned text rows when not.
- **Numbers done right.** `(1,200)` is negative, `12,34,567` (Indian grouping) works, dashes are
  zero, currency symbols and `%` are stripped, and a "Note" column is not mistaken for data.
- **Units.** Detects "in thousands / lakhs / crores / millions / billions" and can convert to base units.
- **Explainable.** Every value carries the matched label, page, score and method, so you can audit it.
- **Batch friendly.** Folders of PDFs, parallel workers, and one broken file never stops the run.

## Install

```bash
pip install git+https://github.com/Perarulalanloganathan/tabledig.git
# with .xlsx output and DataFrame support:
pip install "tabledig[excel] @ git+https://github.com/Perarulalanloganathan/tabledig.git"
```

From source:

```bash
git clone https://github.com/Perarulalanloganathan/tabledig.git
cd tabledig
pip install -e ".[dev]"
```

## Quick start

### 1. See what is in the PDF

```bash
tabledig inspect examples/sample_income_statement.pdf
```

Prints each detected table (page, header, first rows, declared unit) so you can pick the
labels to ask for.

### 2. Extract

```bash
tabledig extract examples/sample_income_statement.pdf --attr "Revenue" --attr "Net profit=Profit for the year|PAT" -o result.csv
tabledig extract ./reports/ -a attributes.yaml -o result.xlsx --wide -j 4
```

Output is **long format** by default (one row per attribute x column). `--wide` gives one row
per attribute with a column per table column (e.g. one per year).

Other useful flags: `--password` (encrypted PDFs), `--decimal comma` (force `1.234,56` style numbers),
`--normalize-units` (turn "in thousands" into full values), `--top-k N`, `--min-score N`,
`--column "Q2 Budget"` (only matching columns; `--column latest` = most recent period).

Built-in synonym packs (`--pack finance`, `healthcare`, `sports`, `government`, `all`) add common
wordings for the attributes you ask for. `--suggest` shows near-miss rows for anything not found, and
`--memory aliases.yaml` re-uses aliases you accepted (`--suggest --remember` saves them; review the file).

For big batches add `--cache .tabledig-cache`: finished files are skipped on re-runs. Results follow a
published JSON schema (`tabledig schema`). Stuck? See [docs/troubleshooting.md](docs/troubleshooting.md).

**For AI assistants:** `pip install "tabledig[mcp]"` (Python 3.10+) then run `tabledig-mcp` to expose `extract_attributes`,
`inspect_tables` and `suggest_aliases` over MCP; set `TABLEDIG_MCP_ROOT` to limit which folder it can read.
A `Dockerfile` (with Tesseract) is included: `docker build -t tabledig .`.

Nothing matched lexically? `--semantic` (local embeddings) or `fallback=your_model` can pick a row for you;
they never supply the number and their picks are flagged ([docs/fallback.md](docs/fallback.md)).

Aliases can go inline: `--attr "Net profit=Profit for the year|PAT"`. Scope a row to a section with
`--attr "Revenue @ Segment information"`.

### 3. Or use it from Python

```python
from tabledig import extract, to_dataframe

records = extract("examples/sample_income_statement.pdf", ["Revenue", {"name": "Net profit", "aliases": ["Profit for the year", "PAT"]}])
df = to_dataframe(records, wide=True)      # needs tabledig[excel]
```

## Attribute files

YAML (also `.json` and `.csv`):

```yaml
min_score: 80            # default minimum match score, 0-100
top_k: 1                 # best-matching rows kept per attribute and file
normalize_units: false   # true -> convert thousands/lakhs/millions to base units

attributes:
  - Revenue                            # plain string = fuzzy match
  - name: Revenue from operations
    mode: exact                        # exact | contains | fuzzy
  - name: Staff cost
    aliases: [Employee benefits expense, Salaries and wages]
```

CSV needs an `attribute` column and may add `aliases` (separated by `|`), `mode`, `min_score`.

### Match modes

| mode | matches when | use it for |
| --- | --- | --- |
| `exact` | label is identical after lower-casing and stripping punctuation/numbering | precise control |
| `contains` | your words appear, in order, inside the label | "tax" -> "Tax expense" |
| `fuzzy` (default) | word overlap blended with character similarity | typos, word order, plural/singular |

When several rows match, the highest score wins; ties go to the shorter, more specific label.

## Output columns

`file, attribute, status, matched_label, page, column, raw_value, value, unit, score, method, source, note`

- `status`: `found`, `not_found`, or `error` (unreadable PDF; the message is in `note`)
- `value`: parsed number; `raw_value`: the cell text as printed
- `unit`: unit declared on the page (`thousands`, `lakhs`, ...) or `base` after `--normalize-units`
- `source`: `ruled` (grid lines), `text` (whitespace-aligned) or `ocr` (read from a scanned page)
- Optional columns, present only when you ask for them: `confidence`, `check`, `check_note`
  (`--validate`), `row_text` (`--evidence`), `alternatives` (`--explain`)

## Can I trust this value? Validation, evidence, explain

A value can be read correctly and still be the *wrong* value (a neighbouring row, another column).
Tables often contain their own proof, so `--validate` uses it:

```bash
tabledig extract report.pdf --attr "Total income" --attr "Revenue" --validate --evidence --explain
```

- **`check`**: for rows labelled *Total / Subtotal / Grand total* it tests whether the numbers equal the
  rows above (allowing rounding, `(brackets)` negatives and subtotal roll-ups), and whether
  *total assets* equals *total equity and liabilities*. Tables that continue on later pages are joined;
  percentage, rate and ratio columns are skipped. Result: `verified` (all additive columns add up),
  `partial` (some do not, `check_note` says which), `mismatch`, or `unchecked` (nothing to compare against,
  which is true of most rows).
- **`confidence`**: a simple 0-1 heuristic (match score, raised when verified, lowered on partial,
  mismatch or OCR). It is a ranking aid, not a calibrated probability.
- **`--evidence`** adds the whole source row; **`--explain`** lists the runner-up labels that lost.

On the real PDFs in the evaluation, the totals of a 22-column table and of a 16-page report both verify.

## Beyond plain tables

If a row is not in any detected table, tabledig falls back to **key-value reading** of the page text:
- a number printed *before* its label (`327 BALLOTS CAST`);
- several blocks side by side on one line or page column (`Presentes 217 0 217   Votos Afirmativos 129 ...`);
- dot-leader rows (`Stabilizer wiring change ........ Up to $3,790 ...... Up to $766,865.`).

Real tables always win; these rows are used only when nothing else matches, are marked `source = kv`, and
get a slightly lower confidence. Row labels may also be ranges or bands such as `12-19` or `65+`, and
European numbers (`1.393,4`, `(35,8)`) are understood.

## Scanned PDFs (OCR)

```bash
pip install "tabledig[ocr]"      # plus the Tesseract program: apt/brew install tesseract, or the Windows installer
tabledig extract scan.pdf --attr "Total income" --validate
```

Pages with no text layer are rendered, table borders are erased, and the page is read with Tesseract,
then parsed like any other borderless table (`source` = `ocr`). Without the extra, a scanned file returns
`not_found` with a note saying why. `--ocr off|auto|on` and `--ocr-lang eng+deu` control it.
OCR can misread digits, so combine it with `--validate`.
*Honest status:* OCR is tested on synthetic scans (the sample PDFs rendered to images at 300 dpi), not yet
on a corpus of real, noisy scans.

## Benchmark (synthetic)

`benchmarks/run_benchmark.py` generates a seeded corpus of fictional PDFs - bordered statements,
borderless statements and invoices, with units, negative formats, Indian number grouping, a "Note"
column, look-alike distractor rows and typos in 25% of labels - and scores value-level precision and
recall against known answers.

```bash
python benchmarks/run_benchmark.py --n 60 --seed 7
```

| Queries | Docs | Precision | Recall |
| --- | ---: | ---: | ---: |
| name only (`"Net profit"`) | 60 | 81.8% | 35.0% |
| with aliases (`"Net profit"` + the wordings you expect) | 60 | 100.0% | 100.0% |

How to read it:

- **Synthetic, so optimistic.** It tests controlled layout, wording and typo variation. It is *not* a
  claim about accuracy on arbitrary real-world PDFs.
- **Aliases matter.** Matching is lexical, so "Net profit" cannot find "Profit for the year" on its own.
  Name-only recall is low for exactly that reason; listing the wordings fixes it.
- **Short generic names are risky.** Most name-only false positives come from the one-word query "Tax"
  matching "Tax paid" or "Profit before tax". Use longer names, aliases or `mode: exact` for those.
- A smaller version of this benchmark runs in the test suite as a regression guard.

## How it works

```
PDF --pdfplumber--> tables (ruled -> text fallback) --> header + unit detection
                                   |
 attributes --> score each row label (exact / contains / fuzzy + aliases)
                                   |
                best row(s) --> parse numbers --> records --> CSV / JSON / XLSX / DataFrame
```

Source layout: `reader.py` (tables), `matcher.py` (scoring), `normalize.py` (numbers, units),
`extractor.py` (engine), `config.py` (attribute files), `output.py`, `cli.py`; `app/` holds the
Streamlit demo and `benchmarks/` the benchmark.

## Evaluation on real documents

100 hand-checked cases on real public documents, run in CI: 81 on PDFs from three MIT-licensed test suites
([pdfplumber](https://github.com/jsvine/pdfplumber), [Camelot](https://github.com/camelot-dev/camelot),
[tabula-java](https://github.com/tabulapdf/tabula-java)) and 19 on scanned receipts (CC0). Files are fetched at
pinned commits and not stored here; expected values were read off the printed pages, not produced by tabledig.

| Group | Cases | Passing now | First blind run |
| --- | ---: | ---: | --- |
| PDFs, tuned | 20 | 20 | (code was fixed against these) |
| PDFs, held-out rounds 1-2 | 16 | 16 | 3/7, then 7/9 |
| PDFs, held-out rounds 3-4 | 45 | 45 | 17/21, then 24/24 |
| Scanned receipts, tuned | 12 | 10 | - |
| Scanned receipts, held-out | 7 | 6 | 6/7 |

**97 of 100 pass now.** Read the "passing now" column honestly: it is flattered by fixes made after looking.
The first blind runs (43%, 78%, 81%, 100% on later rounds drawn from similar layouts) are the better guide to a
new document. Across 361 PDFs in the three suites, asking for 3 attributes that do not exist produced
**0 false matches**, at about 0.2 s per PDF. A head-to-head against pdfplumber and Camelot lookups on the
same cases, with its caveats, is in [docs/benchmark.md](docs/benchmark.md).

## Tested beyond finance

The extractor is not tied to financial statements. Besides the synthetic benchmark, it was spot-checked
against public third-party PDFs (FBI firearm background-check tables, a California WARN layoff report,
a Chinese-language land-use standard): values were compared with the printed numbers and matched,
including a 22-column table and a multi-page table whose header appears only on page 1. The test suite also
builds prose-plus-table documents (lab results, sales by region, price lists, German-format statements) and
checks that numbers written in the narrative are never returned. Those third-party PDFs are not included
in this repository.

## Limitations

- Scanned PDFs need the optional OCR extra and Tesseract (see above). On 19 real receipts forced OCR read the
  right total 16 times; garbled digits and white-on-black print are the known failures.
- Borderless tables without a recognisable header get generic column names (`col_2`, `col_3`...).
- Free-form prose ("revenue rose 12% to $4.2m") is deliberately not read: a sentence has no row structure.
- PDFs whose text layer has no spaces between words (some government exports) cannot be matched by label.
- Matching is lexical; it will not know that "turnover" means "revenue" unless you add an alias.

## Roadmap

The plan to make this the best open-source tool for named-value extraction from PDF tables
(trust and validation, harder layouts, scans, smarter matching, PyPI 1.0) is in
[ROADMAP.md](ROADMAP.md), with measurable targets.

## Development

```bash
pip install -e ".[dev,excel]"
python examples/make_sample_pdfs.py   # regenerate the fictional sample PDFs
pytest
ruff check .
```

The sample PDFs are generated from fictional data; the project ships no real company data.

## License

MIT - see [LICENSE](LICENSE).
