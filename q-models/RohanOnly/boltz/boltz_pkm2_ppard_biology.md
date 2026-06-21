# Boltz-2 on PKM2 / PPARD — results + *why the biology breaks it*

**For Rohan.** Ben's TSC2 target-deconvolution check (PKM2 + PPARD), run on Bouchet H200 2026-06-11,
all 15 of Ben's complexes exactly as provided. This doc = the result tables (same as
`results/aws_eval/ben_tsc2_pkm2_ppard.md`) **plus** a structural-biology explanation of why Boltz-2
scored so poorly — so we know whether to trust "inconclusive" and what a fair re-test would need.

**Verdict: INCONCLUSIVE.** The positive controls didn't clear the off-target decoys, so Boltz can't
adjudicate the putatives. Important: this is *not* "the DFP match is wrong" — it's "Boltz-2 is the wrong
instrument for these two targets," and the reasons are specific and predictable.

*The §2 structural-biology claims were independently fact-checked by two reviewers against primary
literature (2026-06-11). Core claims verified — DASA-58 itself co-crystallized at the PKM2 A–A′ subunit
interface (Anastasiou 2012, PMID 22922757); GSK 3787 covalent on Cys249 (Shearer 2010, PMID 20128594);
H12/AF-2 switch; co-fold builds only the chains you supply. Three precision corrections folded in below.*

---

## 1. The numbers

### PKM2 (UniProt P14618, isoform **M2** = canonical, 531 aa) — 7 complexes

| role | QS ID | compound | prob_binder |
|---|---|---|---:|
| **positive control** | QS0321744 | **Dasa-58** | **0.511** |
| putative hit | QS0113172 | QS0113172 | 0.204 |
| negative | QS0214154 | BMS 191011 (KCNMA1) | 0.498 |
| negative | QS0141913 | GF 109203X (PRKCA) | 0.400 |
| negative | QS0061489 | carbamazepine (KCNQ2) | 0.397 |
| negative | QS0321864 | BIIB021 (HSP90) | 0.379 |
| negative | QS0206838 | Biperiden (CHRM3) | 0.183 |

decoys mean 0.371 (max 0.498). **positive − decoy_mean = +0.140; positive − decoy_MAX = +0.013** (tied
with top decoy). putative QS0113172 0.204 → decoy-like, −0.307 below the positive.

### PPARD (UniProt Q03181, 441 aa) — 8 complexes

| role | QS ID | compound | prob_binder |
|---|---|---|---:|
| **positive control** | QS0321760 | **GSK 3787** | **0.209** |
| putative hit | QS0113172 | QS0113172 | 0.232 |
| putative hit | QS0069567 | QS0069567 | 0.204 |
| negative | QS0214154 | BMS 191011 (KCNMA1) | 0.512 |
| negative | QS0061489 | carbamazepine (KCNQ2) | 0.242 |
| negative | QS0206838 | Biperiden (CHRM3) | 0.233 |
| negative | QS0321864 | BIIB021 (HSP90) | 0.120 |
| negative | QS0141913 | GF 109203X (PRKCA) | 0.119 |

decoys mean 0.245 (max 0.512). **positive − decoy_mean = −0.036; positive − decoy_MAX = −0.303**
(a decoy outscores the real binder). putatives 0.204 / 0.232 → decoy-like.

### Margins summary

| target | positive | decoy mean (max) | pos − decoy_mean | pos − decoy_MAX | calibration |
|---|---:|---:|---:|---:|---|
| PKM2 | 0.511 | 0.371 (0.498) | +0.140 | **+0.013** | marginal (tied with top decoy) |
| PPARD | 0.209 | 0.245 (0.512) | −0.036 | **−0.303** | **failed** (positive < decoys) |

All 15 ran clean (rc=0). Whole spread sits in a narrow ~0.12–0.51 band on both targets — the same
low-confidence regime Boltz showed on Nav (0.71), not the clean regime it showed on mTOR (1.000).

---

