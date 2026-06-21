# 05 — Upstream code: the real MAMMAL APIs (generation, scalars, fine-tunes)

**Lane: UPSTREAM CODE.** What is actually in `github.com/BiomedSciAI/biomed-multi-alignment`
(MAMMAL core code), read against the local `mammal_quiver/` wrappers. Goal: document the
*reproducible* APIs — especially **generation** and **numerical-value handling**, which prior
Quiver phases under-tested.

Source read from a fresh shallow clone at commit `56a08ba` (2026-05-28) into `/tmp/bma`, plus the
installed package `/opt/anaconda3/envs/mammal/lib/python3.11/site-packages/mammal` and the `fuse`
tokenizer. File references below are repo-relative (`mammal/...`) unless noted.

> **One-paragraph orientation.** MAMMAL is a single T5 encoder-decoder
> (`T5ForConditionalGeneration`) wrapped by `mammal.model.Mammal`. *Everything* is a prompt string
> in a modular-tokenizer syntax. There are exactly **three forward paths**: `generate()` (decoder
> autoregression — used for classification + would-be generation), `forward_encoder_only()`
> (encoder + an MLP "scalars head" — used for **regression**), and `forward_encoder_decoder()`
> (teacher-forced training). Classification is done *generatively*: seed the decoder with
> `<SENTINEL_ID_0>`, generate, and read the softmax probability of the `<1>` token at output
> position 1 — this is the "P(<1>) trick." Numerical *outputs* (pKd, IC50) come from the scalar
> head, not generation; numerical *inputs* are injected by a `Linear(1, 768)` that is **unused by
> every shipped example**. Crucially: **no free/de-novo generation example (molecule design,
> antibody infilling, PPI generation) ships as runnable code** — those live only in the paper.

---

## 1. The generation API — `Mammal.generate()`

### 1.1 Signature and what it returns
`mammal/model.py:165-233`. `generate()` is a thin wrapper over HuggingFace's
`T5ForConditionalGeneration.generate()`. It feeds **input embeddings** (not token ids — see §2),
forwards all `**generate_kwargs` straight to HF, and writes results back into the batch dict under
the `mammal.keys` names:

```python
# mammal/model.py:165
def generate(self, samples: list | dict, **generate_kwargs: dict):
    batch_dict = CollateDefault()(samples) if not isinstance(samples, dict) else samples
    input_embeddings = self._calculate_inputs_embeddings(batch_dict)        # §2
    generated_output = self.t5_model.generate(
        inputs_embeds=input_embeddings,
        attention_mask=batch_dict[ENCODER_INPUTS_ATTENTION_MASK],
        eos_token_id=self.config.t5_config.eos_token_id,
        pad_token_id=self.config.t5_config.pad_token_id,
        **generate_kwargs,
    )
    ...
    cls_pred = cls_pred[:, 1:]                 # <-- drops the decoder-start token (model.py:205)
    batch_dict[CLS_PRED] = cls_pred.contiguous()
    # only populated when output_scores=True & return_dict_in_generate=True:
    batch_dict[LOGITS]  = torch.vstack([x[None] for x in generated_output.scores]).permute(1,0,2)
    batch_dict[SCORES]  = torch.nn.functional.softmax(batch_dict[LOGITS], dim=-1)
    return batch_dict
```

Output keys (`mammal/keys.py`): `CLS_PRED = "model.out.cls_pred"` (argmax token ids, decoder-start
stripped), `SCORES = "model.out.scores"` (softmax probs, shape `[batch, gen_len, vocab]`),
`LOGITS = "model.out.logits"`. **`SCORES`/`LOGITS` are `None` unless you pass
`output_scores=True, return_dict_in_generate=True`.** The `cls_pred[:, 1:]` line is the reason
every readout uses **position 1** for `CLS_PRED` but reads `SCORES` at position 1 too (SCORES is
*not* shifted; the class token lands at index 1 because index 0 is the sentinel echo).

### 1.2 The canonical invocation (verbatim, README + `begginer_inference.ipynb`)
This is the *only* generation pattern demonstrated in the repo. PPI **binding-affinity
classification** with the base model (works off-the-shelf, no fine-tune):

