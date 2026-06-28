# 00 — The full flow (end-to-end target blueprint)

> Status legend: 🟢 built · 🟡 partial · 🔵 planned · ⚪ proposed (needs a decision). See [`README.md`](README.md).

## 0. The shift this blueprint encodes

Sapphire began as a **decision / diligence firm**: given a CNS question, gather a cited fact dossier
(Bucket 1), debate it (Bucket 2), and write a report. That is real today.

As we add the Quiver tools (ASO Design, OPAL, chronic-tox, Experiment Design) the firm grows a second
and third job. The through-line of this whole plan is **three capability classes**:

| Class | Question it answers | Tools | Output |
|---|---|---|---|
| **Evidence** | "What do we know about X?" | EMET 🟢 · internal moat 🟢 · Q-Models 🟢 · 13 semantic agents 🟢 · `aso-tox` 🟢 | cited **facts** in the dossier |
| **Design / generation** | "What should we make against X?" | **ASO Design** 🔵 · OPAL ⚪ · small-molecule design (Boltz) 🟡 | candidate **assets** (sequences / molecules) |
| **Experiment** | "What should we test next?" | Experiment Design ⚪ · chronic-tox roadmap ⚪ | a proposed **experiment** |

The firm therefore matures from "a recommendation + the spread" into an **iterative design–decision loop**:
*assess a target → if it's worth pursuing, design the modality → assess the designed candidates → deliberate →
propose the experiment that resolves the remaining uncertainty.* Everything below serves that loop.

## 1. The end-to-end flow

```
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │  FRONT DOOR  (Loka scaffold · the consoles)                              🟡 converging │
  │  user query ─▶ intake ─▶ [ ONE live path ] ─▶ streamed trace + the report             │
  └───────────────────────────────────┬─────────────────────────────────────────────────┘
                                       ▼
  ┌──────────────── CONTROL · Engagement Lead ────────────────┐                  🟢 built
  │  triage → scope → engagement plan:                        │
  │   • classify the ask (diligence? design? experiment?)     │
  │   • seat the panel + activate the right agents/TOOLS      │
  └───────────────────────────────────┬───────────────────────┘
                                       ▼
  ┌──────────────── BUCKET 1 · FACTS (analysts + tools) ───────────────────────┐  🟢/🟡
  │  EVIDENCE tools run → cited dossier:                                        │
  │    internal moat 🟢 · EMET 🟢 · Q-Models 🟢 · 13 semantic 🟢/🟡 · aso-tox 🟢 │
  │  Research Manager: completeness · contradiction · VETO · DIVERGENCE · KU     │
  │  ◀───────────── (design outputs re-enter here as new facts) ────────────┐   │
  └───────────────────────────────────┬───────────────────────────────────┼───┘
            (if the engagement calls for it)                               │
                                       ▼                                    │
  ┌──────────────── DESIGN / GENERATION (the loop) ──────────────┐  🔵      │
  │  ASO Design 🔵 (gene → candidate ASOs) · OPAL ⚪ · mol design 🟡│         │
  │  → produces ASSETS; each asset is assessed (aso-tox, off-target)──────────┘
  └───────────────────────────────────┬───────────────────────────┘
                                       ▼
  ┌──────────────── BUCKET 2 · DELIBERATION (partners) ────────────────┐         🟢/🟡
  │  roundtable: independent verdicts → moderated rebuttal → SPREAD     │
  │  veto-class gates adjudicated here (not silent kills)               │
  └───────────────────────────────────┬────────────────────────────────┘
                                       ▼
  ┌──────────────── SYNTHESIS + DELIVERABLE ───────────────────┐                 🟢/🔵
  │  facts + how each player reacted + (🔵) designed candidates │
  │  + (⚪) the proposed experiment to resolve the open question │
  └─────────────────────────────────────────────────────────────┘

  ════ CROSS-CUTTING SUBSTRATE (every box runs on this) ════════════════════════  🟢
  harness (declare→dispatch→validate→guard→stamp→trace) · contracts (schemas+provenance) ·
  data boundary (public IDs only leave; internal scores never do) · memory + self-improvement ·
  append-only trace
```

## 2. The layers (what each is, status, where it lives)

### 2.1 Front door — our consoles (Loka = data + designs, not the scaffold) 🟡
The user-facing surface is **our own consoles** (`frontend2/` :8099 · `orchestrator_ui/` :8101). **Decided
(D8): we do NOT build on Loka's code** — Loka's app is a private single-agent Chainlit PoC that our firm
already supersets. Loka contributes the moat **data** (wired, `moat-real`) and reusable **designs** (the 4
perturbation workflows, the scratchpad pattern, the LLM-judge eval), not the front-end we build on.
Today there are *three* live paths and they have not converged — the keystone:
- canned `orchestrator.run(sid)` (deterministic scenarios; :8099) 🟢
- harnessed `live_engine.run_live(query)` (guard-enforced live firm) 🟡 — offline-verified, partially wired
- `claude -p` console (`orchestrator_ui/` :8101) 🟡
**Target (D1, leaning):** collapse to the one harnessed path behind our console; the others become explicit
demo modes. → [`03_OPEN_DECISIONS.md`](03_OPEN_DECISIONS.md) §D1/§D8.

