"""Streamlit demo for tabledig.

Run locally:
    pip install -e ".[app]"
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from tabledig import Extractor, parse_attribute_lines, read_tables
from tabledig.output import records_to_wide

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = {
    "Income statement (bordered table, 'in thousands')": {
        "path": ROOT / "examples" / "sample_income_statement.pdf",
        "attributes": (
            "Revenue from operations\n"
            "Net profit = Profit for the year | PAT\n"
            "Staff cost = Employee benefits expense\n"
            "Finance costs\n"
            "Dividend paid"
        ),
    },
    "Invoice (borderless table)": {
        "path": ROOT / "examples" / "sample_invoice.pdf",
        "attributes": "Subtotal\nTax = Sales tax\nTotal = Total due\nShipping\nPostage",
    },
}

st.set_page_config(page_title="tabledig demo", page_icon="🔎", layout="wide")


@st.cache_data(show_spinner="Reading tables from the PDF...")
def load_tables(data: bytes):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(data)
        handle.flush()
        return read_tables(handle.name)


def table_to_frame(table) -> pd.DataFrame:
    width = max([len(r) for r in table.rows] + [len(table.header)])
    names, seen = [], {}
    for i in range(width):
        name = table.header[i] if i < len(table.header) and table.header[i] else f"col_{i + 1}"
        seen[name] = seen.get(name, 0) + 1
        names.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    rows = [r + [""] * (width - len(r)) for r in table.rows]
    return pd.DataFrame(rows, columns=names)


def run_extraction(tables, file_name, attributes, min_score, top_k, normalize_units):
    extractor = Extractor(
        attributes, min_score=min_score, top_k=top_k, normalize_units=normalize_units
    )
    return extractor.extract_tables(tables, file_name)


# ---- header ---------------------------------------------------------------
st.title("🔎 tabledig")
st.markdown(
    "Give it a table-style PDF and the **names** of the things you want. "
    "It finds those rows and returns their values, with the page, column and match score. "
    "[Source on GitHub](https://github.com/Perarulalanloganathan/tabledig)"
)

# ---- sidebar --------------------------------------------------------------
with st.sidebar:
    st.header("Matching options")
    min_score = st.slider(
        "Minimum match score", 50, 100, 80, help="Lower = more forgiving, more false matches"
    )
    top_k = st.number_input("Rows to keep per attribute", 1, 5, 1)
    normalize_units = st.checkbox(
        "Convert to base units", help="Applies 'in thousands / lakhs / millions' declared in the PDF"
    )
    wide = st.checkbox("Wide layout (one column per table column)", value=True)
    st.caption("Files are processed in memory for this session only.")

# ---- input ----------------------------------------------------------------
source = st.radio("PDF source", ["Try a sample", "Upload my own"], horizontal=True)

data, file_name, default_attrs = None, "", ""
if source == "Try a sample":
    choice = st.selectbox("Sample", list(SAMPLES))
    sample = SAMPLES[choice]
    data, file_name = sample["path"].read_bytes(), sample["path"].name
    default_attrs = sample["attributes"]
else:
    upload = st.file_uploader("PDF with tables (text-based, not scanned)", type="pdf")
    if upload is not None:
        data, file_name = upload.getvalue(), upload.name
    default_attrs = "Revenue\nNet profit = Profit for the year | PAT"

attr_text = st.text_area(
    "Attributes to extract (one per line)",
    value=default_attrs,
    height=150,
    key=f"attrs-{source}-{file_name}",
    help="Optional aliases after '=', separated by '|'.  Example:  Net profit = Profit for the year | PAT",
)

if data is None:
    st.info("Upload a PDF to begin, or switch to a sample.")
    st.stop()

attributes = parse_attribute_lines(attr_text)
if not attributes:
    st.warning("Add at least one attribute name.")
    st.stop()

# ---- run ------------------------------------------------------------------
try:
    tables = load_tables(data)
except Exception as exc:  # unreadable / encrypted PDF
    st.error(f"Could not read this PDF: {exc}")
    st.stop()

if not tables:
    st.warning(
        "No tables were detected. The PDF may be scanned (needs OCR) or contain no tabular data."
    )
    st.stop()

records = run_extraction(tables, file_name, attributes, float(min_score), int(top_k), normalize_units)
found = {r.attribute for r in records if r.status == "found"}
missing = [a.name for a in attributes if a.name not in found]

c1, c2, c3 = st.columns(3)
c1.metric("Tables detected", len(tables))
c2.metric("Attributes found", f"{len(found)} / {len(attributes)}")
c3.metric("Not found", len(missing))

tab_results, tab_tables, tab_json = st.tabs(["Results", "Detected tables", "JSON"])

with tab_results:
    if wide:
        fieldnames, rows = records_to_wide(records)
        frame = pd.DataFrame(rows, columns=fieldnames)
        # values first, bookkeeping last, so the numbers are visible without scrolling
        meta = {"file", "attribute", "matched_label", "page", "unit", "score", "status", "note"}
        values = [c for c in frame.columns if c not in meta]
        order = ["attribute", "matched_label", *values, "page", "unit", "score", "status"]
        if frame["file"].nunique() > 1:
            order.insert(0, "file")
        frame = frame[[c for c in order if c in frame.columns]]
    else:
        frame = pd.DataFrame([r.as_dict() for r in records])
    st.dataframe(frame, use_container_width=True, hide_index=True)
    if missing:
        st.caption(
            "Not found: " + ", ".join(missing) + ". Try an alias with the exact wording from the "
            "PDF (see 'Detected tables'), or lower the minimum score."
        )
    st.download_button(
        "Download CSV", frame.to_csv(index=False).encode("utf-8"), f"{Path(file_name).stem}_extracted.csv"
    )

with tab_tables:
    st.caption("Every table tabledig found. Use the exact row labels here as attribute names or aliases.")
    for table in tables:
        unit = f" · unit: {table.unit.name}" if table.unit else ""
        with st.expander(f"Page {table.page} · table {table.index} · {table.source}{unit}", expanded=False):
            st.dataframe(table_to_frame(table), use_container_width=True, hide_index=True)

with tab_json:
    st.json(json.loads(json.dumps([r.as_dict() for r in records], default=str)), expanded=False)
