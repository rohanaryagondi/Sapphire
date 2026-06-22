# HANDOFF — Sapphire (Quiver Bioscience)

The full narrative for picking this up cold. `CLAUDE.md` is the quick orientation; this is the why,
the decisions, and the road ahead. Branch: **`Rohan`** · Repo: `~/Desktop/Projects/Quiver/sapphire-capability-map` (local).

> **Building Sapphire?** See `dev/README.md` (the dev harness) — distinct from the product runtime harness in `sapphire-orchestrator/harness/`.

---

## 1. The project

Quiver runs *Sapphire*, a closed-loop CNS drug-discovery engine whose moat is unique functional data
(electrophysiology + CRISPR perturbations fused into a latent space). We are building the **agentic
decision layer on top**: a user-facing orchestrator that answers hard drug-discovery/development questions
at the depth a VC, a consulting firm, or an FDA reviewer would — by gathering cited facts, then convening
expert opinion.

**Architecture framing (2026-06-19 sprint):** **Loka is the front-end + orchestrator scaffold.** Quiver's
tools (OPAL, ASO Design, ASO toxicity, chronic-tox, Experiment Design) plug into it. Sapphire's
orchestrator + harness + 22-agent registry is the agentic layer that connects them into a cited decision
pipeline.

**The bar:** the ~300 prompts in `source/.../Sapphire Prompts and Queries_For ExpoAI.docx` — and
questions harder than those (trial design, FDA-stance prediction, portfolio/franchise strategy, adversarial
diligence).

---

## 2. The operating model — a "firm" in two buckets

```
 user ⇄ ENGAGEMENT LEAD ── plans the engagement (activates ONLY what's needed) ──┐
   BUCKET 1 — FACTS (junior analysts)                                            │ iterate until
     scientific core: Internal Science Lead (→ REAL moat) · EMET Analyst (live) │ the dossier is
       Q-Models Runner · aso-tox (when ASO sequences present)                   │ complete
     semantic intel: FDA-memory ⛔· IP ⛔· trials · payer · KOL · …               │
        RESEARCH MANAGER → complete? contradiction? gap? veto? ──re-run──────────┘
   BUCKET 2 — DELIBERATION (partners)
     ROUNDTABLE MODERATOR seats 3–7 → independent verdicts → moderated rebuttal
        partners may request more facts ──loops back to Bucket 1──
   ENGAGEMENT LEAD → report: the facts + how each player reacted (no forced consensus)
```

Full spec in `sapphire-orchestrator/AGENTS.md`. 22 agents in `harness/agents.json`.

---

## 3. Key design decisions (and why)

1. **A dossier schema defines "done"** (`dossier_schema.md`). Without it, "iterate till comprehensive" never terminates.
2. **Loop triggers ⊃ contradictions.** Re-open Bucket 1 on contradiction, gap, or thin evidence.
3. **Credibility-weighted contradiction.** FDA label outranks a tweet (tiers T1–T4).
4. **Internal↔external contradictions are SIGNAL** — `DIVERGENCE`, not a bug. The Quiver atlas sees targets the literature doesn't.
5. **3 control roles**, not one mega-agent: Engagement Lead / Research Manager / Roundtable Moderator.
6. **Roundtable = verdicts → one moderated rebuttal round** with a mandatory Adversarial Red-Team seat.
7. **Facts vs. judgment is harness-enforced.** Bucket 1 = cited facts; Bucket 2 = opinions citing the dossier.
8. **Institutional archetypes** — ex-FDA Regulator, Payer, KOL, Red-Team — built net-new for VC/consulting/FDA-grade output.
9. **Veto facts are gates, not kills.** A prior CRL / a blocking patent is surfaced to the roundtable.
10. **Selective activation controls cost.** 13 semantic agents × dozens of sources; Engagement Lead activates by beat, default 2–4 agents.
11. **Two execution paths** — canned ($0, deterministic) vs. live harnessed (`run_live`). The Console uses the canned path today; wiring `run_live` to the front door is the keystone remaining task.

---

## 4. Current status