### 2.2 Control — Engagement Lead 🟢
`sapphire-orchestrator/orchestrator.py`. Triage → scope → engagement plan. The plan must now also
**classify the capability class(es)** the ask needs (diligence / design / experiment) so it can activate
the right tools, not just the right evidence agents.

### 2.3 Bucket 1 — facts (evidence tools) 🟢 / 🟡
`live_engine.py` dispatches each evidence agent through the harness. Known gaps (see
`status/SAPPHIRE_GAPS.md`): 6 of 13 semantic agents not yet in the live dispatch list; round-2 absent in the
live path. Every tool here conforms to the **seam pattern** ([`01`](01_TOOL_SEAM_PATTERN.md)).

### 2.4 Design / generation — the new class 🔵
Where the firm *makes* something. The worked example is **ASO Design** ([`02`](02_ASO_DESIGN.md)). Key
property: design tools are **long-running, multi-environment, AWS-orchestrated** jobs that emit ASSETS, and
their assets **re-enter Bucket 1** as new facts (e.g. candidate ASOs get `aso-tox` + off-target annotations).
This is the iterative loop. It reuses the proven Q-Models async-launcher plumbing (tagged EC2 →
run → retrieve → teardown → ledger).

### 2.5 Bucket 2 — deliberation 🟢 / 🟡
`live_engine.py` roundtable. Gaps: round-2 rebuttal + spread missing in the live path; VETO surfaced but not
mechanically gated. The partners must be able to weigh **designed candidates**, not just target facts.

### 2.6 Synthesis + deliverable 🟢 / 🔵
Today: the recommendation + the spread. Target: also the **designed candidate set** (e.g. top-20 ASOs with
tox/off-target/thermo annotations) and the **proposed experiment**. The deliverable is the product.

### 2.7 Cross-cutting substrate 🟢
The harness, contracts, data boundary, memory/self-improvement, and trace already exist and every box runs
through them. New tools inherit all of it for free by conforming to the seam.

## 3. The tool suite (the map)

| Tool | Class | Runs where | Status | Notes |
|---|---|---|---|---|
| Internal moat | evidence | local (SQLite) | 🟢 | `moat-real`; degrades honestly to `[]` |
| EMET (BenchSci) | evidence | Playwright / Chrome-worker | 🟢/🟡 | live but env-conditional |
| Q-Models (24 tools) | evidence/predict | local-cpu 🟢 · GPU async 🟡 | 🟢/🟡 | proven AWS launcher |
| 13 semantic agents | evidence | claude (haiku) | 🟢/🟡 | 6 not yet in live dispatch |
| `aso-tox` | evidence | python subprocess (sklearn) | 🟢 | GBR model; fires on ASO sequences |
| **ASO Design** | **design** | **multi-env: NCBI CLI · R · Docker · EC2/bowtie2** | 🔵 | the worked example ([`02`](02_ASO_DESIGN.md)) |
| OPAL | design (?) | TBD | ⚪ | needs a spec; slot via the seam |
| chronic-tox | evidence/experiment | TBD | ⚪ | roadmap per the sprint deck |
| Experiment Design | experiment | TBD | ⚪ | proposes the next wet-lab experiment |
| small-molecule (Boltz) | design/evidence | hosted API / AWS | 🟡 | structure/binding/ADME |

## 4. The two big through-lines (so the build stays coherent)
1. **One seam, many tools.** Every tool — evidence or design — plugs in through the *same* contract
   ([`01`](01_TOOL_SEAM_PATTERN.md)). New tools should be a config + an adapter, never a new bespoke path.
2. **One live path.** Collapse the three execution paths to one harnessed path behind the front door, so the
   firm you demo is the firm that runs. Until then, every "it works" must say *which path*.

## 5. Build order (proposed — refine in `03`)
1. 🟡→🟢 **Make the live firm whole**: round-2 + spread + the 6 missing semantic agents; VETO as a gate. (small, unlocks parity with the demo)
2. 🟡→🟢 **Converge the front door** to the one harnessed path.
3. 🔵 **ASO Design seam v1** as the first design-class tool (proves the design loop + the AWS-orchestrated seam).
4. 🔵 **Experiment Design** (closes the loop: the firm proposes the test).
5. ⚪ OPAL / chronic-tox slot in via the same seam once specced.
