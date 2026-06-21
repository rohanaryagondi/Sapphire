# Phase 6 — Generation capability of the public base MAMMAL (base_458m)

**Date 2026-06-01. Model: `base_458m` (`ibm/biomed.omics.bl.sm.ma-ted-458m`), CPU, one load.**
Scripts: `experiments/phase6_generation.py` (+ `experiments/phase6_generation_probe2.py`, interpretive
hardening). Raw: `results/phase6_generation.json` (probe2 merged under `followup_probe2`),
`results/phase6_generation_probe2.json`.

## The question

Every prior Quiver phase used MAMMAL's generative *readout* (decode one token, read P(`<1>`) for
classification) but **never tested MAMMAL as an actual generator.** The paper (arXiv 2410.22367)
advertises generation — antibody CDR infilling (+19% AAR), PPI generation, molecule design — but the
upstream-code lane (`docs/lit/05_upstream_code.md`) established the public repo ships **no
free-generation example, no checkpoint, no test** for any generative-output task. `Mammal.generate`
is a thin wrapper over HF `T5ForConditionalGeneration.generate` and forwards `do_sample` / `num_beams`
/ `max_new_tokens` unchanged, so de-novo decoding is *implementable* but unvalidated. This phase built
and measured that harness on the public weights.

MAMMAL is a T5 pretrained with **span corruption** over AA + SMILES vocabularies (200 sentinel tokens
`<SENTINEL_ID_0..199>` confirmed in the tokenizer). So its native generative ability is **span
infilling**: place `<SENTINEL_ID_0>` where a span was removed; a correct T5 decoder emits
`<SENTINEL_ID_0> <fill> <SENTINEL_ID_1> …`. We tested exactly that, plus open-ended decoding, in both
modalities, with greedy / beam / sampling, validating SMILES with RDKit and AA fills against the
20-letter alphabet + position-wise recovery (AAR).

## Bottom line

**The public base model genuinely generates — but only as a *local span-infiller inside a valid
scaffold*, and only format-and-grammar-valid, not *accurate*. It has no usable unconditional
("de-novo") generative prior, and infilling produces plausible *neighbors*, not the held-out truth.**
The paper's headline generation tasks (antibody design, PPI generation) require **unpublished design
checkpoints** and are **not testable** on the public weights — only `base_458m` + 9 task heads ship.

| Capability (public base_458m) | Result | Verdict |
|---|---|---|
| **SMILES span infilling** (mask interior, splice fill) | T5-format-compliant **8/8**; reconstructed molecule RDKit-valid **8/8**; **exact span recovery 1/8** (only a trivial 1-char span). Sampling a short interior span of aspirin yields valid analogs (5-Cl, 5-OH, 5-Br, 5-CH₂OH aspirin) — never the parent | ⚠️ **Valid analog/edit generation, NOT reconstruction.** Knows SMILES grammar + ring chemistry; does not retrieve the masked truth |
| **SMILES de-novo** (header + sentinel, open-ended) | Greedy → a **single atom** (`P`) + `<EOS>`; forcing length (`min_new_tokens=20`) → **invalid** (`PP1P1OP1OP1O…`); beam-5 → 2 atoms (`CP`); scaffold-extend → invalid | ❌ **No de-novo molecule generation.** RDKit "valid_rate 1.0" in the first pass is **hollow** — a lone atom parses as valid. Forced length collapses to garbage |
| **Protein span infilling** (mask interior, AA fill) | Format-compliant **3/3**; all-AA-valid **3/3**; greedy mean AAR **0.40** but driven entirely by hyper-conserved **ubiquitin (AAR 1.0)**; insulin-B **0.20**, lysozyme **0.00** (greedy collapses to homopolymer `SSSSSSS`). Sampling escapes homopolymers but AAR ≈ **0.07** (≈ chance for 20 AA) | ⚠️ **Plausible-residue infilling, not recovery.** Looks like protein; recovers truth only when the span is essentially memorizable |
| **Antibody CDR infilling / PPI generation** (paper headline) | Not shipped — no checkpoint/example/test in the public release | 🚫 **Untestable on public weights.** Requires the unpublished design heads. Not claimed |

## The receipts

**Model is healthy (not a broken-load artifact).** The base model's one *documented* classification
task reproduces exactly: PPI calmodulin–calcineurin → `'<SENTINEL_ID_0><1><EOS>'`, **P1 = 0.946**
(`followup_probe2.base_model_PPI_classification_sanity`). So when the same model emits a SMILES/AA span
fill on a generation prompt, that is the genuine pretraining behavior — not corruption. (Note: a `<BBBP>`
task prompt on *base* returns an infill, not `<0>/<1>` — because BBBP lives in the **fine-tuned
`moleculenet_bbbp` head**, not base. The Phase-1 AUROC 0.968 was that head, never base. Consistent.)

**SMILES infilling — valid edits, not the truth.** Greedy, interior ~⅓ span:

