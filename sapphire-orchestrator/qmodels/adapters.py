# -*- coding: utf-8 -*-
"""Per-tool output adapters — normalize each Q-Models tool's ad-hoc response into the dossier
`validate.runs` shape: {model, out, provenance, score_kind, raw}.

Q-Models has no uniform output schema; each Explorer track returns a body keyed by its `score_kind`
(affinity / probability / panel / complex / panel_ranking / embedding / ranking / analogs). These
formatters turn any of them into a single human-readable `out` line + keep the structured `raw`.
"""
from __future__ import annotations

from typing import Any


def _fmt_affinity(b: dict) -> str:
    v = b.get("value"); units = b.get("units", ""); call = b.get("binder_call") or b.get("call")
    return f"affinity {v}{(' ' + units) if units else ''}" + (f" — {call}" if call else "")


def _fmt_probability(b: dict) -> str:
    v = b.get("value"); call = b.get("call")
    return f"p={v}" + (f" ({call})" if call else "")


def _fmt_panel(b: dict) -> str:
    eps = b.get("endpoints") or []
    parts = [f"{e.get('name')}={e.get('value')}{(' ' + e['call']) if e.get('call') else ''}" for e in eps]
    return "; ".join(parts) if parts else str(b.get("value", b))


def _fmt_complex(b: dict) -> str:
    aff = b.get("affinity"); units = b.get("units", ""); conf = b.get("confidence")
    return f"complex affinity {aff}{(' ' + units) if units else ''}" + (f", confidence {conf}" if conf is not None else "")


def _fmt_panel_ranking(b: dict) -> str:
    rows = b.get("ranking") or b.get("shortlist") or []
    if rows and isinstance(rows[0], dict):
        return " > ".join(str(r.get("name") or r.get("target") or r.get("smiles")) for r in rows[:6])
    return str(rows[:6])


def _fmt_embedding(b: dict) -> str:
    nf = b.get("nearest_family"); dim = b.get("dim")
    return f"nearest family: {nf}" + (f" (dim {dim})" if dim else "")


def _fmt_ranking(b: dict) -> str:
    rp = b.get("rank_percentile"); sl = b.get("shortlist") or []
    head = f"rank pct {rp}" if rp is not None else "ranking"
    return head + (f"; top: {', '.join(map(str, sl[:5]))}" if sl else "")


def _fmt_analogs(b: dict) -> str:
    ns = b.get("neighbors") or []
    return f"{len(ns)} analogs" + (f" (top sim {ns[0].get('similarity')})" if ns and isinstance(ns[0], dict) else "")


_FORMATTERS = {
    "affinity": _fmt_affinity, "probability": _fmt_probability, "panel": _fmt_panel,
    "complex": _fmt_complex, "panel_ranking": _fmt_panel_ranking, "embedding": _fmt_embedding,
    "ranking": _fmt_ranking, "analogs": _fmt_analogs,
}


def normalize(tool: dict, body: dict, provenance: str) -> dict:
    """tool = the registry entry; body = the tool's raw prediction; provenance = live-local|stub|gpu-async|...
    Returns the dossier validate.runs row."""
    score_kind = (body or {}).get("score_kind") or tool.get("score_kind") or "unknown"
    fmt = _FORMATTERS.get(score_kind)
    try:
        out = fmt(body) if fmt and isinstance(body, dict) else str(body)
    except Exception as e:  # never let a formatter crash the run
        out = f"(unparsed {score_kind}: {e})"
    return {
        "model": tool.get("label") or tool.get("name") or tool.get("id"),
        "tool_id": tool.get("id"),
        "score_kind": score_kind,
        "out": out,
        "provenance": provenance,
        "raw": body,
    }
