# Phase 6 — ESM-2 650M vs MAMMAL 458M on protein-family clustering

**Closes the gap `docs/FINDINGS.md` (and HANDOFF §7, CLAUDE.md open-Q3) flagged before Sapphire
commits to MAMMAL embeddings.** Phase 5 compared MAMMAL only against ESM-2 **8M** (MAMMAL won,
NN recall 0.92 vs 0.88) and flagged: *"a 458M model beating an 8M model is unsurprising; ESM-2
650M/3B would likely win and must be checked."* This is that check, against the **650M** model,
on the **identical** 25-protein × 5-family panel and the **identical** metric.

Script: `experiments/phase6_esm650_comparison.py` · Raw: `results/phase6_esm650_comparison.json`
(includes per-protein nearest-neighbor detail + the persisted 25×1280 ESM-650M embeddings).
Run 2026-06-01, CPU, 66.7 s inference. MAMMAL/ESM-8M numbers **reused** from
`phase5_esm_comparison_20260529_113901.json` (not recomputed — one model in RAM at a time).

---

## Head-to-head (the deliverable)

5 families × 5 proteins (kinase / GPCR / ion-channel / nuclear-receptor / serine-protease).
Embedding = mean-pool over residue positions (exclude CLS/EOS), L2-normalize, cosine.
**NN recall** = leave-one-out same-family nearest-neighbor recall (25 proteins). **Gap** =
mean intra-family − mean inter-family cosine.

| Model | Params | NN recall ↑ | intra cos | inter cos | gap | dim |
|---|---|---|---|---|---|---|
| **MAMMAL** | 458M | **0.92** | 0.712 | 0.249 | **0.463** | 768 |
| ESM-2 8M (Phase 5) | 8M | 0.88 | 0.933 | 0.839 | 0.093 | 320 |
| **ESM-2 650M (new)** | 650M | **0.84** | 0.929 | 0.885 | 0.044 | 1280 |

**VERDICT: MAMMAL still wins. The "bigger ESM wins" prediction is FALSIFIED on this benchmark.**
ESM-2 650M does **not** beat MAMMAL — it scores **below both** MAMMAL (0.92) and the tiny ESM-2 8M
(0.88), at **0.84**. Scaling ESM-2 from 8M → 650M *lowered* family-clustering NN recall here
(0.88 → 0.84). On the question as posed — *"off-the-shelf mean-pool + cosine, which embedding
clusters our gene/target panel by family?"* — **MAMMAL is the answer, and the Sapphire embedding
question resolves in MAMMAL's favor for this readout.**

