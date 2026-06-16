# HANDOFF — Sapphire (Quiver Bioscience)

The full narrative for picking this up cold. `CLAUDE.md` is the quick orientation; this is the why,
the decisions, and the road ahead. Branch: **`Rohan`** (the project bedrock).

---

## 1. The project

Quiver runs *Sapphire*, a closed-loop CNS drug-discovery engine whose moat is unique functional data
(electrophysiology + CRISPR perturbations fused into a latent space, plus a Neo4j KG and a literature
store). We are building the **agentic decision layer on top**: a user-facing orchestrator that answers
hard drug-discovery/development questions at the depth a VC, a consulting firm, or an FDA reviewer
would — by gathering facts, then convening expert opinion.

**The bar:** the ~300 prompts in `source/.../Sapphire Prompts and Queries_For ExpoAI.docx` (James'
persona-generated corpus) — and questions harder than those (trial design, FDA-stance prediction,
portfolio/franchise strategy, adversarial diligence).

## 2. The operating model — a "firm" in two buckets

Designed in the 2026-06-16 whiteboard (full spec in `sapphire-orchestrator/AGENTS.md`):

```
 user ⇄ ENGAGEMENT LEAD ── plans the engagement (activates ONLY what's needed) ──┐
   BUCKET 1 — FACTS (junior analysts)                                            │ iterate until
     scientific core: Internal Science Lead · EMET Analyst · Q-Models Runner     │ the dossier is
     semantic intel (Phase 2): FDA-memory ⛔· IP ⛔· trials · payer · KOL · …      │ complete
        RESEARCH MANAGER → complete? contradiction? gap? veto? ──re-run──────────┘
   BUCKET 2 — DELIBERATION (partners)
     ROUNDTABLE MODERATOR seats 3–7 → independent verdicts → moderated rebuttal
        partners may request more facts ──loops back to Bucket 1──
   ENGAGEMENT LEAD → report: the facts + how each player reacted (no forced consensus)
```

**Junior analysts (Bucket 1)** get a task, fetch the facts, and re-go on any gap/contradiction until the
fact dossier is complete. **Partners (Bucket 2)** debate that dossier from their own company's/role's
mandate. Management (the 3 control agents) decides what to run and writes the report.

## 3. Key design decisions (and why) — push-backs that shaped it
1. **A dossier schema defines "done"** (`dossier_schema.md`). Without it, "iterate till comprehensive"
   never terminates or over-fetches. The Engagement Lead scopes which fields are *required* per prompt —
   that scoping **is** "only run what's needed."
2. **Loop triggers ⊃ contradictions.** Re-open Bucket 1 on a literal contradiction, a *gap* (required
   field empty), or *thin evidence* on a load-bearing fact — not contradictions alone.
3. **Credibility-weighted contradiction.** An FDA label outranks a tweet (tiers T1–T4). A high-vs-low-tier
   "conflict" is resolved toward the higher tier, not re-fetched.
