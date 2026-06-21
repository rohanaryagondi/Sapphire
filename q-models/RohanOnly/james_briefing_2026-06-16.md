# Talking to James about the Models work — briefing (2026-06-16)

*Private prep for Rohan. Not a deliverable. The polished external version is
`docs/models_tracks_scorecard.md` (the "Quiver Model Capability Report"). This is your cheat-sheet:
the story, the numbers, the honest caveats, and the answers to the questions James will ask.*

---

## The 30-second version (lead with this)

> "You asked us to build out the table of tracks and find the best model for each Quiver
> capability. We did — it's now a **living, tested scorecard across 9 capabilities**, and for the
> three capabilities where it actually helps, the best models are **running live in a tool** you
> can use today. The headline finding: **off-the-shelf models get you to ~0.9 on targets that
> already have public data, and to chance on the targets we actually care about** (Nav1.8, the
> epilepsy channels, target deconvolution). The lever that closes that gap is a per-target
> fine-tune — and the data that feeds it is the moat. Public data takes us most of the way;
> **Quiver's own screening data is the only thing that finishes the job.**"

## What you asked for → what we delivered

- **Then:** a table idea — "what's the best model for each capability?"
- **Now:**
  1. A **9-track scorecard** with the best model per track, the empirical verdict, and the receipts (`docs/models_tracks_scorecard.md`).
  2. A **live Explorer** (web app) where you pick a capability, paste compounds (or drag a CSV), and get real predictions with a trust verdict next to each — for the 3 tracks where a model genuinely works.
  3. **Two fine-tunes actually run** (not just proposed), which is what turned the scorecard from "model shopping" into a strategy.

## The scorecard, one line each (know these cold)

| # | Capability | Best model | Where it stands |
|---|---|---|---|
| 1 | Protein family clustering | ESM-2-650M (0.875) | Solved for sequence families; SaProt/ProTrek crack the hard "function-defined" families (E3 ligases, nuclear receptors) |
| 2 | **DTI / binder triage** | **Per-target fine-tunes (LIVE)** | **0.95–0.997 where data exists** vs 0.50 zero-shot on ion channels — *the* result |
| 3 | Structure-based binding | Boltz-2 | Co-folding; the confirm step for novel chemistry |
| 4 | BBB penetrance | MapLight (LIVE, 0.90) | Solid, deployed live |
| 5 | Toxicity (hERG/DILI) | MapLight-class (LIVE, 0.88/0.93) | Solid, deployed live; ClinTox dropped (worse than chance) |
| 6 | KG / hypothesis gen | PROTON + ULTRA | Ranks known drugs well (4.3% median); ULTRA fixes hub bias |
| 7 | Generative chemistry | Morgan FP + Enamine REAL | Commodity — skip building here |
| 8 | Off-target / selectivity | Boltz-2 | Right *direction*, margins too narrow to call ratios |
| 9 | Variant effect (GoF/LoF) | funNCion (0.90) | Best public tool — but **doesn't transfer to Nav1.8** (see below) |

## What's genuinely new this push (the "we didn't just shop, we built" part)

1. **Per-target binder fine-tunes — live.** We trained one model per data-rich CNS target on public
   data and **wired them into the Explorer** (CPU, no cloud): **18 targets, 0.95–0.997 scaffold-split**
   (Nav1.7 0.995, Nav1.8 0.987, DRD2 0.995, PKM2/PPARD ~0.99). Off-the-shelf zero-shot on these ion
   channels is **0.50 — chance.** That 0.50 → 0.98 jump is the whole argument for fine-tuning.
2. **We rescued the data-poor epilepsy channels** (KCNQ2/Kv7.2, Cav3.2) using big **non-ChEMBL PubChem
   screens** — 0.79–0.81. Weaker (noisier HTS data) but deployable. *Every* CNS target that can be
   fine-tuned from public data now is.
