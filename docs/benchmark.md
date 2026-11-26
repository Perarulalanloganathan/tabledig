# Head-to-head: tabledig vs. a hand-written lookup

`python benchmarks/head_to_head.py` runs the same real-document cases through the obvious alternatives:
extract the tables with a library, find the row whose first cell equals the attribute (ignoring case and
spacing), read the numbers after it. The baselines use tabledig's own number parser, so they are never
penalised for `1,234` or `(5)`. A case passes if the returned values start with the expected values.

| tool | tuned (n=15) | held-out (n=61) |
|---|---:|---:|
| pdfplumber `extract_tables()` + lookup | 6 (40%) | 8 (13%) |
| pdfplumber + a regex over text lines | 11 (73%) | 55 (90%) |
| Camelot 2.2 (lattice, then stream) + lookup | 8 (53%) | 50 (82%) |
| **tabledig** | 15 (100%) | 61 (100%) |

Numbers are from the CI run (Camelot 2.2; Camelot 1.0.9 scored 10/15 on the tuned group). 76 cases; the 5 cases that select a column are left out because a plain lookup cannot express them.

## Read this carefully

* **tabledig's held-out column is after fixes.** Its first blind runs on the held-out rounds were 3/7, 7/9,
  17/21 and 24/24 (round 4 mostly reused round 3's documents, so it was easier). The baselines were not tuned
  against any case. The fair summary is: on a *new* document tabledig's first-try rate is roughly 80-90%
  in these rounds, comparable to the best simple baseline, and it improves as failure classes are fixed.
* **The gap to the simple text baseline is about ten points, not eighty.** Much of what tabledig adds is
  not measured by "did the right number come back": fuzzy and Unicode label matching, aliases and packs,
  dash/negative/European number formats, column and section selection, validation of totals, a confidence
  value, OCR, and refusing to invent a value (0 false matches over 361 PDFs).
* **The cases were written by the project, not by an independent party,** on public test documents that
  skew towards government statistics and Indian/US/EU tables. They are a reasonable regression suite and
  a poor estimate of any particular organisation's documents. Run it on yours.
* **Camelot and pdfplumber are general table extractors,** not attribute finders; this compares workflows
  ("get me the Revenue row"), not the quality of their table detection.

## Reproduce

```bash
pip install "tabledig[dev]" camelot-py
python benchmarks/head_to_head.py
```
