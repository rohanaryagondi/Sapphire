"""Vector store with a deterministic offline fallback.

Production would use real embeddings (sentence-transformers / hosted embedding
API) backed by a vector DB, and ideally a graph store (Microsoft GraphRAG style)
for multi-hop questions. To keep the scaffold runnable WITHOUT any API keys or
heavy ML dependencies, we ship a pure-Python TF-IDF index as the default.

If `sentence-transformers` happens to be installed, we *could* swap it in, but
the default path requires nothing beyond the standard library so `run.py` works
on a clean machine.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .sources import Chunk

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class ScoredChunk:
    chunk: Chunk
    similarity: float  # raw semantic/lexical similarity in [0, 1]


class TfidfIndex:
    """Minimal, deterministic TF-IDF cosine index.

    Deterministic + dependency-free is the whole point: the scaffold must run
    offline and produce the same output every time for the eval harness.
    """

    def __init__(self, chunks: Sequence[Chunk]):
        self.chunks: List[Chunk] = list(chunks)
        self._doc_tokens: List[Counter] = [Counter(_tokenize(c.text)) for c in self.chunks]
        self._idf = self._compute_idf(self._doc_tokens)
        self._doc_vectors = [self._tfidf(tokens) for tokens in self._doc_tokens]
        self._doc_norms = [math.sqrt(sum(v * v for v in vec.values())) for vec in self._doc_vectors]

    @staticmethod
    def _compute_idf(doc_tokens: Sequence[Counter]) -> dict:
        n_docs = len(doc_tokens)
        df: Counter = Counter()
        for tokens in doc_tokens:
            for term in tokens:
                df[term] += 1
        # Smoothed idf so a term appearing everywhere still contributes a little.
        return {term: math.log((1 + n_docs) / (1 + freq)) + 1.0 for term, freq in df.items()}

    def _tfidf(self, tokens: Counter) -> dict:
        total = sum(tokens.values()) or 1
        return {term: (count / total) * self._idf.get(term, 0.0) for term, count in tokens.items()}

    def query(self, text: str, top_k: int = 10) -> List[ScoredChunk]:
        q_tokens = Counter(_tokenize(text))
        if not q_tokens:
            return []
        q_vec = self._tfidf(q_tokens)
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scored: List[ScoredChunk] = []
        for chunk, dvec, dnorm in zip(self.chunks, self._doc_vectors, self._doc_norms):
            if dnorm == 0:
                continue
            # Cosine similarity over the smaller of the two vectors.
            dot = sum(q_vec.get(term, 0.0) * weight for term, weight in dvec.items())
            sim = dot / (q_norm * dnorm)
            if sim > 0:
                scored.append(ScoredChunk(chunk=chunk, similarity=sim))

        scored.sort(key=lambda s: s.similarity, reverse=True)
        return scored[:top_k]


def build_index(chunks: Sequence[Chunk]) -> TfidfIndex:
    """Factory so callers don't depend on the concrete backend class."""
    return TfidfIndex(chunks)
