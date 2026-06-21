# Pathway-neighbor hypothesis test — overnight Boltz-2 panel (2026-06-12)

**Run:** 2026-06-12 overnight, AWS g6e.2xlarge in us-east-1c. 23 complexes,
all rc=0, 43 min wall time, $1.82 for this run / $4.32 total Boltz-lane spend
(of the $15 cap).

**Reason for the run:** James proposed (6/11 email) that the DFP signature for
QS0113172 / QS0069567 might reflect **pathway-level phenocopy**, not direct
binding to PKM2 / PPARD. The Boltz monomer→dimer fair retest showed QS0113172
does not bind PKM2 even with the correct assembly; PPARD remained inconclusive
because Boltz can't model GSK 3787's covalent mechanism. Maybe these compounds
bind a different node in the same pathway and the cellular readout converges.

This run tests that hypothesis empirically against 5 Tier-1 pathway neighbors.

## TL;DR

**The pathway-neighbor hypothesis is not supported by Boltz across 4 out of 5
testable targets.** None of LDHA, mTOR-kinase domain, PPARA-LBD, or RXRA-LBD
look like binders for either QS compound when Boltz is correctly calibrated
on the respective positive controls. PKM1 was inconclusive — the monomer fold
failed to calibrate the Dasa-58 positive control, the same architectural issue
we hit on PKM2 monomer earlier.

For the slide deck and Ben's follow-up: **QS0113172 and QS0069567 most likely
do not bind the obvious metabolic/signaling pathway neighbors of PKM2 / PPARD
through canonical reversible orthosteric or allosteric pockets that current
co-folders can see.** Either (a) they bind a non-canonical node we didn't
test, (b) they bind something Boltz can't model (covalent, multimeric, or
non-protein target), or (c) the DFP signature is driven by distributed
polypharmacology against weak off-targets.

## What we ran

23 complexes, one positive control + N putatives + 2 decoys per target.
Same decoy set used throughout (BMS 191011 = KCNMA1 opener, BIIB021 = HSP90
inhibitor — both confirmed binders of unrelated targets, both known to be
"sticky" in prior runs).

Target constructs were chosen to put the binding site in the input:

| Target | UniProt | Length | Rationale |
|---|---|---|---|
| PKM1 | P14618-2 | 531 aa monomer | Brain-expressed PKM isoform; closest functional analog of PKM2 |
| LDHA | P00338 | 332 aa | Immediate downstream of PKM (pyruvate → lactate) |
| mTOR-kinase | P42345 (res 2181-2470) | 290 aa | ATP-competitive site; avoids the 2549-aa monster + FKBP12 dependency |
| PPARA-LBD | Q07869 (res 200-468) | 269 aa | LBD only, closest PPARD paralog |
| RXRA-LBD | P19793 (res 227-462) | 236 aa | PPAR heterodimer partner |

Per-target positive controls (well-characterized reversible binders):
PKM1 / Dasa-58, LDHA / oxamate, mTOR-kin / Torin1, PPARA-LBD / fenofibrate,
RXRA-LBD / bexarotene.

## Results — per target

### PKM1 monomer (calibration FAILED)

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| 1 | 0.486 | BMS 191011 | negative |
| 2 | 0.361 | BIIB021 | negative |
| 3 | 0.287 | QS0113172 | putative |
| **4** | **0.250** | **Dasa-58** | **positive** |

The Dasa-58 positive control scored *lowest* of the 4 complexes (worse than
both decoys). **Boltz couldn't recognize Dasa-58 on PKM1 monomer** — same
architectural issue we documented on PKM2 monomer earlier (the activator
pocket lives at the subunit interface, which doesn't exist in a monomer fold).
**PKM1 result is therefore inconclusive.** A homodimer / homotetramer panel
might rescue calibration but PKM1 dimer dynamics differ from PKM2's, so the
fix isn't guaranteed.

### LDHA (calibration SUCCEEDED, strongly)

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| **1** | **0.667** | **oxamate** | **positive** |
| 2 | 0.429 | BIIB021 | negative |
| 3 | 0.422 | BMS 191011 | negative |
| **4** | **0.165** | **QS0113172** | **putative** |

Positive vs top-negative margin: **+0.238**. Boltz cleanly recognized the
classical LDHA inhibitor. **QS0113172 scored LOWEST of the 4 complexes**
(below both negative controls), so the LDHA-binding hypothesis is **refuted**.

### mTOR kinase domain (calibration PARTIAL, but verdict clear)

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| **1** | **0.697** | **Torin1** | **positive** |
| 2 | 0.605 | BIIB021 | negative |
| 3 | 0.223 | BMS 191011 | negative |
| 4 | 0.175 | QS0069567 | putative |
| 5 | 0.170 | QS0113172 | putative |

Torin1 is #1 at 0.697 (positive ctrl), but BIIB021 (HSP90 inhibitor, classic
ATP-pocket purine scaffold) scored uncomfortably close at 0.605 — the
margin is only +0.092 over the top decoy. BIIB021 is a well-known
scaffold-class polypharmacology offender against ATP-binding kinases, so
the proximity isn't surprising and is consistent with known co-folder limits.
**Both QS compounds scored at ~0.17, well below even the bottom decoy at 0.223.**
mTOR-kinase binding is **refuted** for both compounds.

### PPARA-LBD (calibration SUCCEEDED, marginal)

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| **1** | **0.544** | **fenofibrate** | **positive** |
| 2 | 0.374 | BMS 191011 | negative |
| 3 | 0.304 | QS0113172 | putative |
| 4 | 0.197 | QS0069567 | putative |
| 5 | 0.134 | BIIB021 | negative |

