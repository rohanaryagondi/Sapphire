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
  Imports: os, json, subprocess, shutil + harness.dispatch.CLAUDE_BIN.
  No third-party deps.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

try:
    from harness.dispatch import CLAUDE_BIN
except ImportError:
    CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

from report import _derive_citation_labels  # noqa: E402


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

        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError("parsed JSON is not an object")
            answer = str(parsed.get("answer", "")).strip()
            if not answer:
                raise ValueError("empty 'answer' field")
            needs_new_data = bool(parsed.get("needs_new_data", False))
            missing_agent = parsed.get("missing_agent")
            missing_agent = str(missing_agent).strip() if missing_agent else None
            return {
                "answer": answer,
                "citations": citation_labels,
                "needs_new_data": needs_new_data,
                "missing_agent": missing_agent,
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            # Never lose the model's output just because it wasn't perfect JSON.
            return {
                "answer": text,
                "citations": citation_labels,
                "needs_new_data": False,
                "missing_agent": None,
            }

    except Exception:
        return _fallback_answer(dossier, round1)


__all__ = ["answer_followup"]
