"""Number parsing and unit detection."""
from __future__ import annotations

import re
from typing import Optional

from .models import Unit

_DASHES = {"-", "--", "–", "—", "nil", "n/a-", "—-"}
_CURRENCY = re.compile(r"(?i)(?:\brs\.?|\binr\b|\busd\b|\beur\b|\bgbp\b|us\$|[₹$€£])")
_PLAIN_NUMBER = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)")
YEAR_LIKE = re.compile(r"^(?:19|20)\d{2}$")

_UNIT_SCALES = {
    "thousand": 1e3,
    "000": 1e3,
    "lakh": 1e5,
    "lac": 1e5,
    "crore": 1e7,
    "million": 1e6,
    "mn": 1e6,
    "billion": 1e9,
    "bn": 1e9,
}
_UNIT_NAMES = {
    "thousand": "thousands",
    "000": "thousands",
    "lakh": "lakhs",
    "lac": "lakhs",
    "crore": "crores",
    "million": "millions",
    "mn": "millions",
    "billion": "billions",
    "bn": "billions",
}

_UNIT_PATTERNS = (
    re.compile(
        r"\b(?:in|figures\s+in|amounts?\s+in)\s+(?:(?:inr|usd|rs\.?|eur|gbp|[₹$€£])\s*)?"
        r"['’]?(thousands?|000s?|lakhs?|lacs?|crores?|millions?|mn|billions?|bn)\b",
        re.IGNORECASE,
    ),
    re.compile(r"['’(]\s*(000)s?\b", re.IGNORECASE),
)


_SPACED_THOUSANDS = re.compile(r"\d{1,3}(?:[ '](?:\d{3}))+(?:[.,]\d+)?")


def _normalize_separators(s: str, decimal: Optional[str]) -> str:
    """Turn ``1,234.56`` / ``1.234,56`` / ``1 234,56`` / ``1'234.56`` into ``1234.56``.

    ``decimal`` is ``"."``, ``","`` or ``None`` (auto-detect). Auto mode treats a lone comma
    followed by exactly three digits as a thousands separator (``1,234`` = 1234) and any
    other lone comma as a decimal comma (``12,5`` = 12.5).
    """
    s = s.replace("\u00a0", " ").replace("\u202f", " ").replace("’", "'")
    if _SPACED_THOUSANDS.fullmatch(s):
        s = re.sub(r"[ ']", "", s)
    if decimal == ",":
        return s.replace(".", "").replace(",", ".")
    if decimal == ".":
        return s.replace(",", "")
    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        if s.rfind(",") > s.rfind("."):  # 1.234,56
            return s.replace(".", "").replace(",", ".")
        return s.replace(",", "")  # 1,234.56 and Indian 12,34,567.50
    if has_comma:
        parts = s.split(",")
        if len(parts) == 2 and (len(parts[1]) != 3 or parts[0] in {"0", ""}):
            return parts[0] + "." + parts[1]  # 12,5  /  1234,56  /  0,500
        return s.replace(",", "")  # 1,234  /  12,34,567
    if has_dot and re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}", s):
        return s.replace(".", "")  # 1.234.567
    return s


def parse_number(text: object, decimal: Optional[str] = None) -> Optional[float]:
    """Parse a table cell into a float, or ``None`` if it is not a number.

    Handles thousands separators (``1,234``, Indian ``12,34,567``, European ``1.234,56``,
    spaced ``1 234`` and Swiss ``1'234``), negatives in parentheses (``(1,200)``), trailing
    minus, currency symbols, percent signs and dash placeholders (treated as zero).
    Pass ``decimal=","`` or ``"."`` to force the decimal mark instead of auto-detecting it.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    if s.lower() in _DASHES:
        return 0.0

    s = _CURRENCY.sub("", s).strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        if s.endswith("%)"):  # "(8%)" is a rate in a label, not a negative value
            return None
        negative = True
        s = s[1:-1].strip()
    if s.startswith(("-", "−", "–")):
        negative = True
        s = s[1:].strip()
    if s.endswith("-") and len(s) > 1:
        negative = True
        s = s[:-1].strip()
    s = _normalize_separators(s.rstrip("%").strip(), decimal)

    if not _PLAIN_NUMBER.fullmatch(s):
        return None
    value = float(s)
    return -value if negative else value


def is_year_like(token: str) -> bool:
    return bool(YEAR_LIKE.match(token.strip()))


def detect_unit(text: str) -> Optional[Unit]:
    """Find a declared unit such as ``(INR in lakhs)`` or ``USD in millions``."""
    if not text:
        return None
    for pattern in _UNIT_PATTERNS:
        match = pattern.search(text)
        if match:
            word = match.group(1).lower().rstrip("s")
            if word in _UNIT_SCALES:
                return Unit(_UNIT_NAMES[word], _UNIT_SCALES[word])
    return None


_RANGE_LABEL = re.compile(
    r"^(?:[<>\u2264\u2265]\s*)?\d[\d,.]*\s*(?:[-\u2013\u2014]\s*\d[\d,.]*|\+)\s*\S*$|^[<>\u2264\u2265]\s*\d[\d,.]*$"
)


def is_labelish(text: str) -> bool:
    """True if a cell can name a row: it has letters, or it is a range/band such as ``12-19`` or ``65+``."""
    text = str(text).strip()
    if not text:
        return False
    if any(ch.isalpha() for ch in text):
        return True
    return bool(_RANGE_LABEL.match(text)) and parse_number(text) is None
