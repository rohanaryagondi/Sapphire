# ProTrek-650M on Track 1 (protein family clustering) — tested, NOT a clustering upgrade; but its TEXT modality cracks the function-defined families, 2026-06-15

Phase B of the overnight campaign. **ProTrek-650M** (westlake-repl, MIT) is a trimodal (sequence + structure
+ text) contrastive PLM — the SaProt lab's function/text-aware model. Hypothesis: the function/text modality
is the lever to separate the **function-defined families (E3 ligases, nuclear receptors)** that pure-sequence
models (ESM-2/MAMMAL) plateau on (~0.5). Run sequence-only (`get_protein_repr`, no Foldseek) on the same
40-gene CRISPR-N panel as the rest of the Track-1 ladder. g5.xlarge, rc=0 after 2 toolchain fixes (faiss-cpu
+ pandas/tqdm — the repo's requirements.txt omits both).

## Headline: **Two answers. As a clustering embedding ProTrek is NOT an upgrade (0.725 < ESM-2-650M 0.875, and it FAILS E3/NR). But its text-anchored zero-shot family assignment DOES crack the function-defined families (E3 0.75, NR 1.0) — a different, genuinely useful protocol.**

### (1) Protein-embedding NN-recall (apples-to-apples with the Track-1 ladder)
| Family | ProTrek (centered) | ESM-2-650M best-layer (ref) | ESM-3 (ref) |
|---|---|---|---|
| kinase | 0.917 | — | — |
| **gpcr** | **1.000** | — | (SaProt/ProstT5 1.0) |
| ion_channel | 0.875 | — | — |
| nuclear_receptor | 0.500 | — | **1.0** |
| **e3_ligase** | **0.000** | (~0.5 ceiling) | 0.5 |
| lipid_kinase / phosphatase | 0.0 / 0.0 | (singletons) | — |
| **overall** | **0.725** (raw 0.70) | **0.875** | 0.875 |

- ProTrek's single final contrastive repr gives **overall NN-recall 0.725 — below ESM-2-650M best-layer
  0.875**, and ≈ ESM-2's *last-layer-centered* 0.75 (the fair comparison, since ProTrek exposes no
  intermediate layers to sweep). As a clustering embedding it is **not an upgrade**.
- It **fails the very families it was meant to crack**: e3_ligase **0.0** (worse than the ~0.5 universal
  ceiling — the function-aligned projection actively *scatters* the heterogeneous E3 grab-bag in
  protein-protein space), nuclear_receptor 0.5 (vs ESM-3's 1.0).
- GPCR **1.0** and ion_channel 0.875 are strong — consistent with structure/function-aware models nailing
  GPCRs (SaProt, ProstT5 also 1.0).

### (2) Text-anchored zero-shot family assignment (ProTrek's unique modality)
Assigning each protein to the nearest **family-description text embedding** (`get_text_repr`) — a protocol
only a text-aware model can do:
| | overall | e3_ligase | nuclear_receptor |
|---|---|---|---|
| text-anchored accuracy | **0.775** | **0.75** | **1.00** |

**This is the real finding:** the text modality cracks the function-defined families that defeat sequence-only
clustering — **E3 ligase 0.5(ceiling)→0.75, nuclear receptor →1.0** — but as a *zero-shot text classifier*
(match protein↔family-description), NOT as a protein-protein clustering embedding.

## Verdict
- **Track-1 winner unchanged: ESM-2-650M (best-layer 0.875).** ProTrek is not a clustering-embedding upgrade.
- **New tool noted:** for the function-defined families (E3 ligases, nuclear receptors) that are the
  documented Track-1 ceiling, **ProTrek's text-anchored assignment is a viable approach** (E3 0.75, NR 1.0) —
  the function/text modality helps, just via text-classification not NN-recall. If Quiver needs to assign
  function-defined families at scale, this is the method to use, not sequence clustering.
- Confirms (again) that GPCRs are solved by structure/function-aware models (ProTrek/SaProt/ProstT5 all 1.0).

## Scorecard impact
Track 1: ESM-2-650M stays the winner. Add ProTrek to the registry as **tested, not adopted for clustering
(0.725 < 0.875), but its text-anchored family assignment cracks E3/NR (0.75/1.0)** — the first method that
beats the function-defined-family ceiling, via the text modality. MIT, weights ship, sequence-only path works.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/protrek/protrek_result.json`; eval
`aws/protrek_eval.py`; instance `i-05094b1e44d133882` self-terminated (rc=0). ~$0.4 incl. 2 toolchain-fix
relaunches.
