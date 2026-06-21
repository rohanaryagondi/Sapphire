# MAMMAL — Follow-up decision doc: fine-tuning + specialist strategy

**Written 2026-06-01 for Rohan (and his boss for Q3). The decision doc that answers all three
follow-up questions.** Bar: empirical, decision-relevant, honest about uncertainty; Q3 numbers must be
defensible to a non-ML exec.

This synthesizes five lane outputs and reconciles them where they differ:
`docs/analysis/q1_why_underperforms.md`, `q2_specialists_vs_cohesive.md`,
`q3a_finetune_recipe_footprint.md`, `q3b_aws_g4dn_cost.md`, and the empirical
`results/phase7_finetune_probe.md`. It builds on the established evaluation
(`docs/COMPLETE_UNDERSTANDING.md`, `HANDOFF.md`, `docs/FINDINGS.md`) — it does **not** re-derive it.

> **Confidence tags:** **[HIGH]** reproduced/convergent · **[MED]** real but small-n/single-source ·
> **[PAPER]** author-reported, not independently verified by us · **[SPEC]** inference. AWS/tool facts
> dated 2026-06-01.

---

## EXECUTIVE SUMMARY (read this; everything else is receipts)

1. **Q1 — Is MAMMAL underperforming because we didn't use the fine-tuned version? Mostly no.** For all
   7 capabilities with public checkpoints we *used IBM's fine-tuned weights* and reproduced the paper
   (BBBP 0.968, DTI ~0.88, TCR 0.93, ClinTox ~1.0, solubility 0.73/0.83, PGK2 0.97). The weights are
   right; the let-down is two things no head fixes — **benchmark scores don't survive real-world
   deployment** (out-of-distribution per-compound), and the **base model is weak at exactly what we
   want** (cross-modal binding, similarity, generation). Fine-tuning closes **one** gap only:
   in-distribution per-target binder triage.
2. **Q2 — Specialists or one cohesive MAMMAL? Specialists, and it isn't close.** Our Phase 6 test
   falsified the only thing that made "one cohesive model" special — a shared protein↔molecule latent
   space (cosine 0.08, readouts anti-correlated −0.90). So the cohesion is just *one convenient
   interface*, replicable in ~200 lines of router code. **Adopt ConPLex (binder triage), Boltz-2
   (structure + affinity), ADMET-AI (tox/PK de-risking); keep MAMMAL only for protein/gene embeddings +
   BBBP-as-positive-signal + an optional in-house per-target fine-tune.**
3. **Q3 — Fine-tune NOW on public data? Yes — as a cheap de-risking dry-run, not for the public result
   itself.** It fits a 16 GB T4 comfortably (full fine-tune, 458M, ~7.3 GB model state). The small
   g4dn.xlarge pilot is **~$0.69 on-demand (~$0.31 spot) and ~1.3 hours** for a per-target binder head
   (~2k examples × 10 epochs) — empirically corroborated by our local probe to within 8%. BBBP is
   ~$1 / ~1.9 h. **The dollar figure is lunch money; the only real question was ever scientific value,
   not cost.**
