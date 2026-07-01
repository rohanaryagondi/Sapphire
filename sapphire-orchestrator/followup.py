"""
followup.py — main-chat follow-up over a run's STORED evidence.

Answers a free-text follow-up question in an EXISTING conversation using ONLY
the evidence already captured in that conversation's last real run (the
dossier, roundtable verdicts, recommendation/confidence, known-unknowns) —
never by re-convening the 23-agent firm. Mirrors report.py's pattern exactly:
same CLAUDE_BIN resolution, same honesty-guard-in-prompt style, same
never-raises/deterministic-fallback contract, same stdlib-only footprint.

CONTRACT
--------
  answer_followup(question: str, result: dict, runner=None,
                   registry=None, qmodels_client=None) -> dict

  Returns {"answer": str, "citations": list[str], "needs_new_data": bool,
           "missing_agent": str | None, "missing_agent_label": str | None}. Never raises.

  WO-9 PHASE 5 — `missing_agent` is constrained to a REAL, invocable identifier (a
  Bucket-1 agent id or a Q-Models tool id), never free prose: the prompt gives the
  model a closed list of valid {id, label} targets, and the parsed response is
  DEFENSIVELY re-validated against the same list after parsing — anything not on the
  list (hallucinated id, leaked prose) is coerced to None. `missing_agent_label` is
  the id's human-readable label, resolved server-side (never model-generated).

HONESTY GUARD (in the prompt)
  Answer strictly from the evidence provided below. Do not invent facts,
  numbers, citations, or partner opinions. If the question needs data not
  present in this evidence, say so explicitly and name which kind of
  agent/tool would need to run — never invent an answer.

STDLIB-ONLY
  Imports: os, json, re, subprocess, shutil + harness.dispatch.CLAUDE_BIN.
  No third-party deps.

ROBUST PARSING (the model rarely returns clean JSON)
  Real Claude output frequently wraps the JSON in a ```json fence```, adds a short
  preamble, or trails off into extra prose. `_parse_model_response` degrades through
  progressively looser extraction (strict parse → fence-stripped parse → first
  balanced {...} object → regex-salvaged "answer" value → the whole text as bare
  prose) so the UI never renders a literal JSON blob to the user.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

try:
    from harness.dispatch import CLAUDE_BIN
except ImportError:
    CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

from report import _derive_citation_labels  # noqa: E402

# ---------------------------------------------------------------------------
# WO-9 Phase 5 — constrain `missing_agent` to a REAL, invocable identifier.
#
# Human-readable labels for the Bucket-1 roster, resolved SERVER-SIDE (never
# model-generated) so the UI can show "Post-Market Safety" instead of a raw
# id. Deliberately a small hand-authored map (the roster is small + stable) —
# NOT derived from `role` (that field is a long spec description, not a UI
# label) and not a generic id.title() (loses acronyms like FDA/DEA/KOL/CMC).
# ---------------------------------------------------------------------------
_BUCKET1_AGENT_LABELS: dict = {
    "internal-science-lead": "Internal Science Lead",
    "emet-runner": "EMET Runner",
    "q-models-runner": "Q-Models Runner",
    "fda-institutional-memory": "FDA Institutional Memory",
    "patent-ip": "Patent / IP",
    "global-regulatory-divergence": "Global Regulatory Divergence",
    "clinical-trial-registry": "Clinical Trial Registry",
    "post-market-safety": "Post-Market Safety",
    "payer": "Payer",
    "dea-scheduling": "DEA Scheduling",
    "manufacturing-cmc": "Manufacturing / CMC",
    "patient-advocacy": "Patient Advocacy",
    "kol-social": "KOL / Social",
    "policy-legislative": "Policy / Legislative",
    "reputational": "Reputational",
    "financial": "Financial",
    "aso-tox": "ASO Toxicity",
    "boltz": "Boltz-2 Structure / Binding",
    "gnomad-constraint": "gnomAD Constraint",
    "gtex-expression": "GTEx Expression",
    "interpro-domains": "InterPro Domains",
    "geneset-enrichment": "Geneset Enrichment",
    "robyn-scs": "Robyn SCS Connectivity",
}


def _bucket1_targets(registry=None) -> list:
    """Real Bucket-1 agent ids the orchestrator can actually re-invoke, sourced from
    the SAME roster + registry live_engine.run_live() uses (never invented here).
    Returns [] on any import/lookup failure (offline/degraded — honest empty)."""
    try:
        from harness.contracts import load_registry
        from live_engine import _BUCKET1_AGENTS
    except ImportError:
        return []
    try:
        reg = registry if registry is not None else load_registry()
        known_ids = {a.get("id") for a in reg.get("agents", [])}
    except Exception:
        return []
    return [
        {"id": aid, "label": _BUCKET1_AGENT_LABELS.get(aid, aid)}
        for aid in _BUCKET1_AGENTS if aid in known_ids
    ]


def _qmodels_targets(client=None) -> list:
    """Real Q-Models tool ids (dti, variant_effect, kg_hypothesis, ...) with their
    registry label. Returns [] on any import/lookup failure (honest empty)."""
    try:
        from qmodels.client import QModelsClient
    except ImportError:
        return []
    try:
        tools = (client if client is not None else QModelsClient()).tools()
    except Exception:
        return []
    out = []
    for t in tools:
        tid = t.get("id")
        if not tid:
            continue
        out.append({"id": tid, "label": t.get("label") or t.get("name") or tid})
    return out


def _valid_targets(registry=None, qmodels_client=None) -> list:
    """The full list of {"id","label"} the model may name as `missing_agent` — Bucket-1
    agents + Q-Models tools. Concatenated (both rosters are small; no cap needed)."""
    return _bucket1_targets(registry) + _qmodels_targets(qmodels_client)


# Matches the "answer" string value in a (possibly malformed) JSON-ish blob,
# tolerating escaped characters inside the string (\" \\ \n ...).
_ANSWER_VALUE_RE = re.compile(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Strip a single wrapping ```json ... ``` (or ``` ... ```) code fence, if present."""
    m = _FENCE_RE.match(text)
    return m.group(1).strip() if m else text


