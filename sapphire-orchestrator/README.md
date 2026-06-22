# Sapphire Orchestrator

A front-facing **router agent** that turns a single question into a four-stage pipeline:

```
 user ⇄ ROUTER  →  DISCOVER (internal moat + EMET)  →  VALIDATE (Q-Models + ASO tox)  →  CONSULT (persona panel)  →  SYNTHESIZE
```

It **composes**, not replaces, the existing [`../sapphire-cascade/`](../sapphire-cascade/): the cascade
*is* Discover+Validate (internal moat → context **gate** → predictivity **boost**). The orchestrator
adds the two pieces the cascade didn't have — an **on-demand compute step (Q-Models + ASO tox)** and a
**persona-consult panel** — behind one conversational face.

> **The four stages below are the happy-path view.** The full operating model — the two-bucket "firm"
> (junior analysts → partners), the 22-agent roster, the iterate-until-complete fact loop, contradiction/
> veto/divergence handling, and the dossier "done" definition — lives in **[`AGENTS.md`](AGENTS.md)**
> and **[`dossier_schema.md`](dossier_schema.md)**. Start there.
>
> **Building Sapphire?** See `dev/README.md` (the dev harness) — distinct from this product runtime harness in `harness/`.

## Two execution paths

| | **Canned path** — `orchestrator.run(sid)` | **Live harnessed path** — `live_engine.run_live(query)` |
|---|---|---|
| Evidence | pre-captured scenario JSON (`scenarios/*.json`) | dispatched live: each agent via `harness.run` |
| Agents | logic only (facts are authored) | **every agent + persona actually dispatched (22 agents)** |
| Cost | $0, instant, deterministic | real backends (mockable for $0 verification) |
| Used by | `run.py`, `serve.py`/Console | harnessed live firm (verified offline; **not yet wired to front door**) |

**Keystone next step:** wire `run_live` into `serve.py`/Console so any user question runs the full harnessed firm.

## The four stages

| Stage | Subsystem | Produces | Status |
|---|---|---|---|
| **Discover** | internal moat (REAL) + EMET (live) | hypotheses + cited evidence; ranked candidate list | moat **REAL** (`moat-real`); EMET **live** (Playwright) |
| **Validate** | Q-Models + ASO tox | quantitative predictions; ASO tox screen when sequences present | Q-Models CPU live / GPU dry-run; ASO tox **live** (GBR model) |
| **Consult** | auto-convened roundtable — company + institutional partners | multi-viewpoint verdicts, dissent surfaced | persona deliberation **live** (verified offline) |
| **Synthesize** | Engagement Lead + Research Manager + Moderator | recommendation + consensus/dissent + confidence + proposed experiment | — |

## Facts vs. judgment (the key design rule)

EMET and Q-Models produce **facts** (retrieved evidence, computed predictions). Personas produce
**opinions** (priorities, viewpoints) — and must ground every factual claim in the facts above.
This is enforced mechanically by the harness (`must_cite_dossier` guardrail).

## Tool seams (`tools/`)

Stdlib-only Python wrappers that let the harness call Quiver tool implementations:
- **`aso_tox_seam.py`** — wraps `../../tools/aso_tox/predict.py` (Hongkang's GBR model); invoked by
  the `aso-tox` agent (kind `python`, provenance `aso-tox`) when ASO sequences are present in Bucket-1.
  Requires scikit-learn==1.8.0 in the subprocess; engine stays stdlib-only.

## Worked scenarios (6 captured)

- `nav1_8`, `tsc2` — original; real persona deliberation.
- `lrrk2_pd`, `scn2a_epilepsy`, `gba1_pd`, `c9orf72_als` — captured live from EMET (Thorough mode), real PMIDs.

Run any: `python run.py scn2a_epilepsy`. The canned path runs any captured scenario at $0.

## Transparency

```bash
python trace_view.py <engagement_id>          # agent-by-agent timeline: kind · status · provenance · output
python trace_view.py <engagement_id> --full   # include full output payloads
```

Sample trace: `../docs/sample-trace.txt`.

## Run it

```bash
python sapphire-orchestrator/run.py                 # list scenarios
python sapphire-orchestrator/run.py nav1_8          # full run: PLAN → DISCOVER → VALIDATE → CONSULT → SYNTHESIZE
python sapphire-orchestrator/run.py "is RHEB fundable for tuberous sclerosis?"   # free text → routed
python sapphire-orchestrator/run.py --json tsc2     # the canonical run object the site consumes
```

**As a web app on your Claude subscription** — `serve.py` is the bridge: it serves the site and runs
novel queries through **Claude Code headless on your subscription** (no API key):

```bash
python sapphire-orchestrator/serve.py     # http://localhost:8077 — Console (main) + /api/run
```

Note: `serve.py` currently uses the canned path; wiring it to `run_live` is the keystone remaining task.

## See it

The interactive visualization is the **Console** section of the site ([`../site/`](../site/)):
`cd site && python -m http.server 8077`, open `#console`. Type a question or pick a worked scenario.
