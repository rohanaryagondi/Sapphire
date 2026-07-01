"""tool_selector.py — Orchestrator-decided scientific tool selection for Sapphire.

The orchestrator (a Claude reasoning step in the PLAN stage) reads the tool
catalog and the user query + detected inputs, then returns ``tools_selected``
(which scientific tools to run) + ``tool_rationale`` (why each was included or
skipped).

DEGRADE SAFELY: when the Claude call fails or returns malformed output, a
deterministic fallback fires based solely on the QueryScope detected inputs:
  - genes present  → gene tools (gnomad, gtex, interpro, geneset, q-models-runner)
  - SMILES present → DTI/boltz tools
  - ASO sequences  → aso-tox
  - imaging input  → robyn-scs (never from fallback — requires explicit ctx flag)

Runtime stays stdlib-only: only stdlib and first-party imports appear here.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from harness.dispatch import CLAUDE_BIN
except ImportError:
    CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

# ---------------------------------------------------------------------------
# Load the tool catalog (once at import time — pure data, never changes at runtime)
# ---------------------------------------------------------------------------
_CATALOG_PATH = os.path.join(_HERE, "tool_catalog.json")

def _load_catalog() -> list[dict]:
    """Load tool entries from tool_catalog.json. Returns [] on any error."""
    try:
        with open(_CATALOG_PATH, encoding="utf-8") as _f:
            data = json.load(_f)
        return data.get("tools", [])
    except Exception:
        return []

_TOOL_CATALOG: list[dict] = _load_catalog()
_ALL_TOOL_IDS: frozenset = frozenset(t["id"] for t in _TOOL_CATALOG)

# The 8 selectable scientific tool ids (in definition order — canonical ordering).
SCIENTIFIC_TOOLS: list[str] = [t["id"] for t in _TOOL_CATALOG]

# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

def _deterministic_fallback(
    scope,
    explicit_sequences: list | None = None,
    explicit_structure: dict | None = None,
) -> dict:
    """Deterministic tool selection from QueryScope — fires when Claude call fails.

    Rules (conservative — prefer false-negative over false-positive on expensive tools):
      genes present    → gnomad-constraint, gtex-expression, interpro-domains,
                         geneset-enrichment, q-models-runner
      SMILES present   → boltz, q-models-runner (DTI track)
      sequences present→ aso-tox (from scope OR from explicit_sequences param)
      structure present→ boltz (from explicit_structure param or SMILES)
      imaging_input    → robyn-scs (fallback NEVER selects this; requires explicit ctx)
      nothing          → [] (empty — always-on core still runs)

    Overlap: a query with BOTH genes and SMILES gets both sets.

    Parameters
    ----------
    scope              : planner.QueryScope (from classify_query).
    explicit_sequences : explicit ASO sequences from run_live sequences= param.
    explicit_structure : explicit structure/affinity dict from run_live structure= param.
    """
    selected: list[str] = []
    rationale: dict[str, str] = {}

    genes = getattr(scope, "genes", []) or getattr(scope, "candidates", []) or []
    smiles = getattr(scope, "smiles", []) or []
    # Merge text-extracted + explicit sequences.
    sequences = list(getattr(scope, "sequences", []) or [])
    if explicit_sequences:
        sequences = explicit_sequences or sequences  # explicit wins
    # Merge text-extracted SMILES + explicit structure.
    has_structure = bool(smiles) or bool(explicit_structure)

    if genes:
        _gene_tools = ["gnomad-constraint", "gtex-expression", "interpro-domains",
                       "geneset-enrichment", "q-models-runner"]
        for _t in _gene_tools:
            selected.append(_t)
            rationale[_t] = f"fallback: gene symbols detected ({', '.join(genes[:3])})"

    if has_structure:
        for _t in ["boltz", "q-models-runner"]:
            if _t not in selected:
                selected.append(_t)
            rationale[_t] = rationale.get(_t, "") or "fallback: SMILES or structure input detected"

    if sequences:
        if "aso-tox" not in selected:
            selected.append("aso-tox")
        rationale["aso-tox"] = f"fallback: ASO sequences detected ({len(sequences)})"

    # robyn-scs: never in the deterministic fallback (requires explicit ctx["imaging_input"])

    skipped = [t for t in SCIENTIFIC_TOOLS if t not in selected]
    for _t in skipped:
        if _t not in rationale:
            rationale[_t] = "fallback: not triggered by detected inputs"

    return {
        "tools_selected": selected,
        "tool_rationale": rationale,
        "tools_available": [
            {"id": t["id"], "name": t["name"], "purpose": t["purpose"]}
            for t in _TOOL_CATALOG
        ],
        "selection_source": "deterministic-fallback",
    }


# ---------------------------------------------------------------------------
# Claude-driven selection
# ---------------------------------------------------------------------------

def select_tools(
    query: str,
    scope,                              # planner.QueryScope
    ctx: dict | None = None,
    resolved_sequences: list | None = None,
    resolved_structure: dict | None = None,
) -> dict:
    """Select scientific tools for this query using a Claude reasoning call.

    Parameters
    ----------
    query              : the user's free-text engagement question.
    scope              : planner.QueryScope with detected genes, smiles, sequences,
                         query_type.
    ctx                : harness context dict — must carry ``"runner"`` when testing
                         (injected mock runner replaces the subprocess call).
    resolved_sequences : explicit ASO sequences from the ``sequences=`` param to
                         run_live (may differ from scope.sequences which are extracted
                         from query text only). When non-empty, aso-tox is a candidate.
    resolved_structure : explicit structure/affinity inputs from the ``structure=``
                         param to run_live. When non-empty, boltz is a candidate.

    Returns
    -------
    A dict with keys:
        tools_selected  : list[str]  — tool ids to run (subset of SCIENTIFIC_TOOLS).
        tool_rationale  : dict[str, str] — {tool_id: why-included-or-skipped}.
        tools_available : list[{id, name, purpose}] — full selectable tool list
                          (for the frontend toggle panel).
        selection_source: str — "claude" | "deterministic-fallback".

    Never raises. On any failure degrades to _deterministic_fallback(scope).
    """
    ctx = ctx or {}

    # Build the tools_available list (always included regardless of path).
    tools_available = [
        {"id": t["id"], "name": t["name"], "purpose": t["purpose"]}
        for t in _TOOL_CATALOG
    ]

    # Detect imaging_input from ctx (robyn-scs selection channel).
    has_imaging = bool(ctx.get("imaging_input"))

    # Compact detected-inputs summary for the prompt.
    # Merge query-text-extracted entities with explicit params (sequences=, structure=).
    genes = getattr(scope, "genes", []) or []
    smiles = getattr(scope, "smiles", []) or []
    sequences = getattr(scope, "sequences", []) or []

    # Merge explicit sequences (from run_live sequences= param) — these override
    # the text-extracted sequences for the purpose of tool selection. An ASO query
    # passed via the explicit param is as real as one embedded in the query text.
    _explicit_seqs = list(resolved_sequences or [])
    _all_sequences = _explicit_seqs or sequences   # explicit wins; fall back to text-extracted

    # Merge explicit structure inputs (from run_live structure= param or SMILES folding).
    _explicit_struct = dict(resolved_structure or {})
    # Also check if SMILES were detected in text but not in scope.smiles (already in smiles above).
    _has_structure = bool(_explicit_struct) or bool(smiles)

    detected_inputs = {
        "genes": genes,
        "smiles": smiles,
        "aso_sequences": _all_sequences,
        "has_imaging_data": has_imaging,
        "has_structure_input": _has_structure,
        "query_type": getattr(scope, "query_type", "unknown"),
    }

    # Build the prompt input (public identifiers only — data-boundary safe).
    prompt_payload = {
        "instruction": (
            "You are the Sapphire orchestrator's tool-selection agent. "
            "Given the user query and the detected inputs below, select which scientific "
            "tools from the catalog should run. "
            "For each tool in the catalog, decide: INCLUDE (it will return useful facts "
            "for this specific query) or SKIP (it adds no value or lacks required inputs). "
            "Return JSON with exactly these keys: "
            "\"selected\" (array of tool ids to include), "
            "\"rationale\" (object mapping each tool id → one-line reason for INCLUDE or SKIP). "
            "Include ALL catalog tool ids in rationale (both selected and skipped). "
            "Public identifiers only — no Quiver internal data."
        ),
        "query": query,
        "detected_inputs": detected_inputs,
        "tool_catalog": [
            {
                "id": t["id"],
                "name": t["name"],
                "purpose": t["purpose"],
                "required_inputs": t.get("required_inputs", []),
                "when_to_use": t.get("when_to_use", ""),
            }
            for t in _TOOL_CATALOG
        ],
    }

    # JSON schema for the Claude structured output.
    _schema = {
        "type": "object",
        "required": ["selected", "rationale"],
        "properties": {
            "selected": {
                "type": "array",
                "items": {"type": "string"},
            },
            "rationale": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        },
        "additionalProperties": False,
    }

    # Call Claude via subprocess (mirrors report.py + summarizer.py pattern).
    # CLAUDE_BIN-configurable: CLAUDE_BIN=/usr/bin/false → subprocess immediately fails
    # → deterministic fallback fires (the safety net, used in hermetic CI).
    try:
        import subprocess
        import shutil

        _bin = ctx.get("_tool_selector_bin") or CLAUDE_BIN
        runner = ctx.get("runner")

        prompt_str = json.dumps(prompt_payload, ensure_ascii=False)
        schema_str = json.dumps(_schema, ensure_ascii=False)
        cmd = [_bin, "-p", prompt_str, "--output-format", "json",
               "--json-schema", schema_str]

        if runner is not None:
            # Injected mock runner (tests).
            proc = runner(cmd)
        else:
            # Real subprocess.
            if not shutil.which(_bin):
                raise FileNotFoundError(f"CLAUDE_BIN not found: {_bin!r}")
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=60,
            )

        if proc.returncode != 0:
            raise RuntimeError(f"claude exited {proc.returncode}")

        raw = proc.stdout or ""
        data = json.loads(raw)

        # The runner returns {"structured_output": {...}} or the object directly.
        if "structured_output" in data:
            data = data["structured_output"]

        # Validate response shape: must have 'selected' key (a list).
        # If missing, this is a malformed/wrong-type response — fall back.
        if "selected" not in data:
            raise ValueError("tool-selector response missing 'selected' key")
        selected_raw: list = data["selected"] if isinstance(data["selected"], list) else []
        rationale_raw: dict = data.get("rationale", {}) if isinstance(data.get("rationale"), dict) else {}

        # Validate: only known tool ids are honoured (no hallucinations).
        selected = [t for t in selected_raw if t in _ALL_TOOL_IDS]

        # Rationale: keep all known ids, drop hallucinated keys.
        rationale = {k: v for k, v in rationale_raw.items() if k in _ALL_TOOL_IDS}

        # Fill in rationale for any tool the model omitted.
        for _t in SCIENTIFIC_TOOLS:
            if _t not in rationale:
                rationale[_t] = "not addressed by model — assumed skipped"
            if _t not in selected and rationale.get(_t, "").startswith("not addressed"):
                rationale[_t] = "skipped (not addressed by model)"

        # robyn-scs special gate: only include if imaging_input is in ctx.
        if "robyn-scs" in selected and not has_imaging:
            selected = [t for t in selected if t != "robyn-scs"]
            rationale["robyn-scs"] = "removed: no imaging_input in context"

        return {
            "tools_selected": selected,
            "tool_rationale": rationale,
            "tools_available": tools_available,
            "selection_source": "claude",
        }

    except Exception:
        # Any failure → deterministic fallback (with merged explicit inputs).
        fb = _deterministic_fallback(
            scope,
            explicit_sequences=list(resolved_sequences or []),
            explicit_structure=dict(resolved_structure or {}),
        )
        fb["tools_available"] = tools_available
        return fb
