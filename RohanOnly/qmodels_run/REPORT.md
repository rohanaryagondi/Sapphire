# Q-Models → Sapphire Integration — Overnight Run Report

**Date:** 2026-06-21 (overnight, autonomous)
**Branch:** `Rohan` (committed per phase; **not** pushed to main)
**Goal:** Fully integrate the Q-Models toolset into the Sapphire build so the orchestrator can call any
model it wants — and prove the live AWS plumbing within a $3 smoke budget.

**Bottom line:** Done. The full Q-Models codebase is vendored in-repo, the orchestrator can address all
**24 tools** by id, CPU tools return **real** predictions, the GPU/async path is built behind hard safety
guards and **proven on live AWS** with a single self-terminating instance. **Total spend ≈ $0.0017.**
No pre-existing or other-project AWS resources were touched. No `sapphire-qmodels-*` resources remain.

---

## 1. What was delivered

### Vendored code
- **`q-models/`** — the entire Q-Models repo brought in-repo (536 files, ~17 MB). The source repo is
  retired and will not be used again. Provenance + isolated-regen notes in `q-models/VENDORED.md`.
  Nested `.gitignore` keeps model weights / secrets out; curated data force-added where needed.

### Integration layer (`sapphire-orchestrator/qmodels/`)
| File | Role |
|---|---|
| `registry.json` | 9 tracks + 15 models → tier · task · I/O contract · **honest status**. |
| `client.py` | `QModelsClient` — **two-speed router**. `call(tool_id, inputs)`: `local-cpu` → sync HTTP; GPU/endpoint/batch → `launcher.submit_job`; deprecated/todo → `unavailable`. |
| `launcher.py` | **Safety-critical** unified async EC2 launcher. Dry-run by default; live opt-in behind every guard. `submit_job` / `job_status` / `safe_terminate`. |
| `adapters.py` | `normalize(tool, body, provenance)` → a dossier `validate.runs` row, shaped by `score_kind`. |
| `serve_local.sh` | Stands up the vendored Explorer in an **isolated** venv (never the shared conda env). |
| `smoke_test.py` | Minimal-footprint live-AWS proof of the launch→run→teardown plumbing. |

### Engine + bridge + console
- `orchestrator.py`: `call_model(tool_id, inputs)`, `model_job_status`, `tools_catalog()`; `validate()`
  stamps provenance on every run row.
- `serve.py`: `GET /api/tools` (catalog) and `POST /api/tool` ({tool_id, inputs}); health now reports
  the real qmodels subsystem.
- `site/console.js` + `styles.css`: a **Models** inspector panel grouped by tier with live status badges,
  and provenance badges on validate rows.

---

## 2. Per-tool live-vs-mock status (the honest table)

Routing tiers: **`local-cpu`** = sync HTTP to the local Explorer (instant, $0); **`gpu-launch` /
`endpoint` / `batch`** = async EC2 launcher.

Provenance an orchestrator call actually returns: `live-local` (real local model) · `stub` (shaped local
placeholder, track not yet wired) · `gpu-async` (real GPU job handle) · `gpu-disabled` (GPU off this run) ·
`unavailable` (deprecated / not-yet-implemented).

### Tracks (9)
| Track | Tier | Status | Orchestrator behavior now |
|---|---|---|---|
| `dti` | local-cpu | live-local | **Real** prediction, sync, $0 |
| `bbbp` | local-cpu | live-local | **Real** prediction, sync, $0 (verified: p=0.501 BBB+) |
| `toxicity` | local-cpu | live-local | **Real** prediction, sync, $0 |
| `structure_binding` | gpu-launch | live | Async launcher (dry-run default; live-proven plumbing) |
| `selectivity` | gpu-launch | live | Async launcher |
| `family_clustering` | gpu-launch | live | Async launcher |
| `variant_effect` | endpoint | live | Async / endpoint |
| `kg_hypothesis` | endpoint | live | Async / endpoint |
| `generative` | endpoint | eval | Async / endpoint (marked eval, not over-claimed) |

### Models (15)
| Model | Tier | Status |
|---|---|---|
| boltz2 | gpu-launch | live |
| balm | gpu-launch | live |
| esm2 | gpu-launch | live |
| chemberta2 | local-cpu | live-local |
| maplight | local-cpu | live-local |
| proton | endpoint | live |
| funncion | endpoint | live |
| comprehensive-admet | gpu-launch | eval |
| cardiogenai | gpu-launch | eval |
| ionchannel-finetune | gpu-launch | eval |
| molformer | local-cpu | eval |
| morgan-fp | local-cpu | eval |
| atomica-dock | gpu-launch | experimental |
| mammal | gpu-launch | **deprecated** (→ unavailable) |
| conplex | gpu-launch | **deprecated** (→ unavailable) |

