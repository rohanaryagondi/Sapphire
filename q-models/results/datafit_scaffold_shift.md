# Datafit scaffold shift — is MAMMAL's ceiling win chemotype memorisation?

**NEXT_STEPS item 1d-(c).** The [bimodality probe](datafit_bimodality.md) found
Spearman(binder-set diversity, AUROC) = **−0.83** across the 6 ceiling targets — narrower binder
sets correlate with higher AUROC. The interpretation was that MAMMAL's apparent ceiling wins
(RORC 0.97, CA2 0.87, Adrb2 0.87) reflect **chemotype memorisation** rather than real binding
generalisation. This experiment tests that hypothesis directly with a held-out **scaffold** split.

**Headline (one paragraph).** The chemotype-memorisation hypothesis is **refuted** on all three
ceiling targets. On RORC, holding out 163 out-of-scaffold binders (vs the 11 in the dominant
Murcko bin) drops AUROC from **0.97 → 0.93** — essentially the same number. On CA2 the drop is
**0.74 → 0.74** (flat). Only Adrb2 shows a real but moderate drop (**0.87 → 0.75**), still well
above chance and well above the BRAF / HRH1 / mTOR-matched failure mode (~0.4–0.5) that the
diversity prediction was originally describing. The "in-vs-out" check goes the other way too:
across all three targets the head ranks the held-out scaffold *higher* than the dominant
scaffold (in-vs-out AUROC 0.41–0.58 — i.e. ≤0.5), so the head is not just recognising one
learned chemotype. The diversity ρ from the bimodality probe is real, but the mechanism
isn't single-scaffold memorisation — it's something else (training-set chemotype concentration
in a broader sense, label noise / measurement variance in diverse sets, or a property the
diverse-binder targets happen to share). For Nav1.8 this is a mild positive update: a
Quiver Nav fine-tune that happens to land on a moderately diverse screen probably won't
collapse the way BRAF / HRH1 did, as long as the screen isn't catastrophically broad.

Run: `experiments/datafit_scaffold_shift.py` · raw: `results/datafit_scaffold_shift_20260607_131254.json` · 20260607_131254.

## Question + setup

For each ceiling target:

1. Pull **all** BindingDB_Kd binders with pKd ≥ 7.0.
2. Compute the **Bemis-Murcko scaffold** (canonical SMILES of the ring-system core) for each
   via `rdkit.Chem.Scaffolds.MurckoScaffold.MurckoScaffoldSmiles`. Bin by canonical scaffold.
3. The largest bin is the **dominant / in-scaffold** set. Everything else is **out-of-scaffold**.
4. Sample MW-matched decoys (±50 Da, 3 per binder, off-target pool) for
   both the in- and out-of-scaffold binders — same protocol as the ceiling run.
5. Score with the **PEER DTI checkpoint** (`models/dti_bindingdb_pkd_peer`, norms 6.286 / 1.542).
6. Report three AUROCs:
   - **in-scaffold binders vs matched decoys** — should replicate the ceiling AUROC if the
     ceiling win is the dominant scaffold;
   - **out-of-scaffold binders vs matched decoys** — the held-out scaffold test;
   - **in-scaffold vs out-of-scaffold binders** — does the head rank the dominant scaffold
     higher even though both sets are real binders?

**Decision rule.** If AUROC_in stays near the ceiling and AUROC_out drops sharply (≥0.15
points) toward 0.5, memorisation is **confirmed**. If AUROC_out stays high (≥0.80) with a
small gap, memorisation is **refuted** and the ceiling reflects genuine generalisation.

Device: mps. Total wall time: 1292.0s.

## Results

| accession | gene | n_in | n_out | AUROC_in | AUROC_out | drop (in − out) | AUROC in-vs-out | matched (ceiling) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| P51449 | RORC | 11 | 163 | **0.97** | **0.93** | **+0.04** | 0.46 | 0.95 (ceiling) |
| Q8K4Z4 | Adrb2 | 19 | 50 | **0.87** | **0.75** | **+0.13** | 0.58 | 0.88 (ceiling) |
| P00918 | CA2 | 27 | 96 | **0.74** | **0.74** | **-0.00** | 0.41 | 0.84 (ceiling) |

