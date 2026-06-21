# Boltz-2 testing for Quiver — handoff package

**Created 2026-06-08 by the prior Claude session.** This folder is self-contained;
you don't need anything else from the repo to do the science here. Read this top
to bottom before running anything.

The science: **does Boltz-2 succeed where MAMMAL and ConPLex failed on Quiver's
voltage-gated sodium channel (Nav) targets?** If yes, that's the first off-the-shelf
DTI tool that actually works on Nav binder triage for Quiver — a real result.
If no, the answer to "what off-the-shelf DTI works for Quiver" becomes simply
"nothing does — only an in-house Quiver Nav fine-tune helps."

---

## 1. Strategic context — why this matters

Quiver Bioscience has been evaluating IBM's MAMMAL biomedical foundation model
(`ibm/biomed.omics.bl.sm.ma-ted-458m`) for drug discovery on their CNS targets.
After ~6 weeks of work the bottom line is:

**MAMMAL's DTI head fails on Nav1.8 — and the failure generalises.** Specifically:

- **MAMMAL** on Nav1.8 binder-vs-decoy AUROC = 0.43 (chance). Cause: the
  BindingDB_Kd dataset MAMMAL was trained on contains **0 Nav1.8 pairs** and only
  5 incidental rodent SCN-family pairs out of 42,236 total. Even on targets with
  rich training data, MAMMAL is bimodal — 3 of 6 well-trained targets work
  (RORC 0.97, CA2 0.87, Adrb2 0.87) but 3 don't (BRAF 0.47, HRH1 0.40, mTOR
  collapses on matched decoys). The "memorisation" hypothesis was **refuted** by a
  scaffold-shift test — ceiling wins are real generalisation, but the underlying
  mechanism behind the bimodality remains open.
- **ConPLex** (the other major open zero-shot DTI model) was tested across all 9
  Nav paralogs (Nav1.1–Nav1.9) — **mean AUROC 0.44, 0/9 above 0.60**. ConPLex is
  pan-Nav blind. On Graham's off-target sanity check, the strongest "specificity"
  signal in the table belonged to *ibuprofen* (a decoy), not the actual Nav
  blockers. **Zero-shot DTI failure on Nav-like targets is a property of the
  BindingDB-trained tooling space, not MAMMAL-specific.**
- **PROTON** (Zitnik Lab CNS-relational FM) was tested on the family-clustering
  panel and *also* lost — NN-recall 0.487 vs MAMMAL/ESM-2 0.750. PROTON's
  KG-embedding objective doesn't optimize for protein-family similarity.

**Boltz-2 is the last off-the-shelf model that could plausibly work** because it
is structurally different — co-folding + affinity head, not a contrastive PLM
trained on the same BindingDB. The earlier MAMMAL + ConPLex failures all reflect
the same training-data gap; Boltz-2 doesn't share that gap.

**The decision rule:** if Boltz-2 binder-vs-decoy AUROC on Nav1.8 is ≥ 0.70, it's
a real Quiver-relevant win — first off-the-shelf model to actually triage Nav
binders. If Boltz-2 also fails (AUROC ~0.5), Quiver's only lever for Nav binder
triage is an in-house fine-tune on Quiver's own Nav data.

What's been done already: 2 of 5 sanity-check complexes succeeded on a prior
g5.xlarge run — ADRB2/propranolol prob=0.997, DRD2/haloperidol prob=0.988 (both
real known binders, prob ~0.99 confirms the model is sane on easy pairs).
**Quiver-relevant Nav-family + mTOR tests have NOT been run yet.** That's the job.

---

## 2. What's in this folder

```
docs/boltz_handoff/
├── README.md                          ← you are here
├── PROMPT.md                          ← paste-ready prompt for a new Claude session
├── data/
│   ├── 00_sanity_complexes.json       ← 4 small-protein decoy pairs; smoke test for install
│   ├── 02_nav1.8_only.json            ← 11 complexes: Nav1.8 × (7 blockers + 4 decoys) — START HERE
│   ├── 03_mtor_panel.json             ← 7 complexes: mTOR × (3 inhibitors + 4 decoys)
│   ├── 04_suzetrigine_selectivity.json← 9 complexes: suzetrigine × all 9 Nav paralogs (selectivity)
│   └── 01_nav_full_panel.json         ← 99 complexes: all 9 paralogs × all 11 drugs (FULL test, expensive)
└── scripts/
    ├── boltz_runner.py                ← hardened runner; loops over complexes, parses affinity, writes results.json
    └── score_results.py               ← reads results.json + prints per-target AUROC vs baselines
```

