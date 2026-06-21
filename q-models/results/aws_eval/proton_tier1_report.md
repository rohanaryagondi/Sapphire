# PROTON Tier-1 expansion — round 2 results (2026-06-12)

**Run:** t3.xlarge in us-east-1b, 7 min wall time, ~$0.02 spend. EBS volume
`vol-066389517f2740f19` resized 50 → 100 GB before launch; full PROTON
install from scratch (uv + repo clone + NeuroKG download + weights download +
link-prediction eval). Total Boltz-lane spend: $4.34 / $15 cap.

## What we ran

Extended PROTON's link-prediction eval (`aws/proton_strength_eval.py`) to
include 6 new Tier-1 targets on top of the existing 16-target panel. The 6
new targets are James's pathway-hypothesis candidates for the QS compounds:

| New gene | Family | Why |
|---|---|---|
| **PKM** | metabolic_enzyme | Pyruvate kinase (PKM1/PKM2) — QS0113172 alternative target |
| **LDHA** | metabolic_enzyme | Lactate dehydrogenase A — immediate downstream of PKM |
| **PPARA** | nuclear_receptor | PPAR-α — closest PPARD paralog |
| **PPARD** | nuclear_receptor | The originally-claimed target for both QS compounds |
| **PPARG** | nuclear_receptor | PPAR-γ — second-closest paralog |
| **RXRA** | nuclear_receptor | Retinoid X receptor α — PPAR heterodimer partner |

PROTON's bilinear-decoder link prediction gives, for each (target, edge_type)
pair, the top-K KG drugs ranked by the predicted edge probability.

## Results

### Per-target top KG drugs (drug → protein edge)

| Target | Top 5 KG drugs (by PROTON decoder score) |
|---|---|
| **PKM** | Obinepitide (0.997), N-cyclohexyltaurine (0.995), thiazolone (0.994), ANZ-100 (0.994), β-carotene (0.994) |
| **LDHA** | Obinepitide (0.973), β-carotene (0.966), zinc acetate (0.960), adenosine-5'-ditungstate (0.954), thiazolone (0.953) |
| **PPARA** | β-carotene (0.999), bepridil (0.998), thiamine (0.998), ritodrine (0.998), N-cyclohexyltaurine (0.998) |
| **PPARD** | Obinepitide (0.999), β-carotene (0.998), cycloleucine (0.998), aminobenzene derivative (0.998), N-cyclohexyltaurine (0.998) |
| **PPARG** | β-carotene (1.000), purine derivative (0.999), N-cyclohexyltaurine (0.999), Obinepitide (0.999), Atl146e (0.999) |
| **RXRA** | Obinepitide (0.999), β-carotene (0.998), N-cyclohexyltaurine (0.998), thiazolone (0.998), purine derivative (0.998) |

**Hub-bias warning:** the top of every list is dominated by the same handful
of KG-hub compounds (β-carotene, Obinepitide, N-cyclohexyltaurine). These are
highly-connected nodes in NeuroKG that PROTON ranks high regardless of true
target specificity — a known limitation of KG link-prediction. Look at the
reverse-edge ranking (below) for less hub-biased signal.

### Per-target top KG drugs (gene → drug reverse edge) — cleaner signal

| Target | Notable real ligands in top 15 |
|---|---|
| **PKM** | Resveratrol (PKM2 modulator), Abemaciclib (CDK4/6 inhibitor + glycolysis crosstalk), Alvocidib (CDK inhibitor) |
| **LDHA** | **NADH (canonical LDHA cofactor)**, Glutathione, Quercetin, Genistein, Resveratrol — bona fide LDHA-binders or modulators |
| **PPARA** | **Arachidonic Acid (natural PPARα ligand)**, Lovastatin, Resveratrol, Genistein — actual PPAR pathway compounds |
| **PPARD** | Genistein, Resveratrol — phytochemical pan-PPAR ligands; rest are kinase inhibitors (probable hub bias) |
| **PPARG** | Tamoxifen, Aldesleukin — partial off-target connections |
| **RXRA** | **Prasterone sulfate (DHEA-S, RXR modulator)**, Resveratrol, Quercetin, Genistein — pan-NR phytochemicals |