```python
import torch
from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
from mammal.model import Mammal
from mammal.keys import *

model = Mammal.from_pretrained("ibm/biomed.omics.bl.sm.ma-ted-458m").eval()
tokenizer_op = ModularTokenizerOp.from_pretrained("ibm/biomed.omics.bl.sm.ma-ted-458m")

sample_dict = {}
sample_dict[ENCODER_INPUTS_STR] = (
    "<@TOKENIZER-TYPE=AA><BINDING_AFFINITY_CLASS><SENTINEL_ID_0>"
    "<MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN><SEQUENCE_NATURAL_START>"
    f"{protein_calmodulin}<SEQUENCE_NATURAL_END>"
    "<MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN><SEQUENCE_NATURAL_START>"
    f"{protein_calcineurin}<SEQUENCE_NATURAL_END><EOS>")
tokenizer_op(sample_dict=sample_dict, key_in=ENCODER_INPUTS_STR,
             key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
             key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK)
sample_dict[ENCODER_INPUTS_TOKENS]        = torch.tensor(sample_dict[ENCODER_INPUTS_TOKENS])
sample_dict[ENCODER_INPUTS_ATTENTION_MASK]= torch.tensor(sample_dict[ENCODER_INPUTS_ATTENTION_MASK])

batch_dict = model.generate([sample_dict], output_scores=True,
                            return_dict_in_generate=True, max_new_tokens=5)
generated_output = tokenizer_op._tokenizer.decode(batch_dict[CLS_PRED][0])   # e.g. '<SENTINEL_ID_0><1><EOS>'
```

**Prompt anatomy** (the "task prompt syntax" the paper advertises): `<@TOKENIZER-TYPE=AA>` selects
the amino-acid sub-tokenizer; **`<BINDING_AFFINITY_CLASS>` is the task token**; `<SENTINEL_ID_0>` is
the T5 sentinel that tells the decoder "generate the answer here"; then the entity blocks
(`<MOLECULAR_ENTITY>…<SEQUENCE_NATURAL_START>seq<SEQUENCE_NATURAL_END>`), then `<EOS>`. Swap the
task token to change the task. `max_new_tokens=5` is universal — the answer is one token.

