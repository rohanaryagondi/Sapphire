# Overnight autonomous campaign — Boltz-level characterization of the per-track winners (2026-06-14)

**Goal.** Give each per-track WINNER the same depth of operating-envelope characterization Boltz-2
got: not a single accuracy number, but **where it works, where it fails, and WHY** — across
targets, protein families, data splits, with statistical + calibration + applicability-domain
rigor and explicit failure-mode analysis. By morning we should be able to say, for each best model,
exactly when to trust it and when not to, and the mechanism behind each behavior.

**Budget.** $20 hard cap (this session). **Autonomy.** ScheduleWakeup self-chain: launch → monitor
every ~5 min → process result (write-up + scorecard + commit/push) → launch next → … until the
queue is empty or the budget gate trips, then write the master report. This doc is the persistent
source of truth the loop reads each wake.

## Winners and what still needs Boltz-depth

| Track | Winner | Already Boltz-deep? | This campaign |
|---|---|---|---|
| 1 — family clustering | ESM-2-650M | ✅ layer sweeps + scale ladder + 167-gene panel | Phase 4 top-up only |
| 2 — cross-modal co-embed | **BALM** | ❌ only n=11/7 | **Phase 1 — DEEP** |
| 2/3/9 — binding/selectivity | Boltz-2 | ✅ (and it's the `boltz` branch's lane) | **skip — do not run Boltz here** |
| 4 — BBBP | **MolFormer-XL** | ⚠️ partial | **Phase 2 — DEEP** |
| 5 — tox/hERG/DILI | **ChemBERTa-2 + ADMET-AI** | ⚠️ partial | **Phase 2 — DEEP** |
| 6 — KG | PROTON | ✅ asymmetry envelope | skip |

Plus opportunistic **upgrade tests** of flagged candidates under strict attempt caps (Phase 3).

---

## Phase 1 — BALM deep characterization  *(priority; ~$2–3)*
BALM just won the cross-modal question (Nav1.8 cosine-AUROC 0.857) but on only 11+7 compounds. Make
it Boltz-level:

1. **Bigger multi-target, multi-family panels.** Keep our Quiver panels (Nav1.8/mTOR + the pan-Nav
   selectivity set + WDR91 SPR) and add diverse benchmark targets — GPCR (DRD2, ADRB2), kinase
   (EGFR, BRAF), protease, nuclear receptor — with **ChEMBL actives + property-matched decoys**
   fetched on the instance (PyTDC/ChEMBL; NOT to this laptop). Target ≥50 compounds/target where
   available.
2. **Per-target & per-family AUROC + binder/decoy cosine separation** — where is the shared space
   real, where does it collapse?
3. **Cross-paralog selectivity** (the Boltz test): does BALM cosine rank Nav1.8 > Nav1.5/1.7/1.1 for
   Nav1.8-preferring drugs? Resolution at the paralog level is the hard test.
4. **Leakage / applicability-domain analysis** — the key caveat. Tanimoto of each test compound to
   common-drug space; stratify AUROC by novelty. **Is 0.857 real cold-target generalization or
   famous-drug memorization?** This is the single most important thing to resolve about BALM.
5. **Protein-truncation probe.** ESM-2 caps at 1024 tokens; Nav1.8 (1956 aa) / mTOR (2549 aa) were
   truncated yet AUROC held. Re-run windowing the **pore / binding domain** — does the signal move?
6. **Calibration.** Is BALM's pKd meaningful in absolute terms or only rank-order? (Reliability vs
   measured Kd where we have it; decoys all landed at pKd ~7 last time = inflated.)

Output: `results/balm_characterization.md` + scorecard Track 2 update. (BALM toolchain is PROVEN —
ESM-2-150M + ChemBERTa-77M, torch≥2.6/cu124, ~$0.30–0.50/run.)

## Phase 2 — De-risking layer deep dive (Track 4/5)  *(~$2–3)*
MolFormer-XL (BBBP) + ChemBERTa-2 (hERG/DILI) + ADMET-AI to full Boltz depth on big external panels
(TDC BBB_Martins, hERG_Karim n≈13k, DILI):
1. **Scaffold-split** (Murcko) held-out eval — the honest generalization number vs the random-split one.
2. **Applicability domain** — per-bin Tanimoto-to-train reliability curve; where does confidence
   become meaningless?
