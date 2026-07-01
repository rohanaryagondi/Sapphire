"""
report.py — full-narrative diligence report synthesizer.

Synthesizes a detailed Markdown diligence report from the Sapphire engagement
outputs (dossier facts, roundtable verdicts, recommendation) using claude -p.
Mirrors the pattern from summarizer.py: CLAUDE_BIN import, never-raises, runner
injection, deterministic fallback.

CONTRACT
--------
  synthesize_report(
      query, dossier, round1, round2, recommendation, confidence,
      known_unknowns, runner=None,
  ) -> str

  Returns Markdown string. Never raises. Always returns non-empty string.

HONESTY GUARD (in the prompt)
  Synthesize ONLY from the evidence provided below. Do not invent facts,
  numbers, citations, or partner opinions. If partner verdicts are marked
  simulated/placeholder, state in ONE sentence that partner reasoning is
  pending a live run rather than inventing stances.

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


_PROV_TO_LABEL = {
    "emet-live": "EMET",
    "emet": "EMET",
    "moat-real": "Quiver data",
    "moat": "Quiver data",
    "internal": "Quiver data",
    "qmodels": "External Models",
    "q-models": "External Models",
    "live-local": "External Models",
    "fda-memory": "FDA memory",
    "fda_memory": "FDA memory",
    "fda-institutional": "FDA memory",
    "patent-ip": "Patent/IP",
    "patent_ip": "Patent/IP",
    "ip": "Patent/IP",
    "clinical-trial": "Clinical-trial registry",
    "clinical_trial": "Clinical-trial registry",
    "post-market": "Post-market safety",
    "post_market": "Post-market safety",
    "payer": "Payer",
    "manufacturing": "Manufacturing/CMC",
    "cmc": "Manufacturing/CMC",
    "patient-advocacy": "Patient advocacy",
    "patient_advocacy": "Patient advocacy",
    "kol": "KOL/social",
    "kol-social": "KOL/social",
    "policy": "Policy/legislative",
    "dea": "DEA",
    "dea-scheduling": "DEA",
    "global-regulatory": "Global regulatory",
    "regulatory-divergence": "Global regulatory",
}

_CITATION_LABEL_ORDER = [
    "EMET", "Quiver data", "External Models", "FDA memory", "Patent/IP",
    "Clinical-trial registry", "Post-market safety", "Payer", "Manufacturing/CMC",
    "Patient advocacy", "KOL/social", "Policy/legislative", "DEA", "Global regulatory",
]


def _derive_citation_labels(dossier: list[dict]) -> list[str]:
    """Derive the set of source labels present in this dossier."""
    seen: set[str] = set()
    for f in dossier:
        prov = str(f.get("provenance", "")).lower()
        for key, label in _PROV_TO_LABEL.items():
            if key in prov:
                seen.add(label)
                break
    return [lbl for lbl in _CITATION_LABEL_ORDER if lbl in seen]


def _report_model() -> str:
    return (os.environ.get("CLAUDE_MODEL") or "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"


def _safe_fact(f: dict) -> dict:
    """Extract only public-safe fields from a dossier fact."""
    return {
        "value": str(f.get("value", ""))[:300],
        "source": str(f.get("source", "")),
        "tier": str(f.get("tier", "")),
        "provenance": str(f.get("provenance", "")),
    }


def _safe_verdict(v: dict) -> dict:
    """Extract only the narrative fields from a partner verdict."""
    return {
        "persona": str(v.get("persona", "")),
        "stance": str(v.get("stance", "")),
        "rationale": str(v.get("rationale", ""))[:400],
        "conviction": v.get("conviction"),
        "revised": bool(v.get("revised", False)),
        "status": str(v.get("status", "")),
    }


def _build_prompt(
    query: str,
    dossier: list[dict],
    round1: list[dict],
    round2: list[dict],
    recommendation: str,
    confidence: str,
    known_unknowns: list[str],
) -> str:
    """Build the diligence report prompt with honesty guard and structured sections."""
    safe_dossier = [_safe_fact(f) for f in dossier[:30]]
    safe_round1 = [_safe_verdict(v) for v in round1[:10]]
    safe_round2 = [_safe_verdict(v) for v in round2[:10]]

    dossier_block = json.dumps(safe_dossier, indent=2)
    round1_block = json.dumps(safe_round1, indent=2)
    round2_block = json.dumps(safe_round2, indent=2) if safe_round2 else "(none)"
    ku_block = "\n".join(f"- {ku}" for ku in known_unknowns) if known_unknowns else "(none)"

    # Derive citation labels from provenance in the dossier
    citation_labels = _derive_citation_labels(dossier)
    if citation_labels:
        _label_descriptions = {
            "EMET": "published literature",
            "Quiver data": "Quiver CNS_DFP",
            "External Models": "predictive models",
            "FDA memory": "FDA institutional memory",
            "Patent/IP": "patent and IP landscape",
            "Clinical-trial registry": "clinical trial registry",
            "Post-market safety": "post-market safety data",
            "Payer": "payer coverage data",
            "Manufacturing/CMC": "manufacturing and CMC data",
            "Patient advocacy": "patient advocacy landscape",
            "KOL/social": "KOL and social sentiment",
            "Policy/legislative": "policy and legislative context",
            "DEA": "DEA scheduling",
            "Global regulatory": "global regulatory landscape",
        }
        label_list_str = ", ".join(
            f"[[{lbl}]] ({_label_descriptions.get(lbl, lbl)})"
            for lbl in citation_labels
        )
        citation_instruction = (
            f"\nCITATION INSTRUCTION: Cite evidence inline using EXACT bracket tokens placed at the END of the sentence or clause the evidence supports. "
            f"Use ONLY these tokens (derived from the evidence below): {label_list_str}. "
            f"Rules: if an ENTIRE paragraph draws on a SINGLE source, cite it ONCE at the end of that paragraph — do NOT repeat the same source token within the paragraph. "
            f"Cite per-sentence only when a paragraph mixes multiple different sources. "
            f"Do NOT cite general reasoning — only evidence-derived claims. Never invent a source label not in this list."
        )
    else:
        citation_instruction = ""

    prompt = f"""You are a senior CNS drug-discovery analyst at Quiver Bioscience. Write a detailed Markdown diligence report for the following query.

