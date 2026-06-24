"""The canonical Sapphire provenance vocabulary (spec §3.3). Every artifact the
Console renders carries one of these; nothing is silently mocked."""
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


def is_valid_provenance(p) -> bool:
    if not isinstance(p, str):
        return False
    return p in PROVENANCE or p.startswith("qmodels:")
