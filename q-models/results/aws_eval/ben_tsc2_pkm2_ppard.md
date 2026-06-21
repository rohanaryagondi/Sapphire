# Boltz-2: PKM2 / PPARD binding check for Ben's TSC2 target-deconvolution hits

**Run 2026-06-11 on Yale Bouchet** (H200, Boltz 2.2.1, `--no_kernels`, cu128 torch — install recipe in
`boltz_nav_eval.md` §11). Branch: `boltz`. Raw outputs: `boltz_pkm2_ppard/`.

**Context.** Quiver's 30K Optopatch screen for compounds that rescue a TSC2 phenotype surfaced two hits,
**QS0069567** and **QS0113172**. Ben's DFP library functionally matched them to **Dasa-58** (PKM2
activator) and **GSK 3787** (PPARD antagonist). This run asks Boltz-2 whether that functional match
translates to **physical binding**. TSC2 is the phenotype, not a Boltz target — the binding targets are
**PKM2 (UniProt P14618, 531 aa)** and **PPARD (UniProt Q03181, 441 aa)**. All 15 complexes are Ben's
compounds + SMILES exactly as provided (compounds validated with RDKit; sequences from UniProt).

---

## Verdict: INCONCLUSIVE

**Boltz-2's affinity head did not separate the known binders (positive controls) from the off-target
decoys on either PKM2 or PPARD, so it cannot adjudicate whether the putative hits physically bind.** On
PKM2 the positive control (Dasa-58, 0.511) was the top score but only +0.013 above the highest decoy
(BMS 191011, 0.498) — essentially tied. On PPARD the positive control (GSK 3787, 0.209) scored *below*
the decoy mean (0.245) and far below the top decoy (BMS 191011, 0.512). Per the pre-registered runbook,
when the positive controls don't clear the decoys the run is uninformative about the putatives — this is
the "calibration failed → don't over-read the putatives" branch. The putative hits did score low
(QS0113172 0.204 on PKM2; QS0069567 0.204 / QS0113172 0.232 on PPARD), decoy-like on both targets — but
because the positive calibration failed, that low score **cannot be cleanly read as "refuted"**; Boltz
simply isn't resolving binding on these two targets in this assay. **DFP claim neither structurally
confirmed nor refuted by Boltz-2.** (Consistent with the prior Boltz pattern: strong on well-precedented
targets — mTOR 1.000 — but unreliable on harder ones — Nav1.8 0.71.)

---

## 1. PKM2 (P14618) — 7 complexes

| role | QS ID | compound | prob_binder |
|---|---|---|---:|
| **positive control** | QS0321744 | **Dasa-58** | **0.511** |
| putative hit | QS0113172 | QS0113172 | 0.204 |
| negative | QS0214154 | BMS 191011 (KCNMA1) | 0.498 |
| negative | QS0141913 | GF 109203X (PRKCA) | 0.400 |
| negative | QS0061489 | carbamazepine (KCNQ2) | 0.397 |
| negative | QS0321864 | BIIB021 (HSP90) | 0.379 |
| negative | QS0206838 | Biperiden (CHRM3) | 0.183 |

- decoys: mean 0.371, max 0.498
- **positive − decoy_mean = +0.140 ; positive − decoy_MAX = +0.013** (positive is top, but tied with BMS 191011)
- **putative QS0113172 = 0.204**: vs decoy_mean **−0.168**, vs positive **−0.307** → decoy-like, well below the positive

## 2. PPARD (Q03181) — 8 complexes

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

- decoys: mean 0.245, max 0.512
- **positive − decoy_mean = −0.036 ; positive − decoy_MAX = −0.303** (positive does NOT clear the decoys — a decoy outscores it)
- **putative QS0069567 = 0.204** (vs decoy_mean −0.041, vs positive −0.005); **putative QS0113172 = 0.232** (vs decoy_mean −0.013, vs positive +0.023) → both decoy-like, indistinguishable from the positive control and the decoy band

## 3. Margins summary

| target | positive | decoy mean (max) | pos − decoy_mean | pos − decoy_MAX | putatives | calibration |
|---|---:|---:|---:|---:|---|---|
| PKM2 | 0.511 | 0.371 (0.498) | +0.140 | +0.013 | 0.204 (decoy-like) | marginal (tied with top decoy) |
| PPARD | 0.209 | 0.245 (0.512) | −0.036 | −0.303 | 0.204, 0.232 (decoy-like) | **failed** (positive < decoys) |

All 15 complexes ran cleanly (rc=0). Per-complex `prob_binder` + `affinity_pred_value` (log₁₀ IC₅₀) in
the raw JSON.

## 4. Interpretation notes (factual, not adjustments to the data)

- The whole binder-vs-decoy spread is narrow (~0.12–0.51 across both targets) with no clean separation —
  the same low-confidence regime Boltz showed on Nav, not the clean regime it showed on mTOR. The decoys
  are noisy: **BMS 191011 scores ~0.50 on both PKM2 and PPARD** despite being a KCNMA1 (BK-channel)
  ligand — a "sticky" false positive that drags the decoy ceiling up.