All `data/*.json` files have the protein sequences and SMILES pre-fetched —
**no PubChem or UniProt lookups needed**. (PubChem's API deprecated `IsomericSMILES`
in mid-2026; only `SMILES` works now. Already handled.)

---

## 3. The plan — three increasingly-ambitious tests

Pick the smallest test you can afford. Each builds on the prior.

### Test A — sanity (4 complexes, ~20 min, free if local CPU works) — `00_sanity_complexes.json`
4 GPCR×decoy pairs (ADRB2, DRD2; ~440-aa proteins). Should return prob_binder
~0.5 or lower for all 4 (decoys are non-binders). **The point isn't the numbers —
it's that Boltz-2 actually runs and writes a results.json.** If this works,
the install is correct and the runner works.

### Test B — Nav1.8 binder-vs-decoy AUROC (11 complexes, ~1 hr GPU) — `02_nav1.8_only.json`
The headline test. Nav1.8 (the suzetrigine target, 1956 aa) × 7 Nav blockers
(positives) + 4 unrelated decoys (negatives) → compute single-target AUROC.
**This is the number that decides whether Boltz-2 beats MAMMAL/ConPLex on the
Quiver-relevant target.** Bar to clear: AUROC ≥ 0.70.

### Test C — pan-Nav selectivity for suzetrigine (9 complexes, ~50 min) — `04_suzetrigine_selectivity.json`
suzetrigine × all 9 Nav paralogs. Quiver's lead Nav1.8-selective drug. If
Boltz-2 ranks Nav1.8 prob highest among the 9 paralogs (and ranks Nav1.5
lowest — Nav1.5 is the cardiotoxicity off-target), it's correctly modeling
*selectivity*, which is huge for Quiver's mechanism-of-action story.

### Test D — mTOR triage (7 complexes, ~40 min) — `03_mtor_panel.json`
mTOR × 3 rapalogs + 4 decoys. mTOR was MAMMAL's other Quiver-relevant fail
(matched-decoy AUROC 0.56, off-target Δ −1.12). Does Boltz-2 do better?
Same bar: AUROC ≥ 0.70.

### Test E — full Nav family panel (99 complexes, ~8 hr) — `01_nav_full_panel.json`
All 9 paralogs × 11 drugs. Only run if A/B/C/D produce promising results AND
budget permits. Gives per-paralog AUROC + the full drug-target matrix for
selectivity analysis.

**Recommended sequence: A → B → (if B promising) C → (if C promising) D → maybe E.**
Stop after B if AUROC ≪ 0.70 — that's the result; no need to spend more.

---

## 4. How to run Boltz-2 (environment-agnostic)

You'll need a CUDA-capable GPU (A10G 24 GB or better; not strictly required but
strongly recommended — the prior CPU-only attempts were unviable).

### 4.1 Install Boltz + the CRITICAL kernel-ops package

Boltz 2.2.1 depends on `cuequivariance_torch` for some operator paths.
`cuequivariance_torch` *itself* depends on `cuequivariance_ops_torch` (a
separate distribution containing the actual CUDA kernels). **Installing
`cuequivariance-torch` alone is NOT enough — Boltz will crash with
`ModuleNotFoundError: cuequivariance_ops_torch` on certain pair sizes.**

```bash
# Use a venv with --system-site-packages if you have a CUDA-prebuilt torch
# (e.g. AWS DL AMI). Otherwise plain `python -m venv` is fine.
python -m venv .boltz_venv
source .boltz_venv/bin/activate
pip install --upgrade pip

pip install boltz                          # the model itself, ~2-3 min
pip install cuequivariance-torch==0.10.0   # the wrapper, pinned to known-working
pip install cuequivariance-ops-cu13-torch  # THE CRITICAL piece — CUDA kernels.
                                           # If you're on CUDA 12 not 13, use
                                           # cuequivariance-ops-cu12-torch instead.

# Verify the import path Boltz hits at runtime:
python -c "from cuequivariance_torch.primitives.triangle import triangle_multiplicative_update; print('OK')"
```