### 1.3 "Generation" of molecules / sequences / antibody infilling / PPI design
**Not shipped.** Searched the whole tree (`mammal/`, `tutorials/`, `mammal_vllm/`,
`mammal_mcp/`) for any free-generation prompt — `do_sample`, `num_beams`, `num_return_sequences`,
`max_new_tokens` > 5, masked `<SEQUENCE_NATURAL_START><MASK>`, "design", "infill", "de_novo". **Zero
hits.** Every `generate()` call in the repo is the 1-token classification readout above
(`max_new_tokens=5`, read position 1). The paper (arXiv 2410.22367) describes antibody-infilling and
PPI/molecule generation, but **the GitHub release contains no example code, no checkpoint, and no
test for any generative-output task.** The architecture *can* do it (it's a full T5 decoder over a
SMILES/AA vocabulary), and `generate()` will forward `do_sample`/`num_beams`/`max_new_tokens` to HF
unchanged — so de-novo decoding is *implementable* by writing a masked/open-ended prompt and raising
`max_new_tokens` — but **nothing in the public code demonstrates or validates it, and there is no
base-model card claiming generation works.** Treat MAMMAL generation as **paper-only / unverified**
for Quiver until we build and test a harness ourselves. (This is the single biggest gap between the
paper's framing and the reproducible artifact.)

---

## 2. Numerical-value handling — the scalar projection + the scalar head

There are **two distinct numeric mechanisms**, and they are easy to conflate. Both pass through the
modular tokenizer's `<@TOKENIZER-TYPE=SCALARS_LITERALS>` syntax.

### 2.1 Numeric INPUTS — `project_input_scalars` (a `Linear(1, 768)` added to the embedding)
`mammal/model.py:137-143` (construction) and `mammal/model.py:325-366` (`_calculate_inputs_embeddings`):

```python
# model.py:137 — built only if config.support_input_scalars is True
if getattr(self.config, "support_input_scalars", False):
    self.project_input_scalars = torch.nn.Linear(
        1, self.t5_model.get_input_embeddings().embedding_dim, bias=True)   # 1 -> 768

# model.py:325 — how a scalar enters the model
def _calculate_inputs_embeddings(self, batch_dict):
    inputs_embeds = self.t5_model.get_input_embeddings()(batch_dict[ENCODER_INPUTS_TOKENS])
    if self.project_input_scalars is not None and batch_dict.get(ENCODER_INPUTS_SCALARS_VALUES) is not None:
        mask = batch_dict[ENCODER_INPUTS_SCALARS_VALID_MASK]
        if mask.any():
            projected = self.project_input_scalars(values[..., None])    # each scalar -> 768-vec
            inputs_embeds[mask] += projected[mask]                       # ADDED onto the token embedding
    ...
    return inputs_embeds
```

**Mechanism:** a scalar does not get its own token. The tokenizer emits a placeholder token at the
scalar's position and a parallel `(values, valid_mask)` pair; the model projects each float through
one shared `Linear(1→768)` and **adds** it to that position's token embedding. This is how MAMMAL
"reads numbers." The relevant `mammal.keys`: `ENCODER_INPUTS_SCALARS = "data.encoder_input.scalars"`,
with `.values` (float tensor) and `.valid_mask` (bool tensor) suffixes (`keys.py:56-60`).

The **syntax** that produces those values (fuse `op.py:401-413`, verbatim docstring):
> for text following `<@TOKENIZER-TYPE=SCALARS_LITERALS>`: `','`-separated float values.
> for `<@TOKENIZER-TYPE=SCALARS_FROM_DICT>`: a key into the sample NDict (inputs only).
> Example encoder input: `…<MOLECULAR_WEIGHT_IN_SOME_UNIT><@TOKENIZER-TYPE=SCALARS_LITERALS>0.3<@TOKENIZER-TYPE=AA><BINDING_AFFINITY_NANOMOLAR><@TOKENIZER-TYPE=SCALARS_LITERALS><MASK>…`
> (a known scalar `0.3` is fed in; a `<MASK>` marks the scalar to be predicted as output).

You opt in by passing `key_out_scalars=ENCODER_INPUTS_SCALARS` to the tokenizer call
(`op.py:471, 538-542`), which fills `.values`/`.valid_mask`.

> **VERIFIED GAP:** despite the machinery, **no shipped example feeds a numeric input scalar.** Grep
> for `SCALARS_LITERALS` across `mammal/` returns exactly two hits — both on the **label** side of
> DTI and cell-line-drug-response (§2.2). DTI's *input* uses a bare `<MASK>` (no scalar value;
> `dti.../task.py:128-133`), and the gene-expression input uses **ranked gene-name tokens, not
> expression values as scalars** (`cell_line_drug_response/task.py:146-152` — genes are sorted by
> value, then only the names `[GENE]` are tokenized). So `project_input_scalars` is present in the
> weights but exercised by *zero* public tasks. If Quiver wants to inject a real-valued covariate
> (dose, concentration, an assay readout) into a prompt, this is the intended hook — but it is
> **untested upstream**, so we'd be first.

### 2.2 Numeric OUTPUTS — the `scalars_prediction_head` (regression via encoder-only)
This is how DTI pKd and cell-line IC50 are produced — **not** via generation. `mammal/model.py:151-163`
builds an MLP head; `forward_encoder_only` (`model.py:235-265`) runs it:

```python
# model.py:260
if self.scalars_prediction_head is not None:
    batch_dict[SCALARS_PREDICTION_HEAD_LOGITS] = \
        self.scalars_prediction_head(model_out["last_hidden_state"]).squeeze(dim=2)
```
`SCALARS_PREDICTION_HEAD_LOGITS = "model.out.scalars_prediction_logits"` (`keys.py:54`).

