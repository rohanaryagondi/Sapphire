# MAMMAL for Quiver — Findings synthesis

> **⚠️ NEWER WORK EXISTS.** This doc covers Phases 0–5. Since then:
> **`COMPLETE_UNDERSTANDING.md` (the master synthesis)** added Phase 6 — cross-modal alignment is a clean
> **NO** (the Sapphire shared-latent-space pitch is falsified off-the-shelf), generation is span-infill
> only, ESM-2 650M does NOT beat MAMMAL, and PGK2 (not WDR91) is the real per-target existence proof.
> And **[`../results/aws_finetune_pilot.md`](../results/aws_finetune_pilot.md)** ran the first in-house
> fine-tune on AWS (~$0.80; pipeline works; fine-tuning only beats IBM on Quiver-specific targets).
> **Read COMPLETE_UNDERSTANDING.md first.** The Phase 0–5 synthesis below is still correct, just narrower.

**As of 2026-05-29 (Phases 0–5 done; Phase 3 fine-tuning confirmed, Phase 4 real-data head audit + Phase 5 extended-evaluation/strategic-recs added).**
This is the authoritative "what we know" doc. Per-experiment detail + raw numbers live in
[`../results/`](../results/); this synthesizes and points there. Setup/run/gotchas: [`../CLAUDE.md`](../CLAUDE.md).

---

## TL;DR — is MAMMAL useful for Quiver?

**Narrowly, off-the-shelf — yes for de-risking and representation; no for the hard cross-modal jobs.
Per-target fine-tuning CAN learn genuine target-specific signal — the PGK2 head tells its hits from
the PGK1 homolog's real ligands at AUROC 0.97 — so the existence proof holds. But on real-data tests
the heads mostly *re-recognize their own trained chemotype* (no graded ranking; weak on novel/out-of-
distribution compounds), and quality is uneven (the WDR91 head barely fires). Q14 (fine-tune per
target) leans YES for chemotype-triage, NOT as a novel-hit or potency predictor.**

| Capability | Off-the-shelf verdict | Evidence |
|---|---|---|
| **BBB-penetrance de-risking** (BBBP) | ⚠️ **Use as a soft positive signal, NOT a rule-out gate.** AUROC 0.968 held-out (TPR 0.98 / **TNR 0.70**), but literature test shows a **false-positive bias** — misses small peripherally-restricted drugs (cetirizine, atenolol, domperidone → "penetrant"); outputs are **hard 0/1, uncalibrated** (95% saturated). Robust to SMILES re-ordering, but standardize protonation/salt first | `phase4_bbbp_literature.md`, `phase4_finetuned_report_card.md` |
| **Toxicity gating** (ClinTox-tox) | ❌ **Not usable as a tox filter.** AUROC 1.0 is memorization of its ~112 training toxics: **0% sensitivity to external clinically-toxic drugs** (misses cerivastatin, troglitazone, terfenadine, thalidomide…); hard 0/1; encoding-fragile (1/6 flips). Earlier "over-predicts" was an input-SMILES-form artifact | `phase4_finetuned_report_card.md` |
| **Protein/gene embeddings** (clustering, KG) | ✅ **Usable** — recovers functional family (NN 0.92); benchmark vs ESM before committing | `phase2_quiver_utility.md` |
| **Protein solubility** (DeepSol) | ✅ functional — acc 0.734 / AUROC 0.829 on DeepSol test; ~at (slightly below) the dedicated baseline (~0.77) | `benchmark_verification.md` |
| **Fast workflow harness** (expand→de-risk) | ✅ ~0.16 s/compound; 150-candidate funnel < 1 min | `phase2_quiver_utility.md` |
| **DTI single-target triage** (does drug X bind target Y?) | ❌ **No** — no binder-vs-decoy separation on Nav1.8/mTOR; not a truncation artifact | `phase1_calibration.md`, `phase2b_quiver_targets.md` |
| **Compound similarity / hit expansion** | ❌ Use Morgan fingerprints — they beat MAMMAL embeddings (0.96 vs 0.72) | `phase2a_expansion_check.md` |
| **Per-target binder scoring (fine-tuned)** | ⚠️ **Works, but head-dependent & not for novel discovery.** Real-data (no-decoy) tests: **PGK2 head** separates its hits from the PGK1 *homolog's* real ligands at AUROC 0.97 — but that's in-distribution recall (sharp on its trained chemotype, no graded ranking, unproven on novel scaffolds). **WDR91 head** is weak/non-specific (PGK2 molecules outscore its own actives, AUROC 0.18; barely fires). Coarse chemotype re-recognition, not potency or novel-hit finding | `phase3_wdr91_finetune.md` |

**One-line strategic read:** MAMMAL's usefulness tracks *task difficulty*, not its SOTA badge. It's an
accurate de-risking filter and a sensible representation model; it is not a binding oracle. Off-the-shelf
it's **commodity enrichment** (the meeting's framing). Whether it becomes more depends entirely on the
fine-tuning question below. The moat stays V1-T + functional trace data.