3. **De-risking, live too**: BBBP 0.90, hERG 0.88, DILI 0.93 — matching/beating the published MapLight.
4. **The negatives that matter** (these are insights, not failures):
   - The **variant** fine-tune **does not transfer** across genes or to Nav1.8 (≈ chance). We even drove
     the SOTA portal model (MissION) on Nav1.8 ourselves — **0.77, and it never confidently calls a
     loss-of-function.** So *no public model* reliably calls Nav1.8 GoF/LoF.
   - **Target deconvolution** (your TSC2 → PKM2/PPARD question): ligand-only models — even a supervised
     one that's 0.99 on ChEMBL — **fail on the actual screen hits** because they're novel chemotypes
     out of the training distribution. Deconvolution needs structure (Boltz-2) or Quiver's functional
     signatures. *(Aside for Ben/Amy: the "Dasa-58" reference SMILES in the TSC2 hit file is wrong — it's
     a nucleotide, not the PKM2 activator. Worth a quick fix.)*

## The strategic story (this is the point — say it plainly)

- **"State of the art on shit is still shit."** Public models are strong on targets that already have
  thousands of public ligands, and at chance on the ones with none — which are exactly Quiver's
  differentiated targets.
- **The fine-tune is the lever; the data is the moat.** 0.50 → 0.98 comes entirely from per-target
  data. Where Quiver has data, we win immediately. Where it doesn't (Nav1.1/Dravet, Nav1.6), **no
  public source can substitute** — that's where Quiver's screening + electrophysiology is irreplaceable.
- **Build vs. buy is now answered per-capability** (`docs/cns_finetune_readiness.md`): buy/commodity for
  family-clustering, BBBP, tox, generative; fine-tune (we did) for the data-rich binders; **build with
  Quiver data** for the data-poor channels and for variant-effect on Nav1.8.

## Be honest about this (protects your credibility, and it's the ask)

**Everything is validated on PUBLIC scaffold-splits — not yet on Quiver's own measured binders.** The one
time a model met real Quiver experimental hits (the TSC2 deconvolution), it **failed** (novel chemotypes,
out-of-domain). So the 0.95–0.99 numbers are "generalizes to new public chemistry," not "validated on our
compounds." **The single highest-value next step is a Quiver held-out panel** — SMILES + measured activity
on a live target — so we can report true Quiver-substrate performance. Lead with this honesty; it makes the
ask land.

## Questions James will probably ask — crisp answers

- **"Is MAMMAL worth it?"** → Commodity enrichment, not core infrastructure. It ties ESM-2 on clustering and
  is at chance on our binder tasks off-the-shelf. The value isn't the model; it's per-target fine-tuning on
  *our* data — and a fingerprint+GBT does that just as well on CPU.
- **"So which model do we standardize on?"** → There isn't one — it's per-capability (the scorecard). For
  binders: per-target fine-tunes + Boltz-2 to confirm. For de-risking: MapLight. For clustering: ESM-2.
- **"Can we trust these numbers?"** → On public chemistry, yes (scaffold-split, honest). On *our* compounds,
  unproven until we run a Quiver panel — which is the ask.
- **"What does it cost?"** → The live fine-tunes are CPU/$0. The whole model-search campaign was <\$15 of AWS.
  Fine-tuning a new target is ~minutes/$0 locally.
- **"What do you need from us?"** → (1) a Quiver held-out validation panel; (2) screening data on the
  data-poor channels (Nav1.1, Nav1.6); (3) green-light to point this at the next live program.

## The demo move (if you have a laptop in the room)

Open the Explorer (http://localhost:8000), go to **DTI**, score a known DRD2 drug → ~1.0 "likely binder,
high confidence"; then score suzetrigine on Nav1.8 → low + "novel chemotype, out-of-domain" — and explain
that the honest confidence flag *is* the product. Then the **Launch Hub**: drop a CSV of 10 compounds across
tracks, hit Run all, show the Results page. One minute, lands the whole story.

## Receipts to have open (if he wants depth)

- `docs/models_tracks_scorecard.md` — the report.
- `results/cns_pertarget_finetune_characterization.md` — the 0.98 binder result + the honest limits.
- `results/variant_finetune_characterization.md` + `results/mission_playwright_nav18.md` — the Nav1.8 GoF/LoF "no public model works."
- `results/tsc2_deconv_supervised_characterization.md` — deconvolution fails OOD + the Dasa-58 SMILES flag.
- `docs/cns_finetune_readiness.md` — build-vs-buy per target.