If that final `python -c` prints OK, you're good. If it raises ImportError,
the ops package isn't installed correctly — try the other CUDA version
(`cu12` vs `cu13`).

### 4.2 Smoke-test on the sanity panel

```bash
mkdir -p /tmp/boltz_out
BOLTZ_OUT=/tmp/boltz_out python scripts/boltz_runner.py data/00_sanity_complexes.json
```

Expect: 4 prob_binder values near 0.5 or below (these are decoy pairs), no
crashes. Wall time ~5-10 min on A10G after weights download.

### 4.3 Run Test B (Nav1.8) and score it

```bash
BOLTZ_OUT=/tmp/boltz_out_nav python scripts/boltz_runner.py data/02_nav1.8_only.json
python scripts/score_results.py /tmp/boltz_out_nav/results.json
```

Expected output: per-target AUROC table, off-target matrix, and a VERDICT
line stating whether Boltz-2 clears the 0.70 bar on Nav1.8.

### 4.4 The runner's environment variables

```
BOLTZ_OUT                    where to write results.json + per-complex dirs (default: /mnt/rohan/boltz_out)
BOLTZ_CACHE                  Boltz weight cache (default: /mnt/rohan/boltz_cache); first run downloads ~10 GB
HF_HOME                      HuggingFace cache (default: /mnt/rohan/boltz_hf)
BOLTZ_PREFLIGHT_TIMEOUT_S    first-complex wall-clock cap, default 3600 (1 hr; includes cold MSA queue)
BOLTZ_PAIR_TIMEOUT_S         per-subsequent-complex cap, default 900 (15 min)
```

If you're not on the EBS volume the prior runs used, you'll want to override
`BOLTZ_OUT`, `BOLTZ_CACHE`, and `HF_HOME` to writable local paths.

---

## 5. Gotchas — landmines hit during the 7-launch saga

These are documented as "things to NOT learn the hard way." All are addressed
in the runner; flagging here so you know why the code is the way it is.

| # | Gotcha | Why it matters |
|---|---|---|
| 1 | **`cuequivariance-torch` ≠ `cuequivariance-ops-torch`** | The wrapper without the ops package crashes on `triangle_multiplicative_update`. Install BOTH (see §4.1). |
| 2 | **Boltz has no `--version` flag** | `boltz --version` returns "No such option." Use `importlib.metadata.version("boltz")`. The runner does this. |
| 3 | **CLI flag names**: `--sampling_steps` and `--diffusion_samples` (NO `_affinity` suffix) | Older docs / examples use `--sampling_steps_affinity` etc — those flags don't exist. The runner uses the correct ones. |
| 4 | **Big proteins (>1500 aa)**: Nav family is 1791–2016 aa, mTOR is 2549 aa | Boltz may take longer or hit memory limits. If a complex consistently times out or OOMs, consider running with the binding-domain window only (e.g. mTOR kinase domain ~aa 2100-2549) instead of full sequence. Prior MAMMAL work showed mTOR truncation alone wasn't the fix — but Boltz uses a different code path so re-test. |
| 5 | **MSA server queue** can take 10-20 min on first call | `--use_msa_server` uses ColabFold's hosted MMseqs2. The runner sets a 60-min preflight timeout for the first complex to accommodate this. Subsequent complexes reuse the cached MSA per protein. |
| 6 | **Cold weight download** ~10 GB; first run is slow | Use a persistent cache directory (`BOLTZ_CACHE`). Subsequent runs reuse. |
| 7 | **PubChem API change**: `IsomericSMILES` deprecated | All SMILES in `data/*.json` are pre-fetched; no PubChem call needed. |
| 8 | **Output schema fragility**: Boltz writes to `<odir>/boltz_results_<name>/predictions/<name>/affinity_<name>.json` | The runner has 4 glob patterns + a parse_warning field for forensics. If a future Boltz update changes the layout, you'll see "PREFLIGHT_PARSE_FAIL" with a directory listing — easy to fix. |
| 9 | **Atomic results.json writes**: runner uses `fsync` + `os.replace` | So you can read partial results mid-run without race conditions. |
| 10 | **bash + pipefail + tee bug** (only matters if you embed the runner in shell scripts) | NEVER do `cmd 2>&1 \| tee log \| tail` under `set -eo pipefail` — `tail` closes its read end, SIGPIPE to cmd, pipefail propagates, `set -e` kills before your error-handling. Use `cmd > log 2>&1; rc=$?; tail log; [ $rc -eq 0 ] \|\| ...`. |

