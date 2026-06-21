#!/usr/bin/env python3
"""Provision the Quiver Explorer GPU inference endpoint (explorer_inference_server.py).

SAFETY: this script is **dry-run by default** — it prints the exact launch plan and
the `aws ec2 run-instances` it WOULD run, and exits without touching AWS. It only
provisions when invoked with BOTH `--launch` and `--yes`. Nothing is launched as a
side effect of importing or running it without those flags.

    python aws/launch_explorer_endpoint.py                 # dry run: print the plan
    python aws/launch_explorer_endpoint.py --launch --yes  # actually provision (costs $)

Cost & guardrails (repo policy): g5.xlarge ≈ $1.00/hr on-demand. $15/session hard cap.
The instance self-terminates after --max-minutes (default 120) as a budget backstop;
terminate it yourself when done. Only ever touches resources YOU launch.

Architecture: this boots ONE GPU instance, sets up a venv, starts the FastAPI model
server (aws/explorer_inference_server.py) on :8080, and prints the URL to set as
EXPLORER_AWS_ENDPOINT. The Explorer backend then POSTs {track, model, inputs} to it.
"""

from __future__ import annotations

import argparse
import base64
import json
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# --- launch parameters (from aws-dlami-userdata-gotchas: AMI, AZ-locked EBS, SG) ---
DEFAULTS = {
    "ami": "ami-012ba162b9cd2729c",        # DLAMI PyTorch 2.7 (driver preinstalled)
    "instance_type": "g5.xlarge",          # 1x A10G, ~$1.00/hr; enough for these models
    "region": "us-east-1",
    "subnet": "subnet-93dd2ccb",           # us-east-1b (where vol-066389517f2740f19 lives)
    "security_group": "sg-1b4dee62",       # no public inbound by default — see --open-port note
    "bucket": "rohan-mammal-bootstrap-20260610-213029",
    "prefix": "explorer_endpoint",
    "max_minutes": 120,
}


def build_userdata(args) -> str:
    ud = (HERE / "explorer_endpoint_userdata.sh").read_text()
    repl = {
        "__BUCKET__": args.bucket,
        "__PREFIX__": args.prefix,
        "__MAXMIN__": str(args.max_minutes),
    }
    for k, v in repl.items():
        ud = ud.replace(k, v)
    return ud


def run_instances_cmd(args, userdata_b64: str) -> list[str]:
    tags = "ResourceType=instance,Tags=[" + ",".join([
        "{Key=Owner,Value=RohanAryaGondi}",
        "{Key=Name,Value=Rohan-Explorer-Endpoint}",
        "{Key=Project,Value=mammal-explorer}",
    ]) + "]"
    return [
        "aws", "ec2", "run-instances",
        "--region", args.region,
        "--image-id", args.ami,
        "--instance-type", args.instance_type,
        "--subnet-id", args.subnet,
        "--security-group-ids", args.security_group,
        "--instance-initiated-shutdown-behavior", "terminate",
        "--block-device-mappings",
        "DeviceName=/dev/sda1,Ebs={VolumeSize=120,VolumeType=gp3,DeleteOnTermination=true}",
        "--tag-specifications", tags,
        "--user-data", "base64://" + userdata_b64,  # placeholder form; see note below
    ]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k, v in DEFAULTS.items():
        p.add_argument(f"--{k.replace('_', '-')}", default=v, type=type(v))
    p.add_argument("--launch", action="store_true", help="actually call AWS (default: dry run)")
    p.add_argument("--yes", action="store_true", help="required with --launch to confirm spend")
    args = p.parse_args()

    userdata = build_userdata(args)
    ud_b64 = base64.b64encode(userdata.encode()).decode()
    cmd = run_instances_cmd(args, ud_b64)

    print("=== Quiver Explorer endpoint — launch plan ===")
    print(f"  AMI            {args.ami}")
    print(f"  instance type  {args.instance_type}  (~$1.00/hr; self-terminates after {args.max_minutes} min)")
    print(f"  region/subnet  {args.region} / {args.subnet}")
    print(f"  security group {args.security_group}")
    print(f"  tags           Owner=RohanAryaGondi, Name=Rohan-Explorer-Endpoint")
    print(f"  userdata       aws/explorer_endpoint_userdata.sh ({len(userdata)} bytes)")
    print()
    print("After it boots, set on your laptop:")
    print('  export EXPLORER_AWS_ENDPOINT="http://<instance-public-dns>:8080/predict"')
    print("  (the server listens on :8080 — open that port to your IP in the SG, or SSH-tunnel it)")
    print()

    if not (args.launch and args.yes):
        print("DRY RUN — nothing launched. To provision (incurs cost), re-run with:")
        print("  python aws/launch_explorer_endpoint.py --launch --yes")
        print()
        print("The run-instances invocation that WOULD execute (userdata elided):")
        shown = [c if not c.startswith("base64://") else "base64://<userdata>" for c in cmd]
        print("  " + " ".join(shlex.quote(c) for c in shown))
        return 0

    # NOTE: aws CLI wants user-data as a file:// or raw string, not base64://. We
    # write the userdata to a temp file and pass file://. (Kept explicit so the
    # dry-run plan above stays readable.)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write(userdata)
        ud_path = f.name
    cmd = [c for c in cmd]
    i = cmd.index("--user-data")
    cmd[i + 1] = "file://" + ud_path
    print("LAUNCHING (this spends money)…")
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        print("run-instances failed:\n", out.stderr, file=sys.stderr)
        return 1
    resp = json.loads(out.stdout)
    iid = resp["Instances"][0]["InstanceId"]
    print(f"launched {iid}. Poll public DNS with:")
    print(f"  aws ec2 describe-instances --region {args.region} --instance-ids {iid} "
          "--query 'Reservations[].Instances[].PublicDnsName' --output text")
    print(f"Terminate when done:  aws ec2 terminate-instances --region {args.region} --instance-ids {iid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
