# AWS infrastructure — Quiver MAMMAL project

**Audience:** any Claude session that needs to launch AWS work for this
project. This is the single source of truth for resources, patterns, and
guardrails. **Read this end-to-end before launching anything.**

**Last updated:** 2026-06-12, after the Boltz campaign closed at $5.59 / $15 spend.

---

## 🚨 The non-negotiable rules

1. **NEVER touch resources you don't own.** This is a shared Quiver AWS account with multiple users. The rules:
   - Never `aws s3 ls` other people's buckets.
   - Never describe / start / stop / terminate other people's instances.
   - Never modify or delete other people's EBS volumes.
   - Never modify shared infrastructure (VPC, subnets, security groups, IAM).
2. **Hard cost cap: $15 per session.** Track cumulative spend via the poller. If approaching $13, terminate the in-flight instance immediately.
3. **Always tag your instances** with `Name=Rohan-<purpose>` AND `Owner=Rohan`. Untagged instances waste time when forensics is needed (see story: `JaneJacques` r5.2xlarge fleet — 140+ instances, no tags, no owner attribution).
4. **Ask before deleting anything.** Even S3 buckets or files you created. Even EBS volumes you provisioned. Always confirm with Rohan first.
5. **Never push AWS credentials to the repo.** Access keys are out-of-band only.

---

## My (Rohan's) authorized resources

These are mine to launch / mount / read / write:

### IAM
- **User:** `RohanAryaGondi`
- **ARN:** `arn:aws:iam::255493511886:user/RohanAryaGondi`
- **Account:** `255493511886` (Quiver shared)
- **Region:** `us-east-1` (everything lives here)

Access key configuration:
- **Out-of-band only.** Rohan provides these in the session prompt or via a separate secure channel. Never committed.
- Set via env vars (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) or `~/.aws/credentials` `[default]` profile.
- Verify identity with: `aws sts get-caller-identity` — should return user `RohanAryaGondi`.

