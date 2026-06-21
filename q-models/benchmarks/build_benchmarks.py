"""Single source of truth for the Quiver model-evaluation benchmark.

Edit LEADERBOARD below when a new model is tested, then run:
    python benchmarks/build_benchmarks.py
to regenerate every per-track README + the master benchmarks/README.md. This keeps the
leaderboards consistent across all 9 tracks. Numbers are the empirical results on Quiver's
own test substrate (CRISPR-N panel, Boltz test-bed, external tox/BBBP panels) — NOT paper
benchmarks. Receipts point at results/*.json / *.md and experiments/*.py.
"""
from __future__ import annotations
import os, json
from datetime import datetime
from pathlib import Path

BENCH = Path(__file__).resolve().parent
UPDATED = "2026-06-13"

# Each track: dir, title, the Quiver question, the metric, status, winner, lesson,
# and a model table: [model, score, license, verdict, receipt]
LEADERBOARD = {
 "01_family_clustering": {
  "title": "Track 1 — Protein family clustering",
  "question": "Given a gene panel (40-gene CRISPR-N; eventually 1,400), which embeddings put same-family genes together?",
  "metric": "Leave-one-out nearest-neighbour same-family recall on the 40-gene CRISPR-N panel. Embeddings are mean-pooled + cosine; **best layer reported** (last-layer mean-pool undersells by ~0.10).",
  "status": "CLOSED on the 40-gene panel (saturated ~0.85-0.875). Open: 1,400-gene panel; function-aware models.",
  "winner": "ESM-2-650M (best-layer 0.875, MIT) ≈ MAMMAL 458M (0.850). Use layer-selected + centered embeddings.",
  "lesson": "**Layer selection, not model scale, is the lever.** 650M ≈ 3B ≈ 15B (~0.85-0.875); the panel is saturated by its design (2 singleton families + functional-not-fold e3/NR groups). ESM-3's function track is the only thing to crack NRs (1.0) — the frontier is function-aware models, not bigger sequence models.",
  "models": [
    ["ESM-2-650M", "0.875", "MIT", "🏆 WINNER — smallest+cheapest+best, layer-selected", "results/esm2_layer_sweep.json"],
    ["ESM-3-open", "0.875", "non-commercial", "ties top; NR=1.0 (function-track win). Research-only.", "results/esm3_layer_sweep.json"],
    ["MAMMAL 458M", "0.850", "Apache-2.0", "ties; incumbent, no embedding edge over ESM-2", "results/mammal_layer_sweep.json"],
    ["ESM-2 3B", "0.850", "MIT", "no scale benefit", "results/esm2_big_layer_sweep.json"],
    ["ESM-2 15B", "0.850", "MIT", "no scale benefit (23x params, 0 gain)", "results/esm2_big_layer_sweep.json"],
    ["Ankh-large", "0.850", "permissive", "ties ceiling, no win", "results/ankh_result.json"],
    ["ESM-C 600M", "0.825", "Cambrian (600M ok)", "not an upgrade; default readout a 0.625 trap", "results/esmc_layer_sweep.json"],
    ["ProstT5", "0.825", "permissive", "GPCR 1.0 specialist (structure-aware), no overall win", "results/prostt5_layer_sweep.json"],
    ["SaProt-650M_AF2", "0.700 (GPCR 1.0)", "MIT", "GPCR specialist (perfect 8/8)", "results/aws_eval/saprot/"],
    ["ESM-C 6B", "0.60 (trap readout)", "non-commercial", "Forge API final-layer only; can't best-layer", "results/esmc6b_forge.json"],
    ["PROTON", "0.487", "—", "KG link-prediction objective ≠ family clustering", "results/aws_eval/proton_results.json"],
    ["PINNACLE", "0.333", "—", "no DRG/sensory contexts in Tabula Sapiens", "results/aws_eval/pinnacle/"],
    ["ProtST-esm1b", "not run", "MIT?", "trust_remote_code tokenizer broke; ESM-3 covered the hypothesis", "—"],
  ],
 },
 "02_dti_binder_triage": {
  "title": "Track 2 — DTI / binder triage on Quiver targets",
  "question": "Given a Quiver target (Nav1.8, mTOR, ...) and a compound, does it bind?",
  "metric": "Binder-vs-decoy AUROC on the Boltz test-bed (Nav1.8 known-binder panel, mTOR-FRB, etc.).",
  "status": "Off-the-shelf eval DONE. Nav1.8 is chance/below-chance for every public DTI model except Boltz-2 (marginal). Quiver-data fine-tune is the only remaining lever.",
  "winner": "Boltz-2 (Nav1.8 AUROC 0.714, mTOR 1.000). [boltz branch owns the structure lane.]",
  "lesson": "**Off-the-shelf DTI is Nav-blind in general, not MAMMAL-specifically.** Every BindingDB-trained model has zero Nav training pairs. Only structure (Boltz-2) clears chance; the real lever is a Quiver-data fine-tune.",
  "models": [
    ["Boltz-2", "Nav1.8 0.714 / mTOR 1.000", "MIT", "🏆 WINNER (co-folded structure+affinity)", "results/aws_eval/boltz_nav_eval.md"],
    ["MAMMAL-DTI (BindingDB+PEER)", "Nav 0.43 / mTOR 0.56", "Apache-2.0", "fails single-target Nav triage", "results/compare_dti_models.md"],
    ["ConPLex", "pan-Nav 0.437 (9 paralogs)", "MIT", "pan-Nav blind; ibuprofen scored top (broken)", "results/compare_conplex_nav_offtarget.md"],
    ["DrugBAN / PerceiverCPI", "not run", "MIT", "ship NO pretrained weights (train-from-scratch) — deferred, would be its own project", "—"],
  ],
 },
 "03_structure_binding": {
  "title": "Track 3 — Structure-based binding (co-folding)",
  "question": "Same as Track 2 but co-folded — works on novel pockets BindingDB doesn't cover.",
  "metric": "Co-fold confidence / affinity on the Boltz test-bed.",
  "status": "Folded into Track 2. [boltz branch owns this lane.]",
  "winner": "Boltz-2 (same as Track 2).",
  "lesson": "Boltz-2's architectural rule: intrasubunit pockets ✓, multimer interfaces ✓ if n_chains supplied, isolated small bromodomains ✗, covalent binders ✗. See boltz branch.",
  "models": [
    ["Boltz-2", "see Track 2", "MIT", "🏆 WINNER (boltz branch)", "results/aws_eval/boltz_nav_eval.md"],
    ["Chai-1", "not run", "non-commercial", "skipped — Boltz covers Track 3; non-commercial; A100 cost", "—"],
    ["AlphaFold3 / RoseTTAFold-AA", "not run", "gated / no affinity head", "AF3 gated; RFAA has no affinity head", "—"],
  ],
 },
 "04_bbbp": {
  "title": "Track 4 — BBBP de-risking",
  "question": "Will a CNS compound actually cross the blood-brain barrier?",
  "metric": "AUROC on an external BBBP panel (held out from BBB_Martins train).",
  "status": "DONE. MolFormer-XL wins; 3D (Uni-Mol2) doesn't help.",
  "winner": "MolFormer-XL (AUROC 0.889). ChemBERTa-2 (0.873) is a close commercial second.",
  "lesson": "2D SMILES transformers win; **3D-conformer awareness (Uni-Mol2) does NOT help BBBP** (0.785). **Operating envelope (2026-06-13, `results/comprehensive_admet_char.md`):** reliable only IN-DOMAIN — BBBP AUROC near-Tanimoto 0.89–0.90 collapses to 0.75–0.79 out-of-domain; **gate predictions on max-Tanimoto-to-train (<0.3 = low-confidence).** Both models have a **yes-bias** (TPR 0.86–0.89 ≫ TNR 0.61–0.72) → trust the yes, keep MAMMAL as the TNR-1.0 trust-the-no backstop. ChemBERTa-2 generalizes across scaffolds better than MolFormer + is better calibrated (Brier 0.12).",
  "models": [
    ["MolFormer-XL", "0.889", "Apache-2.0", "🏆 WINNER", "results/aws_eval/molformer/"],
    ["ChemBERTa-2", "0.873", "MIT", "close commercial 2nd; also does hERG/DILI", "results/chemberta_admet.json"],
    ["MAMMAL BBBP", "0.833", "Apache-2.0", "'trust the no's' specificity backstop (TNR 1.0)", "results/bbbp_characterization.md"],
    ["Uni-Mol2 (3D)", "0.785", "MIT", "3D doesn't help BBBP", "results/unimol2_result.json"],
  ],
 },
 "05_toxicity": {
  "title": "Track 5 — Toxicity / DILI / hERG",
  "question": "Is this compound likely to fail Phase 1 on safety?",
  "metric": "hERG: balanced-acc (TDC hERG_Karim). DILI: TPR/AUROC on the external 30-drug withdrawn-vs-safe panel. ClinTox: external generalization.",
  "status": "DONE — gap filled by a commercial model. ClinTox is dead.",
  "winner": "ChemBERTa-2 (commercial: hERG bal-acc 0.726, DILI ext TPR 0.73) + ADMET-AI (DILI TPR 0.83).",
  "lesson": "**ClinTox is the wrong task — confirmed dead across 4 models** (MAMMAL/MolFormer/ChemBERTa/TxGemma all 0.24-0.47 external despite 0.80-0.96 in-dist). A trained ChemBERTa-2 hERG classifier (0.726) beats the old logP rule (0.65). TxGemma-9B is the ceiling (in-dist 0.95+) but non-commercial. **Operating envelope (2026-06-13, `results/comprehensive_admet_char.md`): hERG is the weakest, least-trustworthy endpoint** — lowest scaffold AUROC, worst calibration (Brier 0.18), worst out-of-domain collapse (ChemBERTa OOD hERG 0.588 ≈ chance). DILI generalizes well (ChemBERTa scaffold 0.879). **Gate ALL tox calls on applicability domain (Tanimoto-to-train); treat OOD/novel-chemotype hERG as soft.**",
  "models": [
    ["ChemBERTa-2 (hERG+DILI)", "hERG 0.726 / DILI ext 0.73", "MIT", "🏆 WINNER (commercial, single model)", "results/chemberta_admet.json"],
    ["ADMET-AI (DILI)", "DILI TPR 0.83", "MIT", "🏆 co-winner for DILI", "results/compare_admet_ai.md"],
    ["TxGemma-9B", "in-dist 0.95+ / DILI ext 0.80", "non-commercial", "research ceiling; NOT shippable", "results/txgemma_results.json"],
    ["hERG rule (logP+basicN+aryl)", "bal-acc 0.65", "—", "weak soft-flag, superseded by ChemBERTa", "results/herg_validate_tdc.json"],
    ["MAMMAL ClinTox", "ext AUROC 0.28", "Apache-2.0", "worse than chance — DEAD", "results/molformer_clintox.json"],
    ["MolFormer-XL ClinTox", "ext AUROC 0.244", "Apache-2.0", "fails external too — ClinTox task doesn't transfer", "results/molformer_clintox.json"],
  ],
 },
 "06_kg_hypothesis": {
  "title": "Track 6 — KG / hypothesis generation",
  "question": "What is connected to this CRISPR-N hit in the literature/KG?",
  "metric": "Bilinear-decoder link-prediction on the full NeuroKG (147,020 nodes / 14.7M edges / 16 node types / 94 relations). Two directions tested: binder-RANKING (recall of a known drug among 8,160 KG drugs) and forward PREDICTION (which drug binds target X).",
  "status": "CLOSED — operating envelope characterized (results/proton_characterization.md).",
  "winner": "PROTON link prediction — but ONLY in the binder-ranking direction (median 4.3% rank percentile; 60/106 top-5%, 80/106 top-10%).",
  "lesson": "STRONGLY ASYMMETRIC. (1) Binder-RANKING works: a known drug lands in the top ~4% for well-studied targets — useful triage. (2) Forward PREDICTION is hub-biased NOISE: 'which drug binds X?' returns the same promiscuous hubs for nearly every target (Bepridil = #1 for 9 unrelated targets incl. all 4 Navs + DRD2 + OPRM1; Obinepitide = #1 for 10 incl. EGFR/BRAF/kinases; Caffeine in 11/22 top-20s), scores saturated ~0.9999 — DO NOT use as a binder/hit generator. (3) Degrades on exactly Quiver's peripheral targets: SCN9A 0.124 / SCN10A 0.254 / MTOR 0.142 vs DRD2 0.026 / EGFR 0.029 / ADRB2 0.046 — popularity bias, not biology. (4) Post-cutoff novel drugs (suzetrigine/VX-548 on Nav1.8) are NOT in the KG at all → zero novel-drug capability. Use it as a literature-recall shortlist on well-studied targets; never as a predictor on novel chemistry. EMET (BenchSci) covers the same use case, wrong-fit at $150-500K/yr — see emet branch.",
  "models": [
    ["PROTON (NeuroKG) — ranking", "median 4.3% binder rank", "MIT + Harvard Dataverse", "🏆 WINNER (hypothesis shortlist, ranking direction only)", "results/proton_characterization.md"],
    ["PROTON (NeuroKG) — forward prediction", "hub-biased (Bepridil/Obinepitide saturate top-20)", "MIT", "❌ NOISE — not a binder generator", "results/proton_characterization.md"],
    ["EMET (BenchSci)", "qualitative", "commercial $150-500K/yr", "real product, wrong-fit cost — see emet branch", "docs/emet_evaluation_2026-06-11.md"],
    ["TxGNN", "not run", "research", "general-disease repurposing SOTA (Nature Med); install drama (old DGL); the one literature-rated alt we skipped", "docs/community_consensus_2026-06-13.md"],
    ["BioPathNet", "not run", "research", "2025 NBFNet path-based KG SOTA — explainable paths vs PROTON's embedding decoder; untested", "docs/community_consensus_2026-06-13.md"],
  ],
 },
 "07_crossmodal_bridge": {
  "title": "Track 7 — Cross-modal Sapphire bridge (V1-T trace → compound)",
  "question": "Given a V1-T functional trace, which compound would produce it?",
  "metric": "Cross-modal retrieval (binders closer than decoys); contrastive alignment.",
  "status": "FALSIFIED off-the-shelf. Build, don't buy.",
  "winner": "Nothing public works — and nothing public CAN (no voltage-trace modality exists by architecture).",
  "lesson": "Phase 6 falsified the 'MAMMAL = shared protein↔ligand latent space' pitch (cross-modal cosine 0.08). **This is the moat.** Build a contrastive head on Quiver's own (V1-T trace ↔ compound) data (prior art: CLOOME / MolPhenix). Tahoe-x1 is the only external model worth a $3 test — blocked on paired V1-T data from Mahdi.",
  "models": [
    ["(all public models)", "cross-modal cosine 0.08", "—", "FALSIFIED — no trace modality by architecture", "results/phase6_crossmodal_alignment.md"],
    ["Tahoe-x1", "not run", "Apache-2.0", "only external candidate; BLOCKED on paired V1-T data (ask Mahdi)", "—"],
    ["scGPT/Geneformer/scFoundation/CellPLM", "DO NOT TEST", "—", "Nature Methods 2025: underperform mean baseline", "—"],
  ],
 },
 "08_generative": {
  "title": "Track 8 — Generative chemistry",
  "question": "Hit-to-lead expansion / novel structure generation.",
  "metric": "Exact-recovery + similarity-expansion quality.",
  "status": "SKIP (not a Quiver bottleneck).",
  "winner": "Morgan fingerprints + Enamine REAL nearest-neighbor (boring, works).",
  "lesson": "MAMMAL public weights are span-infillers, not de-novo (1/8 exact recovery). Morgan FP similarity beats MAMMAL embeddings 0.96 vs 0.72. Quiver's bottleneck is target-ID + triage, not generation — revisit only after Tracks 4-5 ship.",
  "models": [
    ["Morgan FP + Enamine REAL", "0.96 similarity", "—", "🏆 WINNER (use this; skip the track)", "—"],
    ["MAMMAL generation", "1/8 exact recovery", "Apache-2.0", "span-infiller only, not de-novo", "results/phase6_generation.md"],
  ],
 },
 "09_selectivity": {
  "title": "Track 9 — Off-target / paralog selectivity",
  "question": "Does this compound only hit Nav1.8, or also Nav1.5/1.7?",
  "metric": "Paralog-resolved binder ranking (9 SCN paralogs) + off-target sanity.",
  "status": "Folded into Track 2.",
  "winner": "Boltz-2 (ranks suzetrigine Nav1.8 #1, narrow margins).",
  "lesson": "ConPLex pan-Nav blind (0.437, ibuprofen scored highest — wrong). Boltz-2 is target-conditioned (not drug-bias) but margins are narrow. See boltz branch for the paralog completion.",
  "models": [
    ["Boltz-2", "Nav1.8 ranked #1", "MIT", "🏆 WINNER (boltz branch)", "results/aws_eval/boltz_nav_eval.md"],
    ["ConPLex", "pan-Nav 0.437", "MIT", "pan-Nav blind", "results/compare_conplex_nav_offtarget.md"],
  ],
 },
}