4. **The upside verdict (the user said they'll only do it if the upside is real):** **DO IT — but for
   the pipeline, not the public numbers.** The public-data fine-tune has near-zero standalone value (the
   public targets are commodity), yet it is the cheap, low-risk *validation of the per-target fine-tune
   pipeline* — the single path to a defensible Quiver-specific capability (PGK2 0.973 is the existence
   proof). Spend **~$2–5 (3 seeds, on-demand) to de-risk the pipeline end-to-end on public data BEFORE
   touching Quiver screening/DEL data.** Condition: only proceed to the Quiver-data fine-tune if it
   clears **enrichment factor / BEDROC on a held-out *scaffold* split** (random splits make 0.97/11×
   look better than they are).
5. **One-line bottom line:** the weights were right and MAMMAL is still commodity enrichment; buy the
   specialists for the hard jobs, keep MAMMAL for the two it's good at, and run a ~$5 public-data
   fine-tune as a dry-run for the one in-house capability worth building — then gate the Quiver-data
   spend on a scaffold-split enrichment result.

---

## Q1 — Why MAMMAL underperforms despite SOTA on 9/11 benchmarks

### The boss's question, answered up top
> *"Is MAMMAL doing poorly because we are not using the fine-tuned version?"*

**Mostly no.** For all 7 capabilities where IBM ships fine-tuned weights, we loaded *those exact
weights* and reproduced the paper's headline numbers (BBBP AUROC 0.968, DTI NRMSE ~0.88, TCR 0.93,
ClinTox ~1.0, solubility 0.73/0.83, plus the PGK2/WDR91 per-target heads) — and they were *still* not
useful for our jobs. So this is **not** a "you ran the wrong/base model" mistake: the weights are
right, the *capability* is the problem. Fine-tuning is the correct lever for exactly **one** of our
failing use cases — single-target binder triage, which the off-the-shelf DTI head scores at chance but
a per-target head can do (PGK2 tells its hits from the PGK1 homolog's ligands at AUROC 0.97). The rest
of where MAMMAL disappoints is two deeper problems that **no fine-tune fixes**: benchmark scores don't
survive deployment, and the base model is weak at the things we most need. **[HIGH]**

### The causal bullets (why SOTA ≠ useful)

- **We were already using the fine-tuned versions.** 7 tasks, fine-tuned weights, reproduced exactly.
  The disappointment is capability, not checkpoint choice. **[HIGH]**
- **"SOTA on a benchmark" ≠ "works on my compound."** Every classification head ranks beautifully on
  its curated test set and then fails out-of-distribution: BBBP over-passes peripherally-restricted
  drugs (held-out **TNR 0.70**), ClinTox scores ~1.0 by *memorizing* ~112 training toxics and catches
  **0% of external clinical toxics**, and the heads emit **hard 0/1 labels** you can't threshold. **[HIGH]**
- **"SOTA" sometimes means "least-bad at an unsolved problem."** DTI NRMSE 0.906 is only ~9% better
  than guessing the mean affinity (R²≈0.18); the whole field is stuck near this ceiling on honest
  splits. The badge buys a coarse re-ranker, not a binder oracle. **[HIGH]**
- **Our biggest needs live in the BASE model, where no head can save it.** Cross-modal binding,
  compound similarity, and de-novo generation are base-model capabilities — and they're broken
  off-the-shelf: protein/molecule embeddings near-orthogonal (cosine 0.08), Morgan fingerprints beat
  MAMMAL at similarity (0.96 vs 0.72), and the public weights can't generate a usable novel molecule. **[HIGH]**
- **The paper never claimed an off-the-shelf general model.** Every Table-1 number is a *separate
  per-task fine-tune*; the authors' own ablation shows the pre-trained model is near chance (HER2
  binder AUROC 0.53 pre-trained → 0.88 fine-tuned). Our experience is exactly what the paper's design
  predicts. **[PAPER]**

### The base-vs-finetuned split of OUR failing use cases (the whole answer in one table)

| Our failing use case | Depends on | Can a fine-tune fix it? |
|---|---|---|
| Cross-modal binding / shared latent space (Sapphire) | **BASE** geometry | ❌ near-orthogonal (cosine 0.08), readouts anti-correlated −0.90 **[HIGH]** |
| Compound similarity / hit expansion | **BASE** embeddings | ❌ Morgan beats it (0.96 vs 0.72); use fingerprints **[MED]** |
| De-novo molecule generation | **BASE** decoder | ❌ public weights only do grammar-valid span-infill; design heads not public **[HIGH]** |
| Calibrated per-compound probabilities | heads, but **architecture** emits hard 0/1 | ❌ recalibration ≠ generalization (ClinTox) **[HIGH]** |
| **Single-target binder triage (our targets)** | **missing per-target fine-tune** | ✅ **YES** — PGK2 head is the existence proof (0.97 homolog selectivity, EF5 11×) **[MED]** |

**Four of five failing jobs are base-model/architecture limits with no fine-tune to call on; only the
fifth (binder triage) is the kind of gap fine-tuning closes — and even then as in-distribution
chemotype triage, not potency ranking or novel-hit discovery (both heads saturate near 1.0, Spearman
≈ 0).** *State-of-the-art on shit is still shit.* **[HIGH]**

---

## Q2 — Specialist models vs one cohesive MAMMAL

### Recommended posture
**Adopt a best-of-breed funnel behind David's single dispatcher. Keep MAMMAL only for the two narrow
jobs it's genuinely good at plus one optional in-house fine-tune. Do not pursue one-cohesive-MAMMAL for
the hard jobs.** This is not a close call.