4. **Internal↔external contradictions are SIGNAL, not bugs.** If the Quiver moat disagrees with the
   literature, surface it as a `DIVERGENCE` finding — do not loop to fix it. This is the Quiver thesis
   (the atlas sees targets the literature doesn't), so it's load-bearing.
5. **Split the orchestrator into 3 control roles**, not one mega-agent: Engagement Lead / Research Manager
   / Roundtable Moderator — mirrors a real firm and keeps each focused.
6. **Roundtable = verdicts → one moderated rebuttal round**, with a **mandatory Adversarial Red-Team** seat.
   Parallel independent opinions under-deliver; cross-talk + a professional skeptic is the diligence value.
7. **Facts vs. judgment is enforced.** Bucket 1 = cited facts; Bucket 2 = opinions citing the dossier.
   This dodges the documented "persona prompting degrades accuracy" failure (see `expert-agent/PROPOSAL.md`).
8. **Institutional archetypes James' personas lack** — ex-FDA Regulator, Payer/Market-Access, KOL/Academic,
   Red-Team — built net-new for VC/consulting/FDA-grade output. Note FDA/Payer/KOL appear in **both**
   buckets on purpose: Bucket 1 *retrieves facts*, Bucket 2 *renders opinion* (they feed, not duplicate).
9. **Veto facts are gates, not kills.** A prior CRL on the same flaw / a blocking patent is surfaced to the
   roundtable to adjudicate, never silently dropped.
10. **Selective activation controls cost.** 13 semantic agents × dozens of sources is huge; the Engagement
    Lead activates by *beat* (cluster), default 2–4 agents. Full activation = rare deep-diligence.

## 4. What's built vs pending

**Built (Phase 1, this branch):**
- Operating model + roster: `sapphire-orchestrator/AGENTS.md`; dossier "done" definition: `dossier_schema.md`.
- Control: `agents/control/{engagement-lead, research-manager, roundtable-moderator}.md`.
- Scientific-core fact agents: `agents/facts/scientific/{internal-science-lead, emet-analyst, q-models-runner}.md`.
- Institutional partners: `agents/partners/institutional/{ex-fda-regulator, adversarial-red-team, payer-market-access, kol-academic}.md` + `company-partner-template.md`.
- Already existed (prior work, all reusable): the `sapphire-cascade/` evidence pipeline (live EMET), the
  Q-Models mock (`qmodels/`), two worked scenarios with **real persona deliberation** (`scenarios/{nav1_8,tsc2}.json`),
  and the `site/` Console that visualizes a run.

**Pending:**
- **Phase 2 — the 13 semantic fact agents.** Spec each with the Phase-1 template, under
  `agents/facts/semantic/`. Content source: Hayes' `SemanticAgentsHayes_Sapphire_6.16.docx` (Downloads;
  the `SemanticAgents/` folder is deliberately excluded here). Reframe Hayes' MM-120 examples to CNS/Quiver.
  Preserve the ⛔ veto flag on FDA-memory and IP.
- **Wiring.** Turn the `.md` specs into a runnable loop (Engagement Lead → Bucket 1 → Research Manager →
  Bucket 2 → report). Substrate: Claude Code session-driven first (like the cascade), then standalone.
- **Console upgrade.** Extend `site/` to drive the full two-bucket flow (it currently shows the simpler
  4-stage happy path).

## 5. Demo fidelity & assumptions
- **Live:** EMET (BenchSci via Playwright, in the cascade), persona deliberation (real LLM agents on the
  real persona files).
- **Mock (by design, for now):** Q-Models (no AWS yet — same I/O contract), the internal moat (synthetic
  candidates). The user is wiring real AWS + internal data; **assume those land, don't block on them.**
  Always label mocks.

## 6. The research foundation (why the earlier artifacts still matter)
This repo began as the analysis that justifies the build; keep it as reference:
- `capability_map.xlsx` — 16 capability areas × the 299 prompts; what each needs + empirical status.
- `model_landscape.md` — candidate models per capability (proven vs paper-claim), from the Q-Mammal eval.
- `integration_map.md` — external data/tools re-cut into the Internal/Context/Predictivity layers.
- `orchestration_brief_hayes.md` — the agentic-orchestration archetypes the firm model realizes.
- `expert-agent/` — the CAP-15 "expert from public posts" design; the **ex-FDA Regulator partner reuses it**.
- `personas/` — James' 59, the company-partner pool. `meetings/` — the strategy transcript.

## 7. Next steps (concrete)
1. Build Phase-2 semantic agents (13 `.md` files) from Hayes' draft.
2. Define the runnable loop + a couple of end-to-end engagements (reuse Nav1.8 / TSC2; add a "harder"
   one — e.g. trial-design + FDA stance).
3. Upgrade the Console to the two-bucket flow.
4. (User) wire Q-Models→AWS and the real internal moat; flip the mocks.

## 8. Open questions
- Modality-specialist partners (ASO / gene-therapy / chemist) — build as Bucket-2 seats now or on demand?
- Roundtable: keep one rebuttal round, or allow multi-round for the hardest prompts?
- `GenomicsDB` layer membership (internal vs external) — still unconfirmed (affects `integration_map.md`).
- Repo rename: this is still `sapphire-capability-map`; the project has outgrown the name. Consider renaming
  the GitHub repo (e.g. `sapphire`) when convenient — branch/structure already treat the orchestrator as core.

## 9. Pointers
- Operating model + roster → `sapphire-orchestrator/AGENTS.md`
- Q-Models launchpad → github.com/rohanaryagondi/Q-Models · Empirical evals → github.com/rohanaryagondi/Q-Mammal
- Strategy meeting → `meetings/2026-06-11-sapphire-strategy-james.md`
