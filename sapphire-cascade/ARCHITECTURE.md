# Sapphire Cascade — Architecture

A runnable, multi-agent realization of the **three-layer re-ranking cascade** recommended in
[`../orchestration_brief_hayes.md`](../orchestration_brief_hayes.md). It operationalizes James'
three-layer data vision — **internal moat → context *gate* → predictivity *boost*** — as a panel
of cooperating agents, with a calibrated **uncertainty/abstention** gate at the exit.

> **What this is and isn't.** This is a *demonstrable prototype*, driven inside a Claude Code
> session (the orchestration substrate). The internal moat layer (L1) is a **curated synthetic
> mock** — we do not have Quiver's real EP-CRISPR latent space here. Every external evidence
> claim, by contrast, is **real and cited**, pulled live from EMET (BenchSci). The point is to
> make the #7→#1 demo concrete and to prove the *architecture*, not to ship Quiver's moat.

---

## 1. The design principle (why this is not "Emit 2.0")

From the Hayes brief: **our internal latent space is the privileged reasoning substrate, and every
external tool is an envelope around it — a context gate or a predictivity re-ranker, never a peer.**

EMET (BenchSci) is exactly the generic agentic biomedical copilot the brief positions against. We
use it deliberately — as the **external "world" that argues with our internal result**, never as
the substrate that produces it. The asymmetry is structural:

- **L1 (internal moat)** produces the hypothesis and its provenance. It **never** queries EMET.
- **L2 (context gate)** can only **demote or kill** a candidate (subtractive / veto channel).
- **L3 (predictivity boost)** can only **add corroboration mass** to survivors (additive channel).

Gate and boost are **separate channels with separate math** so neither silently overrides the other.

```
            ┌──────────────────────────────────────────────────────────┐
  query ──► │  ORCHESTRATOR  (routes, dispatches panel, builds the      │
            │                 transparent execution plan)               │
            └───────┬──────────────────────────────────────────────────┘
                    ▼
   ┌──────────────────────────────┐   internal only, NEVER EMET
   │ L1  INTERNAL RETRIEVAL        │   curated synthetic candidates
   │  ranked targets + provenance  │   + score s_internal + provenance
   └───────┬──────────────────────┘   (which embeddings contributed)
           ▼   candidates
   ┌──────────────────────────────┐   EMET: Drug Safety / Safety
   │ L2  CONTEXT / SAFETY  (GATE)  │   Assessment / Database Q&A
   │  pass | flag | NO-GO          │   subtractive — veto only
   └───────┬──────────────────────┘
           ▼   survivors
   ┌──────────────────────────────┐   EMET: Pathway Analysis /
   │ L3  PREDICTIVITY  (BOOST)     │   Target Validation / Quant Evidence
   │  + corroboration → re-score   │   additive — boost only
   └───────┬──────────────────────┘
           ▼   re-ranked + evidence
   ┌──────────────────────────────┐
   │ UNCERTAINTY / ABSTENTION      │   neighborhood density + context↔
   │  confident → answer           │   predictivity disagreement +
   │  uncertain → abstain +        │   EMET evidence thinness
   │             propose experiment│
   └───────┬──────────────────────┘
           ▼
   Ranked hits + EXECUTION PLAN
   (which embeddings contributed, which EMET source gated/boosted,
    where evidence contradicts)
```

---

## 2. The agent panel

| Agent | File | Role | Channel | Drives EMET? |
|---|---|---|---|---|
| **Orchestrator** | [`agents/orchestrator.md`](agents/orchestrator.md) | Route the query, dispatch the panel in cascade order, assemble the execution plan + final answer | driver | manages tabs |
| **L1 Internal Retrieval** | [`agents/l1-internal-retrieval.md`](agents/l1-internal-retrieval.md) | Read the curated synthetic moat → ranked candidates + `s_internal` + provenance | substrate | **No** (hard boundary) |
| **L2 Context/Safety critic** | [`agents/l2-context-gate.md`](agents/l2-context-gate.md) | Per candidate, gather public safety / contraindication / prevalence / competition → `pass \| flag \| no-go` | subtractive | **Yes** |
| **L3 Predictivity/Re-ranking** | [`agents/l3-predictivity-boost.md`](agents/l3-predictivity-boost.md) | For survivors, gather independent corroboration (GWAS, PPI, pathway, screens, signatures) → re-score | additive | **Yes** |
| **Uncertainty/Abstention** | [`agents/uncertainty-abstention.md`](agents/uncertainty-abstention.md) | Fuse confidence signals; emit answer or abstain + propose the resolving experiment | exit gate | reads upstream |