QUERY: {query}

RECOMMENDATION: {recommendation}
CONFIDENCE: {confidence}

Write a report with EXACTLY this structure:

A 2–3 sentence abstract (no heading) that states the conclusion (recommendation + core reason + one sentence on what the report covers).

Then these ## headed sections:

## Target & mechanism
Draw on the evidence to describe the biological target, mechanism, and disease relevance.

## Internal evidence (Quiver data)
Synthesize internal (Quiver data/CNS_DFP) dossier facts. If none are present in the dossier, state that no internal evidence was surfaced in this run.

## External evidence & landscape
Synthesize external facts (EMET, Q-Models, semantic agents) into prose. Weave facts into narrative — do NOT list them as bullets.

## Regulatory / IP & commercial
Synthesize regulatory, IP, payer, or commercial evidence from the dossier. Omit this section heading only if the dossier contains no such facts.

## How the partners weighed in
Synthesize the roundtable verdicts — identify the consensus position, note notable dissents, and highlight any conviction shifts from round 1 to round 2.

## Recommendation, risks & next step
Restate the recommendation with confidence level. Enumerate the top 2–3 risks. State the most concrete next experimental or clinical step.

---

HONESTY GUARD: Synthesize ONLY from the evidence provided below. Do not invent facts, numbers, citations, or partner opinions. Refer to sources by name (e.g. 'EMET', 'Quiver data', 'External Models') — never quote DOIs/PMIDs. If the partner verdicts are marked simulated/placeholder, state in ONE sentence that partner reasoning is pending a live run rather than inventing stances. When the answer is naturally tabular — e.g. ranking genes/candidates or comparing options — present it as a GitHub-flavored Markdown table.{citation_instruction}

DOSSIER FACTS (public fields only, capped at 30):
{dossier_block}

ROUNDTABLE — ROUND 1 VERDICTS (capped at 10):
{round1_block}

ROUNDTABLE — ROUND 2 REBUTTALS (capped at 10):
{round2_block}

KNOWN UNKNOWNS:
{ku_block}

