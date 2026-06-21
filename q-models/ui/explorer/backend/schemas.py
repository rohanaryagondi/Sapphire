"""Pydantic v2 request/response models for the Explorer API.

The contract (CONTRACT.md "API contract") asks us to:
  - validate inputs LOOSELY — never 422 on a missing optional field. Each track
    declares its own `inputs` in tracks.json, so the request body is track-shaped
    and we accept whatever keys the form sends (`extra="allow"`, all optional).
  - return a fixed-shape `PredictResponse` / `BatchResponse` so the frontend can
    render every track the same way.

Inner objects (`Verdict`, `Performance`, `Prediction`) are permissive on purpose:
the prediction shape is per-track `score_kind` (embedding/affinity/probability/
panel/ranking/complex/analogs/panel_ranking/none) and we don't want to enumerate
every variant here — the frontend renders by `score_kind`. Pydantic still gives
us a typed envelope and clean OpenAPI docs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ----------------------------- requests -----------------------------

class PredictRequest(BaseModel):
    """A single prediction body.

    Track-shaped and loosely validated: every track has different input field
    names (sequences / smiles / uniprot_acc / gene / targets / ...), all optional
    at the schema level. We accept and echo whatever the form posts; the track's
    own `inputs` definition drives what the UI sends. `extra="allow"` keeps any
    extra keys instead of 422-ing.
    """

    model_config = ConfigDict(extra="allow")

    def inputs(self) -> dict[str, Any]:
        """All posted fields as a plain dict (declared + extras)."""
        return self.model_dump()


class BatchRequest(BaseModel):
    """A batch body: `{rows: [{...}, ...]}` for batch-enabled tracks.

    Each row is a loose dict (same shape as a single predict body). Rows that
    fail to parse become error rows in the response rather than failing the call.
    """

    model_config = ConfigDict(extra="allow")

    rows: list[dict[str, Any]] = Field(default_factory=list)


# ----------------------------- response sub-objects -----------------------------

class Verdict(BaseModel):
    """Operating-envelope verdict shown on every result (badge resolved)."""

    model_config = ConfigDict(extra="allow")

    badge: str | None = None
    badge_label: str | None = None
    badge_emoji: str | None = None
    headline: str | None = None
    why: str | None = None
    recommended_use: str | None = None
    source: str | None = None


class Metric(BaseModel):
    name: str
    value: str


class Performance(BaseModel):
    model_config = ConfigDict(extra="allow")

    headline: str | None = None
    metrics: list[Metric] = Field(default_factory=list)


class Prediction(BaseModel):
    """Track-specific prediction. `score_kind` drives frontend rendering."""

    model_config = ConfigDict(extra="allow")

    score_kind: str = "none"


# ----------------------------- responses -----------------------------

class PredictResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    track: str
    label: str
    model: str
    license: str
    stubbed: bool
    prediction: dict[str, Any]
    verdict: Verdict
    performance: Performance
    inputs_echo: dict[str, Any] = Field(default_factory=dict)


class BatchRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    rank: int | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    prediction: dict[str, Any] | None = None
    error: str | None = None


class BatchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    track: str
    label: str
    model: str
    license: str
    stubbed: bool
    requested: int
    processed: int
    rows: list[BatchRow] = Field(default_factory=list)
    verdict: Verdict
    performance: Performance