**Why the cohesion argument already lost.** The case for "one cohesive MAMMAL" was *never* per-modality
accuracy (the paper never showed cross-modal transfer beating two specialists) — it was a **single
shared cross-modal latent space**: target and ligands as neighbors, retrieve binders by proximity,
co-embed a KG. **Phase 6 falsified that off the shelf** (cross-modal cosine 0.08, binder-vs-decoy
AUROC ≈ chance 0.570, the two proximity readouts anti-correlated −0.90). So the cohesion is real only
as a **single-interface convenience**, not a capability — and that convenience is replicable with ~200
lines of router code. The honest reframe: it's not "elegant cohesive model vs N messy specialists,"
it's "a generalist weak at every hard job Quiver wants vs specialists strong at those exact jobs." You
buy convenience back in software; you **cannot** buy back binder-triage accuracy MAMMAL structurally
lacks. **[HIGH]**

### Which 2–3 specialists to adopt, for which funnel step

| Funnel step | Job | Specialist | Why (not MAMMAL) | License / hardware |
|---|---|---|---|---|
| **0. Expand/dedupe hits** | similarity | **Morgan/ECFP (RDKit)** | beats MAMMAL 0.96 vs 0.72; free, instant | — / CPU |
| **1. Binder triage (cheap, wide)** | decoy-resistant "binds target Y?" | **ConPLex** | purpose-built for the exact axis MAMMAL scores at chance; proteome-scale on 1 A100 | MIT / GPU-light |
| **2. ADMET de-risk (cheap, wide)** | hERG/DILI/BBB/CYP… | **ADMET-AI** (+ MAMMAL BBBP as a 2nd-opinion *positive* flag) | 41 calibrated TDC endpoints; replaces MAMMAL ClinTox (0% external sensitivity, unusable) | MIT / CPU |
| **3. Structure + affinity (expensive, narrow)** | pose + graded affinity on survivors | **Boltz-2** | structure (MAMMAL: none) + near-FEP affinity + graded ranking (MAMMAL heads saturate, Spearman≈0) | MIT / **GPU-heavy** |
| **(parallel) target context** | gene-family clustering, KG node features | **MAMMAL embeddings** (ESM-2 650M fallback) | survived size-matched ESM-2 650M; Apache-2.0, no commercial-license trap | Apache-2.0 / small GPU |

The funnel ordering **is** the cost story: ConPLex + ADMET-AI are cheap and prune the *whole* library;
**Boltz-2's GPU heft only hits the small survivor slice** (top 1–5%), the standard cheap-filter →
expensive-scorer pattern. The three picks are all **MIT, pip-installable, actively maintained, with
real external adoption** (Boltz-2 4,000★; ConPLex ~59 citations; ADMET-AI peer-reviewed 2024) — a
*healthier* dependency set than MAMMAL alone (zero independent benchmarks, 3 lifetime GitHub issues).

### What MAMMAL keeps (and why it's cheap to keep)
- **Protein/gene-family embeddings** (CRISPR-N panel, Sapphire KG node features) — survived the
  size-matched ESM-2 650M challenge on our recipe (NN recall 0.92 vs 0.84); Apache-2.0 vs ESM-3's
  commercial gate. Keep as default, ESM-2 650M (MIT) as the open cross-check. **[MED]**
- **BBBP as a soft *positive* de-risking signal** (not a rule-out gate) alongside ADMET-AI's calibrated
  BBB endpoint. **[HIGH]**
- **Optional in-house per-target chemotype-triage fine-tune** (the Q3 play below) — PGK2 is the
  existence proof; evaluate by EF/BEDROC on a scaffold split. **[MED]**

These three are read-only / enrichment / experimental — none is a pipeline-critical scoring gate, so
keeping MAMMAL costs almost nothing and we already have David's interface.

### The honest integration/maintenance tradeoff
The genuine cost of best-of-breed is maintenance surface: N packages, N environments, N input formats,
N upgrade cadences, plus a dispatcher. **Real, but bounded and cheap relative to the alternative**: (1)
the "one interface" benefit is ~200 lines on top of David's existing pattern; (2) all picks are MIT/
Apache + pip + maintained, *lower* per-tool bus-factor than MAMMAL itself (which we had to debug
firsthand: macOS TF-deadlock, PEER-split trap, vestigial-scalar-head trap, all undocumented); (3) only
Boltz-2 needs real GPU ops — ConPLex/ADMET-AI/Morgan are laptop/CPU-class; (4) you cannot buy back the
accuracy. Net: trade "one fragile unbenchmarked model carrying every hard job" for "MAMMAL on two easy
jobs + three well-supported specialists each on the job they were built for." **Lower capability risk,
modestly higher integration surface, fully bounded. The cross-modal-NO finding removed the only
rationale for the cohesive bet — optimize for the expensive thing (capability), not the cheap thing
(convenience).** **[HIGH]**

