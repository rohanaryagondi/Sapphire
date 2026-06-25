# Sapphire — Documentation Hub

Full-visibility index of the Sapphire build. Start here. For the operating-context primer read the
top-level [`CLAUDE.md`](../CLAUDE.md); for the deepest system walkthrough read
[`ARCHITECTURE.md`](ARCHITECTURE.md).

> **What Sapphire is:** an agentic CNS drug-discovery decision system. A user-facing **orchestrator** runs
> a two-bucket "firm" — Bucket 1 gathers a *cited fact dossier* (internal moat + EMET + Q-Models + 13
> semantic web agents), Bucket 2 is a partner **roundtable** that debates it (no forced consensus), and the
> engine writes a report: the facts + how each player reacted. Goal: the ~300 hard CNS questions in James'
> corpus, and harder.

---

## 1. Read in this order
1. [`CLAUDE.md`](../CLAUDE.md) — orientation, hard rules, status, the map.
2. [`sapphire-orchestrator/AGENTS.md`](../sapphire-orchestrator/AGENTS.md) — the operating model + roster + 7 rules.
3. [`sapphire-orchestrator/dossier_schema.md`](../sapphire-orchestrator/dossier_schema.md) — the "done" definition for the fact bucket.
4. [`ARCHITECTURE.md`](ARCHITECTURE.md) — **consolidated end-to-end architecture** (contracts → harness → agents → engagement loop → memory/self-improvement → console).
5. [`reports/HANDOFF.md`](reports/HANDOFF.md) — vision, decisions + rationale, status. (Live state: [`status/OVERALL.md`](../status/OVERALL.md); north star: [`VISION.md`](VISION.md).)

## 2. Build phases (what's done)
| Phase | What | Status |
|---|---|---|
| 1 | Control + scientific-core + institutional agents + dossier schema | DONE |
| 2 | 13 semantic fact agents | DONE |
| 3 | Orchestrator runs end-to-end (`orchestrator.py` · `run.py` · `serve.py` · Console) | DONE |
| 4 | **Q-Models integration** — 24 tools callable; two-speed routing; live AWS plumbing proven | DONE — [report](../RohanOnly/qmodels_run/REPORT.md) |
| 5 | **Harness · live EMET · self-improvement loop · scenario suite · integration** | DONE — [report](superpowers/PHASE5-REPORT.md) |
| 6 | **ASO-tox tool integrated** — 22-agent harness, GBR model, stdlib seam; `run_live(..., sequences=...)` | DONE — see [`../CLAUDE.md`](../CLAUDE.md) §Phase 6 |

## 3. Phase 5 — specs, plans, reports (the subagent-driven build)
Every workstream: brainstorm → **spec** → **plan** → subagent-driven execution (implement → spec+quality
review → fix-loop → whole-branch review). 278 stdlib-only tests; shipped to `main` (the bedrock).

**Design specs** (`docs/superpowers/specs/`)
- [Phase 5 design spec](superpowers/specs/2026-06-21-sapphire-phase5-design.md) — the whole-phase design (incl. Appendix A: the harness).

**Implementation plans** (`docs/superpowers/plans/`)
- [P0 — shared contracts](superpowers/plans/2026-06-21-sapphire-phase5-p0-shared-contracts.md)
- [D — agent harness](superpowers/plans/2026-06-21-sapphire-phase5-d-harness.md)
- [A — live EMET](superpowers/plans/2026-06-21-sapphire-phase5-a-emet.md)
- [C — self-improvement loop](superpowers/plans/2026-06-21-sapphire-phase5-c-selfimprovement.md)
- [B + integration](superpowers/plans/2026-06-21-sapphire-phase5-b-integration.md)

**Reports**
- [Phase 5 completion report](superpowers/PHASE5-REPORT.md) — what shipped, what reviews caught, safety posture, open items.
- [Q-Models (Phase 4) report](../RohanOnly/qmodels_run/REPORT.md).

## 4. EMET (BenchSci) — live integration
Captured from the live app (`emet.benchsci.com`, signed in, 2026-06-21).
- [`sapphire-cascade/emet_protocol.md`](../sapphire-cascade/emet_protocol.md) — how to drive EMET via Playwright (URLs, mechanics, return envelope).
- [`sapphire-cascade/emet_capabilities.md`](../sapphire-cascade/emet_capabilities.md) — the live catalogue: 9 workflows, 22 capabilities, ~70 data sources, outputs, thinking levels, stringency.
- [`.claude/skills/emet-runner/SKILL.md`](../.claude/skills/emet-runner/SKILL.md) — the reusable, harness-callable EMET skill (MCP-swappable seam).
- [`architecture/bucket1/scientific/emet-experts.md`](../architecture/bucket1/scientific/emet-experts.md) — paste-in Sapphire EMET Experts.

