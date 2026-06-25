---
name: sapphire-aws
description: Execute one external/GPU Q-Models run on AWS end-to-end — account-gate, launch a tagged "Sapphire" GPU instance, attach the Sapphire EBS cache, S3-stage code+inputs, run the tool's eval, retrieve result.json, tear down by ledgered id, and ledger every resource. Use when an agent needs a GPU Q-Models prediction (Boltz-2 structure/binding/selectivity, ESM-2 family clustering, funNCion/PROTON endpoint tools) that cannot run on the local-cpu track. Boltz the hosted API is NOT this skill — this is the self-managed EC2/EBS path only.
---

# sapphire-aws — the AWS Q-Models run procedure

The single operating procedure for running an **external / GPU Q-Models tool on AWS** under Sapphire's
safety model. Every AWS resource this skill touches carries the name **`Sapphire`**. The skill is the
authority for *how* a run is executed; the launcher (`sapphire-orchestrator/qmodels/launcher.py`) is the
code that does it.

> **Scope.** This covers the `gpu-launch` / `endpoint` / `batch-ec2` Q-Models tiers — the ones that need a
> GPU box (Boltz-2 → `structure_binding`/`selectivity`; ESM-2 → `family_clustering`; funNCion/PROTON →
> `variant_effect`/`kg_hypothesis`). The `local-cpu` tier (`dti`, `bbbp`, `toxicity`) never comes here — it
> runs synchronously against the local Explorer for $0. **Boltz the hosted API does NOT run here** — it uses
> its own hosted endpoint; ignore it in this procedure.

---

## 0. The safety model (non-negotiable — read before any AWS call)

This runs in a **shared production Quiver account** with no IAM sandbox. The whole point of this procedure
is that it cannot harm anyone else's resources. Five invariants, in priority order:

1. **Account-gate before any mutation.** `aws sts get-caller-identity --profile Rohan-Sapphire` must return
   account **`255493511886`**. If it does not, **ABORT** — touch nothing. Profile **`Rohan-Sapphire` only**,
   region **`us-east-1`**.
2. **Create-only.** This skill only ever *creates* resources. It never modifies or deletes a resource it did
   not create. The one exception is the terminate path in step 7, which is itself gated by the ledger.
3. **Name everything `Sapphire`.** Every instance, volume, and tag created carries `Name=Sapphire` plus a
   **unique run-suffix** for disambiguation (e.g. `Name=Sapphire`, `Run=sapphire-qmodels-tool-<hex8>`). The
   persistent cache volume is `Name=Sapphire` exactly (the resource inventory record). Untagged or
   mis-named resources are a defect — forensics needs the name (see the JaneJacques 140-instance untagged
   fleet cautionary tale in `q-models/docs/AWS_INFRASTRUCTURE.md`).
4. **Append-only ledger.** Every created resource is appended to `RohanOnly/qmodels_run/aws_ledger.jsonl`
   the moment it is created (one JSON object per line: `{ts, event:"create", resource, id, ...}`).
5. **Teardown ONLY by ledgered id.** Termination takes one explicit instance id that must be (a) in our
   ledger AND (b) absent from the pre-existing snapshot (`aws_preexisting_snapshot.json`). **No
   wildcard / tag-filter / name-filter terminate exists, ever.** `launcher.safe_terminate(id)` enforces
   this and raises `SafetyRefusal` otherwise — proven to refuse `i-0d964d89be16a63f4` (another project's
   GPU box) on 2026-06-21.

**Never** create or modify a VPC, subnet, security group, IAM role/user, or any non-`Sapphire`,
non-ledgered resource. If anything is ambiguous, **halt and report** — do not guess.

---

## Account & network facts (determined for this account, us-east-1)

