"""Pydantic v2 request/response schemas for the Quiver MAMMAL Explorer API.

Every /predict/* response carries BOTH the model output and the reliability
record (ui_spec §3). `providers` is a list so a Quiver fine-tuned head can later
drop in beside the IBM head for the same task and render side by side; today it
has one entry. `prediction` mirrors `providers[0].prediction` to satisfy the
spec's required top-level field.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ----------------------------- requests -----------------------------

class SmilesRequest(BaseModel):
    smiles: str = Field(..., min_length=1, description="drug SMILES string")


class BbbpRequest(SmilesRequest):
    """Alias of SmilesRequest — kept distinct for clearer /docs."""


class DtiRequest(BaseModel):
    smiles: str = Field(..., min_length=1, description="drug SMILES string")
    target_seq: Optional[str] = Field(None, description="protein amino-acid sequence")
    uniprot_acc: Optional[str] = Field(
        None, description="UniProt accession; sequence is fetched if target_seq is absent"
    )

    @model_validator(mode="after")
    def _need_one_target(self) -> "DtiRequest":
        if not (self.target_seq or self.uniprot_acc):
            raise ValueError("provide either target_seq or uniprot_acc")
        return self


class PpiRequest(BaseModel):
    seq_a: str = Field(..., min_length=1, description="protein A amino-acid sequence")
    seq_b: str = Field(..., min_length=1, description="protein B amino-acid sequence")


class SolubilityRequest(BaseModel):
    protein_seq: str = Field(..., min_length=1, description="protein amino-acid sequence")


class TcrRequest(BaseModel):
    tcr_beta_seq: str = Field(..., min_length=1, description="TCR-beta CDR3 amino-acid sequence")
    epitope_seq: str = Field(..., min_length=1, description="epitope peptide amino-acid sequence")


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        description="SMILES or AA with a <SENTINEL_ID_0> span to infill (or a full SMILES to mask)",
    )
    kind: Literal["smiles", "protein"] = "smiles"


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1, description="protein AA sequence or SMILES")
    kind: Literal["protein", "smiles"] = "protein"


# ----------------------------- responses -----------------------------

class Prediction(BaseModel):
    """One model's output. `score_kind` tells the frontend how to render `value`:

    - pkd            : a regression pKd (display as "X.XX pKd")
    - normalized_p1  : calibrated P(<1>)/(P(<1>)+P(<0>)) in [0,1] (display as %)
    - raw_p1         : raw positive-token score, uncalibrated (display as a bare score)
    - none           : non-scalar output (generation text / embedding vector)
    """

    score_kind: Literal["pkd", "normalized_p1", "raw_p1", "none"]
    value: Optional[float] = None
    pred_class: Optional[int] = Field(None, description="argmax label (0/1) where applicable")
    units: Optional[str] = None
    note: Optional[str] = None
    # non-scalar payloads
    text: Optional[list[str]] = Field(None, description="generated string(s)")
    vector: Optional[list[float]] = Field(None, description="embedding vector")
    nearest_family: Optional[str] = None
    family_scores: Optional[dict[str, float]] = None
    extra: Optional[dict[str, Any]] = None


class ReliabilityOut(BaseModel):
    task: str
    badge: str
    badge_emoji: str
    badge_label: str
    headline: str
    why: str
    recommended_use: str
    source: str


class ProviderResult(BaseModel):
    provider_name: str
    provider_kind: Literal["ibm_public", "quiver_finetuned"]
    prediction: Prediction


class PredictResponse(BaseModel):
    task: str
    prediction: Prediction          # mirror of providers[0].prediction (spec's required field)
    reliability: ReliabilityOut
    providers: list[ProviderResult]
    standardized_smiles: Optional[str] = Field(
        None, description="the neutral-parent SMILES actually scored, if standardization ran"
    )


# ----------------------------- batch (many rows, one task) -----------------------------

class BatchRequest(BaseModel):
    """A list of per-row input payloads for one task. Each row is validated against
    that task's single-prediction schema; a row that fails becomes an error row in the
    response rather than rejecting the whole batch. Over the row cap, extra rows are
    dropped and reported (never silently truncated)."""

    rows: list[dict[str, Any]] = Field(..., min_length=1, description="per-row input payloads")


class BatchRow(BaseModel):
    index: int = Field(..., description="position in the submitted list (0-based)")
    rank: Optional[int] = Field(None, description="1-based rank among successful rows (best score first)")
    inputs: dict[str, Any] = Field(..., description="the original submitted row")
    standardized_smiles: Optional[str] = None
    prediction: Optional[Prediction] = None
    providers: Optional[list[ProviderResult]] = None
    error: Optional[str] = Field(None, description="why this row was not scored (parse/fetch/model)")


class BatchResponse(BaseModel):
    task: str
    reliability: ReliabilityOut
    requested: int = Field(..., description="rows submitted")
    processed: int = Field(..., description="rows attempted (after the cap)")
    dropped: int = Field(..., description="rows over the cap that were not attempted")
    rows: list[BatchRow]
