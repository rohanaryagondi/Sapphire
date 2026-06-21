# Overnight Plan — Vendor Q-Models + integrate so the orchestrator can call any model

**Date:** 2026-06-21
**Owner:** Rohan Gondi · **Executor:** Claude (autonomous, self-paced overnight)
**Branch:** `Rohan` · commit per phase · **no push to `main`** · morning report in `RohanOnly/`
**Budget:** $3 cap authorized; internal hard cap **$0.50**; expected spend **~$0.01** (one t3.micro).

> Scoping decisions (locked): **vendor the entire Q-Models repo** into our codebase (the GitHub repo is
> abandoned after this) · **unified batch launcher** for invocation · **two-speed** (CPU sync / GPU
> async) · **orchestrator auto-launch + auto-teardown** for GPU · **full registry, wire LIVE now / mark
> the rest honestly**.

---

## 0. AWS reality (the safety map — discovered via read-only recon 2026-06-21)

Account **255493511886** is the **shared Quiver production account**. Identity = IAM user
`RohanAryaGondi` with **broad access and NO IAM sandbox** — therefore isolation rests **entirely on
executor discipline**, not on permissions. This is the central risk; the guardrails in §1 exist for it.

**OFF-LIMITS — never stop/terminate/reboot/detach/delete/attach/modify (treat as radioactive):**

| Kind | IDs / names | What it is |
|---|---|---|
| EC2 (other project) | `i-0d964d89be16a63f4` (running g4dn), `i-0b68937b2be898b55` (g5) | **Rohan-oEP** — the other important project |
| EBS (other project) | `vol-066389517f2740f19` "Rohan", `vol-033fcaec22eaabbcc`, `vol-0679bcc219686d74b` "oEP - Matt" | Rohan-oEP + Matt's oEP data |
| EC2 (production) | `i-0393d9c9a3a392cc3` (RDS "DO NOT DELETE"), `i-019cbb3b5f35b63c2` (CONFIG "DO NOT DELETE"), `i-0accdb9e9887807ba` (OptoViz), `i-00bdb9517a9fb9646` + `i-0d72d7af705e88287` (Semoss) | live company infra |
| S3 | every `qstatebio-*` bucket, `preeve-ptp-cloudcheckr` | company production data |
| Naming | anything prefixed **`Rohan-`** (e.g. `Rohan-R82-*`, `Rohan-oEP`) | reserved by the other project — I never create or touch these |

**The blanket rule:** *every resource that already exists is off-limits.* I only ever act on resources
I create in this run, tracked by ID. The table above is belt-and-suspenders on top of that rule.

---

## 1. Safety invariant (explicit, non-negotiable)

1. **Profile.** All AWS calls use `--profile Rohan-Sapphire`. (Created in Phase 0 by copying the existing
   `default` credentials — same account, same IAM user; no separate IAM isolation exists, so discipline
   is everything. The profile is for clarity/tagging only.)
2. **Create-only + tag-and-track.** Every resource I create is tagged
   `{Project=sapphire-qmodels, CreatedBy=claude-overnight-2026-06-21, Run=<uuid>}` and named
   `sapphire-qmodels-*`. I **never** use the `Rohan-` prefix. I append every created resource ID to a
   ledger file `RohanOnly/qmodels_run/aws_ledger.jsonl`.
3. **Teardown only by owned ID.** Terminate/delete calls take an explicit ID **from the ledger** only.
   **No wildcard, no tag-filter, no name-filter deletes — ever.** I never pass a resource ID I didn't
   create this run into any mutating call.
4. **Pre-flight blast-radius snapshot.** Before the first create, snapshot all existing instance +
   volume + bucket IDs (read-only) to `RohanOnly/qmodels_run/aws_preexisting_snapshot.json`. Teardown
   only ever targets IDs that appeared *after* the snapshot AND are in my ledger.
5. **Identity gate.** Before any create, assert `aws sts get-caller-identity` == account `255493511886`;
   abort otherwise.
6. **Budget kill-switch.** Internal hard cap **$0.50**. Pre-launch estimate; abort if an action could
   exceed it. Smoke test is **one `t3.micro`** (~$0.0104/hr) for <15 min ≈ $0.003. Never launch GPU.
7. **Triple teardown backstop.** Smoke instance is launched with
   `--instance-initiated-shutdown-behavior terminate` **and** userdata `shutdown -h +15` (self-kill in
   15 min) **and** my explicit terminate-by-ID **and** a post-terminate poll to `terminated`. Belt,
   suspenders, and a parachute.
8. **My own minimal resources only.** A new security group `sapphire-qmodels-sg` (no inbound), a new
   bucket `sapphire-qmodels-scratch-<ts>`, the public Amazon Linux 2023 AMI. I reuse **none** of the
   other project's SG/subnet/bucket/AMI/volume.
9. **Halt conditions** (stop, leave AWS clean, write report, do not guess): ownership ambiguity · any
   pre-existing ID about to enter a mutating call · budget trip · identity mismatch · the local CPU
   endpoint won't stand up · any destructive or irreversible step outside the ledger.

---

## 2. Vendor ALL of Q-Models into our codebase

The repo is small (~13 MB working tree, **no files >5 MB**, model weights + secrets already excluded by
its `.gitignore`). Bring it over wholesale so we own and reshape it; the GitHub repo is then abandoned.

