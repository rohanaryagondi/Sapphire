# Retrieving the fine-tune pilot results (after the instance self-terminated)

The g4dn instance (`i-0e4a5087c22fa257e`) self-terminates after `autorun.sh` finishes the
evals. All results were written to the **persistent 50 GB volume `vol-066389517f2740f19`**
(name "Rohan", us-east-1b, DeleteOnTermination=false — survives termination).

## Result files on the volume (`/mnt/rohan/mammal_ft/`)
- `SUMMARY.txt`       — consolidated BBBP + PGK2 train + eval results
- `eval_bbbp.json`    — BBBP penetrance: AUROC + enrichment on held-out scaffold test
- `eval_pgk2.json`    — PGK2 binder triage: AUROC + top-5/10% enrichment on held-out set
- `eval_*_raw.json`   — per-sample P(<1>) + labels (recompute if needed)
- `autorun.log`, `bbbp.log`, `pgk2.log` — full logs
- `runs/bbbp_ft/best_epoch-v1.ckpt`, `runs/pgk2_ft/best_epoch*.ckpt` — the fine-tuned models

## To read results when AWS access is back
1. Confirm the instance is gone (terminated):
   `aws ec2 describe-instances --instance-ids i-0e4a5087c22fa257e --region us-east-1 --query "Reservations[].Instances[].State.Name" --output text`
2. Launch a cheap instance in **us-east-1b** (same AZ as the volume), e.g. t3.micro with the
   same key `mammal-ft-rohan` + SG `sg-0b9722ea0ea2f1e87`, attach the volume, mount, read:
   `aws ec2 attach-volume --volume-id vol-066389517f2740f19 --instance-id <new> --device /dev/sdf --region us-east-1`
   then `sudo mount /dev/nvme1n1 /mnt/rohan` (device name may vary; check `lsblk`) and
   `cat /mnt/rohan/mammal_ft/SUMMARY.txt`.
3. Terminate the cheap instance when done. (Or just attach the volume to any us-east-1b box you already run.)

Launch vars: see `.launch_vars`. Key pem: `mammal-ft-rohan.pem` (gitignored).