### EBS — persistent data volume
- **Volume ID:** `vol-066389517f2740f19`
- **Size:** 100 GB (resized 50 → 100 on 2026-06-12)
- **Type:** gp3 (3000 IOPS, 125 MB/s throughput)
- **AZ:** `us-east-1b`
- **Default state:** detached (`available`)
- **Contents** (do not delete from `/mnt/rohan` without asking):
  - `boltz_cache/` — Boltz-2 model weights (~7 GB; takes 5-10 min to redownload)
  - `boltz_hf/`, `boltz_out/`, `boltz_venv/` — Boltz workspaces from prior runs
  - `PROTON_strength/` — PROTON repo + NeuroKG + weights (rebuilt 2026-06-12; do not delete)
  - `hf_cache/`, `uv_cache/` — Hugging Face + uv package caches
  - `mammal_ft/` — MAMMAL fine-tune data + checkpoints (Quiver work, ~19 GB)
  - `dfp089_v1_bundle/`, `TransformerModel/` — collaborator data (DON'T touch)
  - Misc log files from prior runs

To attach this volume to a new instance:
```bash
aws ec2 attach-volume --region us-east-1 \
  --volume-id vol-066389517f2740f19 \
  --instance-id <instance-id> \
  --device /dev/sdf
```

Then in the EC2 userdata:
1. Wait for it to attach (poll `lsblk` for the 100 GB disk).
2. **Critical:** filter for unmounted disks AND skip the root device (see Userdata Gotchas below).
3. Mount at `/mnt/rohan`.
4. If you just resized: `resize2fs /dev/nvmeXnY` to grow the filesystem.

### S3 — staging bucket
- **Bucket:** `rohan-mammal-bootstrap-20260610-213029`
- **Region:** `us-east-1`
- **Use for:** staging userdata inputs (panel JSON, runner scripts) and receiving outputs (results.json, logs, tarballs) via presigned PUT URLs.
- **Structure** (canonical):
  ```
  rohan-mammal-bootstrap-20260610-213029/
  └── <prefix>_<timestamp>/
      ├── inputs/
      │   ├── <panel>.json
      │   └── <runner>.py
      └── <subdir>/
          ├── results.json
          ├── progress.log
          ├── userdata.log
          └── affinity_dump.tgz
  ```

---

## Resources I do NOT touch (shared infrastructure / other users)

Listed for awareness, NEVER as targets of my commands:

### Other users' instances (verified via CloudTrail)
- `i-0393d9c9a3a392cc3` (RDS DB LOADING) — pre-existing, named with "DO NOT DELETE"
- `i-019cbb3b5f35b63c2` (CONFIG SERVER) — pre-existing, named with "DO NOT DELETE"
- `i-0accdb9e9887807ba` (OptoViz) — Quiver lab tool
- `i-00bdb9517a9fb9646` (SemossCudavpc) — stopped, Semoss
- `i-0d72d7af705e88287` (semosstest) — stopped
- The **JaneJacques `r5.2xlarge` fleet** (~140 instances) — launched 2026-06-12 by user `JaneJacques` from a Windows Boto3 script. No tags. Not mine.

### Network / IAM / VPC (read-only attachments only)
- VPC `vpc-bca9c6d8` (default in us-east-1) — attach to it, don't modify
- Subnets (per AZ — pick the one matching your instance's AZ):
  - us-east-1a: `subnet-aa6fb0dc`
  - us-east-1b: `subnet-93dd2ccb`
  - us-east-1c: `subnet-8cb0c4e9`
  - us-east-1d: `subnet-58e80a72`
- Default security group: `sg-1b4dee62` (in vpc-bca9c6d8) — attach, don't modify

---

## Instance types — what works

| Type | Cost/hr | Use for | Notes |
|---|---:|---|---|
| **g6e.xlarge** | $1.861 | Boltz-2 panels | 1× NVIDIA L40S 48 GB, the workhorse |
| g6e.2xlarge | $2.243 | Boltz fallback | Same L40S, more vCPU/RAM. Use when xlarge has no capacity |
| **t3.xlarge** | $0.166 | PROTON, light CPU work | No GPU; PROTON link prediction is just dot products |
| g5.xlarge | $1.006 | (mostly historical) | A10G 24 GB, used for early PROTON eval |

**Capacity tip:** g6e capacity bounces across AZs in us-east-1 — always loop through AZs (a, b, c, d) on launch. If g6e is fully out, fall back to g6e.2xlarge first before considering p4d (way overkill, $32/hr).

**Root volume size:**
- DL AMI requires ≥75 GB root.
- **NEVER request a root size that equals the data volume size** (100 GB) — this breaks the disk-detection logic in userdata (the root volume gets matched by size-based detection and you end up chowning the root filesystem). Use 80 GB root (when data EBS is 100 GB) or 150 GB root (Boltz needs space for cache + intermediate files).

**Instance Initiated Shutdown Behavior:** always set to `terminate` so failed instances don't leak EBS volumes.

**IMDSv2 required:** `HttpTokens=required,HttpPutResponseHopLimit=2`.

---

## AMI

**Latest Deep Learning Base OSS NVIDIA AMI (Ubuntu 22.04, x86_64):**

```bash
aws ec2 describe-images --region us-east-1 --owners amazon \
  --filters "Name=name,Values=Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)*" \
            "Name=state,Values=available" "Name=architecture,Values=x86_64" \
  --query 'reverse(sort_by(Images, &CreationDate))[:1].[ImageId,Name]' --output text
```

As of 2026-06-12 the latest is **`ami-01011b868ec560823`** (2026-06-09 build). Re-check before each launch — Amazon updates these regularly.

What this AMI ships:
- Ubuntu 22.04
- Python 3.10
- NVIDIA driver 580
- CUDA 13.0 toolkit
- Pre-installed: pip, git, jq, curl, build-essential, cloud-guest-utils
- No PyTorch by default — install via `pip install` per project

---

## Userdata patterns (canonical templates)

**Canonical template: [`aws/boltz_pathway_userdata.sh`](https://github.com/rohanaryagondi/Q-Mammal/blob/boltz/aws/boltz_pathway_userdata.sh) on the `boltz` branch.**

The pattern is well-validated by 7+ AWS launches in the Boltz campaign. Reuse it. Don't reinvent the wheel.

Key features:
1. **Hard kill timer at top:** `( sleep 14400 && shutdown -h now ) &` — ensures shutdown even if everything else fails.
2. **`exec > /var/log/userdata.log 2>&1; set -x`** — captures everything.
3. **PUT URLs heredoc:** template `__URLS_JSON__` marker, filled in before launch.
4. **Background log uploader:** writes `/var/log/userdata.log` to S3 every 30s via presigned PUT — essential for live debugging without SSH.
5. **`wait_apt()` for cloud-init readiness.**
6. **Safe data-volume detection** (when using the EBS): match size 100 GB AND not the root device AND not already mounted. See "Userdata Gotchas" below.
7. **S3-staged inputs** (panel + runner scripts) via presigned GET — necessary because Q-Mammal is a private repo with no git auth on the EC2.
8. **Atomic results upload at end** with `curl -X PUT` to presigned URL.
9. **`shutdown -h now`** at the end (with `InstanceInitiatedShutdownBehavior=terminate`).

---

## Userdata Gotchas (campaign-learned, do not repeat)

1. **The Q-Mammal repo is PRIVATE.** Don't `git clone` it on the EC2 — there's no git auth. Stage panel + runner to S3 via presigned GET URLs instead.

2. **Disk-size detection trap.** If root volume size equals data volume size, naive `lsblk | awk '$2==size'` matches the ROOT device. We did this once on 2026-06-12: chowned the entire root filesystem and broke sudo. **Always filter by NOT-the-root-device AND NOT-mounted.** Canonical fix:
   ```bash
   ROOT_DEV=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)" 2>/dev/null \
              || basename "$(findmnt -no SOURCE /)" | sed -E 's/p?[0-9]+$//')
   EBS_DEV=$(lsblk -bdn -o NAME,SIZE,TYPE \
     | awk -v s=$EBS_SIZE -v root="$ROOT_DEV" \
           '$3=="disk" && $2==s && $1 != root {print $1}' \
     | while read d; do
         [ -z "$(lsblk -no MOUNTPOINTS /dev/$d | tr -d ' \n')" ] && { echo "/dev/$d"; break; }
       done)
   ```

3. **Boltz install: just `pip install boltz`.** The multimer runner uses `--no_kernels`, so you do NOT need cuequivariance-ops kernel packages. Older docs reference `cuequivariance-ops-cu13-torch` (non-existent) or `cuequivariance-ops-torch-cu12` (real but unnecessary with `--no_kernels`).

4. **PowerPoint chip-text ghost rendering** in LibreOffice PDF QA — this is a LibreOffice artifact, not a slide defect. The actual PowerPoint render is clean. Verify chip placeholders work via the original Quiver template (`assets/slideTemplateQuiver_2025.pptx`) — same ghost appears there too.

5. **g6e capacity:** check multiple AZs on launch. AWS rotates capacity by AZ. Often `us-east-1a` succeeds when `c` and `d` reject — or vice versa.

6. **`InstanceInitiatedShutdownBehavior=terminate` + `DeleteOnTermination=true` (root only).** Data EBS should have `DeleteOnTermination=false` so it survives.

---

## Monitoring pattern (canonical)

**Belt-and-suspenders** — always set up BOTH:

### 1. Harness-tracked poller
A Bash background task that polls AWS state every 120s, terminates on cost cap, exits when instance hits `terminated`/`shutting-down`:

```python
# Run via Bash tool with run_in_background=true
# When the poller exits, the harness re-invokes Claude
```

Template: see `/tmp/poll_*.sh` patterns used throughout the campaign.

### 2. Cron watchdog
An independent CronCreate job every ~4 minutes that checks instance state. If the harness-tracked poller dies, the cron triggers the analysis-and-report path independently.

Off-minute offset (e.g., `3-59/4`) to avoid stampede at :00 and :30.

### 3. Sentinel file
`/tmp/<run_name>_done` — prevents both poller AND cron from running the analysis twice.

### 4. Cost cap kill switch
In the poller, terminate the instance when cumulative session spend approaches $13 (leaves $2 buffer below the $15 cap).

---

## Cost reference (canonical)

As of 2026-06-12:

| Activity | Cost |
|---|---:|
| g6e.xlarge for 1 hour (Boltz workhorse) | $1.86 |
| t3.xlarge for 1 hour (PROTON, light CPU) | $0.166 |
| EBS 100 GB gp3 (monthly) | ~$8 |
| S3 storage (typical run, few MB-GB) | < $0.01/month |
| Typical Boltz panel (15-23 complexes, g6e.xlarge) | $1-3 |
| Full Boltz lane (5 panels): | $5.59 (under $15 cap) |

**Always estimate before launching:**
```
<instance-hourly-cost> × <expected-wall-hours> + 10% buffer = est session cost
```

Append it to the launch metadata tag (`BudgetCapUSD`).

---

## Common one-liner commands

```bash
# Identify yourself
aws sts get-caller-identity

# List MY instances (by tag)
aws ec2 describe-instances --region us-east-1 \
  --filters "Name=tag:Owner,Values=Rohan" \
  --query 'Reservations[].Instances[].[InstanceId, InstanceType, State.Name, Tags[?Key==`Name`]|[0].Value]' --output table

# Volume status
aws ec2 describe-volumes --volume-ids vol-066389517f2740f19 --region us-east-1 \
  --query 'Volumes[0].{state:State, size:Size, az:AvailabilityZone, attachments:Attachments}'

# Bucket list (only mine)
aws s3 ls s3://rohan-mammal-bootstrap-20260610-213029/ --region us-east-1

# Latest DL AMI
aws ec2 describe-images --region us-east-1 --owners amazon \
  --filters "Name=name,Values=Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)*" \
            "Name=state,Values=available" \
  --query 'reverse(sort_by(Images, &CreationDate))[:1].[ImageId,Name]' --output text

# CloudTrail forensics (who launched what today)
aws cloudtrail lookup-events --region us-east-1 \
  --lookup-attributes AttributeKey=EventName,AttributeValue=RunInstances \
  --start-time $(date -u +%Y-%m-%dT00:00:00Z) --max-results 50
```

---

## When something goes wrong

1. **Instance launched but no progress:** check `/var/log/userdata.log` via the periodic S3 uploads (the canonical userdata pattern uploads every 30s).
2. **Instance terminates fast:** check `Client.InstanceInitiatedShutdown: Instance initiated shutdown` reason via `aws ec2 describe-instances --instance-ids <id> --query 'Reservations[0].Instances[0].StateReason'`. Usually means userdata called `shutdown -h now` itself on an error path.
3. **g6e InsufficientCapacity:** try other AZs in order (a → c → d → b). Fall back to g6e.2xlarge.
4. **EBS won't attach:** check the volume's AZ matches your instance's AZ. Volumes are AZ-locked.
5. **Cost panic:** poller's kill switch should fire at $13. If it doesn't (poller died), manually `aws ec2 terminate-instances --instance-ids <id>`.

---

## Branches that touch AWS

- `boltz` — used most heavily (5 panels)
- `models` — used for batch eval (MolFormer, PINNACLE, PROTON, SaProt)
- `emet` — Playwright-driven, NO AWS

If you're working on `boltz` or `models`: reuse the existing userdata templates and monitoring patterns rather than rebuilding.

---

## How to set up credentials (out-of-band)

Rohan will provide `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in your session prompt or via a separate secure channel.

Set them in your shell:
```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"
```

Or write to `~/.aws/credentials`:
```
[default]
aws_access_key_id = AKIA...
aws_secret_access_key = ...
```

Verify with `aws sts get-caller-identity` — should return user `RohanAryaGondi`.

**Don't commit credentials. Don't paste them into a public message. Don't write them to any file in the repo.**
