# Saved :8101 run — TSC2 15-gene blind rescue ranking (EMET-focused)

Captured from the live `:8101` orchestrator (`http://127.0.0.1:8101`), status **Done**. This is a real run of
`live_engine`-style flow driven by `claude -p` + the `sapphire-orchestrate` skill: **moat → EMET (blind,
cached) → ESM → parallel semantic agents → synthesis**, EMET-evidence-primary with the Quiver moat as
corroboration and ESM explicitly down-weighted.

**Question:** "Rank these genes by how strongly knocking each one down reverses the TSC2-KO / mTORC1-
hyperactivation phenotype … weigh FOR vs AGAINST … Genes: BCL2, VPS54, KMT2D, DPM2, RPS3, FZD7, SSU72, DIDO1,
ACTR3, CDK9, NCOA6, SMARCE1, SAP18, MTOR, PSMD13"

| # | Gene | Quiver moat | EMET | ESM (down-weighted) | Verdict | Conf |
|---|---|---|---|---|---|---|
| 1 | MTOR | – (on-target node) | strong | mid 0.938 — doesn't track rescue | RESCUE (on-target; KD = rapamycin-equivalent) | HIGH |
| 2 | CDK9 | rank 42 · d 0.312 | moderate | mid 0.936 — ignored | PARTIAL (P-TEFb/mTORC1; best non-mTOR druggable) PMID:31300006 | MEDIUM |
| 3 | FZD7 | rank 2 · d 0.204 | moderate | lower 0.896 | PARTIAL (Wnt→PI3K→mTOR; strongest moat↔lit AGREEMENT) PMID:27531477 | MEDIUM |
| 4 | VPS54 | rank 5 · d 0.214 | none | distant 0.844 | DIVERGENCE (Quiver alpha — no published mechanism) PMID:26539077 | LOW |
| 5 | BCL2 | rank 8 · d 0.233 | weak | lower 0.882 | DIVERGENCE (downstream autophagy gate) PMID:34161185 | LOW |
| 6 | DPM2 | rank 14 · d 0.252 | none | near 0.943 — disregarded | DIVERGENCE (no mTORC1 basis) | LOW |
| 7 | DIDO1 | rank 20 · d 0.273 | none | near 0.943 — disregarded | DIVERGENCE (chromatin; no link) | LOW |
| 8 | NCOA6 | rank 48 · d 0.336 | weak | mid 0.925 | NO-EFFECT | LOW |
| 9 | SAP18 | rank 32 · d 0.303 | weak | near 0.948 — inert | NO-EFFECT | LOW |
| 10 | SSU72 | – | none | **NEAREST 0.958 — yet inert (headline: ESM ≠ rescue)** | NO-EFFECT PMID:15125841 | LOW |
| 11 | KMT2D | rank 47 · d 0.329 | weak | mid 0.917 | WORSEN (LOSS de-represses mTOR) PMID:30641523 | LOW |
| 12 | SMARCE1 | – | moderate | distant 0.774 | WORSEN (LOSS activates mTOR) PMID:39577862 | LOW |
| 13 | RPS3 | – | strong | near 0.95 — yet worsening | WORSEN (downstream effector; KD collapses translation) | LOW |
| 14 | ACTR3 | – | strong | 0.162 — most distant | WORSEN (pan-essential cytoskeleton) | LOW |
| 15 | PSMD13 | rank 16 (exacerbate) | strong | n/a | WORSEN (exacerbate-direction + pan-essential) | HIGH |

**Synthesis (verbatim):** EMET-focused read. The only evidenced rescues cluster at the top: MTOR is the
unambiguous #1 on-target node (only liability = therapeutic window); CDK9 (#2) is EMET's best non-mTOR
druggable rescue via the P-TEFb/mTORC1 intersection (held to medium — TSC2-KO is a kinase/translation not an
elongation phenotype, weak moat r42); FZD7 (#3) is the strongest CONVERGENCE (partial Wnt→PI3K→mTOR rescue
exactly where the moat is strongest, r2/0.204). The DIVERGENCES — VPS54 (r5), BCL2 (r8), DPM2, DIDO1 — carry
internal rescue signal with no published mechanism; VPS54 is the cleanest Quiver-alpha wet-lab probe. The
against-tail is firm: NCOA6/SAP18/SSU72 inert; KMT2D & SMARCE1 LOSS de-represses/activates mTOR (KD worsens);
RPS3 & ACTR3 pan-essential; PSMD13 last as the lone exacerbate-direction call. **ESM was addressed but
DOWN-WEIGHTED: the ESM-nearest genes (SSU72 0.958, RPS3 0.95, SAP18 0.948) are all no-effect/worsening while
the real hits sit mid-pack — ESM-to-target proximity demonstrably does not track rescue here.** Confidence: medium.

> Provenance: moat = real Quiver EP-signature (cosine_distance); EMET = captured blind dossier (real PMIDs);
> ESM = cached ESM-2-650M; semantic agents = claude-haiku (parallel). Screenshot: `8101_tsc2_run.png`.
