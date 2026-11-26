"""Optional OCR for scanned PDFs (pages with no text layer).

Needs the ``ocr`` extra *and* the Tesseract program::

    pip install "tabledig[ocr]"
    # Tesseract: apt install tesseract-ocr | brew install tesseract | Windows: UB-Mannheim installer

The page is rendered to an image, recognised with Tesseract, and rebuilt as whitespace-aligned
text lines so the normal table reader can parse them. OCR can misread digits, so use
``validate=True`` (totals must add up) to catch mistakes.
"""
from __future__ import annotations

import statistics
from typing import Optional

INSTALL_HINT = (
    'scanned page (no text layer): install OCR with  pip install "tabledig[ocr]"  '
    "and the Tesseract program, or run ocrmypdf first"
)


def ocr_available() -> bool:
    """True when pytesseract is importable and the tesseract binary can be run."""
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def words_to_text(words: list[dict]) -> str:
    """Turn OCR words (``left, top, width, height, text, line key``) into spaced lines.

    Gaps wider than about two characters become runs of spaces, which is what the table
    reader uses to separate columns; narrower gaps are ordinary single spaces.
    """
    words = [w for w in words if w["text"].strip()]
    if not words:
        return ""
    char_w = statistics.median(max(w["width"], 1) / max(len(w["text"]), 1) for w in words)
    lines: dict[tuple, list[dict]] = {}
    for w in words:
        lines.setdefault(w["line"], []).append(w)
    ordered = sorted(lines.values(), key=lambda ws: statistics.mean(w["top"] + w["height"] / 2 for w in ws))
    out = []
    for ws in ordered:
        ws.sort(key=lambda w: w["left"])
        text = ws[0]["text"]
        for prev, cur in zip(ws, ws[1:]):
            gap = cur["left"] - (prev["left"] + prev["width"])
            text += (" " * max(2, round(gap / char_w)) if gap >= 2.0 * char_w else " ") + cur["text"]
        out.append(text)
    return "\n".join(out)


def _longest_runs(mask, axis: int):
    """Length of the longest run of True along ``axis`` for every row/column of a 2-D bool array."""
    import numpy as np

    arr = mask if axis == 1 else mask.T
    out = np.zeros(arr.shape[0], dtype=int)
    for i, line in enumerate(arr):
        if not line.any():
            continue
        padded = np.concatenate(([0], line.astype(np.int8), [0]))
        edges = np.flatnonzero(np.diff(padded))
        out[i] = int((edges[1::2] - edges[::2]).max())
    return out


def remove_rules(image, dpi: int = 300):
    """Erase long straight horizontal/vertical lines (table borders) so they do not confuse OCR."""
    import numpy as np
    from PIL import Image

    arr = np.array(image)
    dark = arr < 160
    min_run = int(dpi * 0.6)  # lines longer than ~0.6 inch; letters are far shorter
    h_runs = _longest_runs(dark, axis=1)
    v_runs = _longest_runs(dark, axis=0)
    rows = np.flatnonzero(h_runs >= min_run)
    cols = np.flatnonzero(v_runs >= min_run)
    for r in rows:
        arr[max(r - 1, 0) : r + 2, :] = 255
    for c in cols:
        arr[:, max(c - 1, 0) : c + 2] = 255
    return Image.fromarray(arr)


def ocr_page_text(page, lang: str = "eng", dpi: int = 300) -> str:
    """Run OCR on a pdfplumber page and return layout-preserving text."""
    import pytesseract

    image = page.to_image(resolution=dpi).original.convert("L")
    try:
        image = remove_rules(image, dpi)
    except ImportError:  # numpy missing: OCR still works, just less well on bordered tables
        pass
    data = pytesseract.image_to_data(
        image, lang=lang, config="--psm 6", output_type=pytesseract.Output.DICT
    )
    words = []
    for i, text in enumerate(data["text"]):
        if not text.strip() or float(data["conf"][i]) < 0:
            continue
        words.append(
            {
                "text": text,
                "left": data["left"][i],
                "top": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
                "line": (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
            }
        )
    return words_to_text(words)


def resolve_mode(mode: Optional[object]) -> str:
    """Normalise the ``ocr`` option to ``"auto"``, ``"on"`` or ``"off"``."""
    if mode in (None, "auto"):
        return "auto"
    if mode in (False, "off", "no", "false", "0"):
        return "off"
    if mode in (True, "on", "yes", "true", "1"):
        return "on"
    raise ValueError(f"ocr must be 'auto', 'on' or 'off', not {mode!r}")