---

## 6. How to interpret results

After `score_results.py` you'll see something like:

```
target     n_pos n_neg    AUROC    mean_pos   mean_neg      sep
----------------------------------------------------------------------
Nav1.8         7     4    0.821     0.842      0.213    +0.629   ← !!
```

That's the dream — AUROC 0.821 means Boltz-2 reliably ranks Nav blockers above
decoys for Nav1.8. **Compare to MAMMAL's 0.43 and ConPLex's 0.39.** If Boltz-2
hits ≥ 0.70, write it up immediately:

- Update `docs/meeting_followup_email.md` Q3 with the Boltz-2 result
- Add a writeup to `results/aws_eval/` or wherever you want
- Update `CLAUDE.md` state findings
- Mention in any open meeting notes

Realistic expectations: Boltz-2 might also fail. The 2 prior successes (ADRB2,
DRD2) were on small GPCRs with well-known drug pharmacology — easy pairs.
Nav-family proteins are larger and Boltz-2's training data emphasis is on
folded structures, not necessarily on Nav-specific binding. **A failure here
is still informative** — it tells Quiver that even structural co-folding
doesn't rescue Nav binder triage, so in-house Quiver Nav data is the only path.

Also worth checking: **off-target Δ** in the score output. If Boltz-2's
predictions are roughly the same for every drug on every Nav paralog (low
off-target Δ), that's the same drug-only-bias failure mode ConPLex showed.

---

## 7. The bigger Quiver narrative — where this fits

Put the Boltz-2 result into the existing chain of findings in
[`docs/meeting_followup_email.md`](../meeting_followup_email.md) and
[`docs/meeting_followup_report.md`](../meeting_followup_report.md). The summary
table the report uses:

| Model | Nav1.8 AUROC | Verdict |
|---|---:|---|
| MAMMAL DTI (PEER) | 0.43 | fail — data gap; only 5 incidental rodent SCN pairs in BindingDB_Kd |
| ConPLex (zero-shot) | 0.39 | fail — pan-Nav blind (0/9 paralogs above 0.60) |
| PROTON | n/a | wrong test (PROTON does family clustering, ≠ DTI; loses there too 0.487 vs 0.750) |
| **Boltz-2** | **YOUR NUMBER HERE** | **YOUR VERDICT HERE** |

If Boltz-2 ≥ 0.70 → Quiver has a working off-the-shelf Nav triage tool.
If Boltz-2 < 0.60 → the conclusion sharpens to: nothing off-the-shelf works for
ion channels; the Quiver Nav fine-tune is the only path forward. **Either way,
the next major Quiver decision is informed.**

---

## 8. After you have results

1. Commit `results.json` outputs into `results/aws_eval/` (or wherever feels right)
2. Write a short summary doc — same format as `results/aws_eval/README.md`
3. Update the parent comparison: `docs/meeting_followup_email.md` Q3 (Boltz row),
   `CLAUDE.md` state findings, `NEXT_STEPS.md` item #2 Boltz row
4. If you got an AUROC ≥ 0.70 on Nav: that's a paper-worthy finding; alert Rohan
   to share with Matt/Graham/Mahdi/David

---

## 9. The user (Rohan) — context for collaboration

Rohan Aryagondi is a Yale sophomore at Quiver (rohan.gondi@quiverbioscience.com).
Plainspoken, technical. Knows MAMMAL paper, Sapphire vision, V1-T context.
Style preferences:
- Push back when something looks wrong; don't just defer
- Flag uncertainty explicitly; verify before claiming success
- Empirical results on Quiver's actual problems beat paper benchmarks
- Small reproducible scripts over heavy frameworks
- Don't burn money: ask before spinning up expensive compute
- Ask before deleting anything

Collaborators referenced in the work:
- Matt — MAMMAL evaluation lead
- Margalise — has a separate MAMMAL interface
- David — wet lab; CTO-ish role
- Mahdi — V1-T supervisor; sharp on physchem
- Graham — pushed the data-gap diagnosis; asked the off-target sanity check
- Caitlin — knowledge graph / Sapphire team
