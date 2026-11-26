"""Optional resolvers for rows the lexical matcher cannot find.

A resolver is any callable ``resolver(attribute, labels) -> (index, score) | None`` that picks one of the
row labels tabledig already found (``labels[index]``) and says how sure it is (0-100). It can never
supply a value: the number always comes from the PDF row it picked. Records it produces carry
``method`` = the resolver's ``method`` ("semantic", "llm", ...) and a lower confidence, so they are easy to
filter out or review.

Built in: :class:`SemanticResolver` (local embeddings, ``pip install "tabledig[semantic]"``).
Bring your own: wrap any model, see ``docs/fallback.md``.
"""
from __future__ import annotations

from math import sqrt
from typing import Callable, Optional, Sequence

from .models import Attribute

Resolver = Callable[[Attribute, Sequence[str]], Optional[tuple[int, float]]]

# Scores from resolvers are capped so a fallback match can never look as certain as a lexical one.
MAX_FALLBACK_SCORE = 75.0


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = sqrt(sum(x * x for x in a)), sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class SemanticResolver:
    """Pick the row whose label is closest in meaning to the attribute ("turnover" ~ "revenue").

    ``threshold`` is the minimum cosine similarity (0-1). ``embedder`` maps a list of texts to vectors;
    by default a small local ONNX model via ``fastembed`` is loaded on first use.
    """

    method = "semantic"

    def __init__(
        self,
        threshold: float = 0.80,
        model: str = "BAAI/bge-small-en-v1.5",
        embedder: Optional[Callable[[list[str]], list[Sequence[float]]]] = None,
    ) -> None:
        self.threshold = threshold
        self.model = model
        self._embedder = embedder
        self._cache: dict[str, Sequence[float]] = {}

    def _embed(self, texts: list[str]) -> list[Sequence[float]]:
        if self._embedder is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise RuntimeError('semantic matching needs: pip install "tabledig[semantic]"') from exc
            engine = TextEmbedding(model_name=self.model)
            self._embedder = lambda items: [list(v) for v in engine.embed(items)]
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            for text, vec in zip(missing, self._embedder(missing)):
                self._cache[text] = vec
        return [self._cache[t] for t in texts]

    def scores(self, attribute: Attribute, labels: Sequence[str]) -> list[float]:
        """Best cosine similarity of each label to the attribute's name or aliases."""
        vectors = self._embed([*attribute.names, *labels])
        names, rows = vectors[: len(attribute.names)], vectors[len(attribute.names) :]
        return [max(cosine(n, r) for n in names) for r in rows]

    def __call__(self, attribute: Attribute, labels: Sequence[str]) -> Optional[tuple[int, float]]:
        if not labels:
            return None
        sims = self.scores(attribute, labels)
        best = max(range(len(sims)), key=sims.__getitem__)
        if sims[best] < self.threshold:
            return None
        return best, min(MAX_FALLBACK_SCORE, sims[best] * 100)
