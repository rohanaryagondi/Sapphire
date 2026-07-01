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
      known_unknowns, runner=None, on_chunk=None,
  ) -> str

  Returns Markdown string. Never raises. Always returns non-empty string.

  `on_chunk` (optional, `Callable[[str], None]`) — WO-9 Phase 2 progressive-report
  streaming. When provided:
    - with an injected `runner` (tests / any caller mocking the subprocess): the
      existing `runner(cmd)` synchronous path is UNCHANGED; `on_chunk` is simply
      called ONCE with the full final text after a successful parse (no real
      streaming subprocess needed to exercise this in hermetic tests).
    - with `runner=None` (the real/production path): a SEPARATE `claude -p`
      invocation is used, with `--output-format stream-json
      --include-partial-messages --verbose` instead of `--output-format text`.
      The subprocess is run via `subprocess.Popen` and its stdout is read
      line-by-line; each JSONL line is parsed and, when it is a
      `{"type": "stream_event", "event": {"type": "content_block_delta",
      "delta": {"type": "text_delta", "text": "..."}}}` line, the delta text is
      accumulated AND passed to `on_chunk` immediately. All other line shapes
      (`thinking_delta`, `content_block_start/stop`, `message_*`, `"type":
      "system"`, `"type": "result"`, malformed/non-JSON lines) are silently
      skipped. The SAME 300s timeout used by the non-streaming path applies; on
      timeout the subprocess is killed and the call degrades to the
      deterministic fallback report (never returns a truncated report as if it
      were complete). `on_chunk=None` ⇒ behavior is byte-for-byte identical to
      before this parameter existed.

HONESTY GUARD (in the prompt)
  Synthesize ONLY from the evidence provided below. Do not invent facts,
  numbers, citations, or partner opinions. If partner verdicts are marked
  simulated/placeholder, state in ONE sentence that partner reasoning is
  pending a live run rather than inventing stances.

STDLIB-ONLY
  Imports: os, json, subprocess, shutil, time + harness.dispatch.CLAUDE_BIN.
  No third-party deps.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

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

DISCOVERY MINDSET: Quiver is a discovery company — the alpha is in genes that carry strong internal (Quiver CNS_DFP / EP-signature / moat) evidence but have received only modest or emerging attention from the published literature. Weight internal evidence heavily as the PRIMARY signal; treat modest or emerging external attention as a POSITIVE (early external validation + a discovery opportunity, not a weakness). Do NOT penalise a target for thin literature coverage when the internal signal is strong — explicitly call out that low literature saturation on a strong-internal hit can itself be the discovery alpha (Quiver seeing what the field has not yet). Genes already saturated with published evidence are less novel; genes with strong internal signal and some external corroboration are the opportunity. Surface contradictions, risks, and DIVERGENCE honestly — this framing is a lens, not a filter.

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


# 300s: a full sonnet synthesis of the dossier runs ~70-100s; 120s was too tight and
# silently fell back to the deterministic report under any variance/load. This cap only
# bounds a hang. Shared by BOTH the non-streaming and the streaming subprocess paths.
_TIMEOUT_S = 300


def _stream_claude_report(cmd: list[str], on_chunk) -> str | None:
    """Run `cmd` (a `claude -p ... --output-format stream-json ...` invocation) via
    `subprocess.Popen`, streaming text deltas to `on_chunk` as they arrive.

    Returns the accumulated report text on success, or `None` on spawn failure,
    a non-zero return code, an empty accumulated buffer, or a timeout (bounded by
    `_TIMEOUT_S`, same as the non-streaming path) — in every `None` case the caller
    falls back to the deterministic report. Never raises.
    """
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
        )
    except Exception:
        return None

    buf: list[str] = []
    start = time.monotonic()
    timed_out = False
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            if time.monotonic() - start > _TIMEOUT_S:
                timed_out = True
                try:
                    proc.kill()
                except Exception:
                    pass
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue  # malformed/non-JSON lines are skipped silently
            if not isinstance(obj, dict) or obj.get("type") != "stream_event":
                continue  # system/result/other top-level lines are skipped silently
            event = obj.get("event") or {}
            if event.get("type") != "content_block_delta":
                continue
            delta = event.get("delta") or {}
            if delta.get("type") != "text_delta":
                continue  # thinking_delta (and any other delta kind) is never surfaced
            chunk = delta.get("text") or ""
            if not chunk:
                continue
            buf.append(chunk)
            try:
                on_chunk(chunk)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        for pipe in (proc.stdout, proc.stderr):
            try:
                if pipe is not None:
                    pipe.close()
            except Exception:
                pass

    if timed_out:
        return None
    if (proc.returncode or 0) != 0:
        return None
    full = "".join(buf).strip()
    return full or None


def synthesize_report(
    query: str,
    dossier: list[dict],
    round1: list[dict],
    round2: list[dict],
    recommendation: str,
    confidence: str,
    known_unknowns: list[str],
    runner=None,
    on_chunk=None,
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
    on_chunk:       Optional ``Callable[[str], None]`` for progressive-report
                    streaming (WO-9 Phase 2). See the module CONTRACT docstring
                    for the exact semantics. ``None`` → unchanged behavior.

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

        if runner is not None:
            # Injected-runner path (all existing + on_chunk tests): unchanged synchronous
            # call. The only addition is a single terminal on_chunk(full_text) so tests can
            # assert it fired without mocking a streaming Popen.
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

            if on_chunk is not None:
                try:
                    on_chunk(text)
                except Exception:
                    pass
            return text

        # runner is None — the real/production path.
        if not shutil.which(CLAUDE_BIN if CLAUDE_BIN != "claude" else "claude"):
            return _fallback_report(
                query, dossier, round1, recommendation, confidence, known_unknowns
            )

        if on_chunk is not None:
            # NEW streaming path: a separate stream-json invocation, never the
            # `--output-format text` `cmd` above (that mode does not stream — the
            # buffered non-streaming path below still uses it when on_chunk is absent).
            stream_cmd = [
                CLAUDE_BIN, "-p", prompt,
                "--output-format", "stream-json",
                "--include-partial-messages", "--verbose",
                "--model", model,
            ]
            streamed = _stream_claude_report(stream_cmd, on_chunk)
            if streamed:
                return streamed
            return _fallback_report(
                query, dossier, round1, recommendation, confidence, known_unknowns
            )

        def runner(cmd: list[str]):  # type: ignore[misc]
            return subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT_S)

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