**Migration guardrails:** pilot ConPLex and Boltz-2 on one Quiver target each (known binders/decoys;
known potencies) before production — empirical-on-our-data beats paper badges. Budget Boltz-2 GPU spend
explicitly (cheapest start: hosted NVIDIA NIM / BioLM API for low volume). Do **not** adopt ESM-3 /
ESM-C-600M (commercial-license-gated); ESM-2 650M (MIT) is the only ESM swap, and only as a cross-check.

---

## Q3 — Fine-tuning MAMMAL now on public data: recipe, footprint, cost, upside

### Q3a — The recipe and footprint: does it fit a T4? **Yes, comfortably.**

The shipped recipe (read directly from `github.com/BiomedSciAI/biomed-multi-alignment`) is a **plain
full fine-tune of all 458M params** — PyTorch Lightning + Hydra, `torch.optim.AdamW` at **lr 1e-5**,
cosine-annealing-with-warmup, **fp32** (no mixed precision set anywhere), **no gradient checkpointing**,
**single GPU** (`devices: 1`), tiny batches (6–20). A LoRA path exists in `lora.py` (PEFT `r=8`) but is
**OFF by default and not wired into the finetune entrypoint** — full FT is what every public example
does. **[HIGH]**

**Memory footprint (the GB math on the verified 458,004,897-param F32 model):**

| Component | Math | Size |
|---|---|---|
| Weights (fp32) | 458M × 4 B | 1.83 GB |
| Gradients (fp32) | 458M × 4 B | 1.83 GB |
| AdamW states (m+v, fp32) | 458M × 8 B | 3.66 GB |
| **Model-state subtotal** | | **≈ 7.33 GB** |
| Activations (config batch sizes, short context) | batch/seq-dependent | ~1–5 GB |
| CUDA + framework overhead | fixed | ~0.5–1.5 GB |
| **Total expected peak** | | **≈ 9–13 GB** |

**Fits a 16 GB T4 with room to spare** — and only because the model is small; the *optimizer* is the
cost driver, not the model. Mixed precision (bf16/fp16 AMP) here is a **speed** lever, **not** a "make
it fit" lever (it doesn't shrink the 7.3 GB model-state floor). The one row to watch is the
1500–1560-token DTI/cancer-drug-response context, where activations inflate — handled by free,
recipe-preserving fixes (AMP / smaller batch + grad-accum / gradient checkpointing). **You do NOT need
an A10G/A100 to fine-tune this model; you only want one for speed.** Empirically corroborated: our
local probe ran a real fp32 batch-1 forward+backward of the 458M model **with no OOM on a 16-GB-class
machine.** **[HIGH on arithmetic + probe; MED on the long-context margin]**

**Cheapest realistic pilot:** a per-target binder classifier (~hundreds to ~1.4k SMILES,
carcinogenicity-template, generative P(`<1>`) readout, short ≤320-token context) → single-digit
GPU-minutes to ~1 GPU-hour. **Heaviest public task:** GDSC2 cancer-drug-response (92,703 pairs,
1500-token context, the only task needing grad accumulation) → GPU-hours. BBBP (~2,050 compounds) sits
between → tens of GPU-minutes. **[HIGH on sizes, MED on steps]**

### Q3b — The BOSS-FACING cost table (reconciled with the empirical probe)

Single-T4 `g4dn.xlarge` is the primary instance (as asked); `g5.xlarge` (A10G, 24 GB) shown as a
comparison row. Central throughput **~10 samples/s** for short SMILES classifier fine-tunes, **~2
samples/s** for the heavy ranked-gene + scalar regression; fixed overhead 0.75 h (small) / 1.0 h
(heavy). Pricing us-east-1, fetched 2026-06-01 (g4dn.xlarge $0.526/h OD, $0.240/h spot; g5.xlarge
$1.006/h OD, $0.619/h spot).

