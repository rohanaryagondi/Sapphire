# Model scout — untested models worth considering per track (2026-06-14)

Output of a 10-agent research workflow (one scout per track + frontier + adversarial judge) over the
2024–2026 landscape, given everything we've already tested. **Verdict: nothing clears our empirical
bar to *displace* a winner** — every candidate is paper-SOTA, untested on our data-poor / no-holo
substrate, and self-flagged non-displacing. So all current winners stand; this is a **prioritized
test-queue**, not a set of UI changes. (The one UI change made: a flagged "ProTrek to watch" note on
the Track-1 tab — see below.) Supersedes/extends `docs/untested_candidates_2026-06-14.md`.

## Highest-ROI candidates (the ones actually worth running)
1. **ULTRA (+UltraQuery)** — *Track 6 KG.* 168k-param KG **foundation model**, inductive **zero-shot**
   link prediction (ICLR 2024, MIT). Directly attacks PROTON's two documented failures (novel-target =
   `binder_not_in_kg`, and hub bias). ~$0 (runs local, 168k params). **Top pick — cheap, targets a
   known weakness.**
2. **CardioGenAI / CToxPred2** — *Track 5 tox.* MIT tri-channel cardiac classifiers: **hERG + NaV1.5 +
   CaV1.2**. Our hERG gate is single-channel; these add **NaV1.5** (the cardiac off-target that the
   Nav-selectivity story cares about) + CaV1.2, and CToxPred2 ships per-compound uncertainty. ~$0 local.
   Most Quiver-relevant tox upgrade.
3. **AdaMBind** — *Track 2/3 DTI.* MAML **few-shot** drug-target affinity, sequence+SMILES, cold-start
   by design — the closest external prior-art to the planned **Quiver Nav fine-tune**. ~$0.30–1.
4. **CheMeleon (CC0) / MapLight** — *Track 4 ADMET.* CheMeleon = descriptor-pretrained D-MPNN built for
   **data-efficient** small-set fine-tuning (public domain). MapLight = the only TDC-ADMET method the
   2026 critical assessment found **well-calibrated**. Both scout-flagged as possible BBBP displacers;
   ~$0 local. Worth a head-to-head vs MolFormer-XL.
5. **Protenix-v1/v2 (ByteDance, Apache-2.0)** — *Track 9 / frontier.* Open AF3-reproduction that
   **co-folds** (so it works on no-holo targets like Boltz-2) with a **cleaner commercial license**.
   A second independent co-folding oracle + paralog cross-check. ~$4–8 (A100, Boltz-class). Coordinate
   with the `boltz` branch.
6. **MissION** — *frontier, uniquely Quiver-native.* pLM ion-channel **missense GoF/LoF** classifier
   (3,176-variant set). The only frontier item natively on Quiver's CNS/ion-channel genetics — a
   GoF/LoF head to prioritize CRISPR-N hits. ~$0–2 (fine-tune ESM-2-650M).

## Per-track summary
| Track | Winner (stays) | Notable untested candidates | Judge action |
|---|---|---|---|
| 1 family clustering | ESM-2-650M | **ProTrek-650M** (MIT trimodal function-aware → E3/NR frontier), ESM-S / SaESM2 (structure-distilled, sequence-only drop-in upgrade tests, ~$0) | worth_testing (ProTrek → UI note) |
| 2/3 DTI / binding | Boltz-2 (+BALM triage) | **AdaMBind** (few-shot), GenSPARC (SaProt-on-AF2), CORDIAL (Apache, leave-superfamily-out), IntFold (Apache co-fold, edge over Boltz — verify) | worth_testing |
| 4 BBBP/ADMET | MolFormer-XL | **CheMeleon** (CC0), **MapLight** (well-calibrated) — both scout-flagged displacers; MolE (NC, ceiling probe) | worth_testing |
| 5 tox/hERG/DILI | ChemBERTa-2 + ADMET-AI + FP/XGB | **CardioGenAI / CToxPred2** (tri-channel hERG+NaV1.5+CaV1.2 + UQ), FATE-Tox (multi-organ), ToxBERT (clinical ADR) | worth_testing |
| 6 KG | PROTON | **ULTRA** (zero-shot KG FM, attacks novel-target + hub bias), REx (RL explainable, down-weights hubs), [TxGNN/BioPathNet known] | worth_testing |
| 7 cross-modal (moat) | build-don't-buy | **CLOOME / PhenoScreen** (contrastive phenotype↔compound = the V1-T bridge template), **InfoCORE** (confounder-removal for V1-T batch effects), [Tahoe-x1 known] | keep_winner (build) |
| 8 generative | Morgan-FP + Enamine REAL | **synflownet-boltz** (GFlowNet using Boltz-2 as reward — most Quiver-native), Saturn (oracle-efficient), f-RAG (NC), PocketXMol (pocket-dependent) | keep_winner (skip — oracle is the bottleneck) |
| 9 selectivity | Boltz-2 | **Protenix-v2** (2nd co-fold oracle, Apache), MMCLKin (kinase-only, not our lane) | keep_winner |
| frontier | — | **MissION** (ion-channel GoF/LoF — Quiver-native), AEV-PLIG (fast FEP-surrogate scoring — new lane), Protenix-v1 | new capabilities |

## What this means
- **No winner is displaced.** UI unchanged except the ProTrek flagged note. Our empirical results
  (BALM family-triage, Boltz-2 co-fold, MolFormer BBBP, ChemBERTa/FP-hERG, PROTON KG) remain the picks.
- **The recurring theme** matches the overnight campaign: structure-based methods are pose/pocket-gated
  for our no-holo targets (so Boltz-2/Protenix co-folding is the route), and the highest-leverage moves
  are the **cheap, data-poor-native** ones (ULTRA, CardioGenAI, AdaMBind, CheMeleon) — not big paper-SOTA.
- **If/when budget for more AWS runs:** the order is ULTRA (KG, ~$0) → CardioGenAI (tox, ~$0) → AdaMBind /
  CheMeleon (~$0–1) → Protenix-v2 (co-fold cross-check, coordinate w/ boltz) → CLOOME (when Mahdi's
  paired V1-T data lands). Each awaits explicit approval.

**Source:** scout workflow `wf_50a23971-177` (full per-candidate detail incl. licenses, weights, evidence
in the run transcript). Licenses noted per candidate — most MIT/Apache/CC0; a few non-commercial
(MolE, f-RAG) are eval-only per our standing research posture.