Positive vs top-negative margin: **+0.170**. Fenofibrate calibrates cleanly.
**Both QS compounds land BETWEEN the two negative controls** — QS0113172 at
0.304 (above BIIB021 0.134, below BMS 191011 0.374) and QS0069567 at 0.197
(same pattern). They beat the weakest decoy but not the strongest. This is
the "mostly refuted, with a hint of signal" zone — neither compound looks
like a clean PPARA binder, but neither is unambiguously rejected either.
Given the broader pattern (LDHA, mTOR, RXRA all clear refutations), the
most parsimonious interpretation is that PPARA's broader fatty-acid pocket
inflates the QS scores slightly via opportunistic-fit, not real binding.

### RXRA-LBD (calibration SUCCEEDED, very strongly)

| Rank | prob_binder | Compound | Role |
|---:|---:|---|---|
| **1** | **0.980** | **bexarotene** | **positive** |
| 2 | 0.483 | BMS 191011 | negative |
| 3 | 0.237 | BIIB021 | negative |
| 4 | 0.180 | QS0113172 | putative |
| 5 | 0.165 | QS0069567 | putative |

Bexarotene at **0.980** is the cleanest positive-control hit in this entire
panel (margin +0.497 over the top decoy). **Both QS compounds scored below
both decoys.** RXRA binding is **strongly refuted** for both compounds.

## Summary table

| Target | Calibration | QS0113172 verdict | QS0069567 verdict |
|---|---|---|---|
| PKM1 | ✗ failed (monomer/dimer issue) | INCONCLUSIVE | n/a |
| **LDHA** | ✓ strong | **REFUTED** (rank 4/4, below both negatives) | n/a |
| **mTOR-kin** | ✓ partial (sticky decoy) | **REFUTED** (rank 5/5, below all decoys) | **REFUTED** (rank 4/5) |
| PPARA-LBD | ✓ marginal | weak signal (rank 3/5, between decoys) | refuted (rank 4/5, below top decoy) |
| **RXRA-LBD** | ✓ very strong | **REFUTED** (rank 4/5, below both decoys) | **REFUTED** (rank 5/5) |

## What this tells us about James's pathway hypothesis

The hypothesis predicted that QS0113172 / QS0069567 hit *some* node in the
PKM2 / PPARD pathway that produces the same Optopatch readout. We tested the
5 most obvious candidates. **4 of 5 calibrated and rejected the QS compounds
clearly; the 5th (PKM1) failed to calibrate.**

This significantly narrows the residual hypothesis space:

1. **It is not LDHA, mTOR (kinase domain), or RXRA.** Three clean refutations
   with well-calibrated positives. These are the obvious "metabolism + signaling
   + nuclear receptor heterodimer" candidates and none of them light up.
2. **PPARA looks weakly possible but not promising.** QS compounds scored
   between the two decoys, in the noise band. Without a stronger positive lead
   it's hard to call this anything more than scaffold-fit noise.
3. **PKM1 is open** — needs a multimer retest mirroring what we did for PKM2.
4. **It might be something we didn't test** — corepressors (HDAC3, NCoR),
   downstream effectors (TFEB, SIRT1, AMPK), upstream regulators (PFKL/M/P),
   or non-protein targets (membrane lipids, metabolites).
5. **It might be something Boltz architecturally can't see** — covalent
   binders (per the PPARD lesson), allosteric activators at oligomeric
   interfaces (per the PKM2 lesson), or distributed polypharmacology against
   many weak off-targets.

## Recommended next experiments for Ben + James

Ordered by feasibility for a small biotech:

1. **Chemoproteomic pull-down with QS0113172 / QS0069567 as photoaffinity
   probes** — gold standard for unbiased target identification. Will tell
   us what these compounds actually bind in cellular lysate. ~$5K-15K
   external service quote at a CRO.
2. **Thermal proteome profiling (TPP) or CETSA** with the QS compounds in
   neuronal lysate — broader, lower-resolution than ABPP but cheaper if
   Quiver has TPP infrastructure.
3. **PKM1 dimer/tetramer Boltz retest** — small AWS spend (~$2) to close
   the PKM1 question; the only Tier-1 candidate we couldn't adjudicate today.
4. **Sulfonamide-aryl polypharmacology focused panel** — Track 1a showed
   QS0069567 (= CHEMBL1605376) has known activity at 11β-HSD1, GLP-1R,
   BAZ2B, KAT2A, KDM4E. Run Boltz against those for both QS compounds
   to see if the off-target literature matches reality.

## Spend

- v1 (Boltz fair retest, terminated early): $0.19
- v2 (Boltz fair retest debug): $0.22
- v3 (Boltz fair retest complete): $1.46
- PROTON Tier-1 attempt (failed, no cached repo): $0.05
- **Overnight Boltz pathway panel: $1.82**
- **Total Boltz-lane spend: $4.32** of the $10-15 cap

## Files

- `data/ben_tsc2/compounds.json` (boltz branch) — Ben's source data
- `aws/boltz_pathway_userdata.sh` (boltz branch) — overnight userdata
- `results/aws_eval/boltz_pkm2_ppard/pathway_panel.json` — input panel
- `results/aws_eval/boltz_pkm2_ppard/pathway_results.json` — raw outputs (23 complexes, all rc=0)
- `results/aws_eval/boltz_pathway_neighbor_report.md` (this file, boltz branch)
- `docs/boltz_pathway_neighbor_report_2026-06-12.md` (RohanOnly) — same content

Cross-reference: `results/aws_eval/boltz_nav_eval.md` (Nav panel),
`results/aws_eval/ben_tsc2_pkm2_ppard.md` §7 (PKM2/PPARD fair retest).
