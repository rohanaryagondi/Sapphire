# Phase 3 `cns_new_models` (DTIAM scout) — BANKED (external ChEMBL/EBI outage), 2026-06-15

Phase 3 of the overnight CNS campaign: scout + test a **NEW** CNS-useful DTI model on the 19-target CNS
panel. The model chosen was **DTIAM** (BerMol drug tower — a 1.6M-ChEMBL-pretrained molecular encoder —
⊕ ESM-2-650M protein tower, few-shot per-target probe), a 2025-era DTI foundation model not previously
tested. **Outcome: banked — a ChEMBL/EBI API outage (HTTP 500 → unreachable) stalled the on-instance panel
build before any AUROC was produced.** Not a toolchain failure; an external data-source outage.

## What succeeded (setup is sound, relaunchable)
- Venv + toolchain assembled cleanly (torch≥2.6/cu124, transformers≥4.45, fair-esm, rdkit, gdown,
  chembl_webresource_client) — the venv-pip gotchas were handled (no rc=92).
- **DTIAM/BerMol checkpoint downloaded OK** — `BerMolModel_base.pkl` (274 MB) from the authors' Drive.
- ESM-2-650M (`facebook/esm2_t33_650M_UR50D`) configured as the protein tower.
- **9 of 22 panel targets pulled from ChEMBL before the outage:** MTOR, PKM(PKM2), PPARD, AKT1,
  RHEB (0 actives — expected sparse), RPS6KB1, SCN1A, SCN2A, SCN8A (60 actives each except noted).

## What blocked it (external)
- At target #10 (**SCN9A / Nav1.7**) the ChEMBL activity endpoint returned **HTTP 500**
  (`Error: 500 | EMBL's European Bioinformatics Institute` — a server-side EBI error page, dumped into the
  run log). The eval's `try/except` caught it (`[warn] SCN9A fetch failed`) and continued.
- The next target (**SCN10A / Nav1.8**) then **stalled with no response** — the chembl_webresource_client
  has no socket timeout, so a non-responding endpoint blocks indefinitely (would have hung to the 90-min
  watchdog). A live cross-check confirmed the outage: direct `curl` to
  `https://www.ebi.ac.uk/chembl/api/data/activity.json` and `/status.json` both **timed out (HTTP 000)**.
- **No `[dtiam]` probe lines, no AUROC** — the run never left the panel-build phase.

## Decision: terminate + bank (not relaunch)
The stalled g5.xlarge was terminated manually (`i-004ec5321344eaaca`) rather than left to burn ~50 min to
the watchdog — ChEMBL was unreachable, so the run could not complete and a relaunch would hit the same wall.
DTIAM is the **non-load-bearing new-model scout**; the campaign's CNS conclusions (Tracks 1–10, the
ion-channel fine-tune verdict from `trunc_test` + `cns_dti`) do **not** depend on it, and the "explore new
models" directive was already well-served (ULTRA, MapLight, PLAPT, CardioGenAI, MissION/funNCion, +~15
others). Spending more of the $45 budget gambling on an external EBI recovery is not justified.

## Relaunchable — what to change first
The eval (`aws/cns_new_models_eval.py`) + userdata are preserved. Before relaunch:
1. **Add a fail-fast ChEMBL timeout** — wrap each `fetch_activities` in a `signal.alarm` (or set a socket
   timeout) so a 500/stall *skips* the target and the build proceeds with whatever pulls, instead of hanging
   to the watchdog. (The DUD-E-style decoys + per-family AUROC only need a few targets per family.)
2. Relaunch when `curl https://www.ebi.ac.uk/chembl/api/data/status.json` returns 200. ~$0.5, g5.xlarge.

## Scorecard impact
**None.** Track 2/DTI winners unchanged (Boltz-2 overall; BALM family-level cosine triage; PLAPT first-pass;
ion channels at zero-shot chance → fine-tune lever). DTIAM filed as **scouted, setup-verified, eval blocked
by an EBI/ChEMBL outage — relaunchable**, not as a tested-and-rejected model.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/cns_new_models/run.log` (BerMol download OK,
9-target pull, SCN9A 500 page); `DONE` (rc=blocked); eval `aws/cns_new_models_eval.py` +
`aws/cns_new_models_userdata.sh`; instance `i-004ec5321344eaaca` terminated.
