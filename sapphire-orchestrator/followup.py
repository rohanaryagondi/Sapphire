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
  answer_followup(question: str, result: dict, runner=None) -> dict

  Returns {"answer": str, "citations": list[str], "needs_new_data": bool,
           "missing_agent": str | None}. Never raises.

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


def _build_prompt(question: str, result: dict, citation_labels: list[str]) -> str:
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

    prompt = f"""You are a senior CNS drug-discovery analyst at Quiver Bioscience. Answer a follow-up
question about a completed diligence run, using ONLY the run's stored evidence below.

ORIGINAL QUERY: {query}
ORIGINAL RECOMMENDATION: {recommendation}
ORIGINAL CONFIDENCE: {confidence}

FOLLOW-UP QUESTION: {question}

HONESTY GUARD: Answer strictly from the evidence provided below. Do not invent facts, numbers,
citations, or partner opinions. If the follow-up question needs data that is NOT present in this
evidence (e.g. it asks about a gene/mechanism/comparison/tool result this run never covered), do
NOT invent an answer — set needs_new_data=true and name, in plain terms, which kind of agent or
tool would need to run to answer it (e.g. "the EMET literature agent" or "a Q-Models
binding-affinity run") — infer this from context, never hallucinate a fake agent id.{citation_instruction}

DOSSIER FACTS (public fields only, capped at 30):
{dossier_block}

ROUNDTABLE — ROUND 1 VERDICTS (capped at 10):
{round1_block}

ROUNDTABLE — ROUND 2 REBUTTALS (capped at 10):
{round2_block}

KNOWN UNKNOWNS:
{ku_block}

Return your response as a SINGLE JSON object on stdout, and nothing else — no markdown fences, no
preamble. The object must have exactly these keys:
  "answer": a markdown string (use [[Label]] citation tokens per the instruction above) that
            answers the follow-up question grounded ONLY in the evidence above.
  "needs_new_data": true or false.
  "missing_agent": a short plain-language description of what would need to run if
                    needs_new_data is true, else null.
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
    }


def answer_followup(question: str, result: "dict | None", runner=None) -> dict:
    """Answer a follow-up question from a run's stored evidence. Never raises.

    Parameters
    ----------
    question : the user's free-text follow-up question.
    result   : the full ``run_live`` result dict for the run being followed up on
               (``{"discover": {...}, "consult": {...}, "synthesize": {...}}``).
    runner   : optional callable ``(cmd: list[str]) -> proc`` injected in tests.
               None → real ``claude -p`` subprocess.

    Returns
    -------
    dict — ``{"answer": str, "citations": list[str], "needs_new_data": bool,
    "missing_agent": str | None}``. Never raises.
    """
    result = result if isinstance(result, dict) else {}
    discover = result.get("discover") or {}
    consult = result.get("consult") or {}
    dossier = discover.get("dossier") or []
    round1 = consult.get("round1") or []

    try:
        citation_labels = _derive_citation_labels(dossier)
        prompt = _build_prompt(question, result, citation_labels)
        model = _report_model()

        cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "text", "--model", model]

        if runner is None:
            if not shutil.which(CLAUDE_BIN if CLAUDE_BIN != "claude" else "claude"):
                return _fallback_answer(dossier, round1)

            def runner(cmd: list[str]):  # type: ignore[misc]
                # Same 300s used by report.py — a comparable full-context synthesis call.
                return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        proc = runner(cmd)

        rc = getattr(proc, "returncode", 0)
        if rc != 0:
            return _fallback_answer(dossier, round1)

        text = (getattr(proc, "stdout", "") or "").strip()
        if not text:
            return _fallback_answer(dossier, round1)

        parsed = _parse_model_response(text)
        answer = parsed["answer"]
        # citations reflect only the [[Label]] tokens actually present in the final
        # answer text, not every label that WAS available as context — an answer
        # that only drew on Quiver data shouldn't claim an EMET citation too.
        used_citations = [lbl for lbl in citation_labels if f"[[{lbl}]]" in answer]
        return {
            "answer": answer,
            "citations": used_citations,
            "needs_new_data": parsed["needs_new_data"],
            "missing_agent": parsed["missing_agent"],
        }

    except Exception:
        return _fallback_answer(dossier, round1)


__all__ = ["answer_followup"]
