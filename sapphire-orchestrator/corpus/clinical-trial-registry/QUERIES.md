# QUERIES — clinical-trial-registry corpus

Six realistic checks the `clinical-trial-registry` agent would run for dossier field **D1**, answered **from the corpus** (`index.jsonl` / `notes/`). Checks the corpus can't answer are stated as the live-search gap.

### Q1. What happened to the anti-amyloid antibody Phase 3 programs?
**A (from corpus):** A 2019 failure wave — aducanumab ENGAGE (NCT02477800) terminated on **futility, explicitly not safety**; crenezumab CREAD (NCT03114657) discontinued at interim as **unlikely to meet its primary endpoint**. (Both predate the later lecanemab/donanemab successes.) → those two cards.

### Q2. Have HTT-lowering antisense oligonucleotides worked in Huntington's disease?
**A (from corpus):** Not yet, registry-wise — Wave's allele-selective WVE-120101 (NCT03225833) was **terminated for "Lack of Efficacy"**; Roche's tominersen GENERATION HD1 (NCT03761849) is registry-**COMPLETED** but its March-2021 dosing halt isn't in the structured data (corroborate via releases). → WVE-120101 + tominersen cards + `notes/` registry-vs-reality caveat.

### Q3. Is an "early termination" status always bad news for a program?
**A (from corpus):** **No** — read `whyStopped`. The pivotal SMA trial ENDEAR (NCT02193074) is "TERMINATED" but for a **positive interim** (roll into open-label); Ionis's MECP2 study (NCT06014541) and Encoded's SCN1A Dravet study (NCT04537832) ended early having **met objectives**. Status alone inverts the signal. → those cards + `notes/` key lesson.

### Q4. What CNS antisense / genetic-modifier programs have been discontinued?
**A (from corpus):** Biogen's **ATXN2-lowering ASO BIIB105** in ALS (NCT04494256) — terminated 2024 by **"Sponsor's decision"**; plus the HD HTT-ASO failures (Q2). → BIIB105 + WVE-120101 cards.

### Q5. Any portfolio/business-driven (non-efficacy) trial signals in genetic epilepsy?
**A (from corpus):** Takeda **withdrew** a Dravet/Lennox-Gastaut study (NCT06395792) for a **"Business Decision"** — a prioritization signal, not an efficacy verdict. → Takeda card.

### Q6. What's the trial precedent / status for ALS futility stops?
**A (from corpus):** Dexpramipexole Phase 3 extension (NCT01622088) terminated after the parent EMPOWER trial failed its endpoint; the Triumeq repurposing Phase 3 (NCT05193994) stopped at interim for **no survival benefit**. → those two cards.

---
### Checks the corpus does NOT fully answer (live-search / follow-up gaps)
- **Published-literature / mechanism evidence** behind these programs (target engagement, biomarker rationale) — EMET Pass B, now addressable (host-permission granted); the priority follow-up for this EMET-central agent. → EMET.
- **Protocol-amendment events, posted AE tables, DSMB/interim timing** — only the trial-record + termination layer was mined; deeper CT.gov endpoints (version history, results) are a follow-up. → live CT.gov query.
- **Specific precedents not yet ingested** — tofersen/VALOR (SOD1), Angelman UBE3A ASOs, C9orf72 ALS. → targeted CT.gov query.
- **Ex-US registries** (WHO ICTRP, EUCTR, ISRCTN…) — not queried this pass. → live search.
