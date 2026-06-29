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

This is the CLASSIFICATION layer: `plane_for` tags dossier facts (for the contract +
UI) and `is_boundary_violation(target_provenance, fact_plane)` expresses the routing
rule (True when an external-provenance agent would receive an internal-plane fact).
The RUNTIME enforcer is a separate, complementary mechanism: `harness/guardrails.py`
`data_boundary()` blocks a dispatch by scanning inputs for internal identifiers/keys.
The two are deliberately kept apart — `data_boundary()` is shared with the public-only
memory subsystem, so it keys on raw internal data, not on a fact's provenance label
(blanket-blocking `moat-real` there would wrongly refuse legitimate internal-data-in-
memory / internal-data-to-reasoning flows the boundary rule permits).
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
    # Boltz-2 biomolecular structure + binding-affinity model (hosted Boltz Compute
    # API via stdlib urllib seam). EXTERNAL model run against PUBLIC identifiers only
    # (protein/RNA/DNA sequences, ligand SMILES, CCD codes); never receives Quiver
    # internal moat data.
    "boltz",
    # quantitative-fact Bucket-1 seams (public APIs via stdlib urllib seams)
    "gnomad",
    "gtex",
    "interpro",
    "gprofiler",
    # Quiver robyn_scs SCS/STA neuronal-connectivity pipeline (imaging-derived, INTERNAL;
    # subprocess delegate). Fires only when imaging data is present in inputs.
    "robyn-scs",
    # LABELED simulated model reasoning (SAPPHIRE_SIMULATE_MODELS=1): a claude-subagent's
    # persona/fact output stood in for a real `claude -p` call (fast demo). Always rendered with
    # a "🧪 simulated" marker — NEVER presented as a real verdict. External plane (no internal
    # data; it is a placeholder, not a real source).
    "simulated",
    # Scientific mechanism reasoning — a claude-subagent (the rescue-mechanism agent) reasoning
    # over PUBLIC inputs (candidate gene symbols + ordinal rank + cited public literature) to
    # produce a plausible, literature-grounded mechanistic explanation. EXTERNAL plane: it never
    # receives raw internal moat scores (only gene symbols + ordinal rank cross to it), and its
    # claims must cite the provided public literature (it abstains rather than fabricate).
    "scientific-reasoning",
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
    "robyn-scs":        "internal",   # Quiver imaging-derived connectivity — internal data

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
    "boltz":            "external",   # hosted Boltz-2 structure/binding model; public-identifier inputs only
    "gnomad":           "external",
    "gtex":             "external",
    "interpro":         "external",
    "gprofiler":        "external",
    "simulated":        "external",   # labeled placeholder model reasoning — not a real source
    "scientific-reasoning": "external",  # claude reasoning over public genes+rank+literature; no internal scores
}

# Sanity guard (BIDIRECTIONAL): the PROVENANCE set and _PLANE_MAP keys must match
# exactly. Evaluated at import time so a drift in either direction is caught immediately:
#   - a PROVENANCE label with no plane  → plane_for() would KeyError at runtime;
#   - an orphan _PLANE_MAP key not in PROVENANCE → is_valid_provenance() would reject it
#     while plane_for() silently accepts it (an invisible inconsistency).
# (qmodels:* is intentionally in NEITHER set — it is handled by the plane_for fast-path.)
_unmapped = PROVENANCE - frozenset(_PLANE_MAP.keys())
if _unmapped:  # pragma: no cover
    raise RuntimeError(
        f"contracts/provenance.py: provenance label(s) missing from _PLANE_MAP: {_unmapped}"
    )
_orphan = frozenset(_PLANE_MAP.keys()) - PROVENANCE
if _orphan:  # pragma: no cover
    raise RuntimeError(
        f"contracts/provenance.py: _PLANE_MAP key(s) not in PROVENANCE: {_orphan}"
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

    Fail-safe: only an **internal** fact can ever violate, so a non-internal
    ``fact_plane`` is always safe; but an internal fact bound for an
    unidentifiable target (non-str / unknown provenance) is conservatively
    treated as a violation (block) rather than waved through.
    """
    if not isinstance(fact_plane, str) or fact_plane != "internal":
        return False  # only internal-plane facts can violate the boundary
    if not isinstance(target_provenance, str):
        return True   # internal fact + unidentifiable target → block (fail-safe)
    try:
        agent_plane = plane_for(target_provenance)
    except KeyError:
        agent_plane = "external"  # unknown provenance → treat as external (block internal)
    return agent_plane == "external"


def is_valid_provenance(p) -> bool:
    if not isinstance(p, str):
        return False
    return p in PROVENANCE or p.startswith("qmodels:")
