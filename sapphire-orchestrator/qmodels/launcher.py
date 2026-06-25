# -*- coding: utf-8 -*-
"""
launcher.py — the unified Q-Models batch launcher (the GPU/async path).

It auto-launches a tagged `sapphire-qmodels` EC2 instance from a tool's eval script, runs it, retrieves
the result to a scratch bucket, and auto-tears-down — so the orchestrator can call any GPU model with a
submit/poll handle.

SAFETY IS THE POINT OF THIS FILE (shared production account, no IAM sandbox). Every guard from
specs/2026-06-21-qmodels-integration-overnight-plan.md is compiled in here:
  - profile Rohan-Sapphire ONLY; identity must == account 255493511886 before any create.
  - CREATE-ONLY + LEDGER: everything is tagged/named sapphire-qmodels-* and appended to the ledger.
  - TEARDOWN ONLY BY LEDGERED ID. terminate takes one explicit id that must be (a) in our ledger and
    (b) NOT in the pre-existing snapshot. No wildcard / tag-filter / name-filter terminate, EVER.
  - BUDGET cap (default $0.50). TRIPLE teardown backstop (userdata self-shutdown + initiated-shutdown=
    terminate + explicit terminate + verify). Halt-and-report on any ambiguity.
  - DEFAULT mode is "dry-run": render the plan + userdata, touch nothing. Live launch is opt-in.

Stdlib only. AWS via the `aws` CLI subprocess.
"""
from __future__ import annotations

import datetime
import json
import os
import shlex
import subprocess
import uuid
from pathlib import Path

# ---------------- config (safety constants) ----------------
PROFILE = "Rohan-Sapphire"
REGION = "us-east-1"
EXPECTED_ACCOUNT = "255493511886"
NAME_PREFIX = "sapphire-qmodels"
TAGS = {"Project": "sapphire-qmodels", "CreatedBy": "claude-overnight-2026-06-21"}
BUDGET_CAP_USD = float(os.environ.get("QMODELS_BUDGET_CAP", "0.50"))
PUBLIC_AMI_SSM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"  # resolved at launch
SMOKE_INSTANCE_TYPE = "t3.micro"

_RUN_DIR = Path(__file__).resolve().parents[2] / "RohanOnly" / "qmodels_run"
_JOBS_DIR = _RUN_DIR / "jobs"
_LEDGER = _RUN_DIR / "aws_ledger.jsonl"
_SNAPSHOT = _RUN_DIR / "aws_preexisting_snapshot.json"

# rough on-demand $/hr (us-east-1) for budget estimates — conservative
_HOURLY = {"t3.micro": 0.0104, "t3.small": 0.0208, "g5.xlarge": 1.006, "g4dn.xlarge": 0.526}


class SafetyRefusal(Exception):
    """Raised when an action would violate the isolation/budget invariant. Never caught silently."""