3. **Calibration** — Brier score + reliability diagram per endpoint.
4. **Failure-mode analysis** — which chemotypes fail (large/flexible/zwitterionic/PAINS/etc.)?
5. **One dedicated hERG model** (deephERG-style or a TDC-leaderboard recipe) head-to-head — can it
   beat ChemBERTa's 0.726 *out-of-distribution* (our external-30), or is that just an in-dist mirage?
   **≤2 setup attempts.**

Output: `results/derisking_characterization.md` + scorecard Tracks 4/5. (MolFormer/ChemBERTa/ADMET-AI
toolchains PROVEN; mostly CPU/fast.)

## Phase 3 — DTI Nav-generalization cross-check (Track 2)  *(~$1–4, capped)*
Does any structure-free affinity model crack the **Nav blind spot** that sinks everything trained on
BindingDB? Test **IPBind** (claims unseen-protein generalization) or **GatorAffinity** on the
Nav1.8/mTOR panels head-to-head with Boltz-2 (0.714/1.000) and BALM (0.857/1.000).
**STRICT ≤2 setup-fix relaunches** — if it fights the toolchain like DrugCLIP did, abandon, write a
brief "toolchain-blocked" note, and bank. Output: `results/dti_generalization.md`.

## Phase 4 — top-ups *(only if >$5 budget remains)*
ESM-2-650M on the full bigger gene panel (function-family edge cases) and/or a quick BALM
ablation. BioPathNet (KG) only if ample budget+time AND it installs cleanly (else skip — heavy).

---

## Safety rails (hard rules for the unattended shift)
- **$20 hard cap.** Track cumulative spend; before each launch, if (spent + worst-case next-job cost)
  > $18, STOP launching and go to final report. Leave a ≥$2 buffer.
- **Only the user's resources.** Tag every instance `Owner=RohanAryaGondi` + `Rohan-<Model>-*`,
  `Project=mammal-explorer`. Use ONLY my S3 prefix `s3://rohan-mammal-bootstrap-20260610-213029/`
  and instances I launch. **NEVER** `aws s3 ls`/touch other buckets, instances, or volumes.
- **Every instance**: `--instance-initiated-shutdown-behavior terminate` + an in-userdata watchdog
  (self-terminate after a max lifetime) + self-`shutdown -h now` on completion. **Verify
  termination + "no stray Owner=RohanAryaGondi instances" after every job.**
- **≤3 concurrent instances**; default sequential.
- **No model weights to this laptop.** All downloads on AWS; cache big checkpoints to my S3 (as done
  for DrugCLIP) so reruns skip re-download.
- **Storage: ephemeral gp3 root (100–120 GB) per job, deleted on terminate.** Will NOT attach or grow
  the user's EBS `vol-066389517f2740f19` unless a single job genuinely needs >120 GB (none expected).
  If one ever did, grow root minimally — never the shared EBS — and only if unavoidable.
- **Toolchain-fight cap: ≤2 setup-fix relaunches per fragile new model.** (DrugCLIP took 8 — that was
  attended; overnight we abandon fast and bank rather than burn budget.) Proven toolchains
  (BALM, MolFormer, ChemBERTa, ESM-2, ADMET-AI) get normal retries.
- **Credentials**: inject into the `/tmp` userdata copy only (sed `__AKID__`/`__SECRET__` from
  `aws configure get`), `shred` it after launch; redact creds in any uploaded log.
- **Do NOT run Boltz-2 / co-folding here** — that's the `boltz` branch's lane.
- **Verify before claiming**: independent sanity checks on every result (e.g. cosine==emb-cosine,
  n_scored==n_total, label balance) before writing a verdict.

## Deliverables by morning
- `results/balm_characterization.md`, `results/derisking_characterization.md`,
  `results/dti_generalization.md` (or abandon-note)
- `docs/models_tracks_scorecard.md` updated per track
- `docs/overnight_campaign_report.md` — master synthesis: each best model's operating envelope
  (works / fails / why), one place.
- All committed + pushed to `models`. A final spend accounting + teardown confirmation.

**Projected spend: ~$7–12 of $20** (buffer for retries/toolchain abandons).
