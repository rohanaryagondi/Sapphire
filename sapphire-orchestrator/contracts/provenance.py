"""The canonical Sapphire provenance vocabulary (spec §3.3). Every artifact the
Console renders carries one of these; nothing is silently mocked.

Data-plane map
--------------
Every provenance label maps to one of two planes:

  "internal" — data that originates from Quiver's private CNS_DFP repository
               (moat-real, and any future Quiver-internal source).  Internal-plane
               data must NEVER be transmitted to external-fetch agents (EMET, web,
               Q-Models, any public API).

  "external" — data from any source outside Quiver: public databases, external
               APIs, model predictions run against public identifiers, corpus
               retrieval over pre-ingested public literature.

The plane is DERIVED from provenance — it is never asserted by the caller.
Use `plane_for(provenance) -> "internal" | "external"` to get the plane.
For `qmodels:*` labels, the plane is always "external" (public-identifier inputs).

Enforcement: `is_boundary_violation(target_provenance, fact_plane)` returns True
when an external-provenance agent would receive an internal-plane fact, which must
be BLOCKED by the data_boundary guardrail.  See harness/guardrails.py.
"""
from __future__ import annotations

PROVENANCE = frozenset({
    # Phase 5 additions
    "emet-live", "emet-mcp", "memory-recall", "persona-judgment", "synthesis",
    # existing
    "live-local", "gpu-async", "gpu-disabled", "stub", "unavailable", "mock",
    # real Quiver CNS_DFP moat
    "moat-real",
    # corpus-first retrieval: a claim-card from a Bucket-1 agent's pre-ingested
    # local corpus (corpus/<agent_id>/index.jsonl). A T2 lead, never a dispositive
    # veto — a veto still requires its T1 primary.
    "corpus",
    # Quiver ASO acute-toxicity delegate (subprocess; sklearn env)
    "aso-tox",
    # quantitative-fact Bucket-1 seams (public APIs via stdlib urllib seams)
    "gnomad",
    "gtex",
    "interpro",
    "gprofiler",
})

# ---------------------------------------------------------------------------
# Plane map: every label in PROVENANCE maps to exactly one plane.
# "qmodels:*" labels are external (run against public identifiers only).
# This dict is the single source of truth — extend it whenever a new
# provenance label is added to PROVENANCE above.
# ---------------------------------------------------------------------------
_PLANE_MAP: dict[str, str] = {
    # --- internal plane ---
    "moat-real":        "internal",

    # --- external plane ---
    "emet-live":        "external",
    "emet-mcp":         "external",
    "memory-recall":    "external",   # derived from public prior engagements
    "persona-judgment": "external",   # opinion citing the dossier, no internal data
    "synthesis":        "external",   # deterministic assembly of public facts
    "live-local":       "external",   # Q-Models CPU; public-identifier inputs
    "gpu-async":        "external",   # Q-Models GPU async; public-identifier inputs
    "gpu-disabled":     "external",   # Q-Models GPU stub
    "stub":             "external",
    "unavailable":      "external",
    "mock":             "external",
    "corpus":           "external",   # pre-ingested public literature
    "aso-tox":          "external",   # public ASO sequences; GBR model is local but inputs are public
    "gnomad":           "external",
    "gtex":             "external",
    "interpro":         "external",
    "gprofiler":        "external",
}

# Sanity guard: every label in PROVENANCE must have an entry in _PLANE_MAP.
# Evaluated at import time so a missing mapping is caught immediately.
_unmapped = PROVENANCE - frozenset(_PLANE_MAP.keys())
if _unmapped:  # pragma: no cover
    raise RuntimeError(
        f"contracts/provenance.py: provenance label(s) missing from _PLANE_MAP: {_unmapped}"
    )


def plane_for(provenance: str) -> str:
    """Return the data plane ("internal" or "external") for a provenance label.

    For ``qmodels:*`` labels, always returns ``"external"`` (Q-Models runs only
    against public identifiers — no Quiver internal data crosses that boundary).

    Raises ``KeyError`` for an unrecognised label (use ``is_valid_provenance``
    first if the label may be user-supplied).
    """
    if isinstance(provenance, str) and provenance.startswith("qmodels:"):
        return "external"
    return _PLANE_MAP[provenance]


def is_boundary_violation(target_provenance: str, fact_plane: str) -> bool:
    """Return True when routing a fact with ``fact_plane`` to an agent whose
    output provenance is ``target_provenance`` would violate the data-boundary rule.

    The rule: an **external**-plane agent must never receive **internal**-plane facts.

    Example::

        is_boundary_violation("emet-live", "internal")  # → True  (must BLOCK)
        is_boundary_violation("emet-live", "external")  # → False (safe)
        is_boundary_violation("moat-real", "internal")  # → False (internal agent, fine)

    This function encodes the rule; the enforcement seam is ``harness/guardrails.py``
    ``data_boundary()``, which blocks the call before dispatch.
    """
    if not isinstance(target_provenance, str) or not isinstance(fact_plane, str):
        return False
    try:
        agent_plane = plane_for(target_provenance)
    except KeyError:
        # Unknown provenance → conservatively treat as external (block internal facts).
        agent_plane = "external"
    return agent_plane == "external" and fact_plane == "internal"


def is_valid_provenance(p) -> bool:
    if not isinstance(p, str):
        return False
    return p in PROVENANCE or p.startswith("qmodels:")
