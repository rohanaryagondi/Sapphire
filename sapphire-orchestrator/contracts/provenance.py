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
    # Quiver ASO acute-toxicity delegate (subprocess; sklearn env)
    "aso-tox",
    # quantitative-fact Bucket-1 seams (public APIs via stdlib urllib seams)
    "gnomad",
})


def is_valid_provenance(p) -> bool:
    if not isinstance(p, str):
        return False
    return p in PROVENANCE or p.startswith("qmodels:")
