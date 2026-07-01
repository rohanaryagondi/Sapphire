"""
scoped_chat.py — context-scoped side-chat for one Info-tab step.

Answers a free-text question using ONLY the facts (+ provenance) of the single
trace step the user has open — never the whole dossier, never outside knowledge.
Mirrors summarizer.py's pattern exactly: same CLAUDE_BIN resolution, same
honesty-guard-in-prompt style, same never-raises/deterministic-fallback contract.

CONTRACT:
  answer_scoped(question: str, facts: list[dict], runner=None) -> str

  Returns a plain-English answer grounded strictly in `facts`, or a deterministic
  fallback ("No evidence available for this step." / a claude-failure stub) if the
  call fails. Never raises; never blocks the UI.

HONESTY GUARD (embedded in prompt):
  "Answer strictly from the evidence below. If the answer is not contained in
   these facts, say so explicitly — do not speculate or use outside knowledge."

SCOPE: the caller (frontend2/server.py POST /api/step-chat) is responsible for
narrowing `facts` to exactly the selected step's contributed-facts list before
calling this — this module has no access to the rest of the dossier and cannot
widen scope on its own.
"""
from __future__ import annotations

import json
import os
import subprocess

from harness.dispatch import CLAUDE_BIN

_NO_EVIDENCE = "No evidence available for this step — nothing to answer from."


def answer_scoped(
    question: str,
    facts: list[dict],
    runner=None,
    detail: "dict | None" = None,
) -> str:
    """
    Answer `question` using ONLY `facts` (and optionally `detail`) as context
    (a single trace step's contributed facts + per-agent full output).
    Never fabricates; explicitly declines when the answer isn't in the evidence.

    Parameters
    ----------
    question : the user's free-text question, scoped to one step.
    facts    : list of fact dicts — each with keys `value`, `source`, and
               optionally `tier`, `provenance`. ONLY this list (+ detail below)
               is ever sent to the model; the caller must have already narrowed
               it to the selected step (this function does not see the full dossier).
    runner   : optional callable that takes a cmd list and returns an object
               with `.returncode` and `.stdout`. When None, uses subprocess.run
               with a 30-second timeout.
    detail   : optional per-agent full output dict (public-safe; stripped of any
               internal keys by the caller). When present, it is appended to the
               evidence section so follow-up questions can be answered from the
               complete per-agent evidence. Internal keys (starting with '_') are
               stripped here defensively as well.

    Returns
    -------
    A plain-English string, always. Never raises.
    """
    question = (question or "").strip()
    if not question:
        return "Ask a question to get a scoped answer from this step's evidence."

    if not facts and not detail:
        return _NO_EVIDENCE

    try:
        # Serialize only the value/source/tier/provenance — strip internal keys
        # that would bloat the prompt or leak data the client shouldn't see.
        slim_facts = [
            {
                "value": f.get("value", ""),
                "source": f.get("source", ""),
                "tier": f.get("tier", ""),
                "provenance": f.get("provenance", ""),
            }
            for f in (facts or [])
        ]

        # Build the evidence section. When detail is present, append it as
        # supplementary evidence so the model can answer richer follow-ups.
        evidence_json = json.dumps(slim_facts, separators=(",", ":"))
        detail_section = ""
        if detail:
            # Strip any internal keys (starting with '_') for safety.
            safe_detail = {k: v for k, v in detail.items() if not k.startswith("_")}
            if safe_detail:
                detail_section = (
                    "\n\nAdditional per-agent detail (supplementary evidence — "
                    "may be used if the fact list above does not answer the question):\n"
                    + json.dumps(safe_detail, separators=(",", ":"))
                )

        prompt = (
            "Answer strictly from the evidence below. If the answer is not "
            "contained in these facts, say so explicitly — do not speculate or "
            "use outside knowledge. Never cite a source not in this list. "
            "Return ONLY the answer — no preamble, no explanation of these "
            "instructions.\n\n"
            f"Question: {question}\n\n"
            f"Evidence (the ONLY facts you may use):\n"
            f"{evidence_json}"
            f"{detail_section}\n\n"
            "Write a concise, plain-English answer grounded ONLY in the evidence "
            "above."
        )

        model = os.environ.get("CLAUDE_MODEL", "").strip() or "claude-haiku-4-5"
        cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "text", "--model", model]

        if runner is None:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        else:
            proc = runner(cmd)

        if proc.returncode != 0:
            raise RuntimeError(f"claude exited {proc.returncode}")

        text = proc.stdout.strip()
        if not text:
            raise RuntimeError("empty response")

        return text

    except Exception:
        # Never raises — return a deterministic, honest fallback. We do NOT
        # fabricate an answer when the model call fails; we say so plainly.
        return (
            f"Could not reach the model to answer — here is the raw evidence "
            f"for this step instead: "
            + "; ".join(f.get("value", "") for f in facts[:5] if f.get("value"))
        )


__all__ = ["answer_scoped"]