## 4b. Loka (prior Quiver vendor) — what to reuse
[`LOKA.md`](LOKA.md) — analysis of Loka's "GenAI Accelerator" shared folder: their Chainlit/AWS/Bedrock
Drug Discovery Agent (source in the private repo `q-state-biosciences/drug-discovery-agent`), and the
**real Quiver moat data** they left us (`CNS_DFP_distance` parquet — 38.4M perturbation-distance rows) that
can retire Sapphire's mock moat. Includes the reuse plan + the asks to Quiver.

## 5. The agent specs (the firm)
`architecture/` holds every agent spec, organized as the firm. A README at each level.
- `architecture/orchestrator/` — control: Engagement Lead · Research Manager · Roundtable Moderator.
- `architecture/bucket1/scientific/` — Internal Science Lead · EMET Analyst · Q-Models Runner.
- `architecture/bucket1/semantic/` — 13 semantic fact agents (2 veto-class: FDA Memory ⛔, Patent/IP ⛔).
- `architecture/bucket2/` — partner roundtable: company-partner template + institutional archetypes.

## 6. The code (`sapphire-orchestrator/`)
| Path | Role |
|---|---|
| `orchestrator.py` | the engine (triage→scope→plan→Bucket-1→Bucket-2→synthesize) |
| `engagement.py` | **Phase-5 loop wrapper**: recall priors → harness trace → reflect to memory (additive) |
| `run.py` · `serve.py` | CLI · subscription bridge (Claude headless) |
| `contracts/` | shared P5 contracts: stdlib JSON-Schema validator · provenance vocab · schemas |
| `harness/` | **the agent harness** — one runtime every agent runs through |
| `emet/` | live-EMET adapter + handler (the harness `emet-playwright` seam) |
| `memory/` | append-only, public-only durable memory (write/recall/record_outcome) |
| `selfimprove/` | governance · reflect · authoring · metrics · `record-outcome` CLI |
| `qmodels/` | the real model launchpad (24 tools, two-speed routing) |
| `scenarios/` | shipped scenarios + `manifest.json` (variety matrix) + `capture.py` |

## 7. Run & test
> **Demo:** the 2-minute **TSC2 / tuberous-sclerosis** walkthrough (real moat + real EMET PMIDs +
> the spread + a DIVERGENCE, replayable $0/offline) is in [`frontend/DEMO_TSC2.md`](../frontend/DEMO_TSC2.md)
> — pick the *"Replay (captured TSC2 · $0)"* profile in `chainlit run frontend/main.py`.

```bash
# the firm, end-to-end (canned scenario)
python sapphire-orchestrator/run.py nav1_8

# the Phase-5 loop on the real engine (recall → trace → reflect)
cd sapphire-orchestrator && python -c "import engagement; print(engagement.run_engagement('nav1_8')['reflection'])"

# active-learning feedback + metrics
python -m selfimprove record-outcome <proposal_id> confirmed --data "..." --source wetlab
python -m selfimprove report

# the whole Phase-5 test surface (~137 tests, stdlib only)
cd sapphire-orchestrator && for s in contracts harness emet memory selfimprove; do python -m unittest discover -s $s/tests; done && python -m unittest discover -s tests

# the site / Console
cd site && python -m http.server 8077      # regenerate data: python _build/build_orch_data.py
```

## 8. Hard rules (non-negotiable — full text in CLAUDE.md)
Data boundary (public identifiers only leave Quiver) · facts vs judgment · internal↔external = DIVERGENCE
(surface, don't reconcile) · veto = gate (adjudicated, never silent) · label demo fidelity · empirical
culture ("SOTA on shit is still shit"). The harness enforces the first four **mechanically**.

## 9. Conventions
**`main` is the bedrock**; work on a feature branch `<handle>/<slug>` cut from `main` and ship via a PR that
Rohan's Claude reviews/merges (see [`../dev/CONTRIBUTOR_RULES.md`](../dev/CONTRIBUTOR_RULES.md)). Agent `.md`
files follow one template (see end of `AGENTS.md`). Generated run artifacts live under `RohanOnly/`.
