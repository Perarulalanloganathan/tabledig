"""tabledig - pull named attributes out of table-style PDFs."""
__version__ = "0.8.0"

from .config import load_attributes, load_config, parse_attribute_line, parse_attribute_lines
from .extractor import Extractor, extract
from .models import Attribute, Record, Table, Unit
from .output import result_schema, to_dataframe, write_records
from .reader import read_tables

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
    "result_schema",
    "to_dataframe",
    "write_records",
]