def _extract_balanced_object(text: str) -> "str | None":
    """Return the first top-level {...} substring in ``text`` (string/escape aware),
    or None if no balanced object is found. Tolerates a preamble and/or trailing prose
    around the JSON object — real model output rarely returns bare JSON."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _dict_with_answer(obj) -> "dict | None":
    """Return obj if it's a dict with a non-empty 'answer' string, else None."""
    if not isinstance(obj, dict):
        return None
    answer = str(obj.get("answer", "")).strip()
    if not answer:
        return None
    needs_new_data = bool(obj.get("needs_new_data", False))
    missing_agent = obj.get("missing_agent")
    missing_agent = str(missing_agent).strip() if missing_agent else None
    return {"answer": answer, "needs_new_data": needs_new_data, "missing_agent": missing_agent}


def _salvage_answer_value(text: str) -> "str | None":
    """Last-resort: regex out just the `"answer": "..."` string value and JSON-unescape
    it, WITHOUT requiring the surrounding object to be valid JSON. Never dumps raw JSON."""
    m = _ANSWER_VALUE_RE.search(text)
    if not m:
        return None
    try:
        # Wrapping the captured group back in quotes and parsing it AS a JSON string
        # literal correctly resolves \n, \", \\, \uXXXX, … — safer than hand-rolling
        # unescaping. strict=False additionally tolerates a raw (unescaped) control
        # character the model left inside the string.
        unescaped = json.loads('"' + m.group(1) + '"', strict=False)
        unescaped = str(unescaped).strip()
        return unescaped or None
    except (json.JSONDecodeError, ValueError):
        return None