**Training-target encoding** (DTI, `dti_bindingdb_kd/task.py:151-168`; identical in
`cell_line_drug_response/task.py:172-188`): the *label* is written as a scalar literal, and the model
learns to emit it at position 0 of the scalar head:
```python
ground_truth_value = (ground_truth_value - norm_y_mean) / norm_y_std      # normalize
sample_dict[LABELS_STR] = (
    f"<@TOKENIZER-TYPE=SCALARS_LITERALS>{ground_truth_value}<@TOKENIZER-TYPE=AA>"
    + "".join(["<PAD>"] * (encoder_input_max_seq_len - 1)))
```
**Readout** (`dti_bindingdb_kd/task.py:191-212`): take `scalars_preds[:, 0]`, de-normalize:
```python
batch_dict["model.out.dti_bindingdb_kd"] = scalars_preds[:, 0] * norm_y_std + norm_y_mean
```
This matches our `mammal_quiver/dti.py` exactly, and explains the norm-constant gotcha
(cold-split `5.794/1.338` vs PEER `6.286/1.542`): they are the y-normalization used at train time and
must be reused at inference or the pKd is silently wrong.

> **Why the per-target heads (wdr91/pgk2) needed the P(<1>) readout, settled.** DTI is a *regression*
> task → it uses `forward_encoder_only` + the **scalar head**. The wdr91/pgk2 checkpoints carry a
> DTI-shaped config (a `scalars_prediction_head`) but were trained as **classifiers** — so their
> scalar head is untrained/vestigial (Phase 3 found it bit-identical to base → AUROC 0.43, a false
> negative). The trained signal lives in the **generative** path, hence `binder_prob` reads P(<1>),
> not the scalar head. The two numeric mechanisms being separate is the whole reason that trap
> existed.

---

## 3. The classification readout (the "P(<1>) trick") — task-token + sentinel construction

Every MAMMAL **classifier** (molnet BBBP/ClinTox, carcinogenicity, protein-solubility, TCR-epitope,
PPI, scRNA cell-type, and the wdr91/pgk2 per-target heads) uses the identical pattern. Two moving
parts: **(a)** a prompt that places a **task token** then `<SENTINEL_ID_0>` before the entity, and
**(b)** a readout that reads `SCORES[classification_position=1, token_id("<1>")]`.

### 3.1 Prompt construction (task token varies; structure is fixed)
| Task | Task token | Prompt source |
|---|---|---|
| MoleculeNet | `<BBBP>` / `<TOXICITY>` / `<FDA_APPR>` | `molnet/molnet_infer.py:112` |
| Carcinogenicity | `<CARCINOGENICITY>` | `carcinogenicity/task.py:95` |
| Protein solubility | `<SOLUBILITY>` | `protein_solubility/task.py:111` |
| PPI (base model) | `<BINDING_AFFINITY_CLASS>` | README / `begginer_inference.ipynb` |
| scRNA cell-type | (none; sentinel only) | `scrna_cell_type/task.py:161` |
| **WDR91 / PGK2** | `<WDR91_ASMS>` / `<PGK2_ASMS>` / `<PGK2_DEL>` | `mammal_quiver/wdr91.py:78` |

Canonical small-molecule classifier prompt (`molnet_infer.py:112`):
```python
f"<@TOKENIZER-TYPE=SMILES><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
f"<{task_name}><SENTINEL_ID_0><@TOKENIZER-TYPE=SMILES@MAX-LEN=2100>"
f"<SEQUENCE_NATURAL_START>{smiles_seq}<SEQUENCE_NATURAL_END><EOS>"
```
Our `mammal_quiver/wdr91.py:_prompt` reproduces this exactly with the per-target token — that match
is *why* the reverse-engineered readout is trustworthy.

