"""Credibility + recency weighted retrieval.

We take the raw semantic similarity from the index and re-rank by a composite
score that folds in source credibility and recency, mirroring the dynamic
source-weighting + recency-modality ideas from financial-sentiment pipelines.

    final = similarity^a * credibility_weight^b * recency_weight^c

All exponents are configurable so the weighting policy is tunable, not baked in.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import List, Optional

from .store import ScoredChunk, TfidfIndex


@dataclass
class RetrievalConfig:
    top_k: int = 5
    candidate_k: int = 25          # how many to pull before re-ranking
    similarity_exp: float = 1.0    # a
    credibility_exp: float = 1.0   # b
    recency_exp: float = 0.5       # c
    recency_halflife_days: float = 540.0  # ~18 months
    min_final_score: float = 0.0   # below this we treat sources as "thin"


@dataclass
class RankedChunk:
    scored: ScoredChunk
    recency_weight: float
    final_score: float


def _recency_weight(published: Optional[_dt.date], halflife_days: float, today: _dt.date) -> float:
    """Exponential decay by age. Undated content is treated as moderately stale."""
    if published is None:
        return 0.5
    age_days = max(0, (today - published).days)
    return 0.5 ** (age_days / halflife_days)


def retrieve(
    index: TfidfIndex,
    question: str,
    config: Optional[RetrievalConfig] = None,
    today: Optional[_dt.date] = None,
) -> List[RankedChunk]:
    """Return chunks re-ranked by the composite credibility/recency score."""
    config = config or RetrievalConfig()
    today = today or _dt.date.today()

    candidates = index.query(question, top_k=config.candidate_k)
    ranked: List[RankedChunk] = []
    for sc in candidates:
        rec = _recency_weight(sc.chunk.published, config.recency_halflife_days, today)
        final = (
            (sc.similarity ** config.similarity_exp)
            * (sc.chunk.credibility_weight ** config.credibility_exp)
            * (rec ** config.recency_exp)
        )
        ranked.append(RankedChunk(scored=sc, recency_weight=rec, final_score=final))

    ranked.sort(key=lambda r: r.final_score, reverse=True)
    return ranked[: config.top_k]
