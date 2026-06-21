# Scout-candidate AWS test campaign — high-detail characterization (2026-06-14)

Empirically test the highest-ROI untested candidates from `docs/model_scout_2026-06-14.md`, at
Boltz-level detail (where each works/fails + why), to see if any actually beats a current winner
**on our substrate**. Budget **$20**. Autonomy: ScheduleWakeup self-chain (build → launch → monitor
→ write-up → next). Safety: only `Owner=RohanAryaGondi` resources + our S3 prefix; never touch
others'; self-terminate + verify-no-strays each job; no weights to this laptop; ephemeral 100 GB root
(no EBS attach/grow); ≤2 toolchain-fix relaunches per fragile model then bank; creds in /tmp only + shred.

## In scope (4 phases — all models-branch lanes, cheap, fit our data-poor reality)
1. **ULTRA** (Track 6 KG) — zero-shot inductive KG link-prediction FM (MIT, 168k params). Does it beat
   PROTON's known-binder ranking (median 4.3%) AND avoid PROTON's hub bias (Bepridil-for-everything)
   AND handle novel targets (PROTON's `binder_not_in_kg` failure)? Detail: per-target rank, hub-bias
   check, inductive novel-target case, head-to-head vs PROTON. ~$0.3.
2. **CardioGenAI / CToxPred2** (Track 5 tox) — tri-channel **hERG + NaV1.5 + CaV1.2** classifier (MIT).
   Detail: per-channel AUROC on TDC hERG_Karim + our panels, calibration/UQ, applicability domain,
   head-to-head vs our hERG (FP-XGBoost 0.89 / ChemBERTa); does it flag **NaV1.5** (cardiac off-target)
   for the Nav drugs? ~$0.3.
3. **AdaMBind** (Track 2/3 DTI) — MAML **few-shot** drug-target affinity (cold-start). Detail: zero-shot
   vs few-shot (k=5 adaptation) AUROC on Nav1.8/mTOR binder-decoy panels, head-to-head vs BALM
   (0.857/1.000) + Boltz-2 (0.714/1.000). Tests the cold-start claim = the Nav-fine-tune prior-art. ~$0.3–1.
4. **CheMeleon (CC0) + MapLight** (Track 4 ADMET) — data-efficient descriptor FM + the well-calibrated
   CatBoost recipe. Detail: TDC BBB/hERG/DILI scaffold-split + AD reliability + calibration,
   head-to-head vs MolFormer-XL (0.889). The two scout-flagged BBBP-displacer candidates. ~$0–0.5.

Total projected: **~$2–5 of $20** (4 cheap jobs + retry headroom).

## Deferred (with reason)
- **Protenix-v2** (Track 9 co-folding) — it's the **`boltz` branch's lane** (co-folding) + A100 +
  cuequivariance toolchain ($4–8, fragile). Coordinate with the boltz branch; don't launch here.
- **CLOOME / PhenoScreen** (Track 7 moat) — needs **Mahdi's paired (V1-T trace, compound) data** for the
  real test; off-the-shelf it ingests Cell-Painting images, not our traces. Blocked until that lands.
- **MissION** (frontier, ion-channel GoF/LoF) — different task (variant effect, not binding); Quiver-
  native and worth doing, but lower priority + needs the variant dataset. Queue after the 4 above.

## Build → run
Eval scripts + userdata are built+verified by a workflow (each builder reads the model's REAL repo
inference API from source — no arg-name guessing — and follows the proven `balm_characterization`
userdata pattern: self-contained venv, torch≥2.6/cu124 where .bin checkpoints, numpy<2 w/ rdkit==2022.9.5,
defensive per-section guards, S3 result upload, creds-redaction, watchdog, shutdown=terminate). Then the
autonomous chain stages each to its S3 prefix, launches a g5.xlarge, monitors, writes
`results/<model>_characterization.md` + updates the scorecard + commits, and advances. Master report at the end.
