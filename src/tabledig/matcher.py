"""Label matching: exact, contains and fuzzy scoring (no external deps)."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_STOP = {"of", "the", "and", "to", "for", "on", "in", "a", "an"}
_LEADING_INDEX = re.compile(r"^\s*\(?[a-z0-9]{1,3}[.)]\s+", re.IGNORECASE)


def normalize_label(text: str) -> str:
    """Lower-case, drop accents, list numbering and punctuation; collapse whitespace.

    Works for any script: ``"Résultat net"`` -> ``"resultat net"`` and Chinese, Cyrillic or Greek
    labels are kept (only punctuation is removed).
    """
    s = _LEADING_INDEX.sub("", str(text))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold().replace("&", " and ")
    s = re.sub(r"[\W_]+", " ", s)
    return s.strip()


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokens(normalized: str) -> list[str]:
    return [_stem(t) for t in normalized.split() if t not in _STOP]


def _contiguous(needle: list[str], haystack: list[str]) -> bool:
    n = len(needle)
    if n == 0 or n > len(haystack):
        return False
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def score_label(query: str, label: str, mode: str = "fuzzy") -> tuple[float, str]:
    """Score how well ``label`` matches ``query`` (0-100) and say how.

    Modes
    -----
    exact     only identical text after normalisation
    contains  query words appear, in order, inside the label
    fuzzy     word overlap blended with character similarity (typo tolerant)
    """
    q = normalize_label(query)
    lab = normalize_label(label)
    if not q or not lab:
        return 0.0, "none"
    if q == lab:
        return 100.0, "exact"
    if mode == "exact":
        return 0.0, "none"

    q_tokens, l_tokens = tokens(q), tokens(lab)
    if q_tokens and q_tokens == l_tokens:
        return 99.0, "normalized"

    if mode == "contains":
        if _contiguous(q_tokens, l_tokens):
            return 90.0, "contains"
        if not q.isascii() and q in lab:  # scripts written without spaces (e.g. Chinese)
            return 90.0, "contains"
        return 0.0, "none"

    if len(q.replace(" ", "")) <= 2 and q.isascii():
        return 0.0, "none"  # initials like "P" or "TO" must match whole words, never fuzzily

    # fuzzy
    q_set, l_set = set(q_tokens), set(l_tokens)
    overlap = len(q_set & l_set)
    token_score = 0.0
    if q_set and l_set:
        coverage = overlap / len(q_set)  # how much of the query is present
        precision = overlap / len(l_set)  # how much of the label is the query
        token_score = 100.0 * (0.7 * coverage + 0.3 * precision)
    char_score = 100.0 * SequenceMatcher(None, q, lab).ratio()

    if token_score >= char_score:
        return round(token_score, 2), "fuzzy"
    return round(char_score, 2), "fuzzy"