| Fact | Value | How used |
|---|---|---|
| Account (gate) | `255493511886` | `_assert_identity()` aborts if mismatch |
| Profile / region | `Rohan-Sapphire` / `us-east-1` | every `aws` call |
| Default VPC | `vpc-bca9c6d8` | attach, **never modify** (read-only HALT-if-none check exists) |
| AZ for the **Sapphire EBS volume** | **`us-east-1b`** | volume is AZ-locked; GPU instance MUST launch in the same AZ to attach it |
| Subnet (us-east-1b, default-for-az) | `subnet-93dd2ccb` | launch the instance here to co-locate with the volume |
| Other default subnets | 1a `subnet-aa6fb0dc` · 1c `subnet-8cb0c4e9` · 1d `subnet-58e80a72` | capacity fallback (see note below) |
| Security group | default `sg-1b4dee62` (in `vpc-bca9c6d8`) | attach, **never modify**; outbound HTTPS only is all a GPU job needs (HF weights + S3) |
| GPU AMI | DL Base OSS Nvidia (Ubuntu 22.04), x86_64 | **resolve fresh at launch** (Amazon rolls these); 2026-06-19 latest = `ami-002e2f8ce04e32766` |
| Default GPU instance | **`g6e.xlarge`** (1× L40S 48 GB, ~$1.86/hr) | the Boltz workhorse. **Registry's `g5.xlarge` is STALE** — per the 2026-06-25 wiring plan, use `g6e.xlarge` |
| GPU fallback | `g6e.2xlarge` (~$2.24/hr) | on `InsufficientCapacity` for xlarge |
| CPU instance (PROTON) | `t3.xlarge` (~$0.166/hr) | PROTON link-prediction is dot products — no GPU needed |
| S3 write path | **presigned PUT/GET URLs** (operator-side, no instance IAM role) | the proven pattern; instance needs no role |

**IAM for S3 (the decision).** The launched instance is given **no IAM role**. Instead, the operator
(whose `Rohan-Sapphire` creds already have S3 access) generates **presigned GET URLs** for code+inputs and
**presigned PUT URLs** for `result.json`/logs, and bakes them into the userdata. This is the pattern the
proven Boltz scripts use (`q-models/aws/boltz_validation_userdata.sh`), keeps us inside create-only (we
create no IAM), and needs no shared-infra changes. Staging bucket: reuse the existing Sapphire-owned
`rohan-mammal-bootstrap-20260610-213029`, or create a ledgered `sapphire-qmodels-scratch-<acct>` on first
use (idempotent create, ledgered). **Do not** `aws s3 ls` any `qstatebio-*` / `quiver-*` bucket — those
are not ours.

> **AZ vs. capacity (important).** The Sapphire EBS volume lives in **`us-east-1b`** and EBS volumes are
> AZ-locked — so for a run that needs the **warm weights cache**, the GPU instance MUST launch in
> `us-east-1b`. g6e.xlarge is currently offered in 1a/1b/1c/1d, so 1b is normally fine. If 1b returns
> `InsufficientCapacity`, the choices are: (a) retry 1b / fall back to `g6e.2xlarge` in 1b; or (b) launch
> cold in another AZ and **cold-download** weights for that run (no cache attach). Never move the volume by
> deleting it; if a permanent AZ migration is ever needed, snapshot → create-from-snapshot in the new AZ
> (both create-only, both ledgered) — that is a deliberate, separately-authorized action, not part of a
> routine run.

---

## The procedure (one AWS Q-Models run, end-to-end)

Default mode is **dry-run** (render + validate + cost-estimate, touch nothing). A live run is **opt-in**:
`mode="live"` (or `QMODELS_GPU=on`) AND the per-job budget cap must clear. Walk these in order.

### 1. Account-gate (read-only — mandatory first)
```bash
aws sts get-caller-identity --profile Rohan-Sapphire --region us-east-1
# Account MUST == 255493511886. Anything else → ABORT, touch nothing.
```
Also confirm the pre-existing snapshot exists (`RohanOnly/qmodels_run/aws_preexisting_snapshot.json`) — the
teardown guard refuses to act without the before-state. `launcher._assert_identity()` does the gate in code.

### 2. Resolve the tool + budget
- Look the tool up in `sapphire-orchestrator/qmodels/registry.json` by id; confirm its `tier` is
  `gpu-launch` / `endpoint` / `batch-ec2` (a `local-cpu` tool does not belong here).