### Done ✅
| Area | Notes |
|---|---|
| Firm runs end-to-end (canned) | CLI (`run.py`) + Console (`serve.py`) + 6 captured scenarios |
| **Live harnessed engine** (`live_engine.run_live`) | Every agent + persona through `harness.run`; verified offline, $0 |
| **22-agent harness registry** | Guard-enforced, schema-validated, provenance-stamped, traced |
| **Internal moat — REAL** | Loka CNS_DFP SQLite; `moat-real` provenance; direction-aware mimic/rescue |
| **EMET — live** | Playwright on emet.benchsci.com; real cited PMIDs |
| **ASO tox — integrated** | `tools/aso_tox/` (Hongkang's GBR model) + `tools/aso_tox_seam.py`; fires on ASO sequences |
| CLI transparency (`trace_view.py`) | Agent-by-agent timeline; sample in `docs/sample-trace.txt` |
| Self-improvement loop | Memory accumulates, recall, outcome→blind-spot, metrics report |
| Captured scenarios (6) | `nav1_8, tsc2, lrrk2_pd, scn2a_epilepsy, gba1_pd, c9orf72_als` |
| Tests | **268, all green** |

### Not yet done ⛳
1. **Wire `run_live` to the front door** — `serve.py`/Console still use the canned engine for novel queries. This is the keystone: route the Console/CLI through `run_live` with real backends (flag-gated).
2. **ASO Design → aso-tox pairing** — the ASO Design tool (when integrated) will generate sequences that feed `aso-tox` automatically. Wire the handoff.
3. **Scenario coverage** — 6 of ~300 target questions captured; stubs remain in the manifest.
4. **Q-Models GPU eval** — CPU tracks run live; one real GPU eval has never been run.
5. **Loka's rescue scoring** — raw EP-antipodal-distance does not reproduce Loka's "rapamycin rescues TSC2" result; gated on getting their repo + 7-stage workflow doc.
6. **Real wet-lab outcomes** — `record_outcome` feeds the self-improvement loop; real outcomes needed for blind-spot calibration to improve predictions.
7. **Console trace view** — trace transparency is terminal-only (deliberately deferred).

---

## 5. Demo fidelity & honesty

- **REAL:** internal moat (`moat-real`, Loka CNS_DFP SQLite), EMET (live Playwright), ASO tox (GBR model), Q-Models CPU tracks.
- **Offline verified / not paid-run:** `run_live` persona + semantic agents (mocked LLM in tests); Q-Models GPU dry-run.
- **NOT yet wired:** `run_live` → front door; ASO Design → aso-tox handoff.
- **Always label mocks.** The provenance vocabulary (`contracts/provenance.py`) makes this mechanical.

---

## 6. The research foundation (why the earlier artifacts still matter)

- `capability_map.xlsx` — 16 capability areas × 299 prompts; what each needs + empirical status.
- `model_landscape.md` — candidate models per capability (proven vs paper-claim).
- `integration_map.md` — external data/tools re-cut into the Internal/Context/Predictivity layers.
- `orchestration_brief_hayes.md` — the agentic-orchestration archetypes the firm model realizes.
- `expert-agent/` — the CAP-15 "expert from public posts" design; the ex-FDA Regulator partner reuses it.
- `personas/` — James' 59, the company-partner pool.

---

## 7. Next steps (prioritized)

1. **Wire `run_live` to `serve.py`/Console** (behind a flag) — converts the proven-but-isolated live engine into the actual product.
2. **ASO Design tool integration** — pair with `aso-tox` so Design → sequence → tox screen is automatic.
3. **Broaden scenario coverage** — use `_build/capture_scenario.py` to capture more of the ~300 target questions via live EMET.
4. **Q-Models real GPU eval** — flip one track from dry-run to live.
5. **Real wet-lab outcomes** — feed `record_outcome` to prove the self-improvement loop improves predictions.

---

## 8. Pointers

- Operating model + roster → `sapphire-orchestrator/AGENTS.md`
- Living architecture → `REPORT.md`
- Two execution paths + harness → `docs/ARCHITECTURE.md`
- Loka data + framing → `docs/LOKA.md`
- Dev harness → `dev/README.md`
- Q-Models launchpad → github.com/rohanaryagondi/Q-Models · Empirical evals → github.com/rohanaryagondi/Q-Mammal
- Strategy meeting → `meetings/2026-06-11-sapphire-strategy-james.md`
