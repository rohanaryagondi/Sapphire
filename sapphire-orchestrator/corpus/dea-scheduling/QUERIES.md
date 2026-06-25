# QUERIES — dea-scheduling corpus

Six realistic checks the `dea-scheduling` agent would run for dossier field **D4**, answered **from the corpus** (`index.jsonl` / `notes/`). Checks the corpus can't answer are stated as the live-search gap.

### Q1. Is psilocybin a controlled substance, and what schedule?
**A (from corpus):** Yes — **Schedule I** (hallucinogen, 21 CFR 1308.11(d), DEA code 7437). FDA Breakthrough research + state programs don't change the federal listing. Program impact: Schedule I research registration + quota + secure storage. → `index.jsonl` Psilocybin.

### Q2. What schedule is esketamine (Spravato), and how was it scheduled?
**A (from corpus):** **Schedule III**, controlled **by isomer-reference** as the (S)-isomer of ketamine under the 1999 ketamine final rule (64 FR 37673) — there is no standalone esketamine scheduling action. → Esketamine + Ketamine cards.

### Q3. If FDA approves a product whose molecule is otherwise Schedule I, what happens to its schedule?
**A (from corpus):** DEA places the **approved product** in a lower schedule — Epidiolex/CBD → Schedule V (2018); FDA-approved marijuana products → Schedule III (2026); dronabinol capsules → Schedule III (1999). The schedule attaches to the *product* and can be formulation-specific (Marinol III vs Syndros oral-solution II). → Cannabidiol, FDA-approved-marijuana, Dronabinol cards + `notes/` Pattern 2.

### Q4. How is GHB / sodium oxybate (Xyrem) scheduled — isn't GHB a date-rape drug?
**A (from corpus):** **Split schedule** — GHB is Schedule I in bulk, but the FDA-approved product (sodium oxybate/Xyrem) is **Schedule III with Schedule I criminal sanctions** (65 FR 13235, 2000, per Pub. L. 106-172); marketed under a restricted REMS. → Sodium oxybate / GHB card.

### Q5. Did marijuana's federal schedule change recently?
**A (from corpus):** Yes — effective **April 28, 2026**, DEA/DOJ placed **FDA-approved marijuana products** in **Schedule III** (down from Schedule I); botanical marijuana itself stays Schedule I unless FDA-approved. → FDA-approved-marijuana card.

### Q6. What's the program impact of a Schedule I designation for a CNS research compound?
**A (from corpus):** The most restrictive controls — DEA Schedule I registration, production/procurement quotas, secure storage, and (for psychedelics like psilocybin/LSD/MDMA) a major research hurdle — surfaced as a *constraint*, not a veto. → per-card `program_impact` + `notes/` Pattern 1.

---
### Checks the corpus does NOT answer (live-search gaps)
- **In-flight rescheduling petitions / dockets** (e.g. live Regulations.gov comment periods) — not ingested; → live search.
- **Analog-act ambiguity** for a novel unscheduled CNS compound — case-specific; → live search + possibly counsel.
- **Biomedical literature behind abuse-potential findings** (mechanism, e.g. 5-HT2A) — EMET Pass B pending the BenchSci extension permission (`manifest.md` gap 1). → EMET.
- **Exact pre-1996 original FR placement text** for LSD/psilocybin/MDMA — predates govinfo full-text; current status confirmed via codified CFR instead.
