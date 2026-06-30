"""
summarizer.py — per-step fact distillation for the live trace panel.

Distills each agent's facts into one tight ~12–18-word takeaway ("the skill
that chooses the words carefully"). Uses the smallest model (haiku) via the
existing `claude -p` subprocess path. Hard word budget + honesty guard.

CONTRACT
--------
  summarize_step(facts, agent_id, runner=None) -> str

  Returns a 12–18-word plain-English takeaway, or a deterministic fallback
  "{n} facts · {provenance}" if the call fails or the word budget is exceeded.
  Never raises; never blocks the engagement.

HONESTY GUARD (in the prompt)
  "Only restate what is stated in the cited facts below. If you are uncertain
   about any claim, say so. Never add a claim that is not present in the
   evidence. Return ONLY the summary sentence, nothing else."

CACHING
  The caller stamps the returned string onto the event dict as event["summary"].
  History replay is instant ($0) because the summary is already stored in the
  trace event and never re-computed.

STDLIB-ONLY
  This module imports only stdlib (subprocess, json, os, shutil) plus the
  CLAUDE_BIN constant from harness.dispatch (which itself is stdlib-only + env).
  No third-party deps enter the engine through this module.
"""
from __future__ import annotations

import json
import os
import subprocess
import shutil

# Reuse the same CLAUDE_BIN resolution the harness already uses (env-injectable
# in tests via CLAUDE_BIN=<mock>).  Import is lazy-safe: harness.dispatch is
# stdlib-only and always available in the engine runtime.
try:
    from harness.dispatch import CLAUDE_BIN
except ImportError:
    CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

# Hard budget: prompt asks for ≤18 words; we tolerate a small buffer of 2.
_WORD_BUDGET = 18
_WORD_BUDGET_HARD = _WORD_BUDGET + 2  # 20 — if exceeded, fall back to stub

# Default model: haiku — cheapest, fastest; overrideable via SAPPHIRE_SUMMARY_MODEL
# (or CLAUDE_MODEL for backward-compat with the dispatch path's lever).
_DEFAULT_MODEL = "claude-haiku-4-5"


def _summary_model() -> str:
    """Resolve the model for summarization. Cheaper env var wins first."""
    return (
        os.environ.get("SAPPHIRE_SUMMARY_MODEL")
        or os.environ.get("CLAUDE_MODEL")
        or _DEFAULT_MODEL
    ).strip() or _DEFAULT_MODEL


def _build_prompt(facts: list[dict]) -> str:
    """Build the summarizer prompt with the honesty guard and hard word budget."""
    if not facts:
        return (
            "Summarize the following agent result in 12–18 words, maximum.\n\n"
            "Facts: (none — agent returned no cited facts)\n\n"
            "HONESTY GUARD: Only restate what is stated in the cited facts above. "
            "If you are uncertain about any claim, say so. "
            "Never add a claim that is not present in the evidence. "
            "Return ONLY the summary sentence (12–18 words), nothing else.\n\n"
            "If there are no facts, return: 'No cited facts returned by this agent.'"
        )

    # Compact fact list: value + source only (no internal metadata)
    fact_lines = []
    for i, f in enumerate(facts[:10], 1):  # cap at 10 to keep the prompt short
        val = str(f.get("value", "")).strip()
        src = str(f.get("source", "")).strip()
        line = f"  {i}. {val}"
        if src:
            line += f" [{src}]"
        fact_lines.append(line)

    facts_block = "\n".join(fact_lines)

    return (
        f"Summarize the following cited facts in exactly 12–18 words, maximum. "
        f"Use plain English. Do NOT use bullet points or lists.\n\n"
        f"Facts:\n{facts_block}\n\n"
        f"HONESTY GUARD: Only restate what is stated in the cited facts above. "
        f"If you are uncertain about any claim, say so. "
        f"Never add a claim that is not present in the evidence. "
        f"Return ONLY the summary sentence (12–18 words), nothing else."
    )


def _fallback(facts: list[dict], agent_id: str) -> str:
    """Deterministic 1-line stub used when the summarizer call fails."""
    n = len(facts)
    prov = ""
    if facts:
        prov = str(facts[0].get("provenance", "")).strip()
    label = prov if prov else agent_id
    return f"{n} fact{'s' if n != 1 else ''} · {label}"


def summarize_step(
    facts: list[dict],
    agent_id: str,
    runner=None,
) -> str:
    """Distill ``facts`` into a tight ≤18-word takeaway for the live trace panel.

    Parameters
    ----------
    facts:    list of fact dicts (``{"value": …, "source": …, …}``).  Empty list
              is valid — the fallback string reflects it honestly.
    agent_id: agent identifier, used only in the fallback string.
    runner:   optional callable ``(cmd: list[str]) -> proc`` (same interface as
              harness/dispatch.py).  Injected in tests to avoid a live subprocess.
              ``None`` → real ``claude -p`` subprocess.

    Returns
    -------
    str — a ≤18-word plain-English summary, or the deterministic fallback stub.
    Never raises.
    """
    try:
        prompt = _build_prompt(facts)
        model = _summary_model()

        cmd = [
            CLAUDE_BIN, "-p", prompt,
            "--output-format", "text",
            "--model", model,
        ]

        if runner is None:
            # Check that the claude binary is available; if not, fall back immediately.
            if not shutil.which(CLAUDE_BIN if CLAUDE_BIN != "claude" else "claude"):
                return _fallback(facts, agent_id)

            def runner(cmd: list[str]):  # type: ignore[misc]
                return subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30
                )

        proc = runner(cmd)

        rc = getattr(proc, "returncode", 0)
        if rc != 0:
            return _fallback(facts, agent_id)

        text = (getattr(proc, "stdout", "") or "").strip()
        if not text:
            return _fallback(facts, agent_id)

        # Enforce hard word budget
        words = text.split()
        if len(words) > _WORD_BUDGET_HARD:
            return _fallback(facts, agent_id)

        return text

    except Exception:
        return _fallback(facts, agent_id)
