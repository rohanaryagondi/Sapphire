# Plan — Wiring external / GPU Q-Models to predict live on AWS, end-to-end

**Date:** 2026-06-25
**Author:** Head Claude delegate (read-only scoping investigation)
**Status:** PROPOSAL for review (no code changes, no AWS launches were made)
**Scope source:** `sapphire-orchestrator/qmodels/` · `q-models/` · `RohanOnly/qmodels_run/` on `origin/main` @ `a72c853`

> **One-line answer to the question.** The CPU track is genuinely live. The GPU track has a **proven
> safety + lifecycle skeleton** (launch → ledger → teardown verified on a real t3.micro for ~$0.0017) but
> the part that actually *runs a model and returns its prediction is a stub*: the generic userdata template
> clones a **retired** repo, has **no weights**, calls eval scripts with the **wrong CLI contract**, and
> `job_status()` **never retrieves the S3 result**. The gap is "make the GPU job actually fold a complex and
> hand the JSON back," not "figure out how to launch EC2 safely" (that's done). Closing it is a focused
> piece of work, gated by one decisive single-model live run (Boltz-2).

---

## A. Current state per track (the honest ledger)

Routing is by `tier` in `sapphire-orchestrator/qmodels/registry.json`; the client (`client.py`) sends
`local-cpu` → sync HTTP, and `gpu-launch` / `endpoint` / `batch-ec2` → the async launcher
(`launcher.py`). Every return carries a `provenance` string so nothing fabricated is shown as real.

### What is genuinely LIVE today
| Tool(s) | Tier | Reality |
|---|---|---|
| `dti`, `bbbp`, `toxicity` (tracks); `chemberta2`, `maplight` (models) | `local-cpu` | **Real predictions, sync, $0** — POST to the vendored Explorer backend (`/api/predict/{track}`, CPU joblibs). Verified earlier (`bbbp` → p=0.501). Provenance `live-local`. Requires the local Explorer running (`qmodels/serve_local.sh`). |

### What is PROVEN-PLUMBING-BUT-DRY-RUN (the GPU/external track)
| Tool(s) | Tier | Reality |
|---|---|---|
| `structure_binding`, `selectivity`, `family_clustering` (tracks); `boltz2`, `balm`, `esm2` (models) | `gpu-launch` | Status `live` in the registry, **but the orchestrator only ever reaches `launcher.submit_job(...)` which defaults to `mode="dry-run"`** — it renders userdata + estimates cost and touches nothing. Provenance returned is `gpu-async` (a *job handle*, not a prediction). A real prediction has **never** run through this path. |
| `variant_effect`, `kg_hypothesis` (tracks); `proton`, `funncion` (models) | `endpoint` | Same launcher path (or a persistent FastAPI endpoint that is **not currently stood up**). Dry-run. |
| `generative` track; `comprehensive-admet`, `cardiogenai`, `ionchannel-finetune`, `atomica-dock`, `molformer`, `morgan-fp` | `gpu-launch`/`endpoint`/`local-cpu` | Status `eval`/`experimental` — addressable, honestly not wired to a routine path. |

### What is intentionally OFF
| Tool(s) | Status | Reality |
|---|---|---|
| `mammal`, `conplex` | `deprecated` | Client returns `provenance: unavailable` by design (≈chance on Nav substrate). Leave off. |

**The proven AWS plumbing covers exactly this and no more** (per `RohanOnly/qmodels_run/REPORT.md` +
`smoke_result.json` + `aws_ledger.jsonl`, run 2026-06-21):

- identity gate (account `255493511886`) ✓ · default-VPC read-only check ✓ · public-AMI resolve via SSM ✓
- budget gate ✓ · **launch one tagged self-terminating `t3.micro`** ✓ (`i-020f68795ea74a1be`, ledgered)
- `safe_terminate` by ledgered id ✓ · **verify `terminated`** ✓ · **total spend ≈ $0.0017**
- Refusal proven: `safe_terminate` *refuses* to touch `i-0d964d89be16a63f4` ("Rohan-R82-encode-gpu") and
  anything not in the ledger / present in the pre-existing snapshot.

