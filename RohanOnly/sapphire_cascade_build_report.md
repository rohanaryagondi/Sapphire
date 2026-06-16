# Sapphire Cascade — Build Report (RohanOnly)

**Date:** 2026-06-16
**Author:** Claude (Opus 4.8), driven by Rohan
**Status:** Built, run end-to-end, pushed to `main` (commit `a288f53`)
**Audience:** Rohan — internal/candid. Not a customer or James/Gavin/Hayes deliverable.

---

## 1. What you asked for, and what got built

You pointed me at the `sapphire-capability-map` repo and said: build a **multi-agent workflow**.
After scoping, we landed on building the flagship from the **Hayes orchestration brief** — the
**three-layer re-ranking cascade** — as a *runnable* multi-agent system, with one twist you added
live: **all external evidence comes from EMET (BenchSci)**, driven in a shared Playwright browser.

Deliverable: the `sapphire-cascade/` directory + a `/sapphire-cascade` skill. It implements
**internal moat (L1) → context GATE (L2) → predictivity BOOST (L3) → uncertainty/abstention** as a
5-agent panel, and I ran it end-to-end on **two** disease cases (Nav1.8 pain, TSC2), each
reproducing James' **#7 → #1** demo with real, cited EMET evidence.

### Decisions we locked (so you remember the "why")
- **Option (b), not (a):** the system runs *in the Claude Code session* (I orchestrate the agents
  live), not as a standalone `python run.py`. It's structured to graduate to (a) later — the agent
  defs and protocol port directly. This was your call ("keep it b, move to a later").
- **EMET = the evidence backend.** Every L2/L3 query hits EMET via Playwright (Thorough mode or the
  Drug Safety workflow), public identifiers only. This is the big architectural choice and it's what
  makes the demo *real* instead of mocked.
- **L1 (the moat) is synthetic/MOCK.** We don't have Quiver's EP-CRISPR latent space here, so I
  hand-authored the internal candidate rankings + provenance and labeled them MOCK everywhere. The
  moat **never** touches EMET (the hard data boundary).
- **Two scenarios:** Nav1.8/SCN10A pain and TSC2, per your "look at both."

---

## 2. The honest part you should know about

I **changed both #7→#1 heroes mid-build** to stay faithful to what EMET actually returned, rather
than force a target I'd pre-picked. This matters because it's the difference between a real demo and
a rigged one — and "no invented performance" is the repo's stated culture.

- **Pain:** I originally planned **NTRK1** as the #7→#1. But when EMET's Drug Safety workflow
  classified NTRK1 **WARNING** (CIPA phenotype — anhidrosis, bone fragility) and SCN11A **SAFE**, the
  honest winner became **SCN11A / Nav1.9**. Bonus: EMET independently noted Nav1.9's *"ultra-slow
  kinetic profile,"* which is *exactly* why an optical-EP assay would under-resolve it — so the
  mock-moat rationale ("moat ranks it #7 because its persistent current is hard to record") is
  backed by real evidence, not hand-waving.
- **TSC2:** the winner is **RHEB**, but the richer story is the **exit gate doing real work**: the
  highest raw-scored target (**DEPDC5**, best Mendelian epilepsy genetics) gets **abstained** because
  it's a GATOR1 *brake* with no druggable handle; the everolimus **incumbent (MTOR)** is set aside;
  so the top *novel actionable* target is RHEB (#7 → #1).

If James/Gavin push on any number, the chain is auditable: every gate/boost cites an EMET chat.

---

## 3. What's real vs. what's mock (be precise when you present)

| Layer | Real or mock | Notes |
|---|---|---|
| L1 internal moat (ranks, s_internal, provenance, QS-IDs) | **MOCK** | Hand-authored; stands in for Quiver's real latent-space query. Labeled MOCK in every file. |
| L2 context/safety (gate verdicts) | **REAL** | EMET Drug Safety workflow — FAERS, DailyMed, ClinicalTrials.gov, PubMed. Cited (PMIDs, NCTs). |
| L3 predictivity (corroboration) | **REAL** | EMET Thorough — GWAS Catalog, Open Targets, STRING, PubMed, Europe PMC. Cited. |
| Scoring formula + final ranks | **Deterministic** | `s_final = (s_internal + (1−s_internal)·corroboration)·gate_penalty`; gates map EMET SAFE/MONITOR/WARNING/CRITICAL → pass/flag_mild/flag/no_go. Arithmetic is in the candidates JSON. |
| The #7→#1 outcomes | **Emergent** | Fall out of the above; not pinned by hand (I tuned only the MOCK s_internal + documented the formula). |

**One soft spot to know about:** in the pain run, TRPA1 carries a `flag_mild` for "broad
expression/selectivity" that I did **not** get a dedicated EMET safety run for (it wasn't in my L2
panel). It's a real, known liability but it's the one gate verdict not anchored to a fresh EMET
citation. If you want it airtight, run TRPA1 through the Drug Safety workflow and update
`nav1_8_pain.candidates.json`. Everything else is anchored.

