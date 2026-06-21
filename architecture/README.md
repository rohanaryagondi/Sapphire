# Sapphire Architecture — the agent firm

This folder is the **agent specifications**, organized the way the system actually works: a firm.
A question goes to an **engagement lead**, who runs two buckets — junior analysts gather a **cited fact
dossier** (Bucket 1), partners **deliberate** over it (Bucket 2) — and a recommendation comes back with
the dissent intact. No forced consensus; the spread is the product.

The runnable engine that executes this is in [`../sapphire-orchestrator/`](../sapphire-orchestrator/)
(`orchestrator.py`, `run.py`, `serve.py`). The operating model + the 7 rules are in
[`../sapphire-orchestrator/AGENTS.md`](../sapphire-orchestrator/AGENTS.md); the "done" definition for the
dossier is [`../sapphire-orchestrator/dossier_schema.md`](../sapphire-orchestrator/dossier_schema.md).

## The flow

```
ask ─▶ ORCHESTRATOR (control)         plan & scope, own the loop, write the report
        │
        ▼
   BUCKET 1 — FACTS (cited)           internal moat → EMET → Q-Models → 13 semantic agents
        │  Research Manager: complete? contradictions? vetoes?  ──re-run──┐
        ▼  (dossier complete)                                            │
   BUCKET 2 — DELIBERATION            company personas + institutional archetypes
        │  Roundtable Moderator: verdicts → rebuttal → spread            │
        │  partners may request more facts ──────────────────────────────┘
        ▼
   SYNTHESIS                          recommendation + consensus + dissent + proposed experiment
```

## Folders (a README at every level)

| Folder | What's in it |
|---|---|
| [`orchestrator/`](orchestrator/) | The control layer — 3 agents that plan the work, judge completeness, and run the debate. |
| [`bucket1/`](bucket1/) | The fact-gathering bucket — [`scientific/`](bucket1/scientific/) (3) + [`semantic/`](bucket1/semantic/) (13). Cited facts only. |
| [`bucket2/`](bucket2/) | The deliberation bucket — the company-partner template + [`institutional/`](bucket2/institutional/) archetypes (4). Opinions that cite the facts. |

## Full roster (one line each — see the bucket READMEs for 2–3 lines per agent)

**Orchestrator / control**
- **Engagement Lead** — interprets the prompt, scopes the dossier, writes the plan, owns the loop, delivers.
- **Research Manager** — owns Bucket 1: completeness, contradiction-by-tier, VETO/DIVERGENCE, re-runs.
- **Roundtable Moderator** — seats the panel, runs verdicts → rebuttal, maps the spread.

**Bucket 1 — scientific core**
- **Internal Science Lead** — the Quiver EP-CRISPR moat; authors the ranked hypothesis (MOCK in demo).
- **EMET Analyst** — the single door to EMET (BenchSci); cited biomedical evidence (live).
- **Q-Models Runner** — specialist models on demand: binding / ADMET / cardiac / selectivity (**REAL**: 24 tools by id; CPU live-local, GPU via the safe async launcher).

**Bucket 1 — semantic intelligence (13)**
- **FDA Institutional Memory ⛔** · **Patent & IP ⛔** — the two veto-class agents.
- **Global Regulatory Divergence · DEA Scheduling · Clinical-Trial Registry · Post-Market Safety** — regulatory/clinical.
- **Financial & Investor · Payer & Market Access · Manufacturing/CMC** — commercial.
- **Patient Advocacy · KOL & Social Signal · Policy & Legislative · Reputational** — ecosystem/perception.

**Bucket 2 — partners**
- **Company partners** (via the template) — Pharma BD · Biotech CSO · VC GP · Pharma R&D SVP, from 59 real-company personas.
- **Institutional** — Ex-FDA Regulator · Adversarial Red-Team (always seated) · Payer / Market-Access · KOL / Academic.

## The rules that make it work
- **Internal-first:** the moat reasons first; external tools only **gate** (veto) then **boost** (corroborate) — never author.
- **Facts vs. judgment:** Bucket 1 = cited facts; Bucket 2 = opinions that cite them. Partners never invent facts.
- **Veto = gate:** a prior CRL or a blocking patent is tabled for the panel, never a silent kill.
- **Abstain:** thin or contradictory evidence → propose the experiment that resolves it, don't guess.

## What's real vs. mock (today)
- **Claude** — live (the reasoning, on the Quiver subscription).
- **EMET** — real evidence captured in the shipped scenarios; not yet wired to live web queries.
- **Q-Models** — **REAL** (vendored in-repo; orchestrator calls any of 24 tools by id; CPU tracks
  `live-local`, GPU tracks via the live-proven async EC2 launcher; remaining tracks marked `stub`/`eval`
  in `qmodels/registry.json` — never silently mocked).
- **Internal moat** — MOCK (synthetic stand-in until the real EP-CRISPR data lands).

Every fact in the Console carries a provenance badge (✓ EMET-captured / ◇ Claude-reconstructed / ◍ mock;
Q-Models rows additionally carry live-local / gpu / stub / unavailable).

## Agent file format (every spec follows it)
`Bucket/layer` · `One-liner` · `Activate when` · `Inputs` · `Procedure` · `Output (contract)` ·
`Sources/tools` (fact agents) or `Persona grounding` (partners) · `Rules` · `Hands off to`.
