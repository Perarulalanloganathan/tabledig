# Why did it not match?

Start with what tabledig actually sees:

```bash
tabledig inspect report.pdf            # every detected table, with headers and rows
tabledig extract report.pdf --attr "Revenue" --explain --evidence --validate
```

`--explain` shows the runner-up labels, `--evidence` shows the whole source row, `--validate` says whether
totals add up.

| Symptom | Likely cause | What to do |
|---|---|---|
| `not_found`, but the row is on the page | The PDF words it differently ("Turnover") | `tabledig extract ... --suggest` lists near-miss rows; add an alias, or use `--pack finance` |
| `not_found` and the PDF is a scan | No text layer | Install Tesseract and `pip install "tabledig[ocr]"`; use `--ocr force` for scans that already carry a poor text layer |
| `not_found` for a short name ("TO", "P") | One- and two-letter names match whole words only | Use the full wording as an alias |
| Wrong row picked ("Sub Total" instead of "Total") | Both score alike for the query | Set `mode: exact` for that attribute in an attribute file, or raise `--min-score`; check with `--explain` |
| Value is right but the wrong column | Several periods in one row | `--column "FY 2024"` or `--column latest` |
| Same label in several sections | Repeated headings | `--attr "Revenue @ Segment information"` |
| Numbers off by a thousand | "in thousands" header | `--normalize-units` |
| `1.234,56` read as `1.23456` | Decimal comma | `--decimal comma` |
| `check: mismatch` | A total does not equal the sum of its rows; often an OCR or layout error | Look at the page; do not trust the value blindly |
| `Could not read this PDF: ... password` | Encrypted file | `--password` |

Two things tabledig will not do: invent a value for a label that is not on the page, and silently pick a
low-score guess. If you set `--min-score` low, read `score` and `confidence` before trusting a row.
