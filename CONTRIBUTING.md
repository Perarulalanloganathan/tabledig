# Contributing

Thanks for helping! Bug reports with a small (non-confidential) PDF or a description of the table
layout are the most useful thing you can send.

## Setup

```bash
git clone https://github.com/Perarulalanloganathan/tabledig.git
cd tabledig
pip install -e ".[dev,excel]"
python examples/make_sample_pdfs.py
pytest && ruff check .
```

## Guidelines

- Add a test with every behaviour change; tests build their own fictional PDFs (see `tests/conftest.py`).
- Never commit real company documents or extraction output - use generated or public-domain samples.
- Keep the core dependency list small (`pdfplumber`, `pyyaml`); heavier matchers should be optional extras.