### The win is NOT a raw-cosine artifact (the obvious objection, pre-empted)
ESM-2 mean-pooled vectors are notoriously **anisotropic** (everything in a narrow cone — note
ESM-650M's intra 0.929 / inter 0.885: *all* pairs ≈ 0.9). The standard fix is to mean-center the
cloud before cosine. We ran it: **centering makes ESM-650M *worse*, 0.84 → 0.76 NN recall** (it
widens the gap to 0.578 but mis-ranks more neighbors). So the obvious "you just used raw cosine on
an anisotropic model" rebuttal cuts the wrong way — MAMMAL's 0.92 stands clear under both readouts.

### Where ESM-650M fails (interpretable, not random)
Per-family NN recall: GPCR 1.0, nuclear-receptor 1.0, serine-protease 1.0, but **kinase 0.6,
ion-channel 0.6**. All 4 misses pull the two *large multidomain* families toward each other / NRs:
`BRAF→ESR1` (0.948), `ABL1→KCNQ2` (0.978), `HCN1→PPARG` (0.981), `TRPV1→PPARG` (0.981) — every
wrong neighbor sits at cosine > 0.94, *higher* than many correct in-family pairs. Naive last-layer
mean-pool of a big ESM smears large/multidomain proteins together. MAMMAL's mean-pool happens to
stay better-separated (intra 0.71 / inter 0.25) on the same proteins.

---

## Read this before you over-claim (skeptic's caveats — the bar is empirical, not a badge)

This result is **real and decision-relevant, but narrow**. Three load-bearing caveats:

1. **n = 25 is tiny.** 5 families × 5 proteins; one protein flipping = 4 points of NN recall, two
   = 8. The **0.92 / 0.88 / 0.84 ordering is suggestive, not a leaderboard** — the per-model
   confidence intervals overlap heavily. What's solid is the *direction*: bigger-ESM did **not**
   win, which is enough to kill the "must scale ESM before trusting MAMMAL" worry. It is **not**
   enough to claim MAMMAL embeddings are categorically superior to ESM-2's.

2. **Naive mean-pool is the *weakest* way to use ESM-2 — this benchmark tests that, not ESM's
   best.** ESM-2's strong protein-level representations for homology/function typically use a
   *selected* layer (often not the last), per-residue features, or whitened/contact-head outputs —
   not a raw last-layer residue mean. Last-layer mean-pool is the known-anisotropic worst case (and
   650M's anisotropy is the worst of the three models here). So the honest statement is: **"with the
   same off-the-shelf mean-pool+cosine recipe, MAMMAL clusters this panel better than ESM-2 650M,"**
   *not* "MAMMAL > ESM-2 as protein encoders." A properly layer-selected / pooled / whitened
   ESM-650M could close or reverse this. We did not chase that — it's out of scope for the "what do
   we get off-the-shelf for Sapphire" question, and would be the obvious next step if the gap were
   load-bearing.

3. **Apples-to-apples is on the recipe, not the architecture.** MAMMAL's 0.92 is its masked
   mean-pool of the encoder last hidden state (768-d, `mammal_quiver/embed.py`); both numbers are
   the same *protocol* applied to each model. That's the fair comparison for "drop-in embedding
   layer." It does not control for each model's *optimal* extraction.

**Cross-model cosine *gap* is NOT comparable** and should not be cited as "MAMMAL separates 5×
better." ESM's raw bands sit near 1.0 (anisotropy), so its gap looks tiny even when NN recall is
decent; MAMMAL's bands are naturally spread. NN recall is the only cross-model-comparable metric
here; gap is within-model context.

---

## Bottom line for the Sapphire embedding decision

- **The specific fear FINDINGS.md raised — "a bigger ESM will beat MAMMAL, so don't commit" — does
  not hold on this benchmark.** ESM-2 650M (and 8M) lose to MAMMAL on off-the-shelf mean-pool family
  clustering; scaling ESM *down*graded it. There is **no size-matched ESM-2 result that beats
  MAMMAL here**, so the Phase 5 "MAMMAL clusters our targets by family (NN 0.92)" finding survives a
  size-matched challenge.
- **But this clears a blocker; it does not crown MAMMAL.** The honest claim is *"MAMMAL is at least
  as good as ESM-2 (up to 650M) as a drop-in, mean-pooled embedding for family clustering, on a
  small panel"* — good enough to proceed with MAMMAL embeddings for the CRISPR-N gene-clustering /
  KG use case **without** a parallel ESM dependency. If embeddings ever become core (not enrichment)
  infrastructure, re-test at scale (the real 1400-gene CRISPR-N panel) with each model's *best*
  extraction, not just naive mean-pool — that's the test that would actually settle architecture
  choice. ESM-2 3B remains untested (not pursued: 650M already lost, and 3B won't load on this
  18 GB machine).
- Consistent with the project's spine: MAMMAL is **commodity enrichment that holds its own**, not a
  proven moat. "State-of-the-art on shit is still shit" — here MAMMAL isn't shit at this job, and a
  bigger commodity baseline didn't unseat it.

## Reproduce
```bash
USE_TF=0 USE_FLAX=0 PHASE6_FORCE_CPU=1 \
  /opt/anaconda3/envs/mammal/bin/python experiments/phase6_esm650_comparison.py
```
Loads **only** ESM-2 650M (forces CPU — MPS thrashes on this 18 GB box); reuses cached MAMMAL/ESM-8M
numbers from the latest `phase5_esm_comparison_*.json`; falls back to ESM-2 150M if 650M fails to
load (it loaded fine). UniProt sequences cached in `results/_uniprot_cache.json`.

**One gotcha hit and fixed:** `AutoModel.from_pretrained(..., low_cpu_mem_usage=True)` + `.to("cpu")`
raises *"Cannot copy out of meta tensor"* (weights land on the `meta` device, can't be `.to()`-moved).
Fix: load plainly (HF defaults to CPU) and only `.to(device)` for a real accelerator. See the script.
