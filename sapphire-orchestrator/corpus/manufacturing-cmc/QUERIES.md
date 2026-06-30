# QUERIES — manufacturing-cmc corpus

Six realistic checks the `manufacturing-cmc` agent would run for dossier field **E5**, answered **from the corpus** (`index.jsonl`). Checks the corpus cannot answer are stated as the live-search gap.

### Q1. What are the most common FDA CGMP violations that lead to warning letters for sterile injectable manufacturers?
**A (from corpus):** Failure to establish validated aseptic procedures (21 CFR 211.113(b)) is the most common citation. Specific patterns: inadequate aseptic technique by operators, ISO 5 particulate excursions, inadequate media fill simulation of commercial operations, data integrity failures (destroyed records), and inadequate investigation of out-of-specification events. → Cards 1, 2, 3.

### Q2. What happened when Intas Pharmaceuticals was inspected in 2023?
**A (from corpus):** FDA issued a warning letter (November 2023) for data integrity violations and failure to investigate NVP (non-viable particulate) excursions at ISO 5 filling stations. Intas voluntarily recalled batches due to particle contamination in retain samples. Quote: "Excessive particulates in the ISO 5 environment can lead to non-viable or biological contamination of sterile drug products." → Card 3.

### Q3. What is a Drug Master File (DMF) and why does it matter for CMO diligence?
**A (from corpus):** A DMF is a confidential FDA submission by manufacturers providing detailed information about facilities, processes, or articles used in drug manufacturing. A Type II DMF covers the drug substance/API. CMO engagement with a filed Type II DMF signals FDA-readiness for IND/NDA supply. Absence of a DMF = supply-readiness risk. → Card 4.

### Q4. Are there FDA warning letters specifically for ASO oligonucleotide manufacturing facilities?
**A (from corpus):** Cannot answer from corpus — no ASO/oligonucleotide-specific CMO warning letters were found in accessible public records (see manifest known-gap 1). The general aseptic manufacturing enforcement patterns (cards 1-3) are the applicable precedents for injectable oligonucleotide formulations. → Live search gap.

### Q5. How can a program team screen a candidate CMO's inspection history before committing to a partnership?
**A (from corpus):** The FDA Inspections Dashboard (`datadashboard.fda.gov`) provides weekly-updated final inspection classifications (NAI / VAI / OAI) for drug manufacturing facilities. OAI classification or an outstanding warning letter = supply-chain risk that can delay IND or NDA filing. → Card 5.

### Q6. What is the track record of Emergent BioSolutions facilities for CGMP compliance?
**A (from corpus):** Cangene BioPharma LLC dba Emergent BioSolutions (Baltimore, MD) received an FDA warning letter in August 2022 for particulate contamination of sterile biologics and inadequate aseptic technique, with similar deviations cited in a prior 2021 inspection — indicating repeat violations. → Card 1.

---
### Checks the corpus does NOT answer (live-search gaps)
- **ASO oligonucleotide-specific CMO warning letters** — not found in accessible public records; live search.
- **Gene therapy (AAV) facility enforcement actions** — not pre-ingested; live search.
- **FDA Form 483 specific observations** for a named facility — most 483s require FOIA; live search.
- **DEA-licensed manufacturer availability** for controlled substance synthesis at clinical/commercial scale — deferred to DEA scheduling agent.
- **CMO capacity / capacity availability** for specific modalities — not publicly indexed; live search.