| drug | held-out span | predicted fill | reconstructed (canonical) | valid? | = parent? |
|---|---|---|---|---|---|
| aspirin | `c1ccccc` | `C1CC` | `CC(=O)OC1CC1C(=O)O` | ✅ | ✗ |
| ibuprofen | `cc(C(C)C` | `cc(CC` | `CC(C)Cc1ccc(CC(=O)O)cc1` | ✅ | ✗ |
| caffeine | `c(=O)n(C` | `nc(O` | `Cn1cnc2c1nc(O)c(=O)n2C` | ✅ | ✗ |
| ethanol | `C` (1 char) | `C` | `CCO` | ✅ | ✅ |

Short-span aspirin (mask 2 chars), 8 samples: fills `c(Cl)c`, `c(O)c`, `c(Br)c`, `c(CO)c`, `(OC)cc` →
all **valid para-/ortho-substituted aspirin analogs**, **0/8 recover the parent**
(`followup_probe2.smiles_short_span_infill`). The model has real chemical-grammar competence (it closes
aromatic rings, balances valence, adds sensible substituents) but treats the mask as "fill with
*something* plausible," not "restore the original."

**De-novo is a non-starter** (`followup_probe2.denovo_forced`): `<SENTINEL_ID_0>`-only greedy → `P`;
`min_new_tokens=20` → `PP1P1OP1OP1OP1OP1OP` (RDKit-invalid); beam-5 → `CP`; `c1ccccc1<SENTINEL_ID_0>`
extend → `P=OP1]CI12` (invalid). Without a scaffold to fill, the decoder has no coherent prior — it
emits a token and stops, or runs into degenerate repetition.

**Protein infilling — plausible, not recovering.** Greedy: ubiquitin fill `KEGIPPDQQRLI` = exact (AAR
1.0; ubiquitin is one of the most conserved/most-sequenced proteins — effectively memorized), insulin-B
→ `LLL` (AAR 0.20), lysozyme → `SSSSSSS` (AAR 0.0, homopolymer attractor). Sampling lysozyme escapes the
homopolymer (`SNASEST`, `YNLKFG`, `GGFEKNF` — protein-looking) but **mean AAR 0.067 ≈ chance**
(`followup_probe2.protein_sampling_infill`). It generates residues that *look* like protein, with no
recovery of the actual sequence beyond trivially-conserved cases.

## What this means for Quiver

- **"MAMMAL generates molecules" is not true off-the-shelf.** The public base model cannot do de-novo
  molecular design, and its infilling generates valid *analogs* rather than reconstructing intent. For
  the Atlas / "how fast to molecules" question, the public weights give a decoder + tokenizer and a
  **scaffold-decoration toy**, not a generator. (And dedicated tools already do scaffold decoration /
  fragment growing far better.) This corroborates the project frame: MAMMAL is enrichment, not the
  engine.
- **The one thing that *does* work** — grammar-valid SMILES span fills that are chemically reasonable
  neighbors — is exactly the kind of "suggest a substituent at this position" move, but with **zero
  property conditioning** (no potency/ADMET signal in the base decoder) and no recovery fidelity, so it
  is not usable as a design oracle. If anything, it's a weak SMILES-augmentation generator.
- **The paper's marquee generation results stay unverifiable.** Antibody CDR infilling (+19% AAR) and
  PPI generation need checkpoints IBM did not release. We can characterize the base model's span-infill
  *mechanism* (it works, format-wise), but we **cannot** reproduce or refute the design-quality claims —
  flag, don't chase (same posture as the other 6 unpublished-checkpoint tasks).
- **Consistent with every other phase:** benchmark/paper framing ≠ deployable capability. The
  generation badge, like the SOTA classification badges, does not survive contact with our bar
  ("state-of-the-art on shit is still shit"). Here it's worse — the public artifact doesn't even
  expose the generation the paper sells.

## Honest scope / caveats

- **Public weights only.** `base_458m` + the 9 task heads. Antibody-design and PPI-generation heads are
  not public; their claims are out of scope and **not** asserted here either way.
- **Conditional-generation heads we didn't have** could change the molecule story (e.g., a
  property-conditioned or reaction/retrosynthesis fine-tune) — but none ship, so this is the ceiling of
  what's available today.
- **CPU + modest input set** (8 small drugs, 3 short proteins, ≤12 samples/config) — enough to
  characterize the *mode* (infill works, de-novo fails, recovery ≈ chance) with clear separation;
  not a large-scale validity benchmark. The qualitative verdict is robust (8/8 vs 1/8, chance-level
  AAR, de-novo collapse under forcing); exact rates would tighten with more compounds.
- **Readout faithfulness:** decode via `tokenizer_op._tokenizer.decode` (the upstream
  `test_simple_inference` pattern); span fill = text between `<SENTINEL_ID_0>` and the next sentinel,
  specials stripped. The healthy-model PPI control (P1 0.946) rules out a load/decoma bug.
