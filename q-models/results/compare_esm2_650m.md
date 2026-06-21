# ESM-2 650M vs MAMMAL 458M on the 40-gene CRISPR-N panel

**Question.** Phase 5 / phase 6 showed MAMMAL beats ESM-2 (8M, 650M) on a 25-protein/5-family toy panel. Does that hold on the **40-gene CRISPR-N panel** (`experiments/phase5_crispr_gene_panel.py`) — i.e. on a real, heterogeneous panel that includes E3 ligases and outlier TFs, not just clean structural families? If ESM-2-650M matches or beats MAMMAL here, the Sapphire-embedding-layer pitch loses its only remaining empirical win.

---

## Setup

- **Panel**: 40 proteins (kinases 10 + a duplicate-family MAPK3 + 2 outliers, GPCRs 8, ion channels 8, nuclear receptors 6, E3-ligases-labeled 4, lipid kinase 1, phosphatase 1). Same accessions as `phase5_crispr_gene_panel.PANEL`.
- **Sequences**: UniProt REST, cached in `results/_uniprot_cache.json`.
- **Embedding recipe (identical to phase 6's ESM-650M study)**: mean-pool over residue positions (exclude CLS / EOS for ESM; masked mean-pool of encoder last hidden state for MAMMAL via `mammal_quiver/embed.py`), then L2-normalize and cosine.
- **MAMMAL 458M** numbers reused from `phase5_crispr_panel_20260529_113901.json` (no reload — one model in RAM at a time, same protocol as phase 6).
- **ESM-2** model loaded here: `facebook/esm2_t33_650M_UR50D` (650M), dim=1280, CPU.

## Head-to-head (the deliverable)

| Model | Params | NN recall ↑ | k-NN (k=3) | intra cos | inter cos | gap | dim |
|---|---|---|---|---|---|---|---|
| **MAMMAL** | 458M | **0.750** | 0.825 | 0.666 | 0.292 | **0.374** | 768 |
| ESM-2 8M (25-prot panel, context) | 8M | 0.880 | — | 0.933 | 0.839 | 0.093 | 320 |
| **ESM-2 650M** | 650M | **0.725** | 0.800 | 0.928 | 0.889 | 0.039 | 1280 |

**Anisotropy check** (mean-center, then cosine — standard ESM fix): ESM-650M centered NN recall = **0.750** (raw 0.725; centered gap 0.417). If centered is still below MAMMAL, the MAMMAL number is not a raw-cosine artifact.

### Per-family NN recall

| Family | n | MAMMAL | ESM-2 650M |
|---|---|---|---|
| e3_ligase | 4 | 0.25 | 0.25 |
| gpcr | 8 | 1.00 | 1.00 |
| ion_channel | 8 | 0.88 | 0.75 |
| kinase | 12 | 1.00 | 0.67 |
| lipid_kinase | 1 | 0.00 | 0.00 |
| nuclear_receptor | 6 | 0.33 | 1.00 |
| phosphatase | 1 | 0.00 | 0.00 |

## Verdict

**Raw-cosine: MAMMAL nominally wins (0.750 vs 0.725, Δ = +0.025 = 1 protein flip on n = 40). Centered: TIE (both at 0.750).** Unlike the 25-protein panel — where MAMMAL beat ESM-2-650M by 0.08 NN recall and *centering made ESM worse* — on the real 40-gene CRISPR-N panel the standard anisotropy fix **closes the gap entirely**: centered ESM-2-650M = 0.750, identical to MAMMAL. So the Sapphire-embedding pitch's "only remaining empirical win" **technically survives** (raw-cosine readout, the same protocol Phase 5/6 used), but **on the real panel under a fair anisotropy-corrected readout it does not** — it's a tie, and on n = 40 a tie ≈ a loss for the pitch (no longer a distinctive MAMMAL advantage).

The per-family breakdown is more informative than the headline: MAMMAL wins on kinases (1.00 vs 0.67) and ion channels (0.88 vs 0.75); ESM-2-650M wins decisively on nuclear receptors (1.00 vs 0.33) — MAMMAL routes 4/6 NRs to RARA (which is labeled `e3_ligase` here but is itself a nuclear receptor, so this is partly a label artifact, not pure model failure). The two models fail on the same heterogeneous bucket (E3 ligases 0.25 / 0.25), which is the panel-structure problem flagged in Phase 5 — not a model problem.

### Cross-panel context (25-protein toy panel from phase 6)

| Model | 25-prot panel NN | 40-gene CRISPR-N NN |
|---|---|---|
| MAMMAL 458M | 0.920 | 0.750 |
| ESM-2 8M | 0.880 | (not run here) |
| ESM-2 650M | 0.840 | 0.725 |

Both models drop from the toy panel to the real CRISPR-N panel — expected, since the 40-gene panel includes functionally-labeled but structurally heterogeneous families (E3 ligases, TP53-as-NR), and duplicate-family stress tests (MAPK3 in kinase, RARA labeled as E3).

## Implication for the Sapphire embedding-layer pitch

- **The pitch's lone empirical win is now load-bearing on protocol choices, not architecture.** Raw mean-pool + cosine: MAMMAL nominally wins by 1 protein. Apply the standard ESM anisotropy correction (mean-center before cosine): they tie at 0.750. Cross-panel: MAMMAL beat ESM-2-650M cleanly on the toy 25-protein panel (0.92 vs 0.84, and centering hurt ESM there); on the real 40-gene panel that margin collapses.
- **What this clears:** the CLAUDE.md caveat ("benchmark vs ESM-2 650M before committing to Sapphire at scale") is closed — MAMMAL is at worst tied with the open MIT-licensed ESM-2-650M on the real panel. There is no off-the-shelf reason to *block* on the embedding question.
- **What this does NOT support:** "MAMMAL embeddings are the right Sapphire layer because they uniquely cluster our targets." That claim was real on the toy panel; on the CRISPR-N panel it's a coin-flip under a fair readout. Anyone arguing for ESM-2-650M (open weights, MIT, mature tooling, layer-selection options not explored here) has a clean parity argument.
- **Caveats:** n = 40 → per-flip sensitivity ≈ 0.025, exactly the size of the raw-cosine margin. Mean-pool is the *worst* way to use ESM-2 (typical pipelines select an intermediate layer + whiten); we did not chase that. ESM-2 3B untested (memory). The CRISPR-N panel itself has heterogeneous-family labeling (RARA labeled `e3_ligase`) that costs both models real recall.
- **Strategic read** (CLAUDE.md spine intact): MAMMAL embeddings are at parity, not superiority, on the real panel. They remain a usable commodity enrichment for CRISPR-N gene clustering; they are not a moat. The moat stays V1-T + functional trace data + per-target fine-tuning on Quiver-specific data.

## Reproduce

```bash
USE_TF=0 USE_FLAX=0 COMPARE_FORCE_CPU=1 \
  /opt/anaconda3/envs/mammal/bin/python experiments/compare_esm2_650m.py
```
Loads only ESM-2-650M (CPU); reuses MAMMAL CRISPR-N numbers from the latest cached `results/phase5_crispr_panel_*.json`. UniProt sequences are cached in `results/_uniprot_cache.json`.