What the smoke test deliberately did **not** exercise (the gap, precisely): no S3 bucket, no security group,
no GPU instance, **no model, no weights, no result retrieval.** It proved the *lifecycle skeleton*, not a
prediction.

---

## B. The exact gap to make GPU/external tools actually predict on AWS

Four concrete defects sit between "dry-run handle" and "real prediction returned." All are in
`sapphire-orchestrator/qmodels/launcher.py` unless noted.

### Gap 1 — The generic userdata template is a non-working stub (`_render_tool_userdata`)
It currently does:
```
git clone --depth 1 https://github.com/rohanaryagondi/Q-Models.git qm   # ← RETIRED repo (VENDORED.md says abandoned)
pip install -r requirements.txt                                         # ← MAMMAL stack, NOT the GPU model's deps
python3 <eval_script> --inputs /tmp/inputs.json --out /tmp/result.json  # ← WRONG CLI CONTRACT (see Gap 2)
```
Three things are broken here:
1. **Retired source.** `q-models/VENDORED.md` states the GitHub repo is abandoned; the code now lives only
   in-repo. A fresh EC2 has no git auth to a private repo anyway (the real userdata scripts stage code via
   **S3 presigned GET**, see `q-models/docs/AWS_INFRASTRUCTURE.md` §Gotchas #1).
2. **No model weights.** `q-models/.gitignore` excludes `models/` (~17 GB) and all HF/torch caches.
   The generic template never downloads weights. Boltz-2 pulls ~7–10 GB on first run; ESM-2-650M / funNCion
   pull their own; the MAMMAL checkpoints come via `scripts/download_models.sh`. **None of this happens.**
3. **Wrong deps.** `requirements.txt` is the MAMMAL exploration stack. The real GPU jobs install per-model
   (`pip install boltz`, torch `cu121/cu124`, etc.) — see the real userdata scripts.

### Gap 2 — Eval-script I/O contract mismatch (the registry lies about how to call them)
The registry maps each GPU tool to an `eval_script`, but those scripts do **not** take `--inputs/--out`.
Verified from the vendored sources:
| Registry `eval_script` | Actual invocation contract |
|---|---|
| `aws/boltz_runner.py` | `python boltz_runner.py <complexes.json>` (positional), reads `BOLTZ_CACHE`/`BOLTZ_OUT` **env**, writes `$BOLTZ_OUT/results.json`. The real run actually uses `boltz_runner_multimer.py`, not `boltz_runner.py`. |
| `aws/esm2_big_layer_sweep.py` | `python esm2_big_layer_sweep.py <panel_seqs.json> <out_dir>` (positional argv) |
| `aws/mission_eval.py` (funNCion) | **env-driven**: `OUT=...`, `DATA_TSV=...`, `ESM2_MODEL=...`, `MAX_VARIANTS=...`; no argparse |
| `aws/maplight_b3db_eval.py` | env-driven: `OUT=...`, `SEED=...`, `B3DB_LOCAL=...` |
| `aws/proton_eval.py` | env-driven: `PROTON_OUT=...`; needs the PROTON repo + NeuroKG + weights staged |
| `aws/comprehensive_admet_char.py` | no argv/env input parsing found — needs inspection before wiring |

**Implication:** there is no single generic `--inputs/--out` shim that works. Each model needs a small
**per-tool adapter** (input JSON → that script's expected argv/env + output path → normalized result). The
real userdata scripts already encode the correct per-model recipe — they are the spec to copy from.

### Gap 3 — No result retrieval or teardown loop (`job_status` is incomplete)
`launcher.submit_job` (live mode) launches + ledgers, then returns. `job_status(job_id)` only calls
`describe-instances` for the **instance state** — it **never downloads `s3://…/<job_id>/result.json`**, never
parses it, and never calls `safe_terminate`. So even if a job ran perfectly, the orchestrator could not
retrieve the prediction, and teardown relies *entirely* on the userdata `shutdown -h now` +
`instance-initiated-shutdown-behavior=terminate` backstop (which is real, but the explicit ledgered
`safe_terminate` + verify is not wired into the async lifecycle). The client's `poll()` just forwards to
`job_status`, so the orchestrator has no "done → here's the JSON" transition.

### Gap 4 — No scratch S3 bucket exists; no GPU security group / SSM-egress path verified
- The userdata templates write to `s3://sapphire-qmodels-scratch/<job_id>/result.json`. **That bucket was
  never created** (REPORT.md §6 lists it as deferred; final verification confirms "S3 buckets: none").
  Comment in `launcher.py` says "created on first use" but there is **no `create-bucket` call anywhere**.
- The smoke test used **no security group** (a bare instance with default egress is enough for `aws s3 cp`
  outbound on the default VPC). A GPU job also only needs outbound HTTPS (HF weights + S3), so the **default
  SG is likely sufficient** — but this must be confirmed, and the AWS_INFRASTRUCTURE doc's IMDSv2 +
  no-shared-SG rules honored. The instance needs an **instance profile / role** OR credentials to write to
  S3; the smoke instance wrote nothing, so the **S3-write IAM path for the launched instance is unproven.**

### (Not a gap, but a decision) Cold-start cost vs. a persistent EBS cache
The real Boltz runs mount a **persistent 100 GB gp3 volume** (`vol-066389517f2740f19`) holding
`boltz_cache/` (~7 GB weights) and `PROTON_strength/` — so they skip the 5–10 min cold weight download.
The Sapphire launcher's safety model is **create-only + teardown-by-ledger**; mounting a *pre-existing shared
volume* sits awkwardly with that (it's someone's data, AZ-locked, and not in our ledger). Two clean options:
- **(Recommended for first light) Cold-download per run** — slower (~10–15 min added) but self-contained and
  inside the create-only safety model. Fine for first proof + low call volume.
- **(Later, for routine use) A Sapphire-owned cache volume or a warm endpoint** — create our own small gp3
  cache volume (ledgered) or stand up the `explorer_endpoint` FastAPI server warm. Defer.

---

## C. Ordered steps (with rough effort + est. AWS cost)

Effort = focused engineering time. Cost = incremental AWS spend, us-east-1 on-demand.

| # | Step | What | Effort | AWS cost |
|---|---|---|---|---|
| **0** | **Pre-flight (read-only)** | Re-snapshot pre-existing AWS state; refresh the public DL-GPU AMI id (`Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)*`); confirm default VPC + subnet per AZ; confirm credentials write-scope (`s3`, `ec2 run/terminate`, `ssm get-parameter`). **No launches.** | 0.5 h | $0 |
| **1** | **Create the ledgered scratch bucket** | Add a `_ensure_bucket()` to `launcher.py` (create `sapphire-qmodels-scratch-<acct>`, ledger it, idempotent). Add a matching `safe_delete_bucket` guarded the same way as `safe_terminate`. | 1 h | ~$0 (<$0.01/mo S3) |
| **2** | **Solve the instance→S3 write path** | Either (a) attach a minimal **instance role** scoped to the one bucket prefix (cleanest; needs an IAM role — check the account allows it, AWS_INFRASTRUCTURE forbids touching *shared* IAM, a new scoped role is create-only) **or** (b) presigned PUT URLs generated launch-side and passed in userdata (the pattern the real scripts already use — **no IAM, recommended**). Pick (b). | 2 h | $0 |
| **3** | **Rewrite `_render_tool_userdata` to the proven pattern** | Port the validated structure from `q-models/aws/boltz_validation_userdata.sh`: hard-kill timer; `exec > log; set -x`; background 30s log uploader to S3; `wait_apt`; **stage code + inputs from S3 via presigned GET** (no git clone of the retired repo); per-model dep install; **per-tool entrypoint adapter** (Gap 2); atomic result upload via presigned PUT; `shutdown -h now`. | 1 day | $0 (rendering only) |
| **4** | **Per-tool adapters (start with ONE: Boltz-2)** | A small mapping per `gpu-launch` tool: registry inputs → the script's real argv/env + output path → `adapters.normalize`. Do **Boltz-2 only** first (`structure_binding`/`selectivity`); it's the headline tool and its userdata recipe is the best-documented. | 1 day (Boltz) + ~0.5 day each thereafter | $0 |
| **5** | **Finish the async lifecycle in `launcher.py` + `client.py`** | `job_status`: when instance is `terminated`/`shutting-down`, **download `result.json` from S3**, parse, set `status=done` + attach the prediction; call ledgered `safe_terminate` + verify as a belt; surface `done`→normalized row up through `client.poll`. Add a `wait_for(job_id, timeout)` convenience. | 1 day | $0 |
| **6** | **DECISIVE LIVE PROBE — one Boltz-2 complex** | End-to-end live: `QMODELS_GPU=on`, `mode="live"`, raise `QMODELS_BUDGET_CAP` to ~$5 for this job, **g6e.xlarge** (L40S 48 GB; the proven Boltz workhorse — NOT the registry's stale `g5.xlarge` default), one protein+ligand. Verify: launch → cold weight DL → fold+affinity → `result.json` to S3 → retrieve → normalized dossier row → **verified teardown** → ledger closed. | 0.5 day (mostly watching) | **~$1–3** (g6e.xlarge @ $1.86/hr × ~0.5–1.5 h incl. cold start) |
| **7** | **Generalize to the other live GPU tools** | Repeat steps 4+6 for `esm2` (family_clustering), `funncion`/`proton` (endpoint tier — decide launcher-per-call vs. one warm endpoint). funNCion + ESM run on cheaper boxes (ESM on g5/g6e; PROTON is CPU-only `t3.xlarge` $0.166/hr — cheap). | 0.5 day each | ESM ~$1–2; PROTON <$0.25 each |
| **8** | **Wire `gpu_enabled` into the real entry point + governance** | Today only the offline `live_engine` path touches the launcher and the front door uses the canned path. Decide the trigger (explicit only? budget-gated auto?), keep `QMODELS_GPU=off` as the safe default, and add a per-engagement budget ceiling above the per-job cap. Tests + a captured scenario. | 1 day | $0 |

**Through Step 6 (external Q-Models *proven* predicting live on AWS): ~4–5 focused days + ~$1–3 AWS.**
**Through Step 8 (the GPU track usable in routine runs): ~7–8 focused days + <$10 AWS total.**

---

## D. Risks & safety guards

**Already in place (keep, do not weaken):**
- Identity gate (account `255493511886`) before any create; profile `Rohan-Sapphire` only.
- Create-only + append-only ledger (`RohanOnly/qmodels_run/aws_ledger.jsonl`).
- **Teardown ONLY by ledgered id**, refused if pre-existing — no wildcard/tag/name terminate exists.
- Budget cap (`QMODELS_BUDGET_CAP`, default $0.50) gates live launches; dry-run is the default mode.
- Triple teardown backstop: userdata `shutdown -h now` + `instance-initiated-shutdown-behavior=terminate`
  + (to be wired in Step 5) explicit ledgered `safe_terminate` + verify.
- Inputs base64-encoded before reaching any shell (injection guard).

**New risks introduced by going live, with the guard for each:**
| Risk | Guard |
|---|---|
| GPU job hangs / leaks (g6e @ ~$1.86/hr) | Hard-kill timer in userdata (the real scripts use `(sleep N && shutdown)`) **sized to the per-job budget**; raise `QMODELS_BUDGET_CAP` *only* for the specific job, restore to $0.50 after. Background S3 log uploader for live visibility without SSH. |
| Cold weight download balloons wall-time | Per-job `max_minutes` ceiling enforced in budget math; the budget cap refuses the launch if est > cap. First runs cold by design (accepted cost). |
| Instance can't write S3 (IAM) | Use **presigned PUT URLs** (Step 2b) — no instance IAM role needed; matches the proven pattern. |
| Touching shared infra (the cardinal sin) | Default-VPC read-only check already HALTs if no default VPC; **never** create/modify SG/VPC/IAM that isn't ours; new resources are create-only + ledgered + namespaced `sapphire-qmodels-*`. |
| `g6e` InsufficientCapacity | Loop AZs a→c→d→b, fall back g6e.xlarge→g6e.2xlarge (AWS_INFRASTRUCTURE §capacity). |
| Stale registry defaults (`g5.xlarge`, wrong `eval_script`) | Fix the registry `instance_type` to `g6e.xlarge` for Boltz and correct the `eval_script`/entrypoint to the real runner as part of Step 4. |
| Front-door auto-launch surprises spend | Keep `QMODELS_GPU=off` default; gate live GPU behind explicit opt-in + per-engagement budget ceiling (Step 8). |

---

## E. Realistic ETA to "external Q-Models predicting live on AWS"

- **First decisive proof (one Boltz-2 complex, end-to-end live, retrieved + torn down):**
  **~4–5 focused engineering days**, **~$1–3 AWS**. This is the milestone that flips `structure_binding`
  from "proven plumbing / dry-run" to "proven prediction."
- **GPU track usable in routine orchestrator runs (Boltz + ESM + funNCion/PROTON wired, governance + tests
  + a captured scenario):** **~7–8 focused days total**, **<$10 AWS total.**
- **Critical path is engineering, not AWS** — the safety/lifecycle skeleton and CPU track are done; the work
  is (1) a correct userdata template, (2) per-tool entrypoint adapters, (3) the retrieval/teardown loop, then
  (4) one cheap live probe to de-risk it all.

---

## F. What I could NOT confirm from code/reports (would need to verify)

1. **The launched instance's S3-write IAM permission** — the smoke instance wrote nothing, so whether a
   tagged instance can write to S3 (via role or presigned URL) under this account is **unproven**. Step 2
   resolves it by choosing presigned URLs, but the presigned-PUT generation needs the *operator's* creds to
   have `s3:PutObject` on the bucket — confirm at Step 0.
2. **Whether the account permits creating a new (scoped) IAM role** — only matters if we reject presigned
   URLs; the plan avoids this by design.
3. **Exact GPU wall-time + cold-start for a single Boltz-2 complex on g6e.xlarge** — REPORT/registry quote
   "7–15 min warm, ~30–50 min cold" for panels; a single complex should be at the low end, but the $1–3
   estimate assumes ≤1.5 h including cold weight download. Step 6 measures it for real.
4. **`comprehensive_admet_char.py` input contract** — no argv/env parsing surfaced in the quick grep; needs
   a direct read before wiring (it's `eval`-status anyway, so not on the critical path).
5. **Persistent-cache-volume option** — `vol-066389517f2740f19` exists and holds warm Boltz weights, but it
   is not a Sapphire-owned/ledgered resource; the plan deliberately defers any reuse of it in favor of
   cold-download-then-(optionally)-own-cache, to stay inside the create-only safety model.
6. **The `endpoint`-tier serving model** — `explorer_endpoint_userdata.sh` exists (a FastAPI server for
   proton/funncion/boltz/etc.), but standing it up warm vs. launcher-per-call is an open design choice for
   Step 7; both are viable, neither is wired today.

---

### Appendix — key files

- `sapphire-orchestrator/qmodels/launcher.py` — the safety-critical async EC2 launcher (Gaps 1, 3, 4 live here).
- `sapphire-orchestrator/qmodels/client.py` — the two-speed router; `poll()` → `job_status` (Gap 3).
- `sapphire-orchestrator/qmodels/registry.json` — tool↔tier↔eval_script↔instance_type (stale defaults; Gap 2).
- `sapphire-orchestrator/qmodels/adapters.py` — output normalizer (already generic over `score_kind`; reusable).
- `q-models/aws/boltz_validation_userdata.sh` + `boltz_runner.py` — the **proven** real pattern to port from.
- `q-models/aws/{mission,proton,maplight_b3db,esm2_big_layer_sweep}_eval.py` — real entrypoints + their true I/O contracts.
- `q-models/docs/AWS_INFRASTRUCTURE.md` — canonical AWS rules, AMI, instance types, cost, gotchas.
- `q-models/scripts/download_models.sh` — how MAMMAL/HF weights are fetched (~17 GB).
- `RohanOnly/qmodels_run/REPORT.md` + `smoke_result.json` + `aws_ledger.jsonl` — proof of the lifecycle skeleton.
