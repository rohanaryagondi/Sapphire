# -*- coding: utf-8 -*-
"""
smoke_test.py — minimal-footprint live AWS proof that the launcher plumbing works.

Launches ONE self-terminating t3.micro from a public AMI, confirms its user-data ran (via console
output), and verifies it terminates. Smallest possible blast radius: no S3 bucket, no security group,
no IAM — just one ledgered, self-terminating instance. ~$0.001.

Safety: identity gate (account 255493511886), default-VPC-only (else HALT rather than touch shared
network), tag sapphire-qmodels-*, ledger the instance id, initiated-shutdown=terminate + parachute
`shutdown -h +10`, explicit safe_terminate by ledgered id, verify terminated. Halts and reports on any
ambiguity. Usage: python smoke_test.py            (default: live)
                   python smoke_test.py --dry-run  (no launch)
"""
from __future__ import annotations

import base64
import json
import sys
import time

import launcher as L  # same package dir

MARKER = "SAPPHIRE_SMOKE_OK"
RESULT_PATH = L._RUN_DIR / "smoke_result.json"


def _userdata() -> str:
    return f"""#!/bin/bash
set -x
shutdown -h +10 &          # parachute (terminate within 10 min no matter what)
echo "{MARKER} $(hostname) $(date -u +%FT%TZ)"
sleep 150                  # stay up briefly so console output populates (still ~$0.0005)
shutdown -h now            # initiated-shutdown-behavior=terminate -> terminate
"""


def main(dry_run: bool = False) -> int:
    result = {"started": L._now(), "dry_run": dry_run, "steps": []}

    def step(name, **kw):
        result["steps"].append({"step": name, "ts": L._now(), **kw})
        print(f"  · {name}: {kw}")

    # 1. identity gate
    try:
        L._assert_identity()
        step("identity_gate", ok=True, account=L.EXPECTED_ACCOUNT)
    except Exception as e:
        step("identity_gate", ok=False, error=str(e)); _save(result); return 1

    # 2. default VPC check (read-only) — refuse to use shared network infra
    vpcs = L._aws("ec2", "describe-vpcs", "--filters", "Name=isDefault,Values=true",
                  "--query", "Vpcs[].VpcId")
    if not vpcs:
        step("default_vpc", found=False, action="HALT — no default VPC; declining to use shared subnets unsupervised")
        result["status"] = "skipped-no-default-vpc"
        _save(result); print("SMOKE SKIPPED (safe): no default VPC."); return 0
    step("default_vpc", found=True, vpc=vpcs[0])

    # 3. resolve public AMI
    ami = L._aws("ssm", "get-parameter", "--name", L.PUBLIC_AMI_SSM, "--query", "Parameter.Value")
    step("resolve_ami", ami=ami)
    est = L._estimate_usd("t3.micro", 10)
    if est > L.BUDGET_CAP_USD:
        step("budget", refused=True, est=est); result["status"] = "refused-budget"; _save(result); return 1
    step("budget", est_usd=est, cap=L.BUDGET_CAP_USD, ok=True)

    if dry_run:
        result["status"] = "dry-run-ok"; _save(result); print("DRY-RUN OK (no instance launched)."); return 0

    # 4. LAUNCH one tagged, self-terminating t3.micro
    name = f"{L.NAME_PREFIX}-smoke"
    tag_spec = ("ResourceType=instance,Tags=[" + ",".join(
        [f"{{Key=Name,Value={name}}}"] + [f"{{Key={k},Value={v}}}" for k, v in L.TAGS.items()]) + "]")
    ud_b64 = base64.b64encode(_userdata().encode()).decode()
    out = L._aws("ec2", "run-instances", "--image-id", ami, "--instance-type", "t3.micro",
                 "--instance-initiated-shutdown-behavior", "terminate",
                 "--user-data", ud_b64, "--tag-specifications", tag_spec, "--count", "1")
    iid = out["Instances"][0]["InstanceId"]
    L._ledger_append({"event": "create", "resource": "instance", "id": iid, "job": "smoke", "instance_type": "t3.micro"})
    result["instance_id"] = iid
    step("launched", instance_id=iid)

    # 5. retrieve evidence: poll console output for the marker (best-effort, up to ~5 min)
    marker_found = False
    for i in range(20):
        time.sleep(15)
        co = L._aws("ec2", "get-console-output", "--instance-id", iid, "--query", "Output", parse=True)
        text = co if isinstance(co, str) else (co or "")
        if MARKER in (text or ""):
            marker_found = True; step("console_marker", found=True, after_s=(i + 1) * 15); break
        st = L._aws("ec2", "describe-instances", "--instance-ids", iid,
                    "--query", "Reservations[].Instances[].State.Name")
        if st and st[0] in ("shutting-down", "terminated"):
            step("console_marker", found=False, note=f"instance already {st[0]} before console populated"); break
    result["console_marker_found"] = marker_found

    # 6. teardown by ledgered id (belt; the instance self-terminates anyway) + verify
    try:
        term = L.safe_terminate(iid)
        step("safe_terminate", **term)
    except Exception as e:
        step("safe_terminate", note=f"already terminating/terminated or refusal: {e}")
    # verify terminated
    final = None
    for _ in range(20):
        time.sleep(15)
        st = L._aws("ec2", "describe-instances", "--instance-ids", iid,
                    "--query", "Reservations[].Instances[].State.Name")
        final = st[0] if st else None
        if final == "terminated":
            break
    result["final_state"] = final
    step("verify_terminated", final_state=final)

    result["status"] = "ok" if final == "terminated" else "WARN-not-confirmed-terminated"
    result["spend_estimate_usd"] = round(est, 4)
    _save(result)
    print(f"SMOKE {result['status']} | instance {iid} -> {final} | marker={marker_found} | ~${est:.4f}")
    return 0 if final == "terminated" else 2


def _save(result: dict) -> None:
    RESULT_PATH.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
