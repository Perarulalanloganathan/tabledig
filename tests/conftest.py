import importlib.util
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _load_generator():
    spec = importlib.util.spec_from_file_location("make_sample_pdfs", EXAMPLES / "make_sample_pdfs.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_sample_pdfs"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def income_pdf(tmp_path_factory):
    pytest.importorskip("reportlab")
    path = tmp_path_factory.mktemp("pdfs") / "income.pdf"
    _load_generator().income_statement(path)
    return path


@pytest.fixture(scope="session")
def invoice_pdf(tmp_path_factory):
    pytest.importorskip("reportlab")
    path = tmp_path_factory.mktemp("pdfs") / "invoice.pdf"
    _load_generator().invoice(path)
    return path