# ---------------- ledger / snapshot ----------------
def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _ledger_append(event: dict) -> None:
    _RUN_DIR.mkdir(parents=True, exist_ok=True)
    event = {"ts": _now(), **event}
    with open(_LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _ledger_created_instance_ids() -> set:
    ids = set()
    if _LEDGER.exists():
        for line in _LEDGER.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") == "create" and e.get("resource") == "instance" and e.get("id"):
                ids.add(e["id"])
    return ids


def _preexisting_instance_ids() -> set:
    if not _SNAPSHOT.exists():
        raise SafetyRefusal("pre-existing AWS snapshot missing — refuse to act without the before-state.")
    snap = json.loads(_SNAPSHOT.read_text())
    return {i["id"] for i in snap.get("instances", [])}


# ---------------- aws cli wrappers ----------------
def _aws(*args, parse=True, check=True):
    cmd = ["aws", *args, "--profile", PROFILE, "--region", REGION, "--output", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"aws {' '.join(args[:2])} failed: {proc.stderr.strip()[:300]}")
    if not parse:
        return proc.stdout
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _assert_identity() -> None:
    acct = _aws("sts", "get-caller-identity").get("Account")
    if acct != EXPECTED_ACCOUNT:
        raise SafetyRefusal(f"identity account {acct} != expected {EXPECTED_ACCOUNT} — ABORT.")


def _estimate_usd(instance_type: str, max_minutes: int) -> float:
    return _HOURLY.get(instance_type, 1.0) * (max_minutes / 60.0)


# ---------------- userdata renderers ----------------
def _render_smoke_userdata(job_id: str, bucket: str, max_minutes: int = 15) -> str:
    """Trivial plumbing job: prove launch→run→retrieve→teardown on a CPU micro instance. No model."""
    return f"""#!/bin/bash
set -x
# backstop self-terminate (parachute) in case the explicit teardown ever fails
shutdown -h +{max_minutes} &
RESULT=/tmp/result.json
echo '{{"job":"{job_id}","kind":"smoke","ran":true,"host":"'$(hostname)'","ts":"'$(date -u +%FT%TZ)'"}}' > $RESULT
aws s3 cp $RESULT s3://{bucket}/{job_id}/result.json --region {REGION} || true
# done — terminate now (initiated-shutdown-behavior=terminate makes this a terminate)
shutdown -h now
"""


def _render_tool_userdata(job: dict, bucket: str, max_minutes: int = 60) -> str:
    """Template for a real Q-Models eval (DRY-RUN ONLY in this overnight run — not executed live).
    A live GPU run would clone q-models, set up the env, run eval_script on the inputs, upload result."""
    import base64
    eval_script = (job.get("eval_script") or "aws/<tool>_eval.py")
    # SECURITY: base64-encode inputs so no user JSON ever reaches a shell with metacharacters
    # (base64 alphabet is shell-safe). The instance decodes it back to JSON.
    inputs_b64 = base64.b64encode(json.dumps(job.get("inputs", {})).encode()).decode()
    return f"""#!/bin/bash
set -x
shutdown -h +{max_minutes} &   # parachute
cd /home/ec2-user || cd /home/ubuntu
git clone --depth 1 https://github.com/rohanaryagondi/Q-Models.git qm 2>/dev/null || true
cd qm
python3 -m pip install -q -r requirements.txt || true
echo {inputs_b64} | base64 -d > /tmp/inputs.json
python3 {shlex.quote(eval_script)} --inputs /tmp/inputs.json --out /tmp/result.json || \
  echo '{{"job":"{job['job_id']}","error":"eval failed"}}' > /tmp/result.json
aws s3 cp /tmp/result.json s3://{bucket}/{job['job_id']}/result.json --region {REGION} || true
shutdown -h now
"""


# ---------------- job lifecycle ----------------
def _job_path(job_id: str) -> Path:
    return _JOBS_DIR / f"{job_id}.json"


def _write_job(job: dict) -> None:
    _JOBS_DIR.mkdir(parents=True, exist_ok=True)
    _job_path(job["job_id"]).write_text(json.dumps(job, indent=2))


def submit_job(tool: dict, inputs: dict, *, mode: str = "dry-run", kind: str = "tool",
               instance_type: str | None = None, max_minutes: int = 30) -> dict:
    """Submit a GPU/batch job. mode='dry-run' (default) renders + validates without touching AWS.
    mode='live' launches a real tagged instance (passes every guard first)."""
    job_id = f"{NAME_PREFIX}-{kind}-{uuid.uuid4().hex[:8]}"
    itype = instance_type or (SMOKE_INSTANCE_TYPE if kind == "smoke" else tool.get("invoke", {}).get("instance_type", "g5.xlarge") if tool else "g5.xlarge")
    bucket = _bucket_name()  # account-scoped scratch bucket; created (idempotent) in live mode
    job = {
        "job_id": job_id, "kind": kind, "mode": mode, "status": "created",
        "tool_id": (tool or {}).get("id"), "eval_script": (tool or {}).get("invoke", {}).get("eval_script") or (tool or {}).get("eval_script"),
        "instance_type": itype, "inputs": inputs, "created": _now(),
        "est_usd": round(_estimate_usd(itype, max_minutes), 4),
    }
    # render userdata
    job["userdata"] = (_render_smoke_userdata(job_id, bucket, max_minutes) if kind == "smoke"
                       else _render_tool_userdata(job, bucket, max_minutes))

    over_budget = job["est_usd"] > BUDGET_CAP_USD

    if mode == "dry-run":
        # dry-run never spends — validate + render the plan; just flag if a LIVE run would exceed budget
        job["status"] = "dry-run-validated"
        if over_budget:
            job["note"] = f"would exceed budget: est ${job['est_usd']} > cap ${BUDGET_CAP_USD} (NOT launched — dry-run)"
        _write_job(job)
        return job

    if mode != "live":
        raise SafetyRefusal(f"unknown mode '{mode}'")

    # ---- LIVE path: budget gate, then every safety guard, then launch ----
    if over_budget:
        job["status"] = "refused-budget"
        job["note"] = f"LIVE launch refused: est ${job['est_usd']} > cap ${BUDGET_CAP_USD}"
        _write_job(job)
        return job
    return _launch_live(job, bucket, max_minutes)


def _launch_live(job: dict, bucket: str, max_minutes: int) -> dict:
    _assert_identity()  # account gate
    ensure_bucket()     # idempotent, ledgered: the GPU job's userdata uploads result.json here
    ami = _aws("ssm", "get-parameter", "--name", PUBLIC_AMI_SSM, "--query", "Parameter.Value")
    tag_spec = "ResourceType=instance,Tags=[" + ",".join(
        [f"{{Key=Name,Value={job['job_id']}}}"] + [f"{{Key={k},Value={v}}}" for k, v in TAGS.items()]) + "]"
    import base64
    ud_b64 = base64.b64encode(job["userdata"].encode()).decode()
    out = _aws("ec2", "run-instances", "--image-id", ami, "--instance-type", job["instance_type"],
               "--instance-initiated-shutdown-behavior", "terminate",
               "--user-data", ud_b64, "--tag-specifications", tag_spec, "--count", "1")
    iid = out["Instances"][0]["InstanceId"]
    _ledger_append({"event": "create", "resource": "instance", "id": iid, "job": job["job_id"],
                    "instance_type": job["instance_type"], "est_usd": job["est_usd"]})
    job.update({"status": "launched", "instance_id": iid, "launched": _now()})
    _write_job(job)
    return job


def job_status(job_id: str) -> dict:
    p = _job_path(job_id)
    if not p.exists():
        return {"ok": False, "job_id": job_id, "status": "unknown"}
    job = json.loads(p.read_text())
    if job.get("status") in ("dry-run-validated", "refused-budget", "done", "torn-down"):
        return job
    iid = job.get("instance_id")
    if iid:
        st = _aws("ec2", "describe-instances", "--instance-ids", iid,
                  "--query", "Reservations[].Instances[].State.Name")
        job["instance_state"] = (st[0] if st else None)
    _write_job(job)
    return job


def safe_terminate(instance_id: str) -> dict:
    """Terminate ONE instance — only if it is in our ledger AND not pre-existing. No other path exists."""
    created = _ledger_created_instance_ids()
    preexisting = _preexisting_instance_ids()
    if instance_id not in created:
        raise SafetyRefusal(f"REFUSE terminate {instance_id}: not in our ledger (we did not create it).")
    if instance_id in preexisting:
        raise SafetyRefusal(f"REFUSE terminate {instance_id}: present in pre-existing snapshot.")
    _aws("ec2", "terminate-instances", "--instance-ids", instance_id)
    _ledger_append({"event": "terminate", "resource": "instance", "id": instance_id})
    # verify
    st = _aws("ec2", "describe-instances", "--instance-ids", instance_id,
              "--query", "Reservations[].Instances[].State.Name")
    return {"instance_id": instance_id, "terminated_state": (st[0] if st else None)}


# ---------------- scratch bucket (Gap 4a: GPU jobs write result.json here) ----------------
def _bucket_name() -> str:
    """The account-scoped scratch bucket (globally-unique). One bucket, reused across all jobs."""
    return f"{NAME_PREFIX}-scratch-{EXPECTED_ACCOUNT}"


def _ledger_created_buckets() -> set:
    names = set()
    if _LEDGER.exists():
        for line in _LEDGER.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") == "create" and e.get("resource") == "bucket" and e.get("id"):
                names.add(e["id"])
    return names


def ensure_bucket(aws=None) -> str:
    """Idempotently create the ledgered scratch bucket (CREATE-ONLY, account-gated). Returns its
    name. Safe to call repeatedly — no-ops if it already exists. `aws` is injectable for tests."""
    aws = aws or _aws
    name = _bucket_name()
    try:
        aws("s3api", "head-bucket", "--bucket", name)
        return name                                   # already exists → no-op
    except RuntimeError:
        pass
    _assert_identity()                                # gate before the create mutation
    aws("s3api", "create-bucket", "--bucket", name)   # us-east-1: no LocationConstraint
    _ledger_append({"event": "create", "resource": "bucket", "id": name,
                    "purpose": "qmodels GPU job scratch (result.json)"})
    return name


def safe_delete_bucket(bucket: str, aws=None) -> dict:
    """Delete a scratch bucket — ONLY if it is in our ledger AND matches our scratch naming (mirrors
    safe_terminate). Empties it first. Never deletes a bucket we did not create."""
    aws = aws or _aws
    if bucket not in _ledger_created_buckets():
        raise SafetyRefusal(f"REFUSE delete bucket {bucket}: not in our ledger (we did not create it).")
    if not bucket.startswith(f"{NAME_PREFIX}-scratch"):
        raise SafetyRefusal(f"REFUSE delete bucket {bucket}: not a sapphire-qmodels scratch bucket.")
    aws("s3", "rm", f"s3://{bucket}", "--recursive", parse=False, check=False)   # empty
    aws("s3api", "delete-bucket", "--bucket", bucket)
    _ledger_append({"event": "delete", "resource": "bucket", "id": bucket})
    return {"bucket": bucket, "deleted": True}


# ---------------- presigned URLs (Gap 4b: stage inputs/code via GET, upload results via PUT) ----------------
def _presign(bucket: str, key: str, method: str = "get_object", expires: int = 3600, s3=None) -> str:
    """A presigned S3 URL — GET to stage inputs/code onto the GPU box, PUT to upload its results.

    Avoids an instance IAM role (plan Gap-4 option b): the URL is signed LAUNCH-SIDE and curl'd from
    userdata. Uses **boto3 lazily** — only here in the live-launch path, never at engine import time
    (client.py imports the launcher lazily, so the stdlib engine import graph is unaffected — same
    boundary discipline as aso-tox's sklearn-in-subprocess). `s3` is injectable for offline tests.
    """
    if s3 is None:
        import boto3  # lazy: operational AWS tooling only
        from botocore.config import Config
        s3 = boto3.Session(profile_name=PROFILE).client(
            "s3", region_name=REGION, config=Config(signature_version="s3v4"))  # SigV4 (curl PUT)
    return s3.generate_presigned_url(method, Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)


# ---------------- per-tool GPU recipes (Gap 2: registry inputs → a real eval run) ----------------
def _boltz_complexes(inputs: dict) -> list:
    """Map registry inputs {target_seq, smiles} → boltz_runner.py's `complexes` list
    ([{name, protein_seq, smiles}], the validation_panel format). Raises on missing inputs."""
    seq = inputs.get("target_seq") or inputs.get("protein_seq") or inputs.get("seq")
    smi = inputs.get("smiles") or inputs.get("smi")
    if not (seq and smi):
        raise ValueError("boltz2 requires target_seq + smiles")
    return [{"name": inputs.get("name", "complex_1"),
             "target": inputs.get("target"), "drug": inputs.get("drug"),
             "protein_seq": seq, "smiles": smi}]


# tool_id → recipe. `code`: local repo files staged onto the box (presigned GET); `inputs_fn`
# builds the JSON the eval reads (staged as `inputs_name`); `deps`: pip installs; `out_env`: the
# env var the eval writes its outputs under; `run`: the in-cwd command; `result`: file under
# out_env to upload (presigned PUT). One entry per `gpu-launch` tool — Boltz-2 first (the proof).
_GPU_TOOLS = {
    "boltz2": {
        "code": {"boltz_runner.py": "q-models/aws/boltz_runner.py"},
        "inputs_name": "complexes.json",
        "inputs_fn": _boltz_complexes,
        "deps": ["boltz"],
        "out_env": "BOLTZ_OUT",
        "run": "python boltz_runner.py complexes.json",
        "result": "results.json",
    },
}


def _gpu_recipe(tool_id: str) -> dict:
    """The per-tool GPU recipe, or raise SafetyRefusal for an unwired tool (never guess a run)."""
    r = _GPU_TOOLS.get(tool_id)
    if r is None:
        raise SafetyRefusal(f"no GPU recipe for tool '{tool_id}' — refuse to launch an unwired eval.")
    return r