| Pilot | #examples | epochs | est. steps (samples) | T4 train time | **T4 total time** | **g4dn.xlarge on-demand $** | **g4dn.xlarge spot $** | *g5.xlarge total / OD$ / spot$* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Small per-target binder** | 2,000 | 10 | 20,000 | 0.56 h | **1.3 h** | **$0.69** | **$0.31** | *1.0 h / $1.03 / $0.64* |
| **MoleculeNet BBBP** | 2,050 | 20 | 41,000 | 1.14 h | **1.9 h** | **$0.99** | **$0.45** | *1.3 h / $1.33 / $0.82* |
| **Heavy: cancer-drug-response** | 200,000 | 5 | 1,000,000 | 138.9 h | **139.9 h** | **$73.58** | **$33.57** | *70.4 h / $70.87 / $43.61* |

*"est. steps (samples)" = #examples × epochs = total forward/backward sample-passes. In optimizer-step
terms at batch 16 that is ~1,250 / ~2,560 / ~62,500 steps — small fine-tunes, exactly as the upstream
configs imply.*

**Reading the table for the boss:**
- The two realistic Quiver pilots (a per-target binder head; a MoleculeNet-scale property head) each
  finish in **under 2 hours for about a dollar on-demand, under 50 cents on spot.** Cost is **not** a
  barrier — it's a rounding error against an analyst-hour.
- The heavy 200k-pair case is the only one that costs real money/time on a single T4 (~6 days). For
  that you'd use 4×T4 `g4dn.12xlarge` ($3.91/h OD) or a `g5` — roughly the same dollars, ~4× less
  wall-clock — **not** a single `g4dn.xlarge`. Shown to bound the range, not as a recommended single-T4 run.
- **g5.xlarge (A10G) is the smarter default for anything non-trivial:** ~2× T4 throughput for ~1.9× the
  rate ≈ break-even dollars but half the wall-clock, plus 24 GB removes any long-context anxiety. g4dn
  stays primary per the ask; reach for g5 if you run more than a toy.

**Assumptions & uncertainty bands (state these to the boss):**
- **Throughput is the dominant uncertainty: ±2.5× on the small pilots, ±3× on the heavy one.** So BBBP
  is "$0.45–$1.90 on-demand, most likely ~$1." The *qualitative* claim ("a small fine-tune is ~1–2
  GPU-hours and ~$1") is robust across the entire band; even at the pessimistic 4 samples/s it's 3.6 h
  and **under $2.** What we're not certain of is the exact hour — which doesn't change the decision.
- **Spot is live and zone-varying — re-quote before any run.** Interruption is a non-issue for a 1–2 h
  job (restart, lose cents) but a real risk for the ~6-day heavy run (use on-demand or checkpoint-resume).
- **Per-seed.** The paper reports mean±std over 3 seeds; a publication-grade run is **3×** (still ~$3 / ~6 h
  for BBBP — trivial).
- **Epochs illustrative; cost scales linearly in examples × epochs.** Real fine-tunes often early-stop,
  making these *upper* estimates. No EBS/storage line (~$0.08/day, rounding error).

**Empirical-probe anchor — and the reconciliation.** A direct M3-Pro/MPS probe (`results/phase7_finetune_probe.md`)
ran the real per-target classifier forward+backward and measured **MPS 13.0 samples/s @ batch 1**,
landing inside the cost lane's assumed T4 band (central 10, range 4–25). An independent from-scratch
recompute of the small binder pilot at the probe's own 12 samp/s gave **$0.64 OD / 1.21 h — reproducing
the cost lane's $0.69 / 1.3 h to within ~8%.** The two lanes **agree**; where they differ, the probe is
*slightly more optimistic* (12 vs 10 samp/s). **Per the brief's instruction to present the reconciled,
more conservative number, the headline above uses the cost lane's $0.69 OD / $0.31 spot / 1.3 h** (the
marginally higher = safer figure) — the probe corroborates rather than contradicts it. **One honest
scope flag the probe itself raises:** it anchors **only the short-context classifier row** (binder/BBBP
— the realistic pilot). It says **nothing empirical about the heavy 1500-token regression row**, whose
~$34–74 / ~6-day figure keeps its wider ±3× band and should be re-measured on a real GPU before being
leaned on. Do not let the clean pilot result imply the heavy case is verified — it isn't. **[HIGH for
the pilot row; MED→LOW for the heavy row]**