def _parse_model_response(text: str) -> dict:
    """Robustly parse the model's response into {"answer","needs_new_data","missing_agent"}.

    Real Claude output is frequently NOT clean JSON — a ```json fence```, a short
    preamble ("Here's the answer:"), trailing prose after the object, or a stray
    unescaped character can all break a strict ``json.loads``. This never dumps the
    raw (possibly JSON-looking) text to the user as a fallback; it degrades through
    progressively looser extraction, and the last resort is treating the ENTIRE text
    as plain-prose answer (a model that ignored the JSON instruction entirely and
    just answered directly is still a valid, honest answer).
    """
    stripped = _strip_fences(text)
    balanced = _extract_balanced_object(stripped)
    # Tracks whether we ever saw something that LOOKS like a JSON object was
    # attempted (a top-level dict, even if unusable) — used below to decide
    # whether the ultimate fallback should be the raw text (bare prose, safe to
    # show) or a generic honest message (a broken/incomplete JSON object, which
    # must NEVER be dumped verbatim to the user).
    looked_like_json = balanced is not None

    candidates = [text, stripped]
    if balanced:
        candidates.append(balanced)

    for candidate in candidates:
        try:
            # strict=False tolerates raw control characters (e.g. a literal,
            # unescaped newline) inside string values — a common real-model slip
            # that would otherwise sink an object that is OTHERWISE well-formed.
            parsed = json.loads(candidate, strict=False)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            looked_like_json = True
        result = _dict_with_answer(parsed)
        if result is not None:
            return result

    # Still no valid {"answer": "..."} object — salvage just the answer string via
    # regex (tolerates trailing garbage / an unescaped char elsewhere in the blob
    # that broke strict parsing, without requiring the whole object to be valid).
    salvaged = _salvage_answer_value(stripped)
    if salvaged:
        return {"answer": salvaged, "needs_new_data": False, "missing_agent": None}

    if looked_like_json:
        # The model attempted a structured JSON object but we could not extract
        # a usable answer from it (e.g. the "answer" key itself is missing) —
        # NEVER dump the raw JSON/braces to the user; degrade to an honest,
        # generic message instead.
        return {
            "answer": (
                "Could not parse a clear answer from the model's response — "
                "try rephrasing the question."
            ),
            "needs_new_data": False,
            "missing_agent": None,
            "_parse_failed": True,  # sentinel for retry logic; stripped before return
        }

    # No JSON structure recognizable at all — the model answered in bare prose.
    # That prose IS the answer; render it as-is rather than erroring.
    return {"answer": text.strip(), "needs_new_data": False, "missing_agent": None}