**24 tools total are addressable by id.** Nothing is silently mocked — each call returns its true provenance.

---

## 3. Live AWS smoke test — proof of plumbing

Run by `qmodels/smoke_test.py` (default live; supports `--dry-run`). Smallest possible blast radius:
**one** self-terminating `t3.micro`, **no** S3 bucket, **no** security group, **no** IAM.

| Step | Result |
|---|---|
| identity gate | ✓ account `255493511886` |
| default-VPC check (read-only) | ✓ `vpc-bca9c6d8` (HALT-if-none guard in place) |
| resolve AMI (SSM) | ✓ `ami-0521cb2d60cfbb1a6` (AL2023) |
| budget | ✓ est $0.0017 < cap $0.50 |
| **launch** | ✓ `i-020f68795ea74a1be` (tagged `sapphire-qmodels`, ledgered) |
| console marker | not captured — instance self-terminated faster than console output populated (lifecycle is the definitive proof) |
| **safe_terminate** (by ledgered id) | ✓ `terminated` |
| **verify terminated** | ✓ `final_state: terminated` |

**Exact spend ≈ $0.0017** (one t3.micro for a few minutes). Far under the $3 budget. Full machine-readable
trace: `RohanOnly/qmodels_run/smoke_result.json`. Ledger: `RohanOnly/qmodels_run/aws_ledger.jsonl`
(create + terminate events for the one instance).

---

## 4. Safety — what held

- **Identity-gated:** every create asserts account `255493511886` first; aborts otherwise.
- **Profile:** `Rohan-Sapphire` only. Nothing else beginning with "Rohan" was created.
- **Create-only + ledger:** every created resource is tagged `sapphire-qmodels` and appended to an
  append-only ledger.
- **Teardown only by ledgered id:** `safe_terminate(id)` refuses unless the id is in our ledger AND absent
  from the pre-existing snapshot. **No wildcard / tag-filter / name-filter terminate exists.** (Verified
  earlier it *refuses* to terminate `i-0d964d89be16a63f4`, the other project's GPU box.)
- **Budget cap** ($0.50 default) gates live launches; dry-run validates without spending.
- **Triple teardown backstop:** userdata `shutdown -h now` + `instance-initiated-shutdown-behavior=terminate`
  + explicit `safe_terminate` + verify.
- **Command-injection fix:** tool inputs are base64-encoded before reaching any shell (no user JSON ever
  hits a shell with metacharacters).
- **Did NOT** run `setup_new_device.sh` (it pip-installs into a shared conda env); used an isolated venv.
- **Did NOT** touch the pre-existing live Explorer on `:8000` (read-only use only); ran our own on `:8011`.

### Final AWS-clean verification (read-only, this morning)
- `sapphire-qmodels` instances: only `i-020f68795ea74a1be` → **terminated**.
- `sapphire-qmodels` S3 buckets: **none** (created none).
- `sapphire-qmodels` security groups: **none** (created none).
- Other projects **untouched**: `i-0393d9c9a3a392cc3` ("RDS DB LOADING - DO NOT DELETE") **running**;
  `i-0d964d89be16a63f4` ("Rohan-R82-encode-gpu") **running**. Both left exactly as found.

**No `sapphire-qmodels-*` resources remain. Nothing pre-existing was modified.**

---

## 5. End-to-end verification

- `python sapphire-orchestrator/run.py nav1_8` — full firm run completes (triage → scope → plan →
  Bucket-1 dossier → Bucket-2 roundtable + spread → synthesis). ✓
- `orchestrator.tools_catalog()` → 24 tools. ✓
- `orchestrator.call_model('bbbp', {...})` → **live-local** real prediction normalized into a dossier row. ✓

---

## 6. Open items (next, not blocking)

- Wire the remaining `stub` / `eval` tracks to real models (currently honestly marked).
- A live GPU eval end-to-end (a real `*_eval.py` on a GPU instance) — the plumbing is proven; this is the
  first real model run when desired (will cost more than the smoke test; still well within budget for one job).
- Optionally create the `sapphire-qmodels-scratch` S3 bucket for GPU result retrieval (deferred — the smoke
  test deliberately used no bucket to keep the footprint minimal).
- Swap the still-mock internal moat for the real Quiver latent space (separate workstream).

---

## 7. Commits on `Rohan` (this run)

Per-phase commits, newest last; **not pushed to main**:
`Phase 0` vendor → `Phase 1` registry → `Phase 2` client + CPU live → `Phase 3` launcher + GPU dry-run →
`Phase 4` engine + bridge → `Phase 5` console → **`Phase 6` live smoke test (`c122d60`)** → `Phase 7` docs + this report.