### 3.2 Readout (verbatim, `molnet/molnet_infer.py:60-83` — identical logic in every task.py)
```python
negative_token_id = tokenizer_op.get_token_id("<0>")
positive_token_id = tokenizer_op.get_token_id("<1>")
classification_position = 1                                   # <-- THE position
scores = decoder_output_scores[classification_position, positive_token_id]   # = P(<1>)
pred   = {negative_token_id: 0, positive_token_id: 1}.get(int(decoder_output[classification_position]), -1)
```
`decoder_output = batch_dict[CLS_PRED][0]`, `decoder_output_scores = batch_dict[SCORES][0]`
(`molnet_infer.py:99-103`). Three tasks also expose a **normalized** score (a real probability over
the two classes) — `carcinogenicity/task.py:175`, `protein_solubility/task.py:204`:
```python
normalized_score = P1 / (P1 + P0 + 1e-10)        # P1=score(<1>), P0=score(<0>) at position 1
```
The solubility docstring (`task.py:181-189`) warns the *raw* `P(<1>)` can be tiny even when the class
is chosen — so for ranking, the **normalized** form is the more honest score. (Our `binder_prob`
returns the raw P(<1>); for cross-compound ranking that's fine since it's monotone per fixed prompt,
but if we ever threshold, switch to the normalized form.)

Multi-class works the same with N class tokens: scRNA reads `SCORES[1, [all 11 CL: ids]]` and argmaxes
(`scrna_cell_type/task.py:242-268`, `ALL_CLASS_LABELS` are 11 Cell-Ontology tokens like
`[CL:0000794]`).

---

## 4. Example training tasks — data format + reproducibility

Run a fine-tune with: `python mammal/main_finetune.py --config-name config.yaml --config-path
examples/<task>` (Hydra; `main_finetune.py:83-144`). It loads base MAMMAL, builds the task's
LightningDataModule, fits, and saves `best_epoch.ckpt` + the (token-extended) `tokenizer/` into
`model_dir` (`main_finetune.py:142-144`, `save_in_model_dir:16-35`). Inference scripts then load
`<dir>/best_epoch.ckpt` + `<dir>/tokenizer`. The fine-tune **adds new special tokens** to the
tokenizer (`load_and_update_tokenizer_op:147-162`) — which is why inference must load the
*fine-tuned* tokenizer, not the base one (carcinogenicity `main_infer.py:28-31` says so explicitly).

| Example | Task / head type | Input format | Label format | Data source (auto-DL?) | Reproducible off-the-shelf? |
|---|---|---|---|---|---|
| **`dti_bindingdb_kd`** | regression (scalar head) | `target_seq` (AA, ≤1250) + `drug_seq` (SMILES, ≤256); input has a bare `<MASK>` scalar slot | `<…SCALARS_LITERALS>{(pKd−μ)/σ}` | TDC `DTI(name="BindingDB_Kd")`, `harmonize_affinities("max_affinity")`, log, **cold-split** (`pl_data_module.py:101-136`) | **YES** — TDC auto-downloads; config ships μ/σ=5.794/1.338. Published ckpt exists. |
| **`protein_solubility`** | binary classifier (generative) | `protein_sequence` (AA, ≤1250), task token `<SOLUBILITY>` | `<SENTINEL_ID_0><{0 or 1}><EOS>` | local `./example_solubility_data` path (`config.yaml:14`); DeepSol/Zenodo `1162886` per README | **Partly** — data is **not** auto-downloaded (must fetch the .tab files; our repo gitignores them, auto-fetched on first run via TDC harness). Published ckpt exists. |
| **`carcinogenicity`** | binary classifier (generative) | `drug_seq` (SMILES, ≤1250), task token `<CARCINOGENICITY>` | `<SENTINEL_ID_0><{0 or 1}><EOS>` | TDC `Tox` single-pred (`pl_data_module.py:9`) | **Train/eval reproducible** (TDC auto-DL), but **NO published checkpoint** → can't verify off-the-shelf without running the fine-tune. |
| **`cell_line_drug_response`** | regression (scalar head) | `genes`+`expressions`+`drug_smiles`; **genes ranked by expression, only names tokenized** (`task.py:140-152`); h5ad/AnnData at infer | `<…SCALARS_LITERALS>{IC50}` | TDC `DrugRes(name="GDSC2")` (`main_infer.py:120-155`) | **Train reproducible** (TDC auto-DL GDSC1/2), **NO published checkpoint.** Needs `anndata`/`scanpy`. |
| **`scrna_cell_type`** | 11-class classifier (generative) | scRNA cell → "double-sorted GeneFormer" gene-name sequence (`task.py:222-240`) | `<SENTINEL_ID_0>[CL:…]<EOS>` (Cell-Ontology) | Zheng-68k h5ad; helper `data/Zheng68k_to_anndata.py`; infer needs a preprocessed `.h5ad` | **Train reproducible** (with the prep script), **NO published checkpoint.** Needs `anndata`/`scanpy`. |

