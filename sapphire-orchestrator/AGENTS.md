# Sapphire Agent Roster & Operating Model

The orchestrator runs like a **firm**: junior analysts gather facts (Bucket 1), partners deliberate
(Bucket 2), and a management layer decides what to run and writes the report. This doc is the index +
the operating rules. Per-agent specs live under [`agents/`](agents/).

> Status: **Phase 1 + Phase 2 done.** Phase 1 = 3 control agents + 3 scientific-core fact agents + 4
> institutional partners + the [dossier schema](dossier_schema.md). Phase 2 = all **13 semantic
> (non-scientific) fact agents** built (from Hayes' draft + 2 project additions). Company partners reuse
> [`../personas/`](../personas/). **Phase 3 done:** the orchestrator runs end-to-end —
> [`orchestrator.py`](orchestrator.py) + [`run.py`](run.py) execute control → Bucket 1 (dossier) →
> Bucket 2 (two-round roundtable) → synthesis; the `site/` Console drives it live (real query intake,
> PLAN/dossier/round-2 stages). Run: `python run.py nav1_8`, or the `/sapphire` skill for a live query.

## The two buckets

```
 user ⇄ ENGAGEMENT LEAD ──plan──┐
                                ▼
   BUCKET 1 — FACTS (junior analysts)            ── iterate until the dossier is complete ──┐
     scientific core: Internal Science Lead · EMET Analyst · Q-Models Runner                │
     semantic intel (Phase 2): FDA-memory · IP · trials · payer · KOL · policy · …          │
        │  RESEARCH MANAGER judges: complete? contradictions? gaps? vetoes?  ──re-run──┘    │
        ▼  (dossier complete)                                                               │
   BUCKET 2 — DELIBERATION (partners)                                                       │
     ROUNDTABLE MODERATOR seats 3–7 partners → independent verdicts → moderated rebuttal    │
        │  partners may request more facts ───────────────────────────────────────────────┘
        ▼
   ENGAGEMENT LEAD assembles the report: the facts + how each player reacted (no forced consensus)
```

## Operating rules

1. **Activate only what's needed.** The Engagement Lead's plan names the minimal agent set for *this*
   prompt. A bucket is never fully fired by default — semantic agents activate by *beat* (cluster), and
   most engagements touch 2–4 of them. Full activation = rare deep-diligence.
2. **"Done" = the [dossier schema](dossier_schema.md)**, scoped to the prompt. The Research Manager
   declares Bucket 1 complete only when the *required* fields are filled to the confidence bar.
3. **Three things re-open Bucket 1:** a literal **contradiction** (credibility-weighted — an FDA label
   outranks a tweet), a **gap** (a required field empty), or **thin evidence** on a load-bearing fact.
4. **Internal↔external contradictions are SIGNAL, not bugs.** If the Quiver moat disagrees with the
   literature, surface it as a candidate finding — do **not** loop to "fix" it. Only external↔external
   conflicts trigger re-fetch.
5. **Facts vs. judgment.** Bucket 1 produces only **cited facts**. Bucket 2 produces **opinions that
   cite those facts**. Partners never introduce new facts; if they need one, the Moderator routes the
   request back to Bucket 1.
6. **Veto facts are gates, not kills.** The FDA-memory and IP agents can raise a hard-stop flag (a prior
   CRL on the same flaw; a blocking patent). The Research Manager attaches it to the dossier and the
   Moderator puts it on the table — a human/partner decides, it isn't silently dropped.
7. **Termination policy.** Each engagement has a round cap and a budget; the Research Manager stops at
   diminishing returns and ships the dossier with explicit "known unknowns" rather than looping forever.

## Roster

### Control layer
| Agent | File | Owns |
|---|---|---|
| Engagement Lead | [`agents/control/engagement-lead.md`](agents/control/engagement-lead.md) | plan · route · activate-only-needed · own the loop · deliver report |
| Research Manager | [`agents/control/research-manager.md`](agents/control/research-manager.md) | Bucket-1 completeness · contradiction/gap/veto handling · re-run orders |
| Roundtable Moderator | [`agents/control/roundtable-moderator.md`](agents/control/roundtable-moderator.md) | convene partners · verdicts → rebuttal · route fact-requests |

### Bucket 1 — scientific core
| Agent | File |
|---|---|
| Internal Science Lead (moat) | [`agents/facts/scientific/internal-science-lead.md`](agents/facts/scientific/internal-science-lead.md) |
| EMET Analyst (+ EMET interface) | [`agents/facts/scientific/emet-analyst.md`](agents/facts/scientific/emet-analyst.md) |
| Q-Models Runner | [`agents/facts/scientific/q-models-runner.md`](agents/facts/scientific/q-models-runner.md) |

### Bucket 1 — semantic intelligence *(Phase 2 — all 13 built, from Hayes' draft + 2 project additions)*
Each maps to dossier fields (see `dossier_schema.md`). Two carry ⛔ veto power.
- **Veto-class:** [FDA Institutional Memory ⛔](agents/facts/semantic/fda-institutional-memory.md) (C3/D2) ·
  [Patent & IP ⛔](agents/facts/semantic/patent-ip.md) (E1)
- **Regulatory/clinical:** [Global Regulatory Divergence](agents/facts/semantic/global-regulatory-divergence.md) (D3) ·
  [DEA Scheduling](agents/facts/semantic/dea-scheduling.md) (D4) ·
  [Clinical-Trial Registry](agents/facts/semantic/clinical-trial-registry.md) (D1) ·
  [Post-Market Safety](agents/facts/semantic/post-market-safety.md) (C1/C2)
- **Commercial:** [Financial & Investor](agents/facts/semantic/financial-investor.md) (E2) ·
  [Payer & Market Access](agents/facts/semantic/payer-market-access.md) (E4) ·
  [Manufacturing/CMC](agents/facts/semantic/manufacturing-cmc.md) (E5)
- **Ecosystem/perception:** [Patient Advocacy](agents/facts/semantic/patient-advocacy.md) (F1) ·
  [KOL & Social Signal](agents/facts/semantic/kol-social-signal.md) (F2) ·
  [Policy & Legislative](agents/facts/semantic/policy-legislative.md) (F3) ·
  [Reputational/Institutional](agents/facts/semantic/reputational-institutional.md) (F4, project addition)

> Hayes' draft framed these on a psychedelics example (MM-120); the source lists are kept and the framing
> adapted to Quiver's CNS context. DEA Scheduling + Reputational/Institutional are the project's two
> additions beyond Hayes' 11. All route literature sub-questions through the EMET Analyst interface.

### Bucket 2 — partners
- **Company partners** — reuse [`../personas/`](../personas/) via the
  [company-partner template](agents/partners/company-partner-template.md): Pharma BD · Biotech CSO · VC GP · Pharma R&D SVP.
- **Institutional archetypes** (net-new): [Ex-FDA Regulator](agents/partners/institutional/ex-fda-regulator.md) ·
  [Adversarial Red-Team](agents/partners/institutional/adversarial-red-team.md) ·
  [Payer / Market-Access](agents/partners/institutional/payer-market-access.md) ·
  [KOL / Academic](agents/partners/institutional/kol-academic.md).
- **Modality specialists** *(later, as needed)*: ASO · gene-therapy · small-molecule chemist.

## Agent file format (the template every spec follows)
`Bucket/layer` · `One-liner` · `Activate when` · `Inputs` · `Procedure` · `Output (contract)` ·
`Sources/tools` (fact agents) or `Persona grounding` (partners) · `Rules` · `Hands off to`.
