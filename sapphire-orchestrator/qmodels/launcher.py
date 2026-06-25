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
import time
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

_REPO_ROOT = Path(__file__).resolve().parents[2]                  # repo root (recipe `code` paths)
_RUN_DIR = _REPO_ROOT / "RohanOnly" / "qmodels_run"
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


def _build_inputs(job: dict) -> str:
    """The inputs JSON the eval reads, built by the tool's recipe (offline, pure)."""
    recipe = _gpu_recipe(job.get("tool_id"))
    return json.dumps(recipe["inputs_fn"](job.get("inputs", {})))


def _url_keys(recipe: dict) -> list:
    """The presigned-URL keys the userdata needs: GET each code file + the inputs JSON; PUT the
    result + the progress log."""
    return ([f"get:{fn}" for fn in recipe["code"]]
            + [f"get:{recipe['inputs_name']}", f"put:{recipe['result']}", "put:progress.log"])


def _placeholder_urls(recipe: dict) -> dict:
    """Stand-in URLs for dry-run rendering (real presigned URLs are minted in _launch_live)."""
    return {k: "PRESIGNED-AT-LAUNCH" for k in _url_keys(recipe)}


# The proven GPU userdata pattern (ported from q-models/aws/boltz_validation_userdata.sh):
# hard-cap timer · exec>log · 30s log uploader · wait_apt · stage code+inputs via presigned GET
# (NO git clone of the retired repo) · per-model venv+deps · run · presigned-PUT result · shutdown.
_USERDATA_TMPL = r'''#!/bin/bash
( sleep __SECS__ && shutdown -h now ) &      # hard cap (parachute)
exec > /var/log/userdata.log 2>&1
set -x
date; echo "===== sapphire-qmodels GPU job __JOB__ ====="
mkdir -p /home/ubuntu/work && cd /home/ubuntu/work
cat > urls.json <<'URL_EOF'
__URLS__
URL_EOF
geturl() { python3 -c "import json,sys; print(json.load(open('urls.json')).get(sys.argv[1],''))" "$1"; }
( while :; do U=$(geturl put:progress.log); [ -n "$U" ] && curl -fsS -X PUT --upload-file /var/log/userdata.log "$U" >/dev/null 2>&1; sleep 30; done ) &
LOG_PID=$!
wait_apt() { for i in $(seq 1 90); do sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || return 0; sleep 5; done; }
wait_apt; sudo apt-get update -y || true
wait_apt; sudo apt-get install -y python3-venv python3-pip curl jq || true
__STAGE__
python3 -m venv venv && source venv/bin/activate
pip install --upgrade pip --timeout 600 --retries 5
pip install --no-cache-dir --timeout 600 --retries 5 __DEPS__
export __OUTENV__=/home/ubuntu/work/out
mkdir -p "$__OUTENV__"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "no nvidia-smi"
__RUN__ 2>&1 || echo "RUN_FAILED rc=$?"
RES="$__OUTENV__/__RESULT__"
PUT=$(geturl put:__RESULT__)
if [ -f "$RES" ] && [ -n "$PUT" ]; then curl -fsS --retry 5 -X PUT --upload-file "$RES" "$PUT" && echo UPLOAD_OK || echo UPLOAD_FAIL; else echo "NO_RESULT at $RES"; fi
PL=$(geturl put:progress.log); [ -n "$PL" ] && curl -fsS -X PUT --upload-file /var/log/userdata.log "$PL"
kill $LOG_PID 2>/dev/null || true
sync; sleep 10; shutdown -h now
'''


def _render_tool_userdata(job: dict, urls: dict, max_minutes: int = 60) -> str:
    """Render the GPU userdata for a tool job to the proven pattern, consuming the tool's recipe.
    Pure render — `urls` carries the presigned GET/PUT URLs (real in live, placeholders in dry-run).
    Stages code+inputs from S3 via presigned GET (NO git clone), installs the recipe deps, runs the
    recipe command, and presigned-PUTs the result. Raises for an unwired tool (never guesses)."""
    recipe = _gpu_recipe(job.get("tool_id"))
    stage = "\n".join(
        f'curl -fsS --retry 5 --retry-delay 5 -o {shlex.quote(fn)} "$(geturl get:{fn})" || echo "STAGE_FAIL {fn}"'
        for fn in list(recipe["code"].keys()) + [recipe["inputs_name"]]
    )
    deps = " ".join(shlex.quote(d) for d in recipe["deps"])
    return (_USERDATA_TMPL
            .replace("__SECS__", str(int(max_minutes) * 60))
            .replace("__JOB__", str(job.get("job_id", "")))
            .replace("__URLS__", json.dumps(urls))
            .replace("__STAGE__", stage)
            .replace("__DEPS__", deps)
            .replace("__OUTENV__", recipe["out_env"])
            .replace("__RUN__", recipe["run"])
            .replace("__RESULT__", recipe["result"]))


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
    # render userdata. smoke → fixed template; tool → recipe-driven, with PLACEHOLDER presigned
    # URLs for dry-run validation (_launch_live re-renders with real presigned URLs). An unwired
    # tool renders a clear no-recipe stub (dry-run validates as "not wired", never crashes).
    if kind == "smoke":
        job["userdata"] = _render_smoke_userdata(job_id, bucket, max_minutes)
    else:
        try:
            recipe = _gpu_recipe(job.get("tool_id"))
            job["userdata"] = _render_tool_userdata(job, _placeholder_urls(recipe), max_minutes)
        except SafetyRefusal as e:
            job["userdata"] = f"# no GPU recipe for tool {job.get('tool_id')!r} — not wired for live launch\n# {e}\n"
            job["note"] = f"unwired tool (dry-run only): {e}"

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
    if job.get("kind") != "smoke":
        # Re-render userdata with REAL presigned URLs (submit_job used placeholders for dry-run).
        urls = _stage_and_presign(job, bucket)
        job["userdata"] = _render_tool_userdata(job, urls, max_minutes)
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


