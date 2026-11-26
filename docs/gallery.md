# Gallery: real documents

Outputs below were produced by running tabledig on public test documents (the pdfplumber test suite, MIT,
and the CC0 `my-receipts` collection). Nothing is hand-edited except trimming columns for width.

## A 23-column government table

`tabledig extract nics-background-checks-2015-11.pdf --attr Alabama --evidence`

| attribute | column | value | score | source |
|---|---|---|---|---|
| Alabama | col_2 | 18,870 | 100 | ruled |
| Alabama | col_3 | 23,022 | 100 | ruled |
| Alabama | col_4 | 22,650 | 100 | ruled |

`--evidence` adds the whole source row so a person can verify it at a glance.

## A Chinese balance sheet

`extract(..., ["其他应付款"], validate=True)` (other payables)

| attribute | column | value | check | confidence |
|---|---|---|---|---|
| 其他应付款 | 期末余额 | 365,680,984.80 | unchecked | 1.0 |
| 其他应付款 | 期初余额 | 365,420,737.42 | unchecked | 1.0 |

Labels need not be English or Latin script.

## A scanned receipt

`tabledig extract dennys-20190420_009.pdf --attr Total --ocr force --validate`

| attribute | value | source | confidence |
|---|---|---|---|
| Total | 30.37 | ocr | 0.9 |

On 19 real receipts forced OCR read the right total 16 times (see `benchmarks/scan_eval.py`); the misses
are listed in the changelog. OCR values are capped at lower confidence than text-layer values.
