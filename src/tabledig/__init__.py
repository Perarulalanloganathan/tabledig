"""tabledig - pull named attributes out of table-style PDFs."""
from .config import load_attributes, load_config, parse_attribute_line, parse_attribute_lines
from .extractor import Extractor, extract
from .models import Attribute, Record, Table, Unit
from .output import to_dataframe, write_records
from .reader import read_tables

__version__ = "0.4.0"

__all__ = [
    "Attribute",
    "Extractor",
    "Record",
    "Table",
    "Unit",
    "extract",
    "load_attributes",
    "load_config",
    "parse_attribute_line",
    "parse_attribute_lines",
    "read_tables",
    "to_dataframe",
    "write_records",
]
