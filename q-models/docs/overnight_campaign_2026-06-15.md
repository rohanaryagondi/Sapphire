# Overnight CNS campaign — 2026-06-15 (data + new models)

**Goal (Rohan, 2026-06-15):** find more models to test; access more CNS data online (licenses all
fine; use Playwright if a source needs a browser); work autonomously overnight; be careful with AWS,
don't touch others' resources, respect budget; when done, write all docs to the repo, update the
website fully, and have a summary ready.

**Budget:** CUMULATIVE **$50** HARD CAP (~$32 spent → ~$18 AWS headroom). Region us-east-1.
**Two thrusts this time vs. the last campaign:** (A) **source CNS data online** (mostly free/headless),
(B) **test new models** in the track gaps. Phase C = docs + website + summary.

This file is the living campaign state the cron driver re-reads each fire. Update the STATUS column
as jobs land.

## Safety (every fire)
`unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; export AWS_DEFAULT_REGION=us-east-1`. Only
Owner=RohanAryaGondi resources + `s3://rohan-mammal-bootstrap-20260610-213029/`. NEVER touch others'.
Every instance: AMI ami-012ba162b9cd2729c, subnet subnet-93dd2ccb, SG sg-1b4dee62,
shutdown-behavior=terminate, 100GB gp3 root, tags Owner=RohanAryaGondi/Project=mammal-explorer; creds
via sed `__AKID__`/`__SECRET__` from `aws configure get` into /tmp then `shred -u`. Max 3 parallel.
≤2 toolchain-fix relaunches per model, then bank. If projected spend >$50, STOP launching + bank.

## Phase A — DATA (online; mostly $0 / headless / local; Playwright fallback)
Scout `a911570da762b64a3` returned (2026-06-15) with verified access methods. Slate:
| Task | Source | Access | STATUS |
|---|---|---|---|
| A1 `gtopdb_ionchannel` | Guide to PHARMACOLOGY — ion-channel ligand affinities (pKd/pIC50/pKi) + SMILES. Nav1.8=targetId 585 | REST API, headless, CC-BY-SA | **RUNNING (local)** — `experiments/pull_gtopdb_ionchannel.py` → `data/cns_ionchannel/` |
| A2 `clinvar_channelopathy` | ClinVar SCN/CACNA/GRIN missense (variant universe + pathogenicity; SCN10A=2,615 recs) | NCBI E-utilities, headless | **RUNNING (local)** — `experiments/pull_clinvar_channelopathy.py` → `data/cns_variants/` |
| A4 `funncion_variants` | funNCion S1/S2 — REAL GoF/LoF labels (2,771 usable: 1007 GoF/1764 LoF). **SCN10A: 44 variants, ALL "unknown" → confirms Nav1.8 build-don't-buy** | raw.githubusercontent, headless, GPL-3.0 | **DONE (local)** — `data/cns_variants/funncion/` |
| A3 docs-only loaders | Papyrus (60M, Zenodo DOI 10.5281/zenodo.13987985), BindingDB (563MB TSV 202606), ChEMBL bulk FTP | large → document loader, don't pull to laptop | TODO (data card w/ URLs + subset loader) |

## Phase B — NEW MODELS (AWS; scout-verified; ~$0.5–1 each; ≤2-fix cap)
| Task | Model | Track | Notes (scout-verified) | STATUS |
|---|---|---|---|---|
| B1 `protrek` | **ProTrek-650M** (trimodal seq+struct+text PLM) | 1 — crack E3-ligase/NR ceiling | MIT; weights ship (3.64GB); sequence-only `get_protein_repr` (no Foldseek); ProTrek's own toolchain (torch 2.0.1/cu118). NO layer sweep (final CLIP repr only) — scores raw+centered vs ESM-2 best-layer 0.875 | **LAUNCHED** i-07043650ea3c962b3 (g5.xlarge, watchdog 6000s) |
| B2 `ligunity` | **LigUnity** (2025 PL FM, ranking-tuned) | 2 — DTI ranking | Apache-2.0; HF fengb/LigUnity_*; **unicore/Uni-Mol install trap** (like DrugCLIP); check protein_ranking ckpt for pocket-free path | TODO (driver to build next; risky) |
| B3 `ctoxpred2` | CToxPred2 (multitask hERG/Nav1.5/Cav1.2) | 5 — ion-channel-aware tox | only verified ion-channel-TRAINED model; ligand-only, CPU-feasible, few traps; cardiac not CNS-channel | **BUILDER RUNNING** a17cebb3 |
| (opt) `drugform_dta` | DrugForm-DTA (uniqsar) | 2 — DTI control | CC-BY-4.0; BindingDB ckpt ships; torch 1.13 (isolate); likely Nav-blind | OPTIONAL stretch |

Deprioritized by scout: TxGNN/BioPathNet (DGL/TorchDrug hell, disease-axis), GEMS (needs structure),
FIRM-DTI (weights not released). MissION = portal-only oracle (Playwright benchmark, not a data feed).
(ChEMBL API confirmed back UP 2026-06-15 — DTIAM relaunch also viable if a DTI slot opens; add socket timeout.)

## Phase C — SYNTHESIS (when A+B processed OR budget exhausted)
- Write `results/<prefix>_characterization.md` for every model run; data cards for every dataset.
- Update `docs/models_tracks_scorecard.md` (the Quiver-facing report) + `docs/cns_model_performance_report.md`.
- Update the Explorer: `ui/explorer/tracks.json` + report if a model wins a track; data additions noted.
- Write `docs/overnight_summary_2026-06-15.md` — the summary for Rohan.
- Final teardown sweep (zero running Owner=RohanAryaGondi); commit; retry push; CronList→CronDelete the
  driver; STOP.

## Driver order each fire (first applicable, then stop)
1. Finished AWS job (S3 DONE appeared, no characterization) → download result+log, parse, write
   `results/<prefix>_characterization.md`, conservative scorecard update, commit (+try push), verify terminated.
2. Finished local data pull / builder → write data card / commit.
3. Built-but-unlaunched AWS eval (script exists, no DONE, none running for it, <3 jobs, budget ok) →
   compile, stage to S3, clear DONE, sed creds, launch, shred, arm a Monitor on its DONE.
4. Scout findings landed + a Phase-A/B task has no script yet + prereqs met + budget ok → spawn ONE
   builder subagent to write the eval/puller (no launch this fire).
5. Failed job (DONE rc!=0) within ≤2-fix cap → one fix + relaunch; else bank + document.
6. All A+B processed + instances terminated → Phase C synthesis + delete cron + STOP.
7. Nothing actionable → verify no strays, note progress, stop quietly.

## Receipts / spend ledger (running)
- Prior campaigns: ~$32 cumulative.
- This campaign: A1 GtoPdb $0 · A2 ClinVar $0 · A4 funNCion $0 (all local/headless).
- B1 ProTrek: launched i-07043650ea3c962b3 g5.xlarge ~$1/hr (watchdog caps ~1.6h) → budget after ~$33-34.
- [append as jobs run]