def md_table(models):
    out = ["| Model | Score | License | Verdict | Receipt |", "|---|---|---|---|---|"]
    for m, s, lic, v, r in models:
        out.append(f"| {m} | {s} | {lic} | {v} | `{r}` |")
    return "\n".join(out)


def write_track(slug, t):
    d = BENCH / slug
    d.mkdir(parents=True, exist_ok=True)
    body = f"""# {t['title']}

**Status:** {t['status']}
**🏆 Best:** {t['winner']}
_Last updated: {UPDATED}. Generated by `benchmarks/build_benchmarks.py` — edit the data there, not here._

## The Quiver question
{t['question']}

## Metric
{t['metric']}

## Leaderboard (empirical on Quiver substrate, not paper benchmarks)
{md_table(t['models'])}

## Lesson / architectural rule
{t['lesson']}
"""
    (d / "README.md").write_text(body)
    return f"{slug}/README.md ({len(t['models'])} models)"


def write_master():
    lines = [f"""# Quiver model-evaluation benchmark — master leaderboard

_Last updated: {UPDATED}. Single source of truth: `benchmarks/build_benchmarks.py` (run it to regenerate)._

**What this is:** the empirical "best model per Quiver capability track" scorecard, tested on
**our own substrate** (CRISPR-N gene panel, Boltz test-bed Nav/mTOR targets, external tox/BBBP
panels) — not paper benchmarks. *"State-of-the-art on shit is still shit."* The canonical
narrative + Q3 punchlist lives in `docs/models_tracks_scorecard.md`; this folder is the
per-track leaderboard archive.

## Best model per track

| # | Track | 🏆 Best | Status |
|---|---|---|---|"""]
    for slug, t in LEADERBOARD.items():
        n = int(slug.split("_")[0])
        name = t["title"].split("—")[1].strip()
        status1 = t["status"].split(". ")[0].rstrip(".")
        lines.append(f"| {n} | [{name}]({slug}/README.md) | {t['winner']} | {status1} |")
    lines.append(f"""
## Cross-cutting lessons from the campaign
1. **Layer selection > model scale** (Track 1): last-layer mean-pool undersells encoders ~0.10; 650M ≈ 15B.
2. **Off-the-shelf DTI is Nav-blind** (Track 2): only structure (Boltz-2) or a Quiver-data fine-tune works.
3. **ClinTox is dead** (Track 5): the *task* doesn't transfer to real withdrawals — 4 models confirm. Use ChemBERTa-2 hERG/DILI + ADMET-AI.
4. **The cross-modal bridge is the moat** (Track 7): no public model has a trace modality — build on Quiver V1-T data.
5. **Verify the readout before the model**: this project flipped its own conclusions multiple times by fixing I/O (wrong layer, wrong checkpoint, wrong env), not the model.

## Licensing note
Commercial-OK winners: ESM-2-650M (MIT), MolFormer-XL (Apache), ChemBERTa-2 (MIT), ADMET-AI (MIT),
Boltz-2 (MIT), MAMMAL (Apache). **Research-only (not shippable):** ESM-3, ESM-C 6B, TxGemma, Chai-1.

## What's NOT here (other branches)
- Boltz-2 specifics + Nav-paralog/TSC2 completion → `boltz` branch.
- EMET / agentic-research-platform eval → `emet` branch.
- Cross-cutting campaign report → `RohanOnly` branch.
""")
    (BENCH / "README.md").write_text("\n".join(lines))


def main():
    written = [write_track(s, t) for s, t in LEADERBOARD.items()]
    write_master()
    print(f"Generated benchmarks/README.md + {len(written)} track READMEs:")
    for w in written:
        print("  -", w)


if __name__ == "__main__":
    main()
