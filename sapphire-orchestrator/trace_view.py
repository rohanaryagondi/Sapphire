"""Terminal transparency tool for Sapphire — pretty-prints the harness trace
of an engagement so a human can see exactly what the orchestrator and every
agent did.

Usage:
    python trace_view.py <engagement_id> [--full]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution — mirrors harness/trace.py exactly
# ---------------------------------------------------------------------------

_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "RohanOnly" / "engagements"


def _base_dir() -> Path:
    return Path(os.environ.get("SAPPHIRE_ENGAGEMENTS_DIR", str(_DEFAULT_DIR)))


def _trace_path(engagement_id: str) -> Path:
    return _base_dir() / engagement_id / "trace.jsonl"


# ---------------------------------------------------------------------------
# Status glyph
# ---------------------------------------------------------------------------

def _glyph(status: str | None) -> str:
    s = (status or "").lower()
    if s in ("ok", "done", "complete", "completed", "success"):
        return "✓"
    if s in ("abstained", "abstain"):
        return "⚠"
    if s in ("escalated", "escalate", "veto", "error", "failed", "fail"):
        return "⛔"
    return "·"


# ---------------------------------------------------------------------------
# Output summary helpers
# ---------------------------------------------------------------------------

def _output_summary(output: dict | None, full: bool) -> str:
    if not output:
        return ""
    if full:
        return json.dumps(output, indent=4)
    # findings: report fact count
    if "findings" in output:
        findings = output["findings"]
        if isinstance(findings, list):
            return f"{len(findings)} finding(s)"
        return str(findings)
    if "facts" in output:
        facts = output["facts"]
        if isinstance(facts, list):
            return f"{len(facts)} fact(s)"
        return str(facts)
    # verdict: report stance
    if "stance" in output:
        return f"stance: {output['stance']}"
    if "verdict" in output:
        return f"verdict: {output['verdict']}"
    if "recommendation" in output:
        return f"recommendation: {output['recommendation']}"
    # fallback: first key=value
    first_key = next(iter(output))
    val = output[first_key]
    if isinstance(val, (dict, list)):
        return f"{first_key}: (complex)"
    return f"{first_key}: {val}"


# ---------------------------------------------------------------------------
# Core renderer
# ---------------------------------------------------------------------------

def render(engagement_id: str, *, full: bool = False) -> str:
    path = _trace_path(engagement_id)
    if not path.exists():
        return f"no trace for {engagement_id}"

    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not rows:
        return f"no trace for {engagement_id}"

    lines: list[str] = []

    # ---- Header -----------------------------------------------------------
    open_row = next((r for r in rows if r.get("type") == "engagement_open"), None)
    lines.append("=" * 70)
    lines.append(f"ENGAGEMENT  {engagement_id}")
    if open_row:
        plan = open_row.get("plan", {})
        if "query" in plan:
            lines.append(f"Query       {plan['query']}")
        if "deliverable" in plan:
            lines.append(f"Deliverable {plan['deliverable']}")
        if "disease" in plan:
            lines.append(f"Disease     {plan['disease']}")
        if "modality" in plan:
            lines.append(f"Modality    {plan['modality']}")
        ts = open_row.get("ts", "")
        if ts:
            lines.append(f"Opened      {ts}")
    lines.append("=" * 70)

    # ---- Agent rows -------------------------------------------------------
    agent_rows = [r for r in rows if "agent_id" in r]
    n_agents = len(agent_rows)
    n_abstained = 0
    n_escalated = 0

    for r in agent_rows:
        status = r.get("status", "")
        glyph = _glyph(status)
        if glyph == "⚠":
            n_abstained += 1
        elif glyph == "⛔":
            n_escalated += 1

        lines.append("")
        lines.append(
            f"  {glyph}  {r.get('agent_id', '?')}  ·  kind={r.get('kind', '?')}  ·  status={status or '?'}"
        )

        prov = r.get("provenance")
        if prov:
            lines.append(f"     provenance : {prov}")

        repairs = r.get("repairs")
        if repairs:
            if isinstance(repairs, list):
                lines.append(f"     repairs    : {', '.join(str(x) for x in repairs)}")
            else:
                lines.append(f"     repairs    : {repairs}")

        guardrails = r.get("guardrails_run")
        if guardrails:
            if isinstance(guardrails, list):
                lines.append(f"     guardrails : {', '.join(str(g) for g in guardrails)}")
            else:
                lines.append(f"     guardrails : {guardrails}")

        error = r.get("error")
        if error:
            lines.append(f"     error      : {error}")

        output = r.get("output")
        summary = _output_summary(output, full)
        if summary:
            if full:
                lines.append(f"     output     :")
                for ol in summary.splitlines():
                    lines.append(f"       {ol}")
            else:
                lines.append(f"     output     : {summary}")

        ts = r.get("ts", "")
        if ts:
            lines.append(f"     ts         : {ts}")

    # ---- Footer -----------------------------------------------------------
    close_row = next((r for r in rows if r.get("type") == "engagement_close"), None)
    lines.append("")
    lines.append("=" * 70)
    if close_row:
        synthesis = close_row.get("synthesis", {})
        rec = synthesis.get("recommendation", synthesis.get("summary", ""))
        if rec:
            lines.append(f"Recommendation : {rec}")
        ts = close_row.get("ts", "")
        if ts:
            lines.append(f"Closed         : {ts}")

    lines.append(
        f"Agents: {n_agents} total  ·  {n_abstained} abstained  ·  {n_escalated} escalated"
    )
    lines.append("=" * 70)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="trace_view",
        description="Pretty-print a Sapphire engagement trace.",
    )
    parser.add_argument("engagement_id", nargs="?", help="Engagement ID to render")
    parser.add_argument("--full", action="store_true", help="Include full output JSON")

    args = parser.parse_args(argv)

    if not args.engagement_id:
        parser.print_usage(sys.stderr)
        sys.stderr.write("error: engagement_id is required\n")
        return 2

    print(render(args.engagement_id, full=args.full))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