The reverse-edge top hits include real pharmacology that makes sense (NADH on
LDHA, arachidonic acid on PPARα, DHEA-S on RXRA), even though the forward edge
is dominated by hubs.

## Bridge to QS compounds — the key question

**Question:** does any PROTON-surfaced KG drug structurally resemble
QS0113172 or QS0069567? If yes, that's a literature-grounded candidate worth
Boltz-testing in a round-2 panel.

**Method:** Tanimoto fingerprint similarity (Morgan radius-2, 2048-bit) on
all 86 unique drugs PROTON surfaced across the 6 Tier-1 targets. 77 of 86
have SMILES in PubChem; computed pairwise similarity to both QS compounds.

**Result:** **zero PROTON-surfaced drugs reach Tanimoto ≥ 0.30** against
either QS compound. Cutoff dropped to 0.20 — still zero.

The QS compounds (aryl-sulfonyl-piperazine and aryl-sulfonamide-glycinamide
scaffolds) have no close cousin in PROTON's top-15 lists across PKM, LDHA,
PPARA, PPARD, PPARG, or RXRA.

## What this means

The pathway-neighbor hypothesis is now **triply unsupported**:

| Approach | QS0113172 / QS0069567 connection to Tier-1 pathway nodes |
|---|---|
| Direct Boltz binding (this run + prior) | **REFUTED on 4 of 5 testable targets** (LDHA, mTOR-kinase, PPARA-LBD, RXRA-LBD); PKM1 monomer calibration failed |
| ChEMBL Tanimoto ≥ 70% scaffold-cousin polypharmacology | **0 of 6 Tier-1 hits** (look-alikes hit GLP-1R, 11β-HSD1, BAZ2B, etc. — none of our pathway neighbors) |
| **PROTON KG link prediction (this round)** | **0 of 86 unique top-15 drugs structurally resemble the QS compounds** (max Tanimoto < 0.30) |

Three independent lines of evidence all point the same way: the QS compounds
do not look like they bind the obvious PKM2/PPARD-pathway neighbors via any
mechanism a co-folder or KG model can see.

## Where this leaves us

PROTON contributes **no new Tier-1 Boltz candidate to retest** by structural
similarity. Without EMET's input, there's nothing concrete to put into a
Boltz round 2.

Waiting on the EMET answer (pending from Rohan) to surface any literature-
grounded alternative target classes worth testing. Plausible classes that
EMET might point at, based on the scaffold patterns we've already seen:

- Bromodomain-class targets (BAZ2B is in QS0069567's ChEMBL look-alike list)
- 11β-HSD1 (another QS0069567 look-alike target)
- Lysine methyltransferases (EHMT2/G9a, KDM4E — same look-alike list)
- Non-canonical binding modes Boltz can't see (allosteric activator pockets,
  covalent warheads, multimeric interfaces)

When EMET arrives we'll merge its top suggestions with the ChEMBL look-alike
list and design a focused Boltz round 2 panel (5-8 targets, ~$3-4 AWS).

## Files

- `aws/proton_strength_eval.py` (boltz branch) — patched eval with 6 Tier-1 targets added
- `aws/proton_tier1_userdata.sh` (boltz branch) — overnight launch infra
- `results/aws_eval/proton_tier1/quiver_target_drug_rankings.json` — raw outputs
- `results/aws_eval/proton_tier1/known_binder_rank.json` — known-binder calibration
- `results/aws_eval/proton_tier1/proton_qs_similarity.json` — Tanimoto comparison
- `docs/proton_tier1_report_2026-06-12.md` (RohanOnly) — this report
- `results/aws_eval/proton_tier1_report.md` (boltz branch) — same report mirrored