---

## What we established, with the receipts

### 1. The published benchmarks are honest (but honest ≠ useful)
We independently reproduced every paper claim that has a public checkpoint (4 of 11 tasks):
DTI NRMSE ~0.88 (paper 0.906), BBBP 0.968 (0.957), TCR-epitope 0.931 (0.879), ClinTox ~1.0 (0.986).
The other 7 tasks ship no public checkpoint and can't be verified off-the-shelf. → `benchmark_verification.md`.
**Key nuance:** the DTI "SOTA" (NRMSE 0.906) is only ~9% better than predicting the mean affinity
(R²≈0.18, Pearson ~0.5–0.65 *on its own benchmark*). SOTA here = "least bad at a hard task."

### 2. DTI does not work for single-target candidate triage on our targets
- Named test **suzetrigine (Jernabix/Journavx/VX-548) → Nav1.8 FAILS**: scores below random small molecules.
- 10 known pairs: Spearman **0.43 with the PEER checkpoint** (and −0.03 with the wrong cold-split one —
  checkpoint choice matters; use `dti_bindingdb_pkd_peer`, norms 6.286/1.542). Good for *coarse ranking
  across diverse pairs*, useless for *"is this a binder of target Y"*.
- Nav1.8 & mTOR binder-vs-decoy separation ≈ 0. **Truncation tested and ruled out** as the cause
  (feeding the binding-domain window didn't help). The model just lacks the resolution. → `phase2b_quiver_targets.md`.

### 3. De-risking value is real but NARROWER than the benchmark implies
BBBP scores SOTA on ranking (0.968) but a literature test (`phase4_bbbp_literature.md`) revises the
"deployable as-is" read: it's reliable in the **positive** direction (11/11 clearly CNS-active drugs
correct; large molecules like sirolimus/vancomycin correctly excluded) but has a **false-positive
bias** in the **de-risk (rule-OUT)** direction — it passes small peripherally-restricted/efflux drugs
(cetirizine, atenolol, domperidone) as "penetrant." Outputs are **hard 0/1, uncalibrated** (95%
saturated); robust to SMILES re-ordering but sensitive to protonation/salt form. Use as a soft
positive signal, not a rule-out gate; don't threshold/rank by the score; standardize inputs.
**ClinTox-tox is worse, and the earlier "over-predicts" call was an artifact:** with neutral SMILES +
the validated readout it does NOT over-predict (0% false-alarm on non-toxic) — instead its AUROC 1.0
is **memorization of ~112 training toxics with 0% sensitivity to external clinically-toxic drugs**
(misses cerivastatin, troglitazone, terfenadine, thalidomide). The phase2b "P(toxic)=1.0 on CNS drugs"
came from feeding raw isomeric/charged SMILES; carbamazepine still mis-flags toxic even on clean SMILES.
Recalibration won't fix a no-generalization head — **don't use ClinTox as a tox gate.**
**Meta-pattern:** every classification head ranks well on its dataset yet fails per-compound out-of-
distribution (over-pass, under-detect, or flip); benchmark AUROC ≠ deployable filter. → `phase4_finetuned_report_card.md`.

### 4. Representation is sensible for proteins, weak for small molecules
Protein embeddings recover family structure (NN 0.92) — promising for CRISPR-N gene clustering and the
Sapphire KG. Compound embeddings carry class signal (0.72) but lose to Morgan fingerprints (0.96).

### 5. Phase 5 — real-data SPR, ESM-2 comparison, tox alternatives, CRISPR panel (`../results/phase5_summary.md`)
Four tests past the Phase 4 audit, plus a tiered (Tier 1 ready-now / Tier 2 next-sprint / Tier 3 longer-term)
deployment plan. These **sharpen, but do not overturn**, the verdicts above:
- **WDR91 head on real SPR data (Ahmad 2023, n=239):** on 38 confirmed SPR binders vs 201 confirmed non-binders
  the head scores **AUROC 0.816** (top-5% enrichment 4.57×) — *higher* than the 0.63 it got on synthetic decoys,
  because confirmed SPR zeros are cleaner negatives than random drug-like ones. Take **0.816 as the canonical**
  binary-separation number; graded potency ranking still fails (Spearman ≈ 0). A binary classifier, not a
  potency predictor.
