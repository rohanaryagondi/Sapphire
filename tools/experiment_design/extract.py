"""
extract.py — Sapphire Experiment Design tool (ED-1): Otter meeting transcript -> structured experiment plan.

Ported/adapted from MatthewCarey24/design-form-agent (Matt Carey, Quiver) — see
this dir's README.md and vendor/design-form-agent/VENDORED.md. The proprietary
domain content (system prompt / MENUS_REFERENCE / schema) is preserved VERBATIM in
extraction_prompt.py and schema.py; THIS module is the adapted plumbing
(extract / render_md / CLI). The Slack bot (app.py) is intentionally NOT ported.

DATA BOUNDARY (dev/CONVENTIONS.md §3): meeting transcripts are internal Quiver
data. This tool sends them ONLY to Claude (the reasoning LLM, via the Anthropic
SDK) and reads/writes ONLY local files. It must NEVER send transcript content to
an external evidence source (EMET / web / public databases). Sending internal
notes to the reasoning LLM is allowed (the personas already do); leaking them to
an external evidence source is not.

Runtime posture: the third-party dep (`anthropic`) lives in THIS tool's subprocess
only and is imported LAZILY inside extract() — the Sapphire engine stays
stdlib-only and imports nothing here. A live run needs ANTHROPIC_API_KEY in env.

Usage: python tools/experiment_design/extract.py transcript.(txt|pdf) [--output-dir ./out]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import datetime
from pathlib import Path

try:  # script-run (this dir on sys.path)
    from extraction_prompt import SYSTEM_PROMPT, EXTRACTION_PROMPT, MENUS_REFERENCE
except ImportError:  # package-style import
    from .extraction_prompt import SYSTEM_PROMPT, EXTRACTION_PROMPT, MENUS_REFERENCE

_MODEL = "claude-opus-4-8"
_MAX_TOKENS = 10000


class ExtractionError(RuntimeError):
    """An honest, user-facing failure (bad input, missing key, non-JSON model output).
    The tool degrades honestly — it never fabricates a plan on bad input."""


# ── Confidence emoji flags (verbatim from the original) ───────────────
CONFIDENCE_FLAG = {
    "high": "",
    "medium": "🔶",
    "low": "⚠️",
    "unresolved": "❌",
}


def flag(field: dict) -> str:
    """Return 'FLAG value (source)' or 'FLAG UNRESOLVED (source)'."""
    c = field.get("confidence", "low")
    v = field.get("value")
    src = field.get("source", "")
    emoji = CONFIDENCE_FLAG.get(c, "⚠️")
    label = str(v) if v not in (None, "") else "—"
    suffix = f" _({src})_" if src else ""
    return f"{emoji} {label}{suffix}"


# ── Extraction ────────────────────────────────────────────────────────
def extract(path) -> dict:
    """Read an Otter transcript (.txt or .pdf), send it to Claude, return the parsed plan dict.

    Honest failure (never a fabricated plan): missing/empty/unsupported input -> ExtractionError
    BEFORE any LLM call; ANTHROPIC_API_KEY unset -> ExtractionError; non-JSON model output ->
    ExtractionError.
    """
    path = Path(path)
    if not path.exists():
        raise ExtractionError(f"transcript not found: {path}")
    if path.stat().st_size == 0:
        raise ExtractionError(f"transcript is empty: {path}")
    if path.suffix.lower() not in (".txt", ".pdf"):
        raise ExtractionError(f"unsupported transcript type {path.suffix!r} (use .txt or .pdf)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ExtractionError("ANTHROPIC_API_KEY is not set — required for a live extraction.")

    try:
        import anthropic  # lazy: keeps the engine/tests import-safe without the dep
    except ImportError as exc:
        raise ExtractionError("the 'anthropic' package is not installed (pip install anthropic)") from exc

    client = anthropic.Anthropic()
    full_system = SYSTEM_PROMPT + "\n\n" + MENUS_REFERENCE

    if path.suffix.lower() == ".pdf":
        prompt = EXTRACTION_PROMPT.replace(
            "--- TRANSCRIPT ---\n{transcript}\n--- END TRANSCRIPT ---",
            "The transcript is attached as a PDF. Extract the structured experiment information as JSON:"
        )
        pdf_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        content = [
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_data},
            },
            {"type": "text", "text": prompt},
        ]
    else:
        transcript = path.read_text(encoding="utf-8")
        prompt = EXTRACTION_PROMPT.replace("{transcript}", transcript)
        content = [{"type": "text", "text": prompt}]

    msg = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=full_system,
        messages=[{"role": "user", "content": content}],
    )

    if not msg.content or not getattr(msg.content[0], "text", None):
        raise ExtractionError("model returned no text content")
    raw = msg.content[0].text
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"model did not return valid JSON: {exc}") from exc


# ── Markdown renderer (verbatim from the original) ────────────────────
def render_md(data: dict) -> str:
    lines = []

    # Header
    lines.append(f"# Meeting Extraction: {data.get('meeting_title', 'Untitled')}")
    lines.append(f"**Date:** {data.get('meeting_date', '—')}  ")
    lines.append(f"**Type:** {data.get('meeting_type', '—')}  ")
    attendees = data.get("attendees", [])
    if attendees:
        lines.append(f"**Attendees:** {', '.join(attendees)}  ")
    lines.append(f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    lines.append("\n---\n")

    # Legend
    lines.append("**Confidence legend:** 🔶 medium &nbsp; ⚠️ low &nbsp; ❌ unresolved\n")
    lines.append("---\n")

    # Experiments
    for i, exp in enumerate(data.get("experiments", []), 1):
        lines.append(f"## Experiment {i}: {exp.get('experiment_name', 'Unnamed')}")
        desc = exp.get("experiment_description", "")
        if desc:
            lines.append(f"_{desc}_\n")

        # Metadata
        m = exp.get("metadata", {})
        lines.append("### Metadata")
        lines.append(f"- **Project code:** {flag(m.get('project_code', {}))}")
        lines.append(f"- **Assay type:** {flag(m.get('assay_type', {}))}")
        lines.append(f"- **Sub-assay type:** {flag(m.get('sub_assay_type', {}))}")
        lines.append(f"- **Round:** {flag(m.get('round_number', {}))}")

        # Culture
        c = exp.get("culture", {})
        lines.append("\n### Culture")
        lines.append(f"- **Plate type:** {flag(c.get('plate_type', {}))}")
        lines.append(f"- **Num plates:** {flag(c.get('num_plates', {}))}")
        lines.append(f"- **Glia:** {flag(c.get('glia', {}))}")

        genos = c.get("genotypes", [])
        if genos:
            lines.append("- **Genotypes:**")
            for g in genos:
                name = flag(g.get("name", {}))
                density = flag(g.get("density", {}))
                lot = flag(g.get("lot_number", {}))
                lines.append(f"  - {name} | density: {density} | lot: {lot}")

        viruses = c.get("viruses", [])
        if viruses:
            lines.append("- **Viruses:**")
            for v in viruses:
                lines.append(f"  - {flag(v)}")

        # Imaging
        img = exp.get("imaging", {})
        lines.append("\n### Imaging")
        lines.append(f"- **Imaging date:** {flag(img.get('imaging_date', {}))}")
        lines.append(f"- **DIV:** {flag(img.get('imaging_div', {}))}")
        lines.append(f"- **Buffer:** {flag(img.get('imaging_buffer', {}))}")
        lines.append(f"- **Stim protocol:** {flag(img.get('stim_protocol', {}))}")
        lines.append(f"- **FOVs/well:** {flag(img.get('fovs_per_well', {}))}")
        lines.append(f"- **Temperature:** {flag(img.get('temperature', {}))}")
        lines.append(f"- **Synaptic blockers:** {flag(img.get('synaptic_blockers', {}))}")

        # Treatments
        treatments = exp.get("treatments", [])
        if treatments:
            lines.append("\n### Treatments")
            for t in treatments:
                cname = flag(t.get("compound_name", {}))
                lines.append(f"- **{cname}**")
                concs = t.get("concentrations", [])
                if concs:
                    conc_str = ", ".join(flag(c) for c in concs)
                    lines.append(f"  - Concentrations: {conc_str}")
                lines.append(f"  - Vehicle: {flag(t.get('vehicle', {}))}")
                lines.append(f"  - Timing: {flag(t.get('timing', {}))}")
                lines.append(f"  - Addition protocol: {flag(t.get('addition_protocol', {}))}")
                purpose = t.get("purpose", "")
                if purpose:
                    lines.append(f"  - Purpose: {purpose}")

        # Plate layout
        pl = exp.get("plate_layout", {})
        lines.append("\n### Plate Layout")
        lines.append(f"- **Strategy:** {flag(pl.get('layout_strategy', {}))}")
        controls = pl.get("controls", [])
        if controls:
            lines.append("- **Controls:**")
            for ctrl in controls:
                lines.append(f"  - {flag(ctrl)}")
        for note in pl.get("notes", []):
            lines.append(f"- _{note}_")

        # Timeline
        tl = exp.get("timeline", {})
        events = tl.get("events", [])
        if events:
            lines.append("\n### Timeline")
            for ev in events:
                div = ev.get("relative_day", "")
                date = ev.get("absolute_date", "")
                when = " | ".join(filter(None, [div, date]))
                note = ev.get("notes", "")
                lines.append(f"- **{when}**: {ev.get('event', '')} {f'_{note}_' if note else ''}")

        # Analysis notes
        anotes = exp.get("analysis_notes", [])
        if anotes:
            lines.append("\n### Analysis Notes")
            for n in anotes:
                lines.append(f"- {n}")

        lines.append("\n---\n")

    # Action items
    action_items = data.get("action_items", [])
    if action_items:
        lines.append("## Action Items")
        for a in action_items:
            pri = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(a.get("priority", ""), "")
            assignee = a.get("assignee") or "unassigned"
            deadline = a.get("deadline") or "no deadline"
            lines.append(f"- {pri} **{assignee}** ({deadline}): {a.get('description', '')}")
        lines.append("")

    # Open questions
    open_qs = data.get("open_questions", [])
    if open_qs:
        lines.append("## Open Questions")
        for q in open_qs:
            lines.append(f"- ❓ **{q.get('question', '')}**")
            ctx = q.get("context", "")
            if ctx:
                lines.append(f"  - _Context: {ctx}_")
            proposed = q.get("proposed_answers", [])
            if proposed:
                lines.append(f"  - Options: {', '.join(proposed)}")
            decider = q.get("who_should_decide")
            if decider:
                lines.append(f"  - Decide: {decider}")
        lines.append("")

    # Additional notes
    notes = data.get("additional_notes", [])
    if notes:
        lines.append("## Additional Notes")
        for n in notes:
            lines.append(f"- {n}")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Extract a Quiver experiment plan from an Otter meeting transcript (.txt or .pdf)."
    )
    parser.add_argument("transcript", help="Path to transcript .txt or .pdf")
    parser.add_argument("--output-dir", default=".", help="Directory for output files (default: .)")
    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    output_dir = Path(args.output_dir)

    try:
        data = extract(transcript_path)
    except ExtractionError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = transcript_path.stem
    json_out = output_dir / f"{stem}_extraction.json"
    md_out = output_dir / f"{stem}_extraction.md"
    json_out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    md_out.write_text(render_md(data), encoding="utf-8")
    print(f"Wrote {json_out}")
    print(f"Wrote {md_out}")


if __name__ == "__main__":
    main()