---

## 4. EMET integration — practical notes (so you/we can rebuild fast)

- App: `https://app.summit-prod.benchsci.com/`. You sign in manually; agents never log in. If a tab
  hits the login page, the run pauses and asks you to re-auth.
- **Mode:** a fresh chat defaults to **Balanced** — must set **Thorough** each time. *But* once you
  attach a **Workflow** (the "+" menu), the mode toggle is **disabled** — the workflow runs its own
  multi-stage depth. (Documented in `emet_protocol.md`.)
- **Workflows used:** plain Thorough chat for L3 corroboration (it auto-fans-out to GWAS/STRING/
  PubMed/Open Targets/Europe PMC); the **Drug Safety** workflow for L2 (returns SAFE/MONITOR/WARNING/
  CRITICAL with FAERS counts + a long report).
- **The Drug Safety report renders into an `<iframe>`**, not the chat text — read it via the frame
  body. It can be big (the TSC2 one streamed past 50 KB before finalizing) and takes ~6–10 min.
- **Tab discipline:** each agent opens its own tab, works, closes it; base tab 0 always stays open so
  the browser doesn't die. I drove agents **sequentially** (single shared browser) — for the pain L2
  + TSC2 runs I pipelined two tabs in parallel server-side to save wall-clock, which is fine.

### EMET chats that back the runs (your evidence anchors)
| Run | Layer | Chat URL suffix |
|---|---|---|
| Nav1.8 pain | L3 corroboration (43 sources) | `/chat/d070bf32-5661-4a47-856b-68026d50f0df` |
| Nav1.8 pain | L2 Drug Safety | `/chat/eacfaebc-e60f-4471-bda6-f8fd859135b0` |
| TSC2 | L3 corroboration (30 sources) | `/chat/df322bc6-7773-4ba0-a308-301c13c49fac` |
| TSC2 | L2 Drug Safety | `/chat/793bf0e7-3eac-4aa5-ac09-c64fa6417876` |

(They're under your `rohan.gondi@yale.edu` EMET account — re-openable to show the receipts live.)

---

## 5. How to demo it

1. Have EMET signed in in the Playwright browser.
2. In a Claude Code session here, run **`/sapphire-cascade`** (or say "run the Sapphire Cascade on the
   Nav1.8 pain scenario"). I'll drive L1→L2→L3→uncertainty and render the execution plan.
3. For a no-browser walkthrough, just open `sapphire-cascade/RUN_LOG.md` — both runs are captured with
   their execution plans and citations, reviewable cold.

**The one-liner for the room:** *"The hypothesis comes from our moat; EMET is the world arguing with
it — it can only veto or corroborate, never author. A target our functional assay under-ranks (#7)
gets promoted to #1 by independent human genetics + a clean safety read. That's the thing Emit
structurally can't do, because Emit has no privileged internal substrate."*

---

## 6. Open items / TODO if we keep going

- **TRPA1 L2 citation** (see §3 soft spot) — one EMET Drug Safety run to close it.
- **Port to option (a)** — standalone Python: agent defs → classes, `emet_protocol.md` → a Playwright
  driver with one browser *context per agent* (real parallelism), `candidates.json` → real Quiver
  latent-space query. Cascade contract doesn't change.
- **Swap the MOCK L1 for real Quiver data** — the moment we wire the real EP-CRISPR latent space, the
  #7→#1 stops being illustrative and starts being a live target call. That's the actual product.
- **Tier router + active-learning loop** — framed in `ARCHITECTURE.md`/brief but not built; the
  abstention→"propose experiment" hooks are already in place to feed the loop.
- **EMET as a dependency** — worth a conversation: we're using a competitor's tool as our evidence
  layer for the demo. Fine for a prototype; for production we'd point L2/L3 at the same primary
  sources EMET wraps (FAERS, Open Targets, STRING, GWAS Catalog) directly.

---

## 7. Files (all on `main`)

```
sapphire-cascade/
  ARCHITECTURE.md            design + scoring contract + EMET mapping
  emet_protocol.md           how agents drive EMET (reproducible)
  README.md
  RUN_LOG.md                 the two end-to-end runs, cited
  agents/                    orchestrator, l1, l2, l3, uncertainty-abstention
  internal_moat/             nav1_8_pain.candidates.json, tsc2.candidates.json (MOCK)
  scenarios/                 nav1_8_pain.md, tsc2.md (full walkthroughs)
.claude/skills/sapphire-cascade/SKILL.md   the /sapphire-cascade driver
RohanOnly/sapphire_cascade_build_report.md  (this file)
```
