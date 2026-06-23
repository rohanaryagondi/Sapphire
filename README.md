# Sapphire — Quiver Bioscience

An agentic CNS drug-discovery **decision system**. A user-facing orchestrator runs a two-bucket "firm":
**Bucket 1** (fact agents — EMET · Q-Models · the Quiver moat · 13 semantic web agents · ASO tox) builds a cited
fact dossier; **Bucket 2** (a roundtable of company + institutional persona agents) deliberates; the
orchestrator reports the facts **and** how each player reacted. Goal: handle the ~300 hard CNS questions
in James' corpus — and harder.

> **New here?** Read **[`CLAUDE.md`](CLAUDE.md)** (quick orientation) → **[`sapphire-orchestrator/AGENTS.md`](sapphire-orchestrator/AGENTS.md)**
> (operating model + roster) → **[`docs/reports/REPORT.md`](docs/reports/REPORT.md)** (living architecture + status) → **[`docs/reports/HANDOFF.md`](docs/reports/HANDOFF.md)** (full narrative, next steps).
> For current build state see **[`status/OVERALL.md`](status/OVERALL.md)**; the north star is **[`docs/VISION.md`](docs/VISION.md)**.
> **`main` is the bedrock**; work on a feature branch `<handle>/<slug>` and ship via PR (see `dev/`). Repo: `rohanaryagondi/Sapphire`.

> **Building Sapphire?** See `dev/README.md` (the dev harness) — distinct from the product runtime harness in `sapphire-orchestrator/harness/`.

---

## What's running today

| Capability | Status |
|---|---|
| **Canned firm** (`orchestrator.run(sid)`) | ✅ CLI + Console + subscription bridge; 6 captured scenarios |
| **Live harnessed firm** (`live_engine.run_live(query)`) | ✅ every agent + persona through `harness.run`; verified offline (not yet wired to front door) |
| **Agent harness** | ✅ 22-agent registry; guard-enforced, provenance-stamped, traced |
| **Internal moat** | ✅ REAL — Loka CNS_DFP SQLite; `moat-real` provenance |
| **EMET** | ✅ live — Playwright on emet.benchsci.com; real cited PMIDs |
| **ASO acute-tox tool** | ✅ integrated — Hongkang's GBR model; fires in Bucket-1 when ASO sequences present |
| **Trace viewer** | ✅ `python trace_view.py <engagement_id>` — agent-by-agent timeline |
| **Tests** | ✅ 268, all green |

**Still TODO (keystone):** wire `run_live` to `serve.py`/Console so *any* user question runs the full harnessed firm.

---

## Architecture framing (2026-06-19 sprint)

**Loka is the front-end + orchestrator scaffold.** Quiver's tools plug into it:
- OPAL
- ASO Design
- **ASO toxicity** (integrated — `tools/aso_tox/` + `sapphire-orchestrator/tools/aso_tox_seam.py`)
- Chronic-tox (roadmap)
- Experiment Design

Sapphire's orchestrator + harness + 22-agent registry is the agentic layer that connects these tools into a reasoned, cited decision pipeline.

---

## Project structure

- **`sapphire-orchestrator/`** — the core engine: `orchestrator.py` (canned path) · `live_engine.py` (harnessed live path) · `harness/` (22-agent registry + runtime) · `moat/` · `emet/` · `qmodels/` · `tools/` (seams) · `memory/` · `selfimprove/` · `trace_view.py` · `serve.py` · `run.py` · `AGENTS.md`
- **`tools/`** — Quiver tool implementations (ASO tox: `tools/aso_tox/`)
- **`sapphire-cascade/`** — the original re-ranking evidence pipeline (live EMET). **`personas/`** — James' 59 company personas.
- **`site/`** — interactive walkthrough + the orchestrator Console (demo surface).
- **`dev/`** — Dev Harness: methodology, conventions, and gates for agents building Sapphire (distinct from the runtime harness).
- **Research foundation** — `docs/foundation/` (`capability_map.xlsx`, `model_landscape.md`,
  `integration_map.md`, `orchestration_brief_hayes.md`) + `expert-agent/`: what to build, which models, the 3-layer data vision.
- **`source/` · `meetings/` · `specs/` · `_build/`** — raw corpus, transcripts, design specs, generators.
- **`docs/`** — VISION.md · ARCHITECTURE.md · LOKA.md · foundation/ · reports/ · superpowers/ · **`status/`** (live build state).

---

## Quick start

```bash
cd ~/Desktop/Projects/Quiver/sapphire-capability-map/sapphire-orchestrator
python run.py tsc2                          # run a captured scenario (canned, $0)
python run.py "is GBA1 druggable in PD?"   # free-text → plan + routed scenario
python trace_view.py <engagement_id>        # see exactly what every agent did
python -m http.server 8077 --directory ../site   # open the Console UI
```

---

## The research foundation (how this started)

The repo began as the analysis that justifies the build — operationalizing James' Feb-2026 prompt corpus
into a living map of what Sapphire must do, what can do it today, and where Quiver should build.

| File | What it is |
|---|---|
| [`docs/foundation/capability_map.xlsx`](docs/foundation/capability_map.xlsx) | 16 capability areas × 299 prompts mapped to capability + disease area. |
| [`docs/foundation/model_landscape.md`](docs/foundation/model_landscape.md) | Supply side: 3–6 candidate models/tools per capability, maturity + `proven`/`paper-claim` flag. |
| [`docs/foundation/integration_map.md`](docs/foundation/integration_map.md) | Tool/data-source frequency re-cut into Internal/Context/Predictivity layers. |
| [`personas/`](personas/) | All 59 personas as markdown + `INDEX.md`. |
| [`expert-agent/`](expert-agent/) | CAP-15 build: the "$50k expert from public posts" design + runnable scaffold. |
| [`docs/foundation/orchestration_brief_hayes.md`](docs/foundation/orchestration_brief_hayes.md) | Strategic brief: 4 agentic-orchestration archetypes for Sapphire. |
| [`sapphire-cascade/`](sapphire-cascade/) | Runnable 3-layer re-ranking cascade (internal moat → gate → boost); live EMET. |
| [`docs/reports/HANDOFF.md`](docs/reports/HANDOFF.md) | Full narrative: vision, decisions + rationale, current status, next steps. |
| [`docs/reports/REPORT.md`](docs/reports/REPORT.md) | Living architecture + status document. |
| [`meetings/`](meetings/) | 2026-06-11 strategy meeting transcript + structured notes. |
| [`source/`](source/) | James' raw Feb-2026 corpus (59 personas, 299 + 100 prompts, 399 pipelines). |