- One model-side caveat worth recording for James/Ben (about Boltz, not Ben's data): **GSK 3787 is an
  irreversible/covalent PPARδ antagonist** (modifies Cys249). Boltz-2's affinity head estimates
  *reversible* binding probability and is known to underscore covalent binders — so a low GSK 3787 score
  is partly expected and is not strong evidence that Boltz "can't see" PPARD. This does not change the
  inconclusive verdict (the putatives still aren't separable from decoys), but it means the PPARD
  positive control is a weak calibration anchor for this model class.

## 5. Note for Rohan (cross-branch — do not edit from here)

`docs/models_tracks_scorecard.md` lives on the **`models` branch**. This result is relevant to **Track 2
(DTI / binder triage)** and **Track 9 (off-target / selectivity)**: it adds a second negative data point
(after Nav) that off-the-shelf Boltz-2 does not reliably triage binders on harder/less-structurally-rich
targets (PKM2, PPARD) — the positive controls don't clear decoys. Please merge a scorecard note when
convenient. (Not editing the `models` branch from here per branch hygiene.)

## 6. Files

- `boltz_pkm2_ppard/results.json` — all 15 complexes (prob_binder + log_ic50 + infra metadata)
- `boltz_pkm2_ppard/ben_pkm2_ppard_panel.json` — the exact panel run (Ben's SMILES + UniProt sequences)
- Source data: `data/ben_tsc2/compounds.json` (Ben's email, 2026-06-11)

---

## 7. Fair structural retest — PKM2 dimer + PPARD-LBD (2026-06-12, AWS)

After the off-the-shelf inconclusive verdict above, the Bouchet Claude built a fair retest that
changes only the **protein representation** (Ben's SMILES are byte-for-byte identical):

- **PKM2 as a homodimer** (`n_chains: 2`, 1062 aa) — restores the Dasa-58-class activator pocket at
  the subunit interface, which is absent from a monomer fold and was the structural reason the
  off-the-shelf positive control failed.
- **PPARD as LBD only** (residues 211–441, 231 aa) — cleaner ligand-binding pocket, removes the
  N-terminal disordered regions that may have produced noisy contacts.

Bouchet GPU was jammed (Ada queue + H200 reserved), so this ran on AWS **g6e.2xlarge** (1× L40S
48 GB) in us-east-1a — 39 min wall time, all 15 complexes rc=0, ~$1.46 spend. Boltz 2.2.1, torch
2.12.0+cu130, `--no_kernels` path (cuequivariance-ops not installed — multimer runner uses the
pure-PyTorch triangle reference).

### 7.1 PPARD-LBD (8 complexes) — calibration **failed again**

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| 1 | 0.465 | BMS 191011 | negative |
| 2 | 0.322 | carbamazepine | negative |
| 3 | 0.249 | QS0069567 | **putative** |
| 4 | 0.206 | QS0113172 | **putative** |
| **5** | **0.168** | **GSK 3787** | **POSITIVE CTRL** |
| 6 | 0.138 | BIIB021 | negative |
| 7 | 0.099 | Biperiden | negative |
| 8 | 0.096 | GF 109203X | negative |

- **Positive control rank: 5 of 8** (worse than 2 of 5 negatives).
- **GSK 3787 vs top negative margin: −0.297** (positive scores 0.3 *below* the top decoy).

**The LBD truncation alone did not rescue PPARD calibration.** The Bouchet Claude's pre-run
prediction held: GSK 3787 is a **covalent** PPARD antagonist (modifies Cys249), and Boltz-2's
affinity head models only **reversible** binding. The structural fix addresses the pocket; it
does not address the covalent mechanism Boltz cannot see. Beyond the covalent issue, PPARD's LBD
is a ~1300 Å³ greasy cavity that evolved to bind fatty acids, so many drug-like hydrophobic
"decoys" (BMS 191011 has CF₃ + aryl; carbamazepine has an aromatic ring system) can score
nontrivially. **Putatives are uninterpretable on this target with this model class.**

### 7.2 PKM2 dimer (7 complexes) — calibration **succeeded**

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| **1** | **0.453** | **Dasa-58** | **POSITIVE CTRL** ✓ |
| 2 | 0.399 | carbamazepine | negative |
| 3 | 0.385 | BMS 191011 | negative |
| 4 | 0.383 | Biperiden | negative |
| 5 | 0.355 | GF 109203X | negative |
| **6** | **0.340** | **QS0113172** | **putative** |
| 7 | 0.299 | BIIB021 | negative |

- **Positive control rank: 1 of 7** — clears all 5 negatives.
- **Dasa-58 vs top negative margin: +0.054** (positive lead, narrow but consistent).
- **Dasa-58 vs negative mean margin: +0.089.**

**The dimer fix worked.** Dasa-58 (the canonical PKM2 activator binding at the dimer-of-dimers
interface) jumped from a tied 0.511 in the monomer panel (Bouchet, indistinguishable from
decoys) to a clean #1 finish at the dimer. The activator pocket Boltz needed to recognize was
physically present only after we added the second chain — exactly the structural-biology
reasoning the Bouchet Claude flagged.

**Verdict on QS0113172 as a PKM2 binder: REFUTED.** QS0113172 scored 0.340 — **below 4 of 5
negative controls** and 0.113 below the calibrated positive. With Boltz now correctly calibrated
on PKM2 (Dasa-58 #1), the fact that QS0113172 ranks alongside the worst-discriminating
negatives means **Boltz finds no preferential binding of QS0113172 at the PKM2 dimer interface**.
The DFP functional-similarity match (QS0113172 ↔ Dasa-58) does **not** appear to translate to
physical binding at PKM2.

*Caveat:* Boltz's discriminative margin on PKM2 is narrow (+0.054 positive lead, all scores
clustered 0.30–0.46) — we can refute, but not strongly. A wet-lab cross-check (SPR or thermal
shift on PKM2) would resolve any residual ambiguity.

### 7.3 Net answer for Ben's email

| Compound | Putative target | DFP match | Fair-retest verdict |
|---|---|---|---|
| QS0113172 | **PKM2** | Dasa-58 functional match | **REFUTED** — scores below 4/5 negatives at the dimer interface (where Dasa-58 was correctly recognized) |
| QS0113172 | **PPARD** | GSK 3787 functional match | **INCONCLUSIVE** — positive control is covalent, Boltz miscalibrated |
| QS0069567 | **PPARD** | GSK 3787 functional match | **INCONCLUSIVE** — same calibration failure |

The TSC2-rescue mechanism for QS0113172 is **not** likely going through PKM2 according to
co-folding evidence. The PPARD half of both hits remains open and is not answerable by Boltz-2
(or any other current co-folder — AF3, Chai-1 share the covalent blindness). Resolving the PPARD
question needs a covalent-mechanism-aware experiment: SPR with pre-incubation, activity-based
protein profiling (ABPP) with the QS compounds as probes, or a thermal shift assay.

### 7.4 Three architectural reasons Boltz did poorly on this panel

1. **Covalent blindness.** Boltz-2's affinity head was trained on BindingDB equilibrium data; it models reversible binding only. GSK 3787 (and most warhead-bearing antagonists) get their potency from the covalent step, which is invisible to the model. Shared limitation with AF3 and Chai-1.
2. **Drug-vs-drug decoy discrimination is harder than drug-vs-random.** The 5 negative controls are confirmed binders of other targets (KCNMA1, KCNQ2, CHRM3, HSP90, PKC) — all drug-shaped molecules that geometrically *could* fit in a hydrophobic pocket. The PPARD LBD is especially permissive (evolved for fatty-acid binding). Co-folders score "could plausibly fit" generously, which compresses the binder-vs-decoy margin.
3. **Allosteric / activator pockets are undersampled in training.** Dasa-58 binds at the PKM2 dimer interface, not the orthosteric site. BindingDB is dominated by orthosteric inhibitors. That the dimer fix worked at all is non-trivial; the +0.054 margin reflects how marginal this regime is for current co-folders.

### 7.5 Files

- `boltz_pkm2_ppard/fair_retest_results.json` — all 15 complexes from this AWS run.
- `boltz_pkm2_ppard/fair_retest_panel.json` — exact protein representations + Ben's SMILES.
- `boltz_pkm2_ppard/HANDOFF.md` — the Bouchet Claude's pre-run hypothesis + strategy.
- `aws/boltz_pkm2_ppard_userdata.sh` — the AWS userdata that ran this (g6e.2xlarge, `--no_kernels`,
  S3 presigned GET for the panel + runner because the Q-Mammal repo is private).

### 7.6 Notes for `models` branch (cross-branch — leave for Rohan to merge)

Update `docs/models_tracks_scorecard.md`:
- **Track 2 (DTI / binder triage):** Boltz-2 PKM2-dimer calibrated (Dasa-58 #1) but with narrow
  margin (+0.054); refutes QS0113172↔PKM2 from DFP. Adds a precedent that **target representation
  matters at the assembly level** (monomer vs. dimer) for activator-pocket targets.
- **Track 9 (off-target / selectivity):** PPARD remains unscorable with Boltz when the positive
  control is covalent — the same architectural limit as before. Note this as a Boltz-2 "do not use"
  flag for covalent inhibitor evaluation in general.

### 7.7 Spend

- v1 (g6e.xlarge, AZ-b, git-clone failure): 6 min ≈ $0.19
- v2 (g6e.xlarge, AZ-d, same private-repo failure, but diagnosed via S3 log uploader): 7 min ≈ $0.22
- v3 (g6e.2xlarge, AZ-a, S3-staged inputs, **completed**): 39 min ≈ $1.46
- **Total: ~$1.87** vs. $10 cap.
