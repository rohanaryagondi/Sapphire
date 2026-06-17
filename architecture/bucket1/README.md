# Bucket 1 — Facts (the junior analysts)

Bucket 1 produces the **cited fact dossier**: every claim carries a source, a credibility tier, and a
confidence. Nothing here is an opinion — judgment is Bucket 2's job. The [Research Manager](../orchestrator/research-manager.md)
decides when the dossier is complete (against [`dossier_schema.md`](../../sapphire-orchestrator/dossier_schema.md))
and orders targeted re-runs. Two sub-groups: the **scientific core** and the **13 semantic agents**.

The evidence engine the scientific core leans on is the separate
[`../../sapphire-cascade/`](../../sapphire-cascade/) (internal moat → context gate → predictivity boost)
— the "Discover" step that produces the ranked #7→#1 candidate.

---

## Scientific core — [`scientific/`](scientific/)

**[Internal Science Lead](scientific/internal-science-lead.md)** — owns Quiver's EP-CRISPR moat. Turns
the question into the internal hypothesis (a ranked candidate list with scores + provenance), flags what
the moat under-resolves, and marks where it disagrees with external evidence (DIVERGENCE). Internal data
never leaves this agent. *MOCK in the demo.*

**[EMET Analyst](scientific/emet-analyst.md)** — the primary biomedical-evidence analyst and the single
door to EMET (BenchSci). Drives EMET in Thorough mode for genetics / pathway / drug-safety, cites every
claim, and runs the semantic agents' batched literature questions. *Live.*

**[Q-Models Runner](scientific/q-models-runner.md)** — runs the right specialist model on a specific
target/pair on demand: Boltz-2 (binding), ADMET-AI (tox/BBB), CardioGenAI (cardiac), the Quiver
ion-channel fine-tune (selectivity). Public inputs only; a prediction is a *fact* for the dossier, not a
verdict. *MOCK (AWS launch next).*

---

## Semantic intelligence — [`semantic/`](semantic/) (13)

Two carry **⛔ veto** power. Each maps to dossier fields (in parentheses).

**[FDA Institutional Memory ⛔](semantic/fda-institutional-memory.md)** (C3 / D2) — reads the FDA's
decades-long record (CRLs, AdComm votes, holds, guidance) and raises a dispositive veto when a program
repeats a flaw the agency already rejected. A veto is a gate the roundtable adjudicates, never a silent kill.

**[Patent & IP ⛔](semantic/patent-ip.md)** (E1) — maps freedom-to-operate / patentability (Lens.org,
USPTO/PTAB, Espacenet, Orange/Purple Book) and raises a veto on a blocking, in-force patent.
Infringement/validity calls are flagged for counsel, not asserted.

**[Global Regulatory Divergence](semantic/global-regulatory-divergence.md)** (D3) — what ex-US regulators
(EMA, TGA, PMDA, NICE…) decided about the same target/class, and where they diverge from the FDA — as
strategic intelligence, not a contradiction to reconcile.

**[DEA Scheduling](semantic/dea-scheduling.md)** (D4) — controlled-substance status and rescheduling
trajectory (DEA orders, Federal Register), translated into trial / manufacturing / prescribing impact. A
schedule is a constraint to surface, not a veto.

**[Clinical-Trial Registry](semantic/clinical-trial-registry.md)** (D1) — reads the registry as an
intelligence analyst: protocol amendments, enrollment health, posted adverse-event tables, termination
timing — the timestamped signals of what actually happened to a program.

**[Post-Market Safety](semantic/post-market-safety.md)** (C1 / C2) — class-level safety officer. Reads
the real-world adverse-event record (FAERS, labels, REMS, post-market commitments) of every approved drug
sharing the mechanism/class, finding the trial-vs-real-world gap. Works alongside the EMET Analyst.

**[Financial & Investor](semantic/financial-investor.md)** (E2) — reads the investor record: SEC filings
(the most candid risk statements companies make), earnings transcripts, and deal-term structures that
encode how the field privately prices success. Maps the competitive pipeline.

**[Payer & Market Access](semantic/payer-market-access.md)** (E4) — answers "will payers cover it, and at
what price?" via ICER, NICE, CMS coverage, and PBM formulary decisions; flags combination-product /
site-of-care reimbursement gaps.

**[Manufacturing / CMC](semantic/manufacturing-cmc.md)** (E5) — asks the manufacturing question early: can
it be made at clinical/commercial scale by a qualified (and, if controlled, DEA-licensed) facility? Reads
FDA Warning Letters, Form 483s, and Drug Master Files.

**[Patient Advocacy](semantic/patient-advocacy.md)** (F1) — treats patient communities as strategic
stakeholders: PFDD testimony shapes FDA benefit-risk; organized advocacy drives recruitment and access.
Down-weights informal/social sources.

**[KOL & Social Signal](semantic/kol-social-signal.md)** (F2) — reads the informal scientific discourse
(conference abstracts, expert posts, newsletters) for forward-looking signal before it hits the formal
record. Named-expert-on-record = T3, social = T4; load-bearing claims still get validated against EMET.

**[Policy & Legislative](semantic/policy-legislative.md)** (F3) — reads the legislative/political
environment (Congress.gov, Federal Register, lobbying disclosures) for power signals that move FDA
timelines, DEA scheduling, and drug pricing.

**[Reputational / Institutional](semantic/reputational-institutional.md)** (F4) — how the program /
sponsor / mechanism is perceived (investigative press, retractions, institutional statements); reputational
headwinds shape FDA scrutiny, partner appetite, and recruitment. *Project addition beyond Hayes' 11.*
