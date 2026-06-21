# Nav/Cav variant GoF/LoF fine-tune (SCION+funNCion) — NEGATIVE but decisive: direction doesn't transfer across channels, 2026-06-15

The SCION-unlocked Track-9 fine-tune. Trained a supervised GoF-vs-LoF classifier (GradientBoosting on
ESM-2-650M features: masked-marginal LLR + windowed WT/MUT residue embeddings + aa/pos/gene aux) on the
**pooled SCION (MIT) + funNCion** Nav/Cav variant corpus, to ask two things: (Q1) does supervision beat the
generic ESM-2 LLR across the family, and (Q2) does cross-channel training **transfer to held-out Nav1.8**
(SCN10A) — the channel with almost no public labels. **Answer to both: no. And that's the point — it's the
empirical proof of build-don't-buy for Nav1.8.** rc=0, g5.xlarge, ~$0.5.

## Corpus
2,212 unique variants (814 GoF / 1,398 LoF, 15 genes) from SCION (375 NaV) + funNCion (2,771 gof/lof; 934
overlap with SCION, dedup SCION-wins). **SCN10A/Nav1.8 = 16 (9 GoF / 7 LoF) — from SCION only**, the held-out
transfer target. 47 variants dropped (refAA≠UniProt). The corpus is **strongly gene-confounded**: many genes
are near-single-class (CACNA1C 95:2 GoF:LoF, CACNA1S 0:119, CACNA1D 35:0, SCN1A 14:684).

## Results
| Eval | AUROC | vs reference | verdict |
|---|---|---|---|
| ESM-2 LLR baseline (these 2,165 variants) | **0.610** | ≈ generic-LLR ref 0.665 | deleteriousness, not direction |
| Supervised, leave-one-GENE-out (GroupKFold) | **0.362** | **< the 0.610 LLR baseline** | ❌ does not generalize across genes |
| Supervised, held-out **Nav1.8/SCN10A** transfer | **0.476** (≈chance) | LLR-on-Nav1.8 = 0.571 | ❌ does not transfer to Nav1.8 |
| (ref) funNCion within-distribution | 0.897 | — | achieved WITHOUT holding out genes |
| (ref) MissION (portal-only) | 0.925 | — | not adoptable |

- **Q1 (beats generic LLR across family): FALSE.** The leave-one-gene-out supervised AUROC (0.362) is *below*
  the LLR baseline (0.610). With each gene's variants skewed to one direction, a cross-gene model learns
  **gene identity**, not transferable variant biology, so it anti-correlates on a held-out gene.
- **Q2 (transfers to held-out Nav1.8): FALSE.** Train on all 2,149 non-SCN10A variants → test on the 16
  Nav1.8 variants = **AUROC 0.476**, no better than chance and below even the generic LLR on those 16 (0.571).
- Some *within-gene* signal exists where a gene is balanced (per-gene held-out: CACNA1A 0.71, Cav1.2 0.56),
  but it does not aggregate into cross-channel generalization.

## Why this matters (the decisive read)
This is the **empirical** version of the scorecard's "Nav1.8 is build-don't-buy" claim — upgraded from
"labels are absent" to "**transfer demonstrably fails**." Even when we *do* assemble Nav1.8 labels (SCION's
16) plus 2,200 other-channel variants, **GoF/LoF direction does not transfer across channels** — it is
channel-specific biology. funNCion's 0.897 and MissION's 0.925 are **within-distribution** numbers (they do
not hold a whole gene/channel out); our leave-one-gene-out protocol is the honest test of whether public data
substitutes for channel-specific data, and it says no. **Conclusion: a deployable Nav1.8 variant-effect model
requires Nav1.8-specific functional measurements (Quiver's own electrophysiology) — public Nav/Cav data
cannot stand in for it.** This is exactly the kind of result that points to where Quiver's data is the moat.

## Honest caveats
- Held-out Nav1.8 n=16 → wide CI; read as directional evidence, corroborated by the family-wide LOGO failure.
- The gene-confounding (per-gene class skew) is itself a property of the *public* data — a balanced
  within-Nav1.8 training set (which Quiver could generate) is a different, tractable problem.
- funNCion remains the **within-distribution** Track-9 tool of record (0.897) for the public channels it
  covers; this run does not displace it — it characterizes the *transfer* limit.

## Scorecard impact
Track 9 (variant effect): funNCion stays the within-distribution winner. **Add the empirical build-don't-buy
result:** a supervised model on pooled public Nav/Cav GoF/LoF data does NOT generalize across channels (LOGO
0.36 < LLR 0.61) and does NOT transfer to held-out Nav1.8 (0.48 ≈ chance) — Nav1.8 variant-effect needs
Quiver functional data, now demonstrated rather than asserted. SCION (16 real Nav1.8 labels) noted as the
seed + eval anchor.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/variant_finetune/variant_finetune_result.json`;
eval `aws/variant_finetune_eval.py`; data SCION + funNCion (`docs/cns_data_sources.md`); instance
`i-033bc9d50b048aa3a` self-terminated (rc=0).