def _report_model() -> str:
    return (os.environ.get("CLAUDE_MODEL") or "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"


def _safe_fact(f: dict) -> dict:
    """Extract only public-safe fields from a dossier fact. Mirrors report.py."""
    return {
        "value": str(f.get("value", ""))[:300],
        "source": str(f.get("source", "")),
        "tier": str(f.get("tier", "")),
        "provenance": str(f.get("provenance", "")),
    }


def _safe_verdict(v: dict) -> dict:
    """Extract only the narrative fields from a partner verdict. Mirrors report.py."""
    return {
        "persona": str(v.get("persona", "")),
        "stance": str(v.get("stance", "")),
        "rationale": str(v.get("rationale", ""))[:400],
        "conviction": v.get("conviction"),
        "revised": bool(v.get("revised", False)),
        "status": str(v.get("status", "")),
    }


def _build_synthesis_blocks(synthesize: dict) -> str:
    """Render the synthesize block as clearly-labelled evidence sections.

    Included only when the run HAS a synthesize block with real content — older/
    simulated runs that lack it are silently skipped (returns empty string).
    ranked_genes (the structured ranking) is rendered compactly as numbered lines.
    report (the final synthesis markdown) is included up to 4000 chars with a note
    if truncated, so ranking/recommendation/report questions can be answered from the
    actual output rather than being incorrectly marked needs_new_data.
    """
    if not synthesize:
        return ""

    parts: list[str] = []

    ranked_genes = synthesize.get("ranked_genes")
    if ranked_genes and isinstance(ranked_genes, list):
        lines: list[str] = []
        for i, entry in enumerate(ranked_genes, 1):
            if isinstance(entry, dict):
                gene = entry.get("gene") or entry.get("name") or entry.get("id") or str(entry)
                score = entry.get("score") or entry.get("rank_score") or entry.get("union_rank")
                note = entry.get("rationale") or entry.get("note") or ""
                line = f"{i}. {gene}"
                if score is not None:
                    line += f" (score: {score})"
                if note:
                    line += f" — {str(note)[:120]}"
                lines.append(line)
            else:
                lines.append(f"{i}. {entry}")
        if lines:
            parts.append("FINAL RANKING (ranked_genes from synthesize):\n" + "\n".join(lines))

    report = synthesize.get("report")
    if report and isinstance(report, str):
        report = report.strip()
        if report:
            _MAX_REPORT = 4000
            if len(report) > _MAX_REPORT:
                truncated = report[:_MAX_REPORT]
                suffix = f"\n[... report truncated at {_MAX_REPORT} chars ...]"
            else:
                truncated = report
                suffix = ""
            parts.append("FINAL REPORT (synthesized):\n" + truncated + suffix)

    return ("\n\n" + "\n\n".join(parts)) if parts else ""


def _build_prompt(question: str, result: dict, citation_labels: list[str],
                   valid_targets: "list | None" = None) -> str:
    """Build the follow-up prompt with the honesty guard and citation instruction."""
    discover = result.get("discover") or {}
    consult = result.get("consult") or {}
    synthesize = result.get("synthesize") or {}
    flags = discover.get("flags") or {}

    dossier = discover.get("dossier") or []
    round1 = consult.get("round1") or []
    round2 = consult.get("round2") or []
    recommendation = str(synthesize.get("recommendation", ""))
    confidence = str(synthesize.get("confidence", ""))
    known_unknowns = flags.get("KNOWN_UNKNOWNS") or []
    query = str(result.get("query", ""))

    safe_dossier = [_safe_fact(f) for f in dossier[:30]]
    safe_round1 = [_safe_verdict(v) for v in round1[:10]]
    safe_round2 = [_safe_verdict(v) for v in round2[:10]]

    dossier_block = json.dumps(safe_dossier, indent=2)
    round1_block = json.dumps(safe_round1, indent=2)
    round2_block = json.dumps(safe_round2, indent=2) if safe_round2 else "(none)"
    ku_block = "\n".join(f"- {ku}" for ku in known_unknowns) if known_unknowns else "(none)"

    # Synthesis evidence (ranked_genes + report) — present only when the run has it.
    synthesis_block = _build_synthesis_blocks(synthesize)

    if citation_labels:
        label_list_str = ", ".join(f"[[{lbl}]]" for lbl in citation_labels)
        citation_instruction = (
            f"\nCITATION INSTRUCTION: Cite evidence inline using EXACT bracket tokens placed at "
            f"the end of the sentence or clause the evidence supports. Use ONLY these tokens "
            f"(derived from this run's evidence): {label_list_str}. Never invent a source label "
            f"not in this list."
        )
    else:
        citation_instruction = ""

    valid_targets = valid_targets or []
    if valid_targets:
        targets_block = "\n".join(f'- "{t["id"]}" — {t["label"]}' for t in valid_targets)
        missing_agent_instruction = f"""
VALID missing_agent TARGETS (the ONLY ids you may return in "missing_agent"):
{targets_block}

"missing_agent" MUST be EITHER exactly one "id" from the list above, OR null — NEVER free
prose, NEVER a description. Only name an id from the list above; if nothing in the list would
answer this, return null even if you can describe in words what's missing — do not invent a
plausible-sounding but fake id."""
    else:
        missing_agent_instruction = (
            '\n"missing_agent" MUST be null (no real invocable targets are available to this run).'
        )

    prompt = f"""You are a senior CNS drug-discovery analyst at Quiver Bioscience. Answer a follow-up
question about a completed diligence run, using ONLY the run's stored evidence below.

ORIGINAL QUERY: {query}
ORIGINAL RECOMMENDATION: {recommendation}
ORIGINAL CONFIDENCE: {confidence}

FOLLOW-UP QUESTION: {question}

HONESTY GUARD: Answer strictly from the evidence provided below. Do not invent facts, numbers,
citations, or partner opinions. If the follow-up question needs data that is NOT present in this
evidence (e.g. it asks about a gene/mechanism/comparison/tool result this run never covered), do
NOT invent an answer — set needs_new_data=true and name which real agent/tool would need to run
to answer it, per the constraint below.{citation_instruction}
{missing_agent_instruction}

DOSSIER FACTS (public fields only, capped at 30):
{dossier_block}

ROUNDTABLE — ROUND 1 VERDICTS (capped at 10):
{round1_block}

ROUNDTABLE — ROUND 2 REBUTTALS (capped at 10):
{round2_block}

KNOWN UNKNOWNS:
{ku_block}{synthesis_block}

Return your response as a SINGLE JSON object on stdout, and nothing else — no markdown fences, no
preamble. The object must have exactly these keys:
  "answer": a markdown string (use [[Label]] citation tokens per the instruction above) that
            answers the follow-up question grounded ONLY in the evidence above.
  "needs_new_data": true or false.
  "missing_agent": one id from the VALID missing_agent TARGETS list above if needs_new_data is
                    true AND a real target would answer it, else null.
"""
    return prompt


def _fallback_answer(dossier: list[dict], round1: list[dict]) -> dict:
    """Deterministic, honest fallback. Never fabricates."""
    n_facts = len(dossier or [])
    n_verdicts = len(round1 or [])
    return {
        "answer": (
            f"Could not reach the model to answer from this run's evidence. {n_facts} dossier "
            f"facts and {n_verdicts} partner verdicts are available — try rephrasing or ask a "
            f"new question."
        ),
        "citations": [],
        "needs_new_data": False,
        "missing_agent": None,
        "missing_agent_label": None,
    }


def answer_followup(question: str, result: "dict | None", runner=None,
                     registry=None, qmodels_client=None) -> dict:
    """Answer a follow-up question from a run's stored evidence. Never raises.

    Parameters
    ----------
    question : the user's free-text follow-up question.
    result   : the full ``run_live`` result dict for the run being followed up on
               (``{"discover": {...}, "consult": {...}, "synthesize": {...}}``).
    runner   : optional callable ``(cmd: list[str]) -> proc`` injected in tests.
               None → real ``claude -p`` subprocess.
    registry : optional pre-loaded harness agents.json dict (injectable for hermetic
               tests); None → ``harness.contracts.load_registry()``.
    qmodels_client : optional pre-built ``QModelsClient`` (injectable for hermetic
               tests); None → a real ``QModelsClient()``.

    Returns
    -------
    dict — ``{"answer": str, "citations": list[str], "needs_new_data": bool,
    "missing_agent": str | None, "missing_agent_label": str | None}``. ``missing_agent``
    is EITHER a real, invocable agent/tool id (validated against the live Bucket-1
    registry + Q-Models tool list — never trusted from the model unvalidated) or
    ``None``; ``missing_agent_label`` is the id's human-readable label, resolved
    server-side. Never raises.
    """
    result = result if isinstance(result, dict) else {}
    discover = result.get("discover") or {}
    consult = result.get("consult") or {}
    dossier = discover.get("dossier") or []
    round1 = consult.get("round1") or []

    try:
        citation_labels = _derive_citation_labels(dossier)
        valid_targets = _valid_targets(registry, qmodels_client)
        prompt = _build_prompt(question, result, citation_labels, valid_targets)
        model = _report_model()

        cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "text", "--model", model]

        if runner is None:
            if not shutil.which(CLAUDE_BIN if CLAUDE_BIN != "claude" else "claude"):
                return _fallback_answer(dossier, round1)

            def runner(cmd: list[str]):  # type: ignore[misc]
                # Same 300s used by report.py — a comparable full-context synthesis call.
                return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Retry the model call up to 3 times on a TRANSIENT failure — a non-zero
        # exit, empty stdout, or an unparseable "looked like JSON but no answer"
        # response. Transient empties happen under momentary resource pressure
        # (the claude subprocess gets starved / OOM-nudged); a couple of retries
        # reliably resolve them. Only fall back to the deterministic answer after
        # EVERY attempt fails — a single empty response must not surface as
        # "could not answer" when a retry would succeed.
        import time as _time
        parsed = None
        _ATTEMPTS = 4
        for _attempt in range(_ATTEMPTS):
            proc = runner(cmd)
            rc = getattr(proc, "returncode", 0)
            text = (getattr(proc, "stdout", "") or "").strip()
            if rc == 0 and text:
                candidate = _parse_model_response(text)
                if not candidate.get("_parse_failed"):
                    parsed = candidate
                    break
                parsed = candidate  # best-effort; keep the parse-failed answer
            # brief, growing backoff before the next attempt so a momentary
            # resource spike (a starved / OOM-nudged claude subprocess on a loaded
            # machine) can clear rather than being hit again immediately.
            if _attempt < _ATTEMPTS - 1:
                _time.sleep(1.5 * (_attempt + 1))
        if parsed is None:
            # every attempt returned empty or non-zero — genuinely unreachable model
            return _fallback_answer(dossier, round1)
        answer = parsed["answer"]
        # citations reflect only the [[Label]] tokens actually present in the final
        # answer text, not every label that WAS available as context — an answer
        # that only drew on Quiver data shouldn't claim an EMET citation too.
        used_citations = [lbl for lbl in citation_labels if f"[[{lbl}]]" in answer]

        # DEFENSIVE VALIDATION (correctness-critical, not optional): never trust the
        # model's `missing_agent` as an invocation target unvalidated. Recompute the
        # same known-id set and coerce anything not in it — free prose, a hallucinated
        # id, a plausible-sounding fake — to None. Only a real id may reach the caller.
        target_by_id = {t["id"]: t["label"] for t in valid_targets}
        raw_missing_agent = parsed["missing_agent"]
        missing_agent = raw_missing_agent if raw_missing_agent in target_by_id else None
        missing_agent_label = target_by_id.get(missing_agent) if missing_agent else None

        return {
            "answer": answer,
            "citations": used_citations,
            "needs_new_data": parsed["needs_new_data"],
            "missing_agent": missing_agent,
            "missing_agent_label": missing_agent_label,
        }

    except Exception:
        return _fallback_answer(dossier, round1)


__all__ = ["answer_followup"]
