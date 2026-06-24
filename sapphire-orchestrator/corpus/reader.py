"""Stdlib corpus reader — corpus-first retrieval for Bucket-1 agents.

Each Bucket-1 agent MAY ship a pre-ingested knowledge corpus at
`sapphire-orchestrator/corpus/<agent_id>/index.jsonl` (one claim-card per line; see
`corpus/<agent>/METHOD.md`). At run time this reader loads that index and returns the
claim-cards whose text overlaps the query / entities — so the stable ~70% of an agent's
domain is answered locally and only the gap needs a live web/EMET call.

Deterministic, stdlib-only (`json`, `re`). No corpus dir → `[]` (agents without a corpus
are unchanged). No match → `[]` (honest empty — never fabricate a hit).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_CORPUS_ROOT = Path(__file__).resolve().parent

# Card fields whose text we match the query against (the agent's "lens" fields). Extra
# fields a card carries are ignored for matching but preserved in the returned card.
_MATCH_FIELDS = (
    "claim", "drug", "sponsor", "indication", "decision", "reason",
    "precedent_implication", "quote", "trial_id", "phase", "status",
    "termination_reason", "value", "field",
)

# Short function words excluded from query terms so matches reflect content, not glue.
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "of", "to",
    "in", "on", "for", "and", "or", "but", "with", "as", "at", "by", "from", "that",
    "this", "these", "those", "it", "its", "has", "have", "had", "do", "does", "did",
    "can", "could", "would", "should", "will", "shall", "may", "might", "must", "not",
    "no", "yes", "we", "you", "they", "i", "he", "she", "what", "which", "who", "how",
    "when", "where", "why", "viable", "target", "targets", "good", "bad", "any",
})

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-]*")


def _terms(text: str) -> set[str]:
    """Tokenise to lowercased content terms of length >= 3, minus stopwords."""
    return {
        t for t in _WORD_RE.findall((text or "").lower())
        if len(t) >= 3 and t not in _STOPWORDS
    }


def _corpus_dir(agent_id: str, base_dir: Path | None = None) -> Path:
    root = Path(base_dir) if base_dir is not None else _CORPUS_ROOT
    return root / agent_id


def has_corpus(agent_id: str, base_dir: Path | None = None) -> bool:
    """True if `corpus/<agent_id>/index.jsonl` exists."""
    return (_corpus_dir(agent_id, base_dir) / "index.jsonl").is_file()


def _load_cards(agent_id: str, base_dir: Path | None = None) -> list[dict]:
    """Load every valid claim-card from the agent's index.jsonl (skips blank/bad lines)."""
    path = _corpus_dir(agent_id, base_dir) / "index.jsonl"
    if not path.is_file():
        return []
    cards: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue  # a malformed line is skipped, never fabricated into a hit
            if isinstance(obj, dict):
                cards.append(obj)
    return cards


def _card_terms(card: dict) -> set[str]:
    parts = [str(card.get(k, "")) for k in _MATCH_FIELDS]
    return _terms(" ".join(parts))


def read_corpus(
    agent_id: str,
    query: str = "",
    entities: dict | None = None,
    *,
    top_n: int = 5,
    base_dir: Path | None = None,
) -> list[dict]:
    """Return the agent's claim-cards matching the query/entities, ranked by overlap.

    Parameters
    ----------
    agent_id  : the Bucket-1 agent whose `corpus/<agent_id>/index.jsonl` to read.
    query     : free-text query; tokenised into content terms.
    entities  : optional {"genes":[...], "diseases":[...], "drugs":[...]} — each value's
                terms are added to the query terms (gene symbols, disease/drug names).
    top_n     : cap on returned cards (highest overlap first).
    base_dir  : override the corpus root (tests point this at a fixture dir).

    Returns
    -------
    A list of the matching card dicts, best match first, capped to `top_n`. Each is a
    copy of the card with an internal `_score` (the overlap count) added for ranking
    transparency; `live_engine._corpus_card_to_fact` plucks only the named fact fields,
    so `_score` never reaches a dossier fact. `[]` when the agent has no corpus dir or no
    card overlaps (honest empty).
    """
    cards = _load_cards(agent_id, base_dir)
    if not cards:
        return []

    q_terms = set(_terms(query))
    ents = entities or {}
    for key in ("genes", "diseases", "drugs"):
        for v in ents.get(key, []) or []:
            q_terms |= _terms(str(v))
    if not q_terms:
        return []

    scored: list[tuple[int, int, dict]] = []
    for idx, card in enumerate(cards):
        overlap = len(q_terms & _card_terms(card))
        if overlap > 0:
            scored.append((overlap, idx, card))

    # Sort by overlap desc, then by original index asc (stable, deterministic).
    scored.sort(key=lambda t: (-t[0], t[1]))

    out: list[dict] = []
    for overlap, _idx, card in scored[: max(0, top_n)]:
        enriched = dict(card)
        enriched["_score"] = overlap
        out.append(enriched)
    return out
