# Command line

```text
tabledig extract FILE_OR_FOLDER... [options]
tabledig inspect FILE.pdf              show detected tables
tabledig schema                        JSON Schema of the json output
```

| Option | Meaning |
|---|---|
| `--attr "Net profit=PAT\|Profit after tax"` | attribute with aliases (repeatable); `Name @ Section` scopes to a heading |
| `-a FILE` | attribute file (.yaml, .json, .csv) |
| `--pack finance\|healthcare\|sports\|government\|all` | built-in synonym packs |
| `--suggest`, `--memory FILE`, `--remember` | near-miss aliases; reuse accepted ones |
| `--column NAME` / `--column latest` | keep matching column(s) only |
| `--validate`, `--evidence`, `--explain` | totals check + confidence; source row; runner-up labels |
| `--ocr auto\|on\|force\|off`, `--ocr-lang` | scanned pages |
| `--decimal auto\|dot\|comma`, `--normalize-units` | number handling |
| `--cache DIR` | resumable batches |
| `--password`, `--workers N`, `--wide`, `-o OUT.{csv,json,xlsx}` | misc |