## 2. Why Boltz-2 fails here — the biology

**The frame.** Boltz-2 is a co-folding + affinity model. It is reliable only when **four conditions**
hold; mTOR (1.0) and the GPCRs (~0.99) satisfy all four, and PKM2 / PPARD / Nav each violate one or more
in a concrete, structural way:

1. The binding pocket actually **exists in the single-chain structure Boltz folds** (orthosteric, not a
   quaternary-interface or cryptic site).
2. The ligand is **drug-like and binds reversibly** (inside the affinity head's training chemistry and
   its equilibrium-binding assumption).
3. The target/family has **dense structural + affinity precedent** in the training data.
4. Binding doesn't hinge on a **conformational/oligomeric state** the apo co-fold doesn't capture.

### PKM2 — the binding site isn't in the model (conditions 1 + 4 + 2 all break)

- **The activator pocket is at a subunit interface, not in the monomer.** The DASA-58 / TEPP-46 / ML-265
  class of PKM2 activators bind a pocket at the **dimer–dimer interface** and work by locking PKM2 into
  its active **tetramer**. Boltz folds a **single chain** — so the activator pocket physically does not
  exist in the structure it scores. You cannot get a meaningful binding probability for a site the model
  never built. This alone is close to disqualifying for PKM2 activators.
- **PKM2 is an allosteric, oligomeric-state machine.** It cycles inactive-dimer ↔ active-tetramer, gated
  by FBP, serine, and SAICAR, plus K⁺/Mg²⁺. Affinity for an allosteric modulator is a function of that
  quaternary state and those cofactors — none of which a single-sequence co-fold represents.
- **The provided PKM2 ligand is a charged, phosphorylated metabolite-class molecule** (per its registered
  SMILES, a phospho-ribosyl/AICAR-like species). Highly anionic phospho-ligands sit at the edge of the
  drug-like chemical space the affinity head was trained on and bind metabolite/allosteric sites — a
  double hit to reliability. (Run as Ben provided; flagged only as a *chemistry* reason, not a data
  criticism.)

### PPARD — covalent mechanism + a big greasy nuclear-receptor pocket (conditions 2 + 3 break)

- **GSK 3787 is a covalent / irreversible antagonist** — it alkylates **Cys249** in the PPARδ
  ligand-binding domain (verified: Shearer 2010, PMID 20128594). Boltz-2's affinity head predicts a
  **reversible / equilibrium** binding strength (a binding likelihood + an IC50-like value) and its paper
  describes no covalent handling — so it is a reasonable *inference* (not a stated Boltz-2 result) that it
  would **underscore covalent binders**, modelling only the weak non-covalent encounter. The 0.209 for a
  known PPARD binder is plausibly partly a *mechanism artifact*, not proof Boltz can't see PPARD — but it
  makes GSK 3787 a weak calibration anchor for this model class.
- **Nuclear-receptor LBD = a large, flexible, lipophilic pocket.** PPARδ's ligand pocket is large,
  buried, Y-shaped and lipophilic, built for fatty-acid-like ligands (~1300 Å³ — a shared PPAR-family
  figure best *measured* for PPARγ; PPARδ is large by homology, not a delta-specific measurement).
  Many drug-like molecules fit it loosely, so the affinity head can't cleanly separate true ligands from
  lipophilic decoys → scores compress (exactly what we see).
- **Agonist vs antagonist is an induced-fit switch** (helix-12 / AF-2 repositioning). A single co-fold
  doesn't reliably resolve that switch, so antagonist affinity in particular is poorly captured.

### Shared reasons it collapses into the "Nav regime"

- **Off-distribution → affinity compression.** The affinity head is sharp where experimental Kd/IC50
  precedent is dense (kinases, mTOR, GPCRs) and regresses toward a narrow mid-band (~0.1–0.5) where it
  is sparse (ion channels, allosteric activators, covalent NR antagonists). A compressed band *is* the
  failure signature — no separation possible.
