# QUERIES — the corpus answering real KOL-Social-Signal checks

Six realistic checks this agent runs at runtime (dossier field **F2**), answered **from the local corpus**
(citing the claim-card(s) / note). The last two show corpus-first → **search-the-gap** (here, the gap is the
agent's core *live* job — ephemeral social signal).

Framing (from the spec): **facts only — report who said what**; the claim's validity is checked against EMET,
not asserted. Heavily down-weight informal sources; never override T1–T2 facts with chatter.

---

### Q1. "What is expert sentiment toward the anti-amyloid Alzheimer's antibodies?"
**Answer — net-skeptical among named KOLs.** Knopman & Perlmutter: aducanumab has "Meager Efficacy and Real
Risks" [card #2]; Bauchner & Alexander describe a "Rejection…by the Health Care Community" [card #3]; Kurkinen
calls lecanemab "not the right drug" [card #1]. Several (Knopman, Alexander) were FDA AdComm members. See `notes/`.

### Q2. "Is the muscarinic antipsychotic class (KarXT/Cobenfy) viewed positively by KOLs?"
**Answer — cautiously optimistic.** Javitt (a leading schizophrenia KOL) frames it as "Hope for Some, or Hope
for All?" [card #4]; others call Cobenfy "a significant advancement…a promising alternative" [card #5]. The
sentiment contrast with anti-amyloid is itself the signal.

### Q3. "Does informal/expert opinion diverge from the formal approval record?"
**Answer — yes, sharply, for anti-amyloid.** The drugs are FDA-approved, yet the named-KOL record is heavily
critical [cards #1–#3] — a divergence a program in the amyloid space inherits. See the divergence read in `notes/`.

### Q4. "A KOL claims lecanemab 'doesn't work in women' — is that load-bearing claim valid?"
**Answer — partially; it overreads an underpowered subgroup.** EMET validation [card #6, Shim et al. 2025
meta-analysis]: efficacy does vary by subgroup (greatest in ApoE4 non-carriers; sex a modifier), but CLARITY
AD wasn't powered for a sex×treatment interaction. So the *signal* is real but the *strong* claim isn't
established — exactly the spec's "validate against EMET" step.

### Q5. "Who are the on-record skeptics vs optimists for these CNS classes?"
**Answer — from the corpus:** skeptics = Knopman, Perlmutter, Bauchner, Alexander, Kurkinen (anti-amyloid);
optimists = Javitt, Hasan/Abid (muscarinic) [cards #1–#5, with attribution + standing noted].

---

## Checks the corpus CANNOT answer → harvest the gap live (the design working)

- **"What are high-signal accounts saying on X/Substack/podcasts about this target *this week*?"**
  → **GAP — and this is the agent's core live job.** Ephemeral social signal (spec T4) is **not pre-ingested**
  (unstable, not verbatim-citable). **Harvest live**, attribute, tier T4 in-flight (manifest gap #1).
- **"What did investigators say at the latest ACNP/APA conference (pre-publication)?"**
  → **GAP.** Conference reactions/posters are live-harvest (gap #1/#2).
- **"KOL sentiment on psychedelics / ALS / pain programs?"**
  → **GAP.** Corpus is anti-amyloid + muscarinic only (gap #3). **Live search.**
- **"Has sentiment shifted since the retrieval window?"**
  → **Always a live call** — sentiment moves fast (gap #4).
