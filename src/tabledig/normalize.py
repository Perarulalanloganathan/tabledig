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


def parse_number(text: object) -> Optional[float]:
    """Parse a table cell into a float, or ``None`` if it is not a number.

    Handles thousands separators (``1,234`` and Indian ``12,34,567``), negatives
    in parentheses (``(1,200)``), trailing minus, currency symbols, percent signs
    and dash placeholders (treated as zero).
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
    s = s.rstrip("%").strip().replace(",", "")

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
