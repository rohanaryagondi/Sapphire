# qmodels-aws-gpu — report (Task 2: GPU Q-Models predict on AWS)

**Branch:** `rohan/qmodels-aws-gpu` · **Built-By:** rohan · **Plan:** `docs/superpowers/plans/2026-06-25-qmodels-aws-wiring.md`

## What this PR is (and isn't)
Closes the 4 gaps that stopped the GPU/external Q-Models track from actually predicting on AWS — the
launch→ledger→teardown skeleton was proven, but the part that *runs a model and hands back its
prediction* was a stub. **This PR is the CODE + offline tests.** The single **live GPU proof run**
(Boltz-2, g6e.xlarge) is the separate step after this merges — it spends real $ and is run under the
full safety model, ledgered, teardown-verified.

## The 4 gaps, closed (`qmodels/launcher.py`)
- **Gap 4a — scratch bucket:** `ensure_bucket()` (idempotent, account-gated, CREATE-ONLY, ledgered;
  `sapphire-qmodels-scratch-<acct>`) + `safe_delete_bucket()` (mirrors `safe_terminate`'s ledger+name
  guard — never deletes a bucket we didn't create).
- **Gap 4b — instance→S3 path (no IAM):** `_presign()` mints **SigV4** GET (stage code/inputs) + PUT
  (upload result) URLs via **boto3 imported LAZILY in the launch-only path** — the engine stays
  stdlib (client.py imports the launcher lazily), same boundary discipline as aso-tox.
- **Gap 2 — per-tool adapter:** `_GPU_TOOLS` recipe registry + `_boltz_complexes()` mapping registry
  inputs `{target_seq, smiles}` → `boltz_runner.py`'s `[{name, protein_seq, smiles}]` (verified against
  its actual reads). `_gpu_recipe()` refuses an unwired tool (never guesses a run). Boltz-2 first.
- **Gap 1 — userdata:** `_render_tool_userdata()` rewritten to the proven q-models pattern (hard-cap
  timer · exec>log · 30s log uploader · wait_apt · **stage code+inputs via presigned GET, NO git clone
  of the retired repo** · per-model venv+deps · run · **presigned-PUT result** · shutdown). Dry-run
  renders with placeholder URLs; an unwired tool renders a clear no-recipe stub (never crashes).
- **Gap 3 — lifecycle:** `_stage_and_presign()` (upload + presign launch-side) → `_launch_live`
  re-renders userdata with the REAL urls before `run-instances`. `job_status()` now **downloads
  result.json from S3** when the instance has terminated, parses + attaches it, sets `done` (or
  `done-no-result` — honest). `wait_for()` blocks to done with a ledgered `safe_terminate` belt on timeout.

## Safety (unchanged + extended)
Profile `Rohan-Sapphire`, account-gate `255493511886`, **dry-run is the default** (live is opt-in),
create-only, **teardown ONLY by ledgered id**, never touch VPC/SG/IAM. Every resource ledgered to
`RohanOnly/qmodels_run/aws_ledger.jsonl`. boto3 is lazy + launch-only (engine import graph unaffected).

## Tests
20 offline launcher tests (injected `aws`/`presign`/`sleep`): bucket create/idempotent/guarded-delete;
SigV4 presign GET/PUT; Boltz input mapping + unwired refusal; userdata staged-not-cloned render;
dry-run boltz vs unwired stub; stage+presign url-set; job_status S3 retrieval (+ done-no-result);
wait_for. Full suite green (gates idle).

## Next (after this merges)
The **live GPU proof**: `submit_job(boltz2, {TSC2 target_seq+smiles}, mode="live")` → `wait_for` →
real prediction retrieved → instance self-terminated → **verify `describe-instances` shows none
running** + report the ~$ cost (g6e.xlarge ~$1.86/hr, minutes). Then the client.poll/e2e wiring (Task 3).
