"""Improvement metrics (spec §6.6): make 'gets better' a tracked number, not a claim."""
from __future__ import annotations

import os
from pathlib import Path

from memory import read_all
from memory.memory import _dir as _memory_dir   # reuse the configured memory dir


def compute_metrics() -> dict:
    recs = read_all()
    by_type: dict = {}
    for r in recs:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    outcomes = [r for r in recs if r["type"] == "experiment_outcome"]
    confirmed = sum(1 for o in outcomes if o["payload"].get("result") == "confirmed")
    refuted = sum(1 for o in outcomes if o["payload"].get("result") == "refuted")
    accuracy = (confirmed / (confirmed + refuted)) if (confirmed + refuted) else None
    return {
        "records": len(recs), "by_type": by_type,
        "proposals": by_type.get("experiment_proposal", 0),
        "outcomes": len(outcomes),
        "prediction_accuracy": accuracy,
        "blindspots": by_type.get("moat_blindspot", 0),
    }


def write_report(path=None) -> dict:
    m = compute_metrics()
    acc = "n/a" if m["prediction_accuracy"] is None else f"{m['prediction_accuracy']:.0%}"
    lines = [
        "# Sapphire Self-Improvement — metrics", "",
        f"- memory records: {m['records']}",
        f"- experiment proposals: {m['proposals']}",
        f"- outcomes ingested: {m['outcomes']}",
        f"- prediction accuracy (confirmed / confirmed+refuted): {acc}",
        f"- moat blind spots opened: {m['blindspots']}", "",
        "## records by type",
    ] + [f"- {t}: {n}" for t, n in sorted(m["by_type"].items())]
    out = Path(path) if path else (_memory_dir() / "REPORT.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return m