- Pick the instance: **`g6e.xlarge`** for Boltz-2/ESM (override the registry's stale `g5.xlarge`);
  `t3.xlarge` for PROTON.
- Estimate cost: `hourly × max_minutes/60 + buffer`. The launcher refuses a live launch if
  `est_usd > QMODELS_BUDGET_CAP` (default **$0.50**). For a real GPU job, raise the cap **only for this
  job** (e.g. `QMODELS_BUDGET_CAP=5`) and restore it to `0.50` immediately after. Append the estimate to a
  `BudgetCapUSD` tag.

### 3. Resolve the GPU AMI (read-only)
```bash
aws ec2 describe-images --region us-east-1 --owners amazon \
  --filters "Name=name,Values=Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)*" \
            "Name=state,Values=available" "Name=architecture,Values=x86_64" \
  --query 'reverse(sort_by(Images, &CreationDate))[:1].[ImageId,Name]' --output text --profile Rohan-Sapphire
```
Re-resolve every run — do not hardcode an AMI id.

### 4. Launch the GPU instance — tagged `Name=Sapphire` (+ unique run-suffix)
Launch in **`us-east-1b`** (to attach the Sapphire volume) with:
- `--instance-initiated-shutdown-behavior terminate` (so a failed box self-reaps and never leaks EBS),
- IMDSv2 required (`HttpTokens=required,HttpPutResponseHopLimit=2`),
- root volume **80–150 GB** (DL AMI needs ≥75 GB; **never** equal to the Sapphire volume's 50 GB — the
  size-based disk-detection in userdata would then match the root device; see the AWS doc gotcha),
- tags: **`Name=Sapphire`**, `Run=<job_id>` (the unique suffix, `sapphire-qmodels-<kind>-<hex8>`),
  `Project=sapphire-qmodels`, `Owner=Rohan`, `BudgetCapUSD=<est>`.

The moment `run-instances` returns, **append a `create` event for the instance id to the ledger** (the
launcher's `_launch_live` already does this). `launcher.submit_job(tool, inputs, mode="live",
instance_type="g6e.xlarge")` performs steps 2–4 behind every guard.

### 5. Attach the Sapphire EBS volume (warm model weights)
```bash
aws ec2 attach-volume --region us-east-1 --profile Rohan-Sapphire \
  --volume-id <SAPPHIRE_VOL_ID> --instance-id <iid> --device /dev/sdf
```
- The Sapphire volume (`Name=Sapphire`, gp3, ~50 GB, **us-east-1b**) holds the warm weights cache
  (Boltz-2 `boltz_cache/` ~7 GB, HF caches, etc.) so a run skips the 5–15 min cold download.
- In userdata, mount it **safely**: match by size **AND** NOT-the-root-device **AND** not-already-mounted
  (the canonical `ROOT_DEV` / `EBS_DEV` filter in `q-models/docs/AWS_INFRASTRUCTURE.md` §Gotchas #2 — a
  naive size-only match once chowned a root filesystem). Mount at `/mnt/sapphire`; point
  `BOLTZ_CACHE=/mnt/sapphire/boltz_cache`, `HF_HOME=/mnt/sapphire/hf_cache`.
- The volume's `DeleteOnTermination` MUST be **false** (it survives the instance). Only the root volume
  is delete-on-terminate.
- **If the volume can't attach** (e.g. instance landed in a different AZ on a capacity fallback): do NOT
  fail the run — proceed **cold** (download weights to instance-local disk for this run) and note it. The
  volume is an optimization, never a hard dependency.

### 6. Stage code + inputs (presigned GET) and run the tool's eval
- The operator generates **presigned GET** URLs for the eval script + a runner and **presigned PUT** URLs
  for `result.json` / `progress.log` / `userdata.log`, and writes them into the userdata `__URLS_JSON__`
  heredoc — exactly the proven `q-models/aws/boltz_validation_userdata.sh` shape (hard-kill timer,
  `exec > log; set -x`, 30s background log uploader, `wait_apt`, per-model dep install, atomic PUT upload,
  `shutdown -h now`).
- **Do NOT `git clone` the retired `Q-Models` repo** (`q-models/VENDORED.md`: source repo is abandoned; a
  fresh EC2 has no git auth to a private repo anyway). Stage from S3.
- Use the **real per-tool entrypoint contract** — the registry's generic `--inputs/--out` does NOT match
  the actual scripts. The true contracts (from the wiring plan §B Gap 2):
  | Tool | Real invocation |
  |---|---|
  | Boltz-2 (`structure_binding`/`selectivity`) | `python boltz_runner_multimer.py <complexes.json>`; env `BOLTZ_CACHE`/`BOLTZ_OUT`/`HF_HOME`; writes `$BOLTZ_OUT/results.json` |
  | ESM-2 (`family_clustering`) | `python esm2_big_layer_sweep.py <panel_seqs.json> <out_dir>` (positional) |
  | funNCion (`variant_effect`) | env-driven: `OUT=`, `DATA_TSV=`, `ESM2_MODEL=`, `MAX_VARIANTS=` |
  | PROTON (`kg_hypothesis`) | env-driven: `PROTON_OUT=`; needs PROTON repo + NeuroKG + weights staged (warm via the Sapphire cache) |
- Inputs are **base64-encoded before reaching any shell** (injection guard — the launcher does this).

### 7. Retrieve the result, then tear down by ledgered id
- Poll instance state (`launcher.job_status(job_id)` → `describe-instances`). When the box reaches
  `shutting-down` / `terminated`, **download `result.json` from the S3 prefix** and parse it into a
  normalized dossier row (`qmodels/adapters.normalize`). The retrieved prediction is the return value of
  the run.
- **Teardown:** call `launcher.safe_terminate(<iid>)` — it verifies the id is in our ledger AND not
  pre-existing, terminates, **appends a `terminate` event to the ledger**, and verifies the final state is
  `terminated`. The userdata `shutdown -h now` + `instance-initiated-shutdown-behavior=terminate` are the
  backstop; the explicit ledgered terminate + verify is the belt.
- **Restore `QMODELS_BUDGET_CAP` to `0.50`** if you raised it.

### 8. Close the run
- Confirm the ledger has a matched create+terminate pair for the instance.
- The **Sapphire volume is NOT torn down** — it is the persistent warm cache, detached (`available`) and
  left for the next run. It is the only created resource that survives.
- Report: tool, instance id + type + AZ, retrieved prediction (or honest failure), spend, ledger lines.

---

## Failure & abort handling
- **Account mismatch / missing snapshot** → ABORT before any create.
- **Over budget** → launcher returns `refused-budget`, launches nothing.
- **`InsufficientCapacity` in 1b** → retry 1b → `g6e.2xlarge` in 1b → (if weights cache not required) cold
  in another AZ. Never silently downgrade the science; note what happened.
- **Eval fails on the box** → the userdata writes an `{"error": ...}` result and self-terminates; retrieve
  the error, tear down by ledgered id anyway, report honestly. Never fabricate a prediction.
- **Anything ambiguous about ownership** → halt and report. The cardinal sin is touching shared infra.

## Provenance (what a run returns)
A real GPU run returns provenance `gpu-async` (job handle) → `gpu-real` once `result.json` is retrieved and
normalized; a disabled GPU run returns `gpu-disabled`; deprecated tools return `unavailable`. Never present
a dry-run handle as a prediction.

## Key files
- `sapphire-orchestrator/qmodels/launcher.py` — the safety-critical launcher (`submit_job` / `job_status` /
  `safe_terminate`). All AWS mutation goes through here.
- `sapphire-orchestrator/qmodels/registry.json` — tool ↔ tier ↔ eval_script ↔ instance_type.
- `sapphire-orchestrator/qmodels/adapters.py` — `normalize(...)` → dossier row.
- `q-models/aws/boltz_validation_userdata.sh` — the **proven** userdata pattern to port from.
- `q-models/docs/AWS_INFRASTRUCTURE.md` — canonical AWS rules, AMI, instance types, gotchas, cost.
- `RohanOnly/qmodels_run/aws_ledger.jsonl` — the append-only ledger (every created resource).
- `RohanOnly/qmodels_run/aws_preexisting_snapshot.json` — the before-state the teardown guard checks.
- `docs/superpowers/plans/2026-06-25-qmodels-aws-wiring.md` — the wiring plan this skill operationalizes.
- `.claude/skills/sapphire-aws/README.md` — naming convention + resource inventory (the Sapphire volume id).
