# Live local de-risking models (BBBP / hERG / DILI) — Explorer Tracks 4 & 5 deployed, 2026-06-15

MapLight (the campaign's Track-4/5 winner) is a fingerprint+gradient-boosting model — so, like the per-target
DTI fine-tunes, it runs on CPU and can be served LIVE in the Explorer. This trains a MapLight-class model per
endpoint (Morgan ECFP4 2048 + MACCS 167 + RDKit 2D descriptors → HistGradientBoosting) on the TDC benchmark
each endpoint uses, with a Murcko scaffold split, and serves them live. Local, **$0, no AWS**.
`experiments/derisking_local_train.py` → `models/derisking_local/*.joblib`.

## Results — matches/beats the MapLight references
| Endpoint | Track | TDC benchmark | scaffold-test AUROC | MapLight ref (AWS) |
|---|---|---|---|---|
| **BBBP** | 4 | BBB_Martins | **0.903** | 0.905–0.919 |
| **hERG** | 5 | hERG_Karim | **0.881** | ~0.89 |
| **DILI** | 5 | DILI | **0.934** | ~0.83 |
All three match (BBBP, hERG) or exceed (DILI) the full-MapLight references — a genuine MapLight-class model,
running live in-process.

## Deployed LIVE in the Explorer
With `EXPLORER_LOCAL_MODELS=1`, Tracks 4 (BBBP) and 5 (toxicity: hERG + DILI panel) return **real
probabilities** (not stubs), each with a **Tanimoto-to-train applicability-domain confidence flag** computed
against the FULL training set (both classes — so a confident non-binder isn't mislabeled "novel"). Verified:
- caffeine → BBB+ (P 1.0), high confidence.
- ibuprofen → hERG 0.003 (low risk, in-domain) ✓; DILI 0.988 (flag, in-domain) — defensible: NSAIDs carry a
  real hepatotoxicity signal in the DILI data; DILI is the noisiest endpoint (the model's 0.934 AUROC is strong).
ClinTox is intentionally omitted (dead — worse than chance externally, per the campaign).

## Why this completes the "live Explorer"
Together with the per-target DTI fine-tunes, the three SMILES-input tracks (2 DTI, 4 BBBP, 5 tox) are now
**all live-local** — real fine-tuned/MapLight-class predictions on CPU, no AWS, no stub. The remaining tracks
genuinely need heavier infra or aren't fine-tunable: family-clustering (ESM-2 embeddings, GPU), KG
(PROTON/ULTRA graph), structure/selectivity (Boltz-2, GPU), variant-effect (funNCion). Those stay
best-model-documented + AWS-served.

## Honest framing
- These are MapLight-CLASS local reproductions (Morgan+MACCS+RDKit-desc → HistGBT), ~0.90/0.88/0.93; the full
  MapLight (CatBoost, multi-FP) remains the documented AWS-served best (≈0.91/0.89). The live local models are
  deployable now and within ~0.01–0.02 AUROC of it.
- Applicability domain is the dominant reliability lever (as everywhere): every call is Tanimoto-gated;
  far-OOD chemotypes are low-confidence. DILI is the hardest/noisiest endpoint — treat a flag as a liability
  signal, not a verdict.

## Scorecard impact
Tracks 4 & 5: the live local MapLight-class models are the in-app default (BBBP 0.903, hERG 0.881, DILI
0.934, scaffold-test); the full MapLight (AWS) + ADMET-AI remain the documented references. ClinTox dropped.

**Receipts:** `experiments/derisking_local_train.py`; `results/derisking_local_result.json`;
`models/derisking_local/*.joblib` (gitignored, local); Explorer wiring `ui/explorer/backend/local_models.py`
+ `inference.py`; TDC benchmarks. All local, $0 AWS.