**Bottom line on reproducibility** (matches `mammal_checkpoint_survey.md`): of the 5 example tasks,
only **DTI** is fully reproducible *and* has a published checkpoint to verify against. Protein
solubility is verifiable (we did: acc 0.734 / AUROC 0.829) once you supply the data. **Carcinogenicity,
cell-line-drug-response, and scRNA cell-type ship training code only — no weights** — so "does MAMMAL
do X" for those is unanswerable without running the fine-tune yourself (each is a standard
1-GPU AdamW lr=1e-5 cosine-warmup job per the configs; non-trivial but not exotic). For a Quiver
in-house per-target fine-tune, **`carcinogenicity` (SMILES→binary, generative readout) is the
closest template** — it is exactly the "hit/non-hit on screening data" shape, the data module just
swaps TDC `Tox` for our parquet via `OpReadDataframe(columns=["Drug","label"])`.

---

## 5. Implications / cross-checks for Quiver

- **Our `mammal_quiver` wrappers are faithful.** `dti.predict_pkd` = the upstream DTI
  `forward_encoder_only` + scalar-head de-norm path; `wdr91.binder_prob` = the upstream molnet
  generative P(<1>)@pos1 readout with the per-target token. Nothing in the source contradicts the
  Phase 1-4 findings; it explains them.
- **Generation is the real unknown.** The paper sells molecule/antibody/PPI **generation**; the code
  ships **none of it** — not a checkpoint, not an example, not a test. If Quiver cares about
  metadata→molecule generation (the Atlas / "how fast to molecules" question), MAMMAL gives us a
  decoder and a tokenizer but **zero reproducible recipe or validation.** Any claim that "MAMMAL
  generates X" must be earned by our own harness (write an open-ended prompt, raise `max_new_tokens`,
  beam/sample via the kwargs `generate()` forwards) and then *measured* — expect to be in
  unvalidated territory. This is the highest-leverage thing this lane surfaces.
- **Numeric covariates are injectable but untested.** `project_input_scalars` (`Linear(1→768)`,
  added to embeddings) + the `SCALARS_LITERALS`/`SCALARS_FROM_DICT` syntax is the intended way to put
  a real number (dose, concentration) into a prompt. **No public task uses it on the input side.** If
  we want it, we're the first to exercise it — validate on a toy monotonic task before trusting it.
- **Don't feed traces.** Confirmed at the code level: the modalities are AA / SMILES / GENE(ranked) /
  scalars / CELL_ATTRIBUTES. There is no time-series / trace tokenizer. (As the project memory says,
  traces are the V1-T project's job, never MAMMAL.)

### File reference index (all repo-relative to the clone / installed pkg)
- Generation + scalar injection + load: `mammal/model.py` (`generate`:165, `forward_encoder_only`:235,
  `_calculate_inputs_embeddings`:325, `project_input_scalars`:137, `scalars_prediction_head`:151,
  `from_pretrained`:385).
- Output/scalar keys: `mammal/keys.py` (`SCORES`/`LOGITS`/`CLS_PRED`:41-45, scalar keys:54-67).
- Classification readout: `mammal/examples/molnet/molnet_infer.py:60-138`; `carcinogenicity/task.py`,
  `protein_solubility/task.py`, `scrna_cell_type/task.py` (`process_model_output` + `data_preprocessing`).
- Regression readout: `mammal/examples/dti_bindingdb_kd/task.py:103-212`,
  `cell_line_drug_response/task.py:84-231`, `…/main_infer.py`.
- Numeric syntax docstring: fuse `…/modular_tokenizer/op.py:401-413` (installed pkg).
- Fine-tune entry: `mammal/main_finetune.py`; per-task `config.yaml` + `pl_data_module.py`.
- Canonical inference notebook: `tutorials/begginer_inference.ipynb`; README §"Protein-Protein
  Interaction". Shared prompts: `mammal_vllm/examples/example_prompts.py`.