- **The decoys are real drugs, not inert molecules.** Our negatives are confirmed binders of *other*
  targets (PKC, KCNQ2, KCNMA1, CHRM3, HSP90) — lipophilic, well-formed, "druggable-looking." A model
  with weak target-specificity scores them ~as high as the true binder. The tell: **BMS 191011 (a
  BK/KCNMA1 opener) scores ~0.50 on *both* PKM2 and PPARD** — a sticky lipophilic false positive that
  lifts the decoy ceiling above the real binders. (Same failure mode as A-803467 in the Nav off-target
  run — a "sticky" compound that scores everywhere.)
- **Single-chain co-fold misses quaternary/cofactor context** — PKM2's tetramer interface, and in
  general missing metals, lipids, and partner proteins that shape real binding sites.

### The contrast — this is selective failure, not a broken model

| target | Boltz result | why |
|---|---|---|
| mTOR + rapalogs | AUROC **1.000** | large kinase, canonical well-characterized orthosteric pocket, famous reversible ligands dense in the PDB — all four conditions hold |
| ADRB2 / DRD2 + known drugs | prob **~0.99** | classic orthosteric GPCR pockets, abundant pharmacology |
| Nav1.8 | AUROC 0.71 | state-dependent ion-channel pharmacology, lipid-exposed fenestration site, sparse complex data |
| **PKM2** | **inconclusive** | activator site is at a **subunit interface absent from the monomer fold**; allosteric/oligomeric; charged ligand |
| **PPARD** | **inconclusive** | **covalent** antagonist (model can't represent it); big greasy NR pocket; induced-fit H12 switch |

---

## 3. What this means + a fair re-test

**Don't read "inconclusive" as "DFP refuted."** Boltz being unable to separate *known* PKM2/PPARD
binders from drug decoys means the **instrument** can't adjudicate these targets — the DFP functional
match is neither confirmed nor refuted structurally. A fairer structural test would need, per target:

- **PKM2:** model the correct **oligomeric assembly** (dimer/tetramer) so the interface activator pocket
  exists — a monomer co-fold can't see it. *(A caveat raised in the claims review: Boltz-2's Limitations
  say its affinity module doesn't explicitly handle multimeric partners, so the fix wasn't guaranteed.*
  **It worked** *— the AWS fair-retest, §7 of `../../results/aws_eval/ben_tsc2_pkm2_ppard.md`, rescued the
  PKM2 positive Dasa-58 to #1 once the dimer was folded, and on that calibrated panel QS0113172 scored
  below 4/5 decoys → **QS0113172↔PKM2 REFUTED**. But the lead was only +0.054 — the low-confidence
  signature of this allosteric regime.)* For a stronger read still, a pocket-restricted docking /
  absolute-FEP run on a PKM2-activator co-crystal template.
- **PPARD:** use a **covalent-aware** scorer for GSK 3787, or anchor calibration on a **reversible**
  PPARδ reference ligand; affinity in the large LBD is better handled by physics-based FEP on a defined
  agonist/antagonist conformation than by a single co-fold.
- **General:** off-the-shelf Boltz-2 is the wrong tool for allosteric-interface and covalent targets;
  this is a Track-2/Track-9 data point that the model's reliability is **target-class-dependent**.

---

## 4. Note for cross-branch merge (don't edit from `boltz`)

`docs/models_tracks_scorecard.md` lives on the **`models` branch**. This result adds a second
negative-but-explainable data point (after Nav) for **Track 2 (DTI / binder triage)** and
**Track 9 (off-target / selectivity)**: Boltz-2's binder-triage reliability is target-class-dependent —
strong on well-precedented orthosteric/reversible targets, unreliable on allosteric-interface (PKM2) and
covalent (PPARD) ones. Please merge a scorecard note; not editing the other branch from here.

*Raw data: `results/aws_eval/boltz_pkm2_ppard/` · companion writeup: `results/aws_eval/ben_tsc2_pkm2_ppard.md`*
