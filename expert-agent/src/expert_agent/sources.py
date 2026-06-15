"""Source registry: dataclasses and credibility tiers.

Every piece of ingested content is PUBLIC expert material. We never ingest
Quiver proprietary functional/EP/CRISPR data here. The registry captures the
provenance metadata we later use for credibility/recency-weighted retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class CredibilityTier(str, Enum):
    """Ordinal credibility tiers, borrowed from financial-sentiment pipelines
    where each source gets a normalized reliability weight.

    Higher weight = more trusted. These are deliberately coarse; tune in config.
    """

    TIER_1_NAMED_CREDENTIALED = "tier_1_named_credentialed"   # ex-FDA, named MD/PhD on record
    TIER_2_NAMED_PRACTITIONER = "tier_2_named_practitioner"   # named industry practitioner
    TIER_3_ANONYMOUS_UNVERIFIED = "tier_3_anonymous_unverified"  # anon/unverified, speculative

    @property
    def default_weight(self) -> float:
        return {
            CredibilityTier.TIER_1_NAMED_CREDENTIALED: 1.0,
            CredibilityTier.TIER_2_NAMED_PRACTITIONER: 0.7,
            CredibilityTier.TIER_3_ANONYMOUS_UNVERIFIED: 0.4,
        }[self]


# Venue type -> whether transcription is required at ingest time.
# Used to route podcasts/talks through the (stubbed) ASR step.
TRANSCRIBED_VENUES = {"podcast", "talk", "webinar", "conference"}


@dataclass
class Source:
    """A registered public source we are allowed to ingest.

    `on_record` distinguishes deliberate, attributable statements (blog, paper)
    from off-the-cuff/speculative ones (a hot take on a podcast). We down-weight
    off-record speculation at retrieval time.
    """

    source_id: str
    author: str
    author_role: str
    venue: str
    url: str
    credibility_tier: CredibilityTier
    on_record: bool = True
    # Optional explicit weight override; otherwise tier default is used.
    weight_override: Optional[float] = None
    license_note: str = ""

    @property
    def credibility_weight(self) -> float:
        base = (
            self.weight_override
            if self.weight_override is not None
            else self.credibility_tier.default_weight
        )
        # Off-record material is additionally discounted (speculation penalty).
        return base * (1.0 if self.on_record else 0.6)

    @property
    def needs_transcription(self) -> bool:
        return self.venue.split()[0].lower() in TRANSCRIBED_VENUES


@dataclass
class Document:
    """A single ingested document tied back to its Source."""

    source: Source
    title: str
    text: str
    published: Optional[date] = None


@dataclass
class Chunk:
    """A retrievable text chunk carrying its full provenance metadata.

    All fields needed for credibility/recency weighting and citation live here
    so retrieve/synthesize never have to reach back into the document.
    """

    chunk_id: str
    text: str
    source_id: str
    author: str
    author_role: str
    venue: str
    url: str
    title: str
    published: Optional[date]
    credibility_tier: CredibilityTier
    on_record: bool
    credibility_weight: float
    extra: dict = field(default_factory=dict)