The scoring contract a candidate carries through the cascade:

```
s_internal   = latent-space rescuer score from the (mock) fused embedding      [L1]
gate         ∈ {pass, flag, no_go}                                             [L2]
corroboration = Σ independent evidence mass (GWAS, PPI, pathway, screen, sig)  [L3]
s_final      = f(s_internal, corroboration)   for gate ∈ {pass, flag}          [L3]
             = −∞ (removed)                    for gate = no_go                [L2]
confidence   = g(neighborhood_density, context↔predictivity_agreement,
                 evidence_sufficiency)                                          [exit]
```

`f` is additive and monotonic in corroboration; `g` is the selective-prediction gate. Exact forms
are specified in each agent file so the math is auditable, not implied.

---

## 3. EMET as the evidence layer

All external evidence comes from **EMET** (`https://app.summit-prod.benchsci.com/`), driven through
a single shared Playwright browser per [`emet_protocol.md`](emet_protocol.md). EMET's built-in
**Workflows** map cleanly onto the panel:

| Cascade need | EMET Workflow(s) | Mode |
|---|---|---|
| L2 safety / contraindication veto | **Drug Safety**, **Safety Assessment** | Thorough |
| L2 prevalence / competition context | **Database Q&A** | Thorough |
| L3 target corroboration | **Target Validation**, **Target Modulation** | Thorough |
| L3 pathway / network corroboration | **Pathway Analysis** | Thorough |
| L3 quantitative effect-size evidence | **Quantitative Evidence** | Thorough |
| repurposing context (optional) | **Drug Repurposing**, **Lead Discovery** | Thorough |

**Hard data boundary.** L1 is synthetic and never touches EMET. Only **public identifiers** (gene
symbols, SMILES, disease terms, trial IDs) ever cross to EMET. No proprietary EP/CRISPR/functional
data is ever entered. This is enforced in every agent prompt and in the protocol.

---

## 4. Execution model

The browser is a **single shared session**, so agents drive EMET **sequentially** — which is also
the cascade's natural data order (L2 needs L1's candidates; L3 needs L2's survivors). Each agent
owns its own tab lifecycle (open → Thorough → query → read → **close**), always leaving **base tab 0**
open so the browser never closes. True parallel evidence-gathering would require separate browser
contexts — a noted upgrade for the standalone Python port (see §6).

---

## 5. The transparent execution plan (the user-facing output)

The plan is a *byproduct of the architecture*, not a post-hoc explanation:

1. **L1** emits the ordered candidate list and, per candidate, *which embeddings contributed*.
2. **L2** logs each candidate's gate verdict + the cited EMET evidence behind it.
3. **L3** logs each survivor's corroboration sources + the score delta they produced.
4. **Uncertainty** attaches the confidence label and any internal-vs-external contradiction found.

Rendered as: *which embeddings contributed, which external source gated or boosted, where the
evidence contradicts* — concretely realizing James' #7→#1 demo.

---

## 6. Path to the standalone version (option a)

This session-driven build (option b) is structured to graduate to a standalone Python program:
- `agents/*.md` → per-agent system prompts / classes.
- `emet_protocol.md` → a Playwright driver module with one browser **context per agent** (real parallelism).
- `internal_moat/candidates.json` → swapped for the real Quiver latent-space query.
- the orchestrator → a LangGraph/plain-Python driver with the same cascade contract.

Nothing in the contract changes; only the substrate under each box does.

---

## 7. Provenance / honesty rules (inherited from the repo)

- **"State-of-the-art on shit is still shit."** External evidence enriches; it never manufactures the hypothesis.
- L1 scores and provenance are **synthetic and labeled MOCK** everywhere they appear.
- Every L2/L3 claim is **cited to a real EMET source**; uncited claims are dropped.
- On thin or contradictory evidence the system **abstains and proposes an experiment** rather than guessing.
