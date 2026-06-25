# sapphire-aws — naming convention & resource inventory

This skill dir holds the operating procedure (`SKILL.md`) for running an **external / GPU Q-Models job on
AWS** under Sapphire's safety model, plus the resource inventory below. The companion agent that executes a
run is `.claude/agents/sapphire-aws-runner.md`.

## Naming convention — "Sapphire" on every resource
Every AWS resource Sapphire creates carries the name **`Sapphire`**:
- **EC2 instances** — `Name=Sapphire` **plus a unique run-suffix** so concurrent runs are distinguishable:
  `Run=sapphire-qmodels-<kind>-<hex8>` (e.g. `Run=sapphire-qmodels-tool-3f9a1c0b`), plus
  `Owner=Rohan`, `Project=sapphire-qmodels`, `BudgetCapUSD=<est>`. Instances are ephemeral — launched,
  used, torn down by ledgered id.
- **EBS volume** — the persistent warm-weights cache is `Name=Sapphire` exactly (see inventory). It is the
  one resource that survives across runs.
- **S3** — staging prefix under the Sapphire-owned bucket; a created scratch bucket is
  `sapphire-qmodels-scratch-<acct>`.
- **Tags double as the ledger key.** Teardown is by ledgered instance id only, never by name/tag filter — so
  the `Name=Sapphire` tag is for human/forensic identification, not for any delete path.

Why a run-suffix on instances but a bare `Name=Sapphire` on the volume: the volume is a singleton inventory
item you look up by name; instances are fleet members you must tell apart and attribute per run.

## Resource inventory (live)

| Resource | Name tag | Id | AZ / region | Spec | State | Cost |
|---|---|---|---|---|---|---|
| **EBS volume (warm Q-Models weights cache)** | `Sapphire` | `vol-0372a48d8defda8e6` | `us-east-1b` / `us-east-1` | gp3, 50 GB (3000 IOPS, 125 MB/s) | `available` (detached) | **~$4.00/mo** (50 GB × $0.08/GB-mo) |

- **Account:** `255493511886` (Quiver shared) · **Profile:** `Rohan-Sapphire`.
- **Created:** 2026-06-25, via the account-gated create in this task. Ledgered in
  `RohanOnly/qmodels_run/aws_ledger.jsonl`.
- **Why us-east-1b:** EBS is AZ-locked; `1b` is the established GPU home in this account (the existing warm
  Boltz cache `vol-066389517f2740f19` lives there) and g6e.xlarge is offered in 1b. The GPU instance must
  launch in `us-east-1b` to attach this volume.
- **Sizing:** ~50 GB covers the ~17 GB total weights cache (Boltz-2 `boltz_cache/` ~7 GB + HF/torch caches +
  PROTON NeuroKG) with headroom; grow with `aws ec2 modify-volume` + `resize2fs` if a future model needs it.
- **Contents (intended):** `boltz_cache/`, `hf_cache/`, PROTON repo/weights — populated on first warm run.
  Empty at creation.

## How the launcher / agent consume the volume
- The **`sapphire-aws-runner`** agent runs the `sapphire-aws` skill: account-gate → launch a
  `Name=Sapphire` g6e.xlarge in `us-east-1b` → **attach this volume at `/dev/sdf`, mount `/mnt/sapphire`**
  (safe size+not-root+not-mounted detection) → point `BOLTZ_CACHE`/`HF_HOME` at it → run the eval → retrieve
  `result.json` → `safe_terminate` the instance by ledgered id. The volume is **never** torn down — it
  detaches back to `available` for the next run.
- The launcher (`sapphire-orchestrator/qmodels/launcher.py`) owns all AWS mutation. Wiring the attach step
  and the warm-cache env into `_render_tool_userdata` is the follow-on engineering task tracked in
  `docs/superpowers/plans/2026-06-25-qmodels-aws-wiring.md` (Steps 3–6); this volume is the resource that
  task consumes.
- If the volume can't attach (instance landed in another AZ on a capacity fallback), the run proceeds
  **cold** (downloads weights to instance-local disk) — the cache is an optimization, never a hard
  dependency.

## Safety recap (full detail in `SKILL.md` §0)
Account-gate before any mutation · create-only · name everything `Sapphire` · append-only ledger ·
teardown only by ledgered id · never touch non-Sapphire / non-ledgered / shared resources · never print
secrets.
