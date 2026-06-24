"""Adapter: render specs (from render.py) → Chainlit messages/elements.

This is the ONLY frontend module that imports chainlit + pandas; it is imported by the
running app (main.py), never by the Gate-1 unit tests (render.py stays pure). Each spec
becomes one `cl.Message`-ready `(content_markdown, elements)` pair via `to_messages(specs)`.
"""
from __future__ import annotations

import chainlit as cl
import pandas as pd


def _table_element(name: str, columns: list, rows: list) -> cl.Dataframe:
    """A cl.Dataframe with explicit column order (LOKA's _create_*_table pattern)."""
    if rows:
        df = pd.DataFrame([{c: r.get(c, "") for c in columns} for r in rows], columns=columns)
    else:
        df = pd.DataFrame(columns=columns)
    return cl.Dataframe(data=df, name=name, display="inline")


def _plan_md(spec: dict) -> str:
    agents = ", ".join(spec["agents"]) or "—"
    panel = ", ".join(spec["panel"]) or "—"
    return (f"#### How the firm scoped this\n"
            f"- **Deliverable:** {spec['deliverable'] or '—'}\n"
            f"- **Disease:** {spec['disease'] or '—'}\n"
            f"- **Modality:** {spec['modality'] or '—'}\n"
            f"- **Bucket-1 agents:** {agents}\n"
            f"- **Roundtable panel:** {panel}")


def _flag_md(spec: dict) -> str:
    items = "\n".join(f"- {it}" for it in spec["items"])
    return f"### {spec['icon']} {spec['title']}\n{items}"


def _roundtable_md(spec: dict) -> str:
    lines = ["### Roundtable — the spread (no forced consensus)"]
    if not spec["round1"]:
        lines.append("_No partner verdicts returned._")
    for v in spec["round1"]:
        conv = "" if v["conviction"] is None else f" · conviction {v['conviction']}"
        lens = f" — _{v['lens']}_" if v["lens"] else ""
        status = "" if v["status"] in ("ok", "") else f" · _{v['status']}_"
        lines.append(f"\n**{v['persona'] or '(persona)'}**{lens}  \n"
                     f"`{v['stance'] or '—'}`{conv}{status}  \n{v['rationale']}")
        if v["fact_claims"]:
            cites = "; ".join(
                (fc.get("claim", "") + (f" [{fc.get('cite')}]" if fc.get("cite") else ""))
                if isinstance(fc, dict) else str(fc)
                for fc in v["fact_claims"])
            lines.append(f"  \n_cites:_ {cites}")
    if spec["has_round2"]:
        lines.append("\n#### Round 2 — rebuttal (reacting to round 1)")
        for v in spec["round2"]:
            conv = "" if v["conviction"] is None else f" · conviction {v['conviction']}"
            lines.append(f"\n**{v['persona']}** → `{v['stance'] or '—'}`{conv}  \n{v['rationale']}")
    return "\n".join(lines)


def _synthesis_md(spec: dict) -> str:
    ents = spec["entities"] or {}
    tags = []
    for k in ("genes", "diseases", "drugs", "smiles"):
        for v in ents.get(k, []) or []:
            tags.append(f"`{v}`")
    tagline = (" · ".join(tags)) if tags else "—"
    return (f"## Synthesis\n"
            f"**Recommendation:** {spec['recommendation'] or '—'}  \n"
            f"**Confidence:** `{spec['confidence'] or '—'}`  \n"
            f"**Proposed experiment:** {spec['proposed_experiment'] or '—'}  \n"
            f"**Entities:** {tagline}\n\n"
            f"_The product is the facts + how each player reacted — not a single verdict._")


def to_messages(specs: list) -> list:
    """Convert render specs → a list of {'content': str, 'elements': [cl.Element]} dicts.

    main.py sends each as a cl.Message. Tables become cl.Dataframe elements; everything else
    is markdown. Provenance/tier/plane strings pass through verbatim from render.py.
    """
    msgs = []
    for spec in specs:
        kind = spec["kind"]
        if kind == "header":
            msgs.append({"content": f"# {spec['query']}", "elements": []})
        elif kind == "plan":
            msgs.append({"content": _plan_md(spec), "elements": []})
        elif kind == "agents":
            note = (f"\n\n_{spec['n_abstained']} of {spec['n_total']} agents abstained/escalated._"
                    if spec["n_abstained"] else "")
            msgs.append({"content": f"### {spec['name']}{note}",
                         "elements": [_table_element(spec["name"], spec["columns"], spec["rows"])]})
        elif kind == "dossier":
            msgs.append({"content": f"### {spec['name']}  ·  _{len(spec['rows'])} fact(s)_",
                         "elements": [_table_element(spec["name"], spec["columns"], spec["rows"])]})
        elif kind == "flag":
            msgs.append({"content": _flag_md(spec), "elements": []})
        elif kind == "roundtable":
            msgs.append({"content": _roundtable_md(spec), "elements": []})
        elif kind == "synthesis":
            msgs.append({"content": _synthesis_md(spec), "elements": []})
        elif kind == "footer":
            eid = spec["engagement_id"] or "—"
            msgs.append({"content": f"---\n_Engagement trace:_ `{eid}`", "elements": []})
    return msgs