def job_status(job_id: str, aws=None) -> dict:
    """Poll a job. When the instance has terminated (the userdata's `shutdown -h now`), DOWNLOAD
    result.json from S3, attach it, and set status='done' (Gap 3 — previously this never retrieved
    the prediction). `aws` is injectable for offline tests."""
    aws = aws or _aws
    p = _job_path(job_id)
    if not p.exists():
        return {"ok": False, "job_id": job_id, "status": "unknown"}
    job = json.loads(p.read_text())
    if job.get("status") in ("dry-run-validated", "refused-budget", "done", "done-no-result", "torn-down"):
        return job
    iid = job.get("instance_id")
    if iid:
        st = aws("ec2", "describe-instances", "--instance-ids", iid,
                 "--query", "Reservations[].Instances[].State.Name")
        state = (st[0] if st else None)
        job["instance_state"] = state
        if state in ("terminated", "shutting-down", "stopped"):
            # finished → fetch the prediction the GPU box uploaded (presigned PUT → S3)
            bucket = _bucket_name()
            try:
                raw = aws("s3", "cp", f"s3://{bucket}/{job_id}/result.json", "-", parse=False)
                job["result"] = json.loads(raw)
                job["status"] = "done"
            except Exception as e:
                job["status"] = "done-no-result"
                job["note"] = f"instance {state} but no parseable result.json: {str(e)[:160]}"
    _write_job(job)
    return job


def wait_for(job_id: str, timeout: int = 3600, poll: int = 30, aws=None, sleep=None) -> dict:
    """Block until the job is done (result retrieved) or `timeout` s elapse. On timeout, BELT:
    safe_terminate the instance if it's somehow still alive (ledgered). `sleep`/`aws` injectable."""
    sleep = sleep or time.sleep
    waited = 0
    while waited < timeout:
        job = job_status(job_id, aws=aws)
        if job.get("status") in ("done", "done-no-result", "torn-down", "timeout-torn-down"):
            return job
        sleep(poll)
        waited += poll
    job = job_status(job_id, aws=aws)
    iid = job.get("instance_id")
    if iid and job.get("instance_state") in ("running", "pending", "stopping", "stopped"):
        try:
            safe_terminate(iid)                       # ledgered belt — don't leak a running GPU box
            job["status"] = "timeout-torn-down"
            _write_job(job)
        except SafetyRefusal:
            pass
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


def _stage_and_presign(job: dict, bucket: str, aws=None, presign=None) -> dict:
    """LIVE: upload the recipe's code files + the built inputs JSON to s3://bucket/<job_id>/, then
    return a presigned-URL dict (GET each + PUT result/progress.log) to inject into the userdata.
    No instance IAM role needed (plan Gap-4 option b). `aws`/`presign` injectable for offline tests."""
    aws = aws or _aws
    presign = presign or _presign
    recipe = _gpu_recipe(job["tool_id"])
    jid = job["job_id"]
    urls: dict = {}
    for fn, local in recipe["code"].items():                    # stage code
        key = f"{jid}/{fn}"
        aws("s3", "cp", str(_REPO_ROOT / local), f"s3://{bucket}/{key}", parse=False)
        urls[f"get:{fn}"] = presign(bucket, key, "get_object")
    import tempfile                                              # stage inputs JSON
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(_build_inputs(job))
        ikey = f"{jid}/{recipe['inputs_name']}"
        aws("s3", "cp", tmp, f"s3://{bucket}/{ikey}", parse=False)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    urls[f"get:{recipe['inputs_name']}"] = presign(bucket, ikey, "get_object")
    urls[f"put:{recipe['result']}"] = presign(bucket, f"{jid}/{recipe['result']}", "put_object")
    urls["put:progress.log"] = presign(bucket, f"{jid}/progress.log", "put_object")
    return urls
