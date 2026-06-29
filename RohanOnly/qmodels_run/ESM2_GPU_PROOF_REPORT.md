# ESM-2 GPU Proof Run — 2026-06-29

## Summary
First real GPU Q-Models run proving the `family_clustering` tool works end-to-end on AWS GPU hardware.
Status flipped: `gpu-unproven` → `live`.

## Run details
| Field | Value |
|---|---|
| Tool | `family_clustering` (ESM-2 layer sweep) |
| Job ID | `sapphire-qmodels-tool-a6e1e92b` |
| Instance | `i-0e68bf59dd5c06cae` (g6e.xlarge, us-east-1b) |
| AMI | `ami-0280bb8a47d83d4b4` (Deep Learning Base OSS Nvidia Driver GPU, Ubuntu 22.04) |
| GPU | NVIDIA L40S, 48 GB VRAM (confirmed via nvidia-smi in progress.log) |
| Launched | 2026-06-29T03:39:18Z |
| Terminated | 2026-06-29T03:48:25Z (ledgered; verified state=terminated) |
| Elapsed | ~9 min (instance running→terminated) |
| Est. cost | $2.33 (g6e.xlarge at ~$1.861/hr × 75 min cap) |
| EBS cache | `vol-0372a48d8defda8e6` attached at /dev/sdf; returned to `available` after termination |

## Input panel
6 public proteins across 2 families (no Quiver-internal data):
- carbonic_anhydrase: CA14 (337aa), CA5A (305aa), CA7 (264aa)
- gpcr: F2RL2 (374aa), TAAR5 (337aa), FFAR3 (346aa)

## Results (from `esm2_big_layer_sweep.json`)
### ESM-2 3B (facebook/esm2_t36_3B_UR50D) — PASSED
- Loaded in 110s on NVIDIA L40S
- All 37 hidden-state layers: LOO NN recall = 1.000 (raw) / 1.000 (centered)
- Best layer: idx 0, nn_raw=1.0, nn_centered=1.0
- Per-family recall: carbonic_anhydrase=1.0, gpcr=1.0
- Protocol: mean-pool ex CLS/EOS, cosine similarity, LOO nearest-neighbor same-family recall

### ESM-2 15B (facebook/esm2_t48_15B_UR50D) — FAILED (infrastructure, not science)
- Failure: `No space left on device (os error 28)` during shard download
- Root cause: 100GB root disk consumed by torch+transformers+venv+3B weights; 7 shards (~4GB each) of 15B do not fit
- Fix: increase root volume to 200GB (`"VolumeSize": 200` in launcher `_launch_live`)
- The GPU inference path is NOT broken; this is a disk-provisioning issue only

## Safety verification
- Account gate: 255493511886 confirmed before any mutation
- Ledger create entry: `{"ts": "2026-06-29T03:39:18.649461+00:00", "event": "create", "resource": "instance", "id": "i-0e68bf59dd5c06cae", ...}`
- Ledger terminate entry: `{"ts": "2026-06-29T03:48:25.191007+00:00", "event": "terminate", "resource": "instance", "id": "i-0e68bf59dd5c06cae"}`
- safe_terminate called explicitly (belt on top of userdata `shutdown -h now`)
- Instance state confirmed `terminated` (polled until clean)
- EBS `vol-0372a48d8defda8e6`: `available`, no attachments (persistent cache survived)
- No shared infra touched (VPC/subnet/SG read-only)
- Budget cap: QMODELS_BUDGET_CAP=3.0 for this run; restored to default 0.50 post-run

## Registry change
`sapphire-orchestrator/qmodels/registry.json` — `family_clustering`:
- `status`: `gpu-unproven` → `live`
- `invoke.instance_type`: `g5.xlarge` → `g6e.xlarge` (correcting stale registry value)
- Added `proven_run` object with full run reference

## Known issue / next step
ESM-2 15B needs 200GB root volume. Update `_launch_live` in `launcher.py`:
```python
{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 200, "VolumeType": "gp3", "DeleteOnTermination": True}}
```
Also: add EBS mount logic in userdata so 15B weights cache to `/mnt/sapphire/hf_cache` (warm on next run).

## Proof verdict
GPU path proven: ESM-2 3B successfully ran CUDA inference on NVIDIA L40S, producing family clustering
embeddings with LOO NN recall 1.0/1.0 across 2 protein families. The `family_clustering` tool is live.