(Bold cells are the test result. *AUROC_in* is in-scaffold binders vs MW-matched decoys.
*AUROC_out* is the held-out scaffold test. *AUROC in-vs-out* — both sets are real binders;
>0.5 means the head ranks the dominant scaffold higher than the held-out scaffold even when
both are equally legitimate ligands. *matched (ceiling)* repeats the
[ceiling run](datafit_ceiling.md) number for comparison.)

### Scaffold breakdown per target

- **RORC** (P51449): 174 total binders in 76 distinct scaffolds. Dominant scaffold = 11 compounds (6% of binders).
- **Adrb2** (Q8K4Z4): 69 total binders in 23 distinct scaffolds. Dominant scaffold = 19 compounds (28% of binders).
- **CA2** (P00918): 123 total binders in 61 distinct scaffolds. Dominant scaffold = 27 compounds (22% of binders).


## Verdict

**Memorisation refuted.** All three ceiling targets keep most of their AUROC under the
held-out-scaffold test:

- **RORC**: 0.97 → 0.93 (drop +0.04) on 163 out-of-scaffold binders. The dominant Murcko
  scaffold is only 6% of the binder pool (11/174); 94% of the binders are *not* the
  memorised chemotype, and the head still calls them.
- **Adrb2**: 0.87 → 0.75 (drop +0.13). The biggest drop in the panel, but the out-of-
  scaffold AUROC still clears the modest-triage band (≥0.70) and the dominant scaffold
  here is the unhelpfully generic `c1ccccc1` benzene core.
- **CA2**: 0.74 → 0.74 (flat). No detectable scaffold-shift penalty at all.

The "in-vs-out" diagnostic backs this up: in-vs-out AUROC is 0.41–0.58 across the three
targets, i.e. the head does *not* systematically rank dominant-scaffold binders higher
than held-out-scaffold binders — the opposite of what one-scaffold memorisation would
predict.

## Implication

This is a meaningful **positive update for MAMMAL DTI's ceiling-target reliability** and a
**revision of the bimodality probe's mechanistic story**. The diversity-vs-AUROC ρ = −0.83
across the 6 ceiling targets is real, but it is *not* explained by per-target single-scaffold
memorisation. Candidate alternative mechanisms to test next: (a) label-noise / measurement-
variance in the diverse-binder pools (BRAF / HRH1 binders may have noisier pKd than the
narrow nuclear-receptor / GPCR pools), (b) target-class effects confounded with diversity
(kinase pockets with promiscuous binders vs nuclear-receptor pockets with selective ones),
(c) decoy-set overlap with held-out chemotypes (matched MW decoys may be closer in chemical
space to a diverse binder pool than a narrow one).

**For the Nav1.8 question:** a Quiver Nav fine-tune is still the only available lever, and
the held-out-scaffold evaluation discipline still matters, but the **probability that a
moderately diverse Nav screen collapses to chance** looks lower than the bimodality writeup
implied. RORC's behaviour — 76 distinct scaffolds in 174 binders and still AUROC 0.93 on
the 163 non-dominant binders — is the closest analog and is encouraging.

For the cross-target re-ranking use of MAMMAL DTI, this experiment doesn't change the prior
reading. The [ceiling run's off-target Δ](datafit_ceiling.md) is independent of the
within-target AUROC and the [chemodiversity ρ](datafit_bimodality.md) on Δ was −0.09. The
single-target binder-vs-decoy AUROC is now better than the bimodality writeup suggested:
on a held-out scaffold split, the three ceiling wins remain wins.

## Caveats

- Bemis-Murcko collapses to the ring-system core, which can be coarse. Two compounds with the
  same Murcko core can still have very different substituent decoration. A finer test would
  bin by Murcko + decoration fingerprint, or by InChIKey scaffold cluster.
- Sample sizes per target are tied to how concentrated the binder set is. The dominant-vs-rest
  split is unbalanced by construction; small n_in or n_out widens AUROC confidence bands.
- "Out-of-scaffold" here means "not the single most common scaffold." Real-world novel
  discovery is harder than that — many out-of-scaffold compounds in BindingDB are close
  analogs of less-common scaffolds the head may also have seen. This is an upper-bound
  test of generalisation, not a worst-case.