- **Destination:** `q-models/` at our repo root — a full copy of the repo (minus `.git/`).
- **Secret review before commit:** inspect the 3 files a regex flagged
  (`docs/AWS_INFRASTRUCTURE.md`, `results/big_panel.json`, `results/_uniprot_cache.json`) — redact any
  real `AKIA…`/secret-key (expected: false positives / infra notes that only contain the account ID and
  resource names already known). Run a final `grep` gate; **no key is committed.**
- **Carry over its ignore rules** into our repo (append to `.gitignore`): `q-models/models/`,
  `q-models/data/` caches, `q-models/aws/*.pem`, `q-models/aws/.launch_vars`, `q-models/results/*_run.log`
  — so we never commit weights/secrets/regenerable data.
- **Manifest:** write `q-models/VENDORED.md` — provenance (source repo + commit), what was kept, what
  the ignore rules exclude, and that it's now the canonical, modifiable home.

---

## 3. The integration (the orchestrator can call any model)

New layer in `sapphire-orchestrator/qmodels/`:

- **`registry.json`** — every tool from the catalog: `id · task · tier(local-cpu|gpu-launch|batch-ec2) ·
  status(live|eval|deprecated|todo) · inputs · outputs · invoke{endpoint|eval_script|handler}`. Full
  registry → "any tool" is addressable; only `live` ones actually call out.
- **`qmodels_client.py`** — the single caller the engine + bridge share. Routes by tier:
  - **local-cpu → synchronous**: POST the vendored local Explorer API (`/api/predict/{track}`) —
    DTI/BBBP/tox. Instant, $0.
  - **gpu-launch → asynchronous**: hand off to `launcher.py`; return a job handle; caller polls.
  - **batch-ec2 → registered, gated**: same launcher path, heavier; not exercised overnight.
  - On any tool whose endpoint/tier is down or `status != live`: return an honest "unavailable / mock"
    result with provenance, never a fabricated number.
- **`launcher.py`** — the unified batch launcher: builds userdata from the registry, launches a
  **tagged, ledgered** instance, runs the tool, retrieves results to the scratch bucket, **auto-tears
  down**, with the §1 budget + ledger guards compiled in. Overnight: validated by **dry-run** + the §6
  smoke test only.
- **`adapters.py`** — per-tool normalizers: each tool's ad-hoc JSON → our dossier `validate.runs`
  shape (`{model, out, provenance, raw}`).
- **Engine** (`orchestrator.py`): VALIDATE stage calls `qmodels_client` (CPU sync inline; GPU async
  job: submit → `running` → fill the dossier field when the result lands).
- **Bridge** (`serve.py`): `/api/run` uses real CPU tools when the local endpoint is up; GPU tools via
  an async job id + a `/api/job/<id>` poll endpoint; provenance flips `◍ mock → ✓ real` per tool;
  honest fallback when an endpoint is down (consistent with the existing EMET-honesty model).
- **Console**: VALIDATE renders real tool outputs + provenance, and a "running"/poll state for async
  GPU jobs.
- **Local CPU endpoint**: run the vendored `q-models/scripts/setup_new_device.sh` (best-effort, ~20 min,
  public data) to stand up DTI/BBBP/tox and test them live at $0. If it fails → CPU tools fall back to
  honest "mock/unavailable" and it's flagged in the report (a halt-soft, not a hard stop).

---

## 4. Phases (self-paced; one commit per phase to `Rohan`)

| # | Phase | AWS? | Output |
|---|---|---|---|
| 0 | Vendor Q-Models + secret review + `.gitignore` + `Rohan-Sapphire` profile + read-only AWS snapshot | read-only | `q-models/`, snapshot, ledger init |
| 1 | Build `registry.json` (full, tiered, status-marked) | none | registry |
| 2 | `qmodels_client.py` + `adapters.py`; stand up local CPU endpoint; wire + **test CPU tools live** | none ($0) | sync path proven |
| 3 | `launcher.py` + GPU async job model + guards; **dry-run** validate | none | launcher (dry-run green) |
| 4 | Engine + bridge wiring (VALIDATE real CPU sync, GPU async, provenance, fallbacks) | none | orchestrator calls tools |
| 5 | Console: real VALIDATE + provenance + async state | none | UI |
| 6 | **AWS plumbing smoke test** — one `t3.micro`, launch→trivial job→retrieve→terminate→verify | **~$0.01** | proof the launcher works on real AWS |
| 7 | Docs (q-models-runner spec, architecture, CLAUDE), morning report, final AWS-clean check | read-only | report |

If AWS is unavailable or anything in §1 trips, phases 0–5 + 7 still complete at $0; phase 6 is skipped
and reported.

## 5. Morning deliverable (`RohanOnly/qmodels_run/REPORT.md`)

Vendored manifest · per-tool live-vs-mock status · what's wired/tested · the smoke-test result with
**proof of teardown** (instance `terminated`) and **exact spend** · confirmation that **no
`sapphire-qmodels-*` resources remain** and **nothing pre-existing was touched** · open items.

## 6. To start

- Confirm: create the `Rohan-Sapphire` profile by **copying the existing `default` credentials**
  (same account/IAM; isolation is by discipline, per §0–§1). If you have a separate scoped key for
  `Rohan-Sapphire`, give me that instead and I'll use it.
- Then: GO → I write the implementation plan (writing-plans) and run overnight.
