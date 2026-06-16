# Sapphire Agent Roster & Operating Model

The orchestrator runs like a **firm**: junior analysts gather facts (Bucket 1), partners deliberate
(Bucket 2), and a management layer decides what to run and writes the report. This doc is the index +
the operating rules. Per-agent specs live under [`agents/`](agents/).

> Status: **Phase 1** (this commit) = the 3 control agents + 3 scientific-core fact agents + 4
> institutional partners + the [dossier schema](dossier_schema.md). **Phase 2** = the 13 semantic
> (non-scientific) fact agents from Hayes' draft. Company partners reuse [`../personas/`](../personas/).

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

### Bucket 1 — semantic intelligence *(Phase 2, from Hayes' draft)*
FDA Institutional Memory ⛔ · Global Regulatory Divergence · DEA Scheduling · Clinical-Trial Registry
Intelligence · Post-Market Safety · Patent & IP ⛔ · Financial & Investor · Payer & Market Access ·
Reputational/Institutional · Patient Advocacy · KOL & Social Signal · Policy & Legislative · Manufacturing/CMC.

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
