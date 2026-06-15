"""Grounded, cited answer synthesis with calibrated abstention.

Design rule (from the proposal): EVERY claim must be grounded in a retrieved,
cited public source. We never rely on "pretend you are Dr. X" — persona
conditioning has shown near-zero/negative effect on task accuracy, so the
emulation is archetype/role-level and all substance comes from citations.

If an LLM API key is configured, a production build would pass the retrieved,
citation-tagged context to the model under a strict "answer ONLY from the
provided sources and cite each claim" instruction. With NO key (the default
offline path), we fall back to an EXTRACTIVE cited summary: we surface the
top-ranked source snippets verbatim, each with an inline citation. This keeps
the scaffold runnable and keeps the grounding guarantee intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .retrieve import RankedChunk


@dataclass
class Citation:
    marker: str          # e.g. "[1]"
    author: str
    venue: str
    url: str
    published: str
    credibility_tier: str
    on_record: bool


@dataclass
class Answer:
    question: str
    body: str
    citations: List[Citation]
    abstained: bool
    confidence: str       # "high" | "moderate" | "low" | "abstain"
    disagreement_note: str


# Thresholds for calibrated confidence/abstention. Deliberately conservative:
# thin or weak evidence should produce an explicit low-confidence/abstain signal
# rather than a confident-sounding hallucination.
_ABSTAIN_BELOW = 0.02      # best final_score below this -> abstain
_LOW_CONF_BELOW = 0.06
_MODERATE_CONF_BELOW = 0.15


def _first_sentences(text: str, max_chars: int = 320) -> str:
    """Trim a chunk to a citable excerpt without cutting mid-word."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    return (cut[:last_space] if last_space > 0 else cut).rstrip(",;") + " ..."


def _confidence(best_score: float) -> str:
    if best_score < _ABSTAIN_BELOW:
        return "abstain"
    if best_score < _LOW_CONF_BELOW:
        return "low"
    if best_score < _MODERATE_CONF_BELOW:
        return "moderate"
    return "high"


def _disagreement_note(ranked: List[RankedChunk]) -> str:
    """Surface multi-expert disagreement and off-record speculation.

    A core proposal requirement: the panel should expose disagreement rather
    than average it away. We flag when an off-record/low-tier source is in the
    mix so the reader can discount speculation accordingly.
    """
    authors = {r.scored.chunk.author for r in ranked}
    off_record = [r for r in ranked if not r.scored.chunk.on_record]
    notes = []
    if len(authors) > 1:
        notes.append(
            f"Retrieved views span {len(authors)} experts; treat any conflicting "
            "claims as genuine disagreement, not consensus."
        )
    if off_record:
        spec_authors = ", ".join(sorted({r.scored.chunk.author for r in off_record}))
        notes.append(
            f"At least one excerpt is OFF-RECORD/speculative ({spec_authors}) and is "
            "down-weighted; do not treat it as established guidance."
        )
    return " ".join(notes)


def synthesize(question: str, ranked: List[RankedChunk]) -> Answer:
    """Compose a grounded, inline-cited answer (extractive offline fallback)."""
    if not ranked:
        return Answer(
            question=question,
            body=(
                "ABSTAIN: No public expert sources in the current corpus are "
                "relevant to this question. Expand the source registry or rephrase."
            ),
            citations=[],
            abstained=True,
            confidence="abstain",
            disagreement_note="",
        )

    best_score = ranked[0].final_score
    confidence = _confidence(best_score)

    if confidence == "abstain":
        return Answer(
            question=question,
            body=(
                "ABSTAIN: The most relevant public sources are too weak/thin to "
                "support a grounded answer. Recommend escalating to a human expert "
                "or expanding the corpus before relying on this."
            ),
            citations=[],
            abstained=True,
            confidence="abstain",
            disagreement_note=_disagreement_note(ranked),
        )

    # Build inline-cited extractive body. Each bullet ties a verbatim excerpt to
    # a numbered citation so the grounding is auditable.
    citations: List[Citation] = []
    lines: List[str] = [
        f"Grounded synthesis for: {question}",
        "(Extractive offline mode — every point below is a cited public-source excerpt.)",
        "",
    ]
    for i, r in enumerate(ranked, start=1):
        ch = r.scored.chunk
        marker = f"[{i}]"
        flag = "" if ch.on_record else " (OFF-RECORD/speculative)"
        excerpt = _first_sentences(ch.text)
        lines.append(f"- {excerpt} {marker}{flag}")
        citations.append(
            Citation(
                marker=marker,
                author=ch.author,
                venue=ch.venue,
                url=ch.url,
                published=ch.published.isoformat() if ch.published else "undated",
                credibility_tier=ch.credibility_tier.value,
                on_record=ch.on_record,
            )
        )

    disagreement = _disagreement_note(ranked)
    if disagreement:
        lines += ["", f"Panel note: {disagreement}"]

    lines += ["", f"Confidence: {confidence.upper()} (best composite score={best_score:.3f})"]
    lines += ["", "Sources:"]
    for c in citations:
        lines.append(
            f"  {c.marker} {c.author} — {c.venue}, {c.published} "
            f"[{c.credibility_tier}, on_record={c.on_record}] {c.url}"
        )

    return Answer(
        question=question,
        body="\n".join(lines),
        citations=citations,
        abstained=False,
        confidence=confidence,
        disagreement_note=disagreement,
    )
