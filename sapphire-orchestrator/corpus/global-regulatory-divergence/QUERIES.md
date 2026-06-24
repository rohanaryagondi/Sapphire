# QUERIES — the corpus answering real Global-Regulatory-Divergence checks

Six realistic checks this agent runs at runtime, answered **from the local corpus** (citing the
claim-card(s) / note). The last two show the corpus-first → **search-the-gap** behaviour: where the
corpus can't answer, it says so, and that *is* the gap the agent escalates to a live regulator/EMET call.

Framing (from the spec): report **what each regulator decided and on what basis** — divergence is
*intelligence* (a different rigorous standard), not a contradiction to auto-reconcile.

---

### Q1. "Has any ex-US regulator refused an amyloid-targeting Alzheimer's drug the FDA approved?"
**Answer — yes, twice.**
- Aducanumab: FDA accelerated approval (Jun 2021); **EMA refused** (17 Dec 2021) — insufficient evidence
  that amyloid reduction predicts clinical benefit [card #6].
- The same surrogate-vs-benefit fault line drove the DMD eteplirsen split (Q3).
**Implication:** a surrogate-based US accelerated approval does **not** travel; EMA demanded clinical
benefit. See `notes/anti-amyloid-divergence.md`.

### Q2. "If the FDA approves an anti-amyloid mAb broadly, will ex-US labels match?"
**Answer — no; expect a narrower, genotype-gated ex-US label.**
MHRA licensed lecanemab (Aug 2024) and donanemab (Oct 2024) but **restricted both to ApoE4 non-carriers
and heterozygotes** (excluding ε4 homozygotes) [cards #1, #2] — narrower than the FDA's initial label.
The driver is a steep APOE ε4 allele-dose ARIA risk (ARIA-E 16.8% carriers → 34.5% homozygotes for
lecanemab) [EMET card #7; PMID 38730496]. **Implication:** model a genotype-restricted ex-US population.

### Q3. "Is a dystrophin (surrogate) approval enough for ex-US regulators in DMD?"
**Answer — no. Surrogate acceptance is regulator-specific.**
FDA accelerated-approved eteplirsen (2016) on increased dystrophin; **EMA adopted a negative opinion**
(2018) [card #4]. The surrogate itself is modest/variable — responders ~8.9%→16.4% of normal dystrophin
[EMET card #9; PMID 21784508]. **Implication:** an ex-US filing on a biochemical surrogate should expect
a functional-endpoint demand.

### Q4. "Does divergence only run FDA-stricter, or can the FDA be the stricter one?"
**Answer — it runs both ways.**
Ataluren (Translarna): **EMA conditional approval (2014)** but **FDA Refuse to File (2016)** — the NDA was
"not sufficiently complete to permit a substantive review" [card #5]. **Implication:** EU authorisation is
no guarantee of even an FDA *filing*; map each agency independently.

### Q5. "If an ex-US regulator approves, does that mean ex-US market access?"
**Answer — no; the HTA/reimbursement gate is separate.**
MHRA licensed lecanemab and donanemab, but **NICE did not recommend either for the NHS** (19 Jun 2025) —
benefit too small for the cost [card #3]. **Implication:** in single-payer systems the binding gate is
HTA, not the regulator; authorisation ≠ funding.

---

## Checks the corpus CANNOT answer → search the gap (this is the design working)

- **"What did PMDA (Japan) / NMPA (China) / TGA (Australia) / Health Canada decide on this class?"**
  → **GAP.** No cards outside EMA/MHRA/NICE this pass (manifest known-gap #2). **Live regulator search.**
- **"What does the EMA EPAR/refusal say verbatim for aducanumab or eteplirsen?"**
  → **GAP for the EMA primary.** EMA's website search was **down on 2026-06-24**; these cards cite faithful
  secondaries, not the EMA EPAR (manifest known-gap #1). **Re-fetch the EMA primary live** before relying
  on exact EMA wording. (Also why tiering is conservative — see manifest Tiering note + `dev/HELP.md`.)
- **"Any divergence in psychiatry / epilepsy / pain / Parkinson's?"**
  → **GAP.** Corpus is Alzheimer's + DMD only (known-gap #5). **Live search.**
- **"Has the divergence status changed since 2026-06-24 (re-examination, new HTA appraisal)?"**
  → **Always a live call.** The corpus is a snapshot (known-gap #6). (E.g., donanemab/lecanemab EMA
  re-examinations and NICE appeals were in motion at retrieval.)
