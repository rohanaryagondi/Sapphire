# QUERIES — patent-ip corpus

Six realistic checks the `patent-ip` agent would run at prioritization/diligence time, answered **from the corpus** (`index.jsonl` / `notes/`). Checks the corpus cannot answer are stated as the demonstrated live-search gap (the corpus-first → search-the-gap design).

### Q1. FTO for a small-molecule SMN2 splicing modifier in the US?
**A (from corpus):** ⛔ veto-candidate — **US 9,969,754 B2** (Roche/PTC), the granted composition member of the risdiplam formula-(I) genus, is **active to ~2035-05-11** (and was litigated in Roche v. Natco). The SMN2-splicing *method* family (US 8,361,977 / US 8,980,853) is also relevant to ~2030. → `index.jsonl` US9969754B2.

### Q2. FTO for an ASO targeting the SMN2 intron-7 ISS-N1 region?
**A (from corpus):** ⛔ veto-candidate — **US 8,980,853 B2** claims the intrathecal ISS-N1 ASO method (active ~2030-11-24) and **US 8,361,977 B2** the SMN2-splicing composition/method (active ~2030-12-23), both CSHL/Ionis→Biogen. → US8980853B2, US8361977B2.

### Q3. Is AAV9 capsid IP still a blocker for a CNS gene-therapy program?
**A (from corpus):** Mostly opening up — the foundational UPenn AAV9 capsid patent **US 7,906,111 B2 lapses ~2026-01-16**, so the *capsid* becomes a freedom point. BUT for SMA specifically the **AAV9-SMN-to-CNS *method*** is still blocked by **US 10,821,154 B2** (Genzyme, active ~2033). Capsid freedom ≠ indication freedom. → US7906111B2, US10821154B2.

### Q4. What ASO platform/backbone chemistry must a CNS ASO program clear?
**A (from corpus):** **US 9,550,988 B2** (Ionis) — mixed bicyclic/non-bicyclic gapmer on a phosphorothioate backbone, claimed for reduced toxicity (2'-MOE 2nd-gen platform), **active to ~2028-11-13**. Relevant to any ASO program. → US9550988B2.

### Q5. Who holds the live blocking patent for AAV9-SMN gene therapy — is it the Zolgensma sponsor?
**A (from corpus):** No — the live blocker is third-party **Genzyme/Sanofi (US 10,821,154 B2, active ~2033)**, not AveXis/Novartis. The AveXis Zolgensma-family disclosure (**WO 2019/094253 A1**) is a **ceased PCT** (landscape, not enforceable). → US10821154B2, WO2019094253A1.

### Q6. What are the expiry cliffs across the SMA franchise (earliest clean entry by modality)?
**A (from corpus):** UPenn AAV9 capsid **2026** → Ionis gapmer platform **2028** → nusinersen SMN2 family **2030** → Genzyme AAV9-SMA method **2033** → risdiplam composition **2035**. → `notes/sma-franchise-and-modality-fto.md` (composite timeline) + each card's `est_expiry`.

---
### Checks the corpus does NOT answer (demonstrated live-search gaps)
- **Orange/Purple Book regulatory-exclusivity dates** for Spinraza/Evrysdi/Zolgensma — not ingested (fda.gov; would be T1). → live search.
- **FTO for non-SMA CNS targets/indications** — corpus is SMA-franchise-anchored. → live search by target/compound.
- **Scientific prior-art / mechanism citations** (e.g., SMN2-splicing biology behind the claims) — EMET Pass B pending the BenchSci extension permission (`manifest.md` gap 1). → EMET.
- **PTAB/IPR/ANDA Paragraph-IV/PACER litigation specifics** beyond the Roche v. Natco mention — → live `known unknowns`, may need FTO counsel.