- **MAMMAL vs ESM-2:** MAMMAL beats **ESM-2 8M** on NN recall (0.920 vs 0.880) and family-separation gap
  (0.463 vs 0.093) over 25 proteins × 5 families — but that's the 8M variant; **benchmark vs ESM-2 650M/3B
  before committing** embeddings to Sapphire at scale (addresses open-question #3, against a weak bar only).
- **Tox-gate alternatives:** reconfirms ClinTox is unusable (0% external-toxic sensitivity) and that no single
  structural filter catches the 5+ tox mechanisms → proposes a **mechanism-specific funnel** (PAINS/BRENK →
  hERG/QTc rule → pkCSM DILI → BBBP); the hERG/QTc rule (basic N + logP>1.5 + 2 aryl rings) hit TPR=1.0/TNR=1.0
  on a small QTc set.
- **CRISPR-N 40-gene panel:** structurally homogeneous families (GPCRs/kinases/ion channels) cluster at ~100%
  NN recall while structurally heterogeneous functional groups (E3 ligases) don't → MAMMAL is **ready for the
  real 1400-gene CRISPR-N panel** on homogeneous families, with manual interpretation for the rest.

Full per-test detail + the Tier 1/2/3 deployment recommendations: [`../results/phase5_summary.md`](../results/phase5_summary.md).

---

## Mapping to the meeting's use cases

| Meeting use case | Verdict |
|---|---|
| 1. Prediction enrichment / re-ranking | Partial — DTI re-rank is weak; **BBBP/ADMET enrichment is the usable form** |
| 2. Gene-target → small-molecule (Atlas) | ❌ off-the-shelf (DTI triage fails) → **needs per-target fine-tuning** |
| 3. Hit-list expansion + de-risk | ✅ workflow runs (Morgan expand + **BBBP** de-risk); ClinTox needs calibration |
| 4. CRISPR-N 1400-gene interrogation | 🔬 protein embeddings cluster genes by family (NN 0.92) — plausible; not yet applied to the real panel |
| 5. TSC top-20 → rescue ranking (mTOR) | ❌ off-the-shelf (rapamycin/everolimus don't rank above decoys vs mTOR) |
| 6. Antibody / ASO design | untested (no public antibody-design checkpoint) |

---

## The central question: general vs fine-tuned (ANSWERED — fine-tuning works, modestly)

Everything above is **off-the-shelf**. The decisive unknown for Quiver was whether **fine-tuning MAMMAL
on a target's own screening data** turns the failing capability (single-target binder triage) into a
useful one. IBM's published `wdr91_asms` / `pgk2_del_cdd` heads are the existence proof — and Phase 3
confirms it **holds**: they are **generative binder classifiers** (prompt with a per-target task token
like `<WDR91_ASMS>`, read P(`<1>`) at the class position — the molnet readout, validated on BBBP=0.996;
NOT the scalar head, which is untrained/vestigial in these classification models). `wdr91_asms` ranks
known WDR91 binders above drug-like decoys with **top-5% enrichment 5.25× (AUROC 0.63)** — modest, but
real, and exactly the triage capability off-the-shelf DTI lacked (Nav1.8/mTOR ≈ 0.5). → `phase3_wdr91_finetune.md`.

(Cautionary note: our first pass used the scalar-head readout → AUROC 0.43 → wrongly looked "broken."
The tokenizer's per-target task tokens + a weight signature matching the working molnet heads revealed it's
a generative classifier. Classic false-negative-from-wrong-I/O; the BBBP validation pinned the right readout.)

So per-target fine-tuning is a **viable path** to target→binder triage. It's a *triage/enrichment* tool
(weak global AUROC, strong inactive prior, no affinity ranking), not a precision oracle. For Quiver:
worth piloting an in-house fine-tune (binary hit/non-hit classification on screening/DEL/ASMS data,
SMILES+label) on a target where we have screening data; evaluate with enrichment factor, not just AUROC.

---

## Environment essentials (full detail in CLAUDE.md)
- Conda env `mammal` (Py 3.11): `/opt/anaconda3/envs/mammal/bin/python`. Deps: `biomed-multi-alignment`, `PyTDC`.
- **`USE_TF=0`** required (transformers deadlocks importing TensorFlow on macOS). Set in `mammal_quiver/__init__.py` + scripts.
- DTI head truncates target protein to 1250 aa, drug SMILES to 256 tokens.
- Weights are local under `models/` (HF downloader resume is broken on this network — fetch big files via `curl -C - --retry`).
- Package `mammal_quiver/` (dti, embed, sequences); runnable `experiments/phase*.py`; outputs `results/`.

## Open questions / next steps
1. **Per-target fine-tuning works (modestly)** — `wdr91_asms` enriches binders 5.25× at top-5% via its
   generative readout. Next: pilot an in-house fine-tune on a Quiver target with screening data (binary
   hit classification, SMILES+label, `mammal/examples/`), evaluate by enrichment factor. → `phase3_wdr91_finetune.md`.
2. **Don't use ClinTox as a tox gate** — Phase 4 showed it's memorization with 0% external-toxic sensitivity (not a calibration problem). Need a different tox model for the funnel's tox step.
3. **Benchmark protein embeddings vs ESM-2** before Sapphire commits to MAMMAL embeddings.
4. **Apply protein-embedding clustering to the real CRISPR-N 1400-gene panel** (use case 4).
5. The 6 unverifiable benchmark tasks remain unverifiable without retraining — note, don't chase.
