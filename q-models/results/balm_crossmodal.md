# BALM — compound↔target shared-embedding cosine eval (2026-06-14)

**Question (user):** is there a model that puts compounds and targets in the *same* embedding
space with a **meaningful cosine** — unlike MAMMAL, whose protein↔ligand cosine was 0.08
(Phase 6, falsified)? **Answer: yes — BALM.**

**Model:** BALM (`BALM/bdb-cleaned-r-esm-lokr-chemberta-loha-cosinemse`, Comms Chem / JCIM 2025,
MIT). Two-tower: ESM-2-150M (protein) + ChemBERTa-77M (ligand) → linear projection → shared
space; **`cosine(protein_emb, drug_emb)` IS the score** (scaled to pKd over [2.0, 10.0]).
**Run:** AWS g5.xlarge, ~$0.30 + 2 short failed setup runs (~$0.30) = ~$0.60 total. Self-terminated.

## Result — the shared cosine space is REAL and competitive

Same Nav1.8 (n=11) + mTOR (n=7) binder/decoy panels Boltz-2 scored, so it's apples-to-apples.

| Target | BALM AUROC (cosine) | Boltz-2 | ConPLex | MAMMAL x-modal cosine | BALM binder/decoy cosine separation |
|---|---|---|---|---|---|
| **Nav1.8** | **0.857** | 0.714 | 0.437 | (0.08, dead) | **+0.31** (binders 0.51 vs decoys 0.19) |
| **mTOR** | **1.000** | 1.000 | — | (0.08, dead) | **+0.30** (binders 0.43 vs decoys 0.12) |

**Headline:** BALM gives a genuine shared space — interacting pairs sit **~0.31 cosine higher**
than non-binders, where MAMMAL's protein↔ligand cosine was a flat 0.08 (no geometry). And the
ranking is **good**: Nav1.8 AUROC **0.857 beats Boltz-2's 0.714**; mTOR ties at 1.000. This is
the first off-the-shelf model that does what the user asked for.

Cross-oracle agreement (Spearman BALM-pKd vs Boltz prob_binder): Nav1.8 0.41, mTOR 0.64 —
moderate; the two models partly agree but aren't redundant.

## The operating envelope (be honest about the caveats)
1. **Small n.** 11 + 7 compounds. AUROC 0.857 on Nav1.8 = essentially "1 decoy (atenolol)
   ranks above 2 weak binders." Encouraging, not decisive. Needs a bigger panel to trust.
2. **Likely partial train-leakage.** BALM trained on BindingDB Kd; the test compounds are famous
   drugs (sirolimus, lidocaine, carbamazepine, …). Nav1.8 as a *target* is data-poor, but these
   *ligands* are almost certainly in BindingDB against *something* — so this is not a clean
   cold-start. The cold-target generalization claim is supported but not cleanly isolated here.
3. **Truncation, and it didn't matter (surprising).** ESM-2 caps at 1024 tokens; Nav1.8 (1956 aa)
   and mTOR (2549 aa) were both truncated to the N-terminal ~1022 residues — yet AUROC held
   (0.857 / 1.000). Either the discriminative signal lives in the N-terminus, or BALM's global
   pooled protein embedding is robust to losing the C-terminal half. Worth probing (window the
   pore domain) before relying on it for big channels.
4. **Decoys still score high in absolute pKd.** Every decoy lands at pKd ~6.8–7.9 (only metformin
   is low, ~4.7). So the *absolute* pKd is inflated/uncalibrated on these targets — use the
   **cosine ranking within a target**, not the absolute pKd, as the signal.

## Verdict
**BALM is the answer to "a model that co-embeds compounds and targets with a usable cosine."**
It is a real two-tower contrastive space (cosine = affinity), MIT, lightweight (150M+77M, ~$0.30/run),
and on our panels it **matches Boltz-2 on mTOR and beats it on Nav1.8** — while being far cheaper
(no per-pair co-fold) and supporting fast library-scale cosine retrieval (embed once, rank by
cosine). The big open question is whether 0.857 on Nav1.8 holds on a larger, leakage-controlled
panel. Operationally: **use BALM cosine for fast cross-modal triage/retrieval; use Boltz-2 to
confirm the top hits** (co-fold the shortlist). DrugCLIP (pocket-based CLIP) is the next test.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/balm_crossmodal/balm_crossmodal_result.json`,
eval `aws/balm_crossmodal_eval.py`, panels `aws/crossmodal_panels.json` (from the Boltz Nav/mTOR runs).