Write the report now. Use ## for section headings. Use **bold** sparingly for key terms. Do NOT use bullet lists inside sections — write flowing prose. Do NOT fabricate partner stances beyond what is in the verdict data above. Return only the Markdown report, nothing else."""

    return prompt


def _fallback_report(
    query: str,
    dossier: list[dict],
    round1: list[dict],
    recommendation: str,
    confidence: str,
    known_unknowns: list[str],
) -> str:
    """Deterministic fallback assembled from structured args. Never a stack trace."""
    internal_facts = [
        f for f in dossier
        if any(k in str(f.get("provenance", "")).lower()
               for k in ("moat", "internal", "cns_dfp", "cnsd"))
    ]
    external_facts = [f for f in dossier if f not in internal_facts]

    lines: list[str] = ["# Sapphire Diligence Report", ""]
    lines.append(f"**Query:** {query}")
    lines.append("")

    # Abstract from recommendation + confidence
    lines.append(f"**Recommendation:** {recommendation}")
    lines.append("")
    lines.append(f"**Confidence:** {confidence}")
    lines.append("")

    # Fact counts by provenance bucket
    lines.append("## Evidence summary")
    lines.append("")
    lines.append(f"- Internal facts (Quiver data): {len(internal_facts)}")
    lines.append(f"- External facts (EMET, Q-Models, semantic): {len(external_facts)}")
    lines.append(f"- Total dossier facts: {len(dossier)}")
    lines.append("")

    # Partner stances if present
    if round1:
        lines.append("## Partner stances (round 1)")
        lines.append("")
        for v in round1[:10]:
            persona = str(v.get("persona", "Unknown"))
            stance = str(v.get("stance", ""))
            rationale = str(v.get("rationale", ""))
            status = str(v.get("status", ""))
            entry = f"- **{persona}**: {stance}"
            if rationale:
                entry += f" — {rationale[:200]}"
            if status and status != "ok":
                entry += f" _(status: {status})_"
            lines.append(entry)
        lines.append("")

    # Known unknowns
    if known_unknowns:
        lines.append("## Known unknowns")
        lines.append("")
        for ku in known_unknowns:
            lines.append(f"- {ku}")
        lines.append("")

    lines.append("_Full narrative pending live Claude run._")
    lines.append("")

    return "\n".join(lines)


def synthesize_report(
    query: str,
    dossier: list[dict],
    round1: list[dict],
    round2: list[dict],
    recommendation: str,
    confidence: str,
    known_unknowns: list[str],
    runner=None,
) -> str:
    """Synthesize a Markdown diligence report from the engagement outputs.

    Parameters
    ----------
    query:          The original user query.
    dossier:        Bucket-1 fact list from the engagement.
    round1:         Roundtable round-1 verdict list.
    round2:         Roundtable round-2 rebuttal list.
    recommendation: Synthesized recommendation string.
    confidence:     Confidence label.
    known_unknowns: List of known-unknown strings from the flags.
    runner:         Optional callable ``(cmd: list[str]) -> proc`` injected in
                    tests. None → real claude -p subprocess.

    Returns
    -------
    str — Markdown report, or the deterministic fallback. Never raises.
    """
    try:
        prompt = _build_prompt(
            query=query,
            dossier=dossier,
            round1=round1,
            round2=round2,
            recommendation=recommendation,
            confidence=confidence,
            known_unknowns=known_unknowns,
        )
        model = _report_model()

        cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "text", "--model", model]

        if runner is None:
            if not shutil.which(CLAUDE_BIN if CLAUDE_BIN != "claude" else "claude"):
                return _fallback_report(
                    query, dossier, round1, recommendation, confidence, known_unknowns
                )

            def runner(cmd: list[str]):  # type: ignore[misc]
                return subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        proc = runner(cmd)

        rc = getattr(proc, "returncode", 0)
        if rc != 0:
            return _fallback_report(
                query, dossier, round1, recommendation, confidence, known_unknowns
            )

        text = (getattr(proc, "stdout", "") or "").strip()
        if not text:
            return _fallback_report(
                query, dossier, round1, recommendation, confidence, known_unknowns
            )

        return text

    except Exception:
        return _fallback_report(
            query, dossier, round1, recommendation, confidence, known_unknowns
        )