### Q3 — The UPSIDE verdict (the user will only fine-tune if the upside is real)

**Recommendation: YES — run the public-data fine-tune, but understand what you're buying.** You are
**not** buying a useful public result (the public targets are commodity — BBBP is a number a 30-line
Random Forest matches; a public per-target head re-recognizes a known chemotype). You are buying a
**cheap, low-risk validation of the per-target fine-tuning *pipeline*** — and that pipeline is the
**single path to a defensible Quiver-specific capability.** The logic chain:

1. The one place fine-tuning demonstrably helps (Q1) is in-distribution per-target binder triage, and
   IBM's PGK2 head proves it works (homolog-selectivity AUROC 0.973, spike-in EF5 11×). **[MED]**
2. The capability Quiver would actually want is that same triage **on Quiver targets, trained on Quiver
   screening/DEL data** — which requires standing up and trusting the full fine-tune pipeline.
3. A public-data fine-tune (BBBP or a public per-target set like PGK2's 1,388 CACHE#7 hits) **exercises
   that exact pipeline end-to-end** — data module swap (TDC/parquet), generative readout, scaffold-split
   eval, the untested-by-us `use_lora`/scalar hooks if wanted — for **lunch money**, before you spend a
   single hour curating or risking Quiver data.
4. It's a **dry run with a known-answer**: reproducing BBBP ~0.957 or PGK2 ~0.97 confirms the wiring is
   correct; a miss surfaces a pipeline bug while it's still free to fix.

**The dollar figure and the condition.** Budget **~$2–5 on-demand** for the de-risking dry-run: one
small per-target binder fine-tune (~$0.69) + optionally BBBP as a known-answer check (~$0.99), each
×3 seeds for a defensible mean if you want it (still ≈ $5 total). On spot it's **~$1–2.** Wall-clock is
**a few hours, not days.** **Condition the *next* step (the actual Quiver-data fine-tune, which is where
real value or real disappointment lives) on the dry-run clearing enrichment factor / BEDROC on a
held-out *scaffold* split** — not a random split, because random is precisely what makes PGK2's 0.97 /
11× look better than novel-scaffold reality. If the public dry-run validates the pipeline and the
Quiver-data run then clears scaffold-split EF/BEDROC, you have the one genuinely useful in-house MAMMAL
capability; if scaffold-split enrichment collapses, you've learned that for ~$5 instead of after a Quiver-data
project. **[MED]**

**Why this clears the user's bar ("only if significant enough upside").** The upside is not in the
public numbers (low) — it's that **~$5 and an afternoon de-risks the only MAMMAL path to a
Quiver-specific moat capability** (per-target triage) that is otherwise gated behind an unvalidated
pipeline and Quiver-data curation cost. That asymmetry — trivial spend, real strategic option value,
known-answer validation — is the "significant enough upside." **The cost was never the question; the
science is, and the cheapest way to test the science is this dry-run.** Recommend **yes**, at **~$5
on-demand (~$2 spot), a few hours**, gated on scaffold-split enrichment before any Quiver-data spend.

---

## Sources & provenance
- **Lane outputs reconciled:** `docs/analysis/q1_why_underperforms.md`, `q2_specialists_vs_cohesive.md`,
  `q3a_finetune_recipe_footprint.md`, `q3b_aws_g4dn_cost.md`; empirical anchor
  `results/phase7_finetune_probe.md`.
- **Grounding (not re-derived):** `docs/COMPLETE_UNDERSTANDING.md` (Phase 6 cross-modal falsification,
  ESM-650M, PGK2 full eval, full scorecard), `HANDOFF.md`, `docs/FINDINGS.md`, `docs/lit/01–05`.
- **External-tool facts** (ConPLex MIT/PNAS 2023; Boltz-2 MIT/4,000★; ADMET-AI MIT/Bioinformatics 2024;
  ESM licensing; AWS g4dn/g5 pricing + T4 specs + throughput anchors) dated and sourced in
  `q2_specialists_vs_cohesive.md` and `q3b_aws_g4dn_cost.md`.

*Q-MAMMAL follow-up decision doc, 2026-06-01. Confidence tags and n explicit; reconciled probe-vs-cost
to the more conservative figure per the brief. Audience: Rohan + boss; numbers defensible.*
