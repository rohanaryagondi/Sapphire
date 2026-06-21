# Variant-effect / channelopathy GoF-LoF — MissION + ESM-2 baseline (NEW capability, 2026-06-14)

A genuinely **new capability** for Quiver's CNS/channelopathy focus: predicting whether an ion-channel
**missense variant is gain- or loss-of-function** from sequence — the computational complement to what
Quiver's V1-T measures functionally. Triggered by the scout flagging **MissION** as "uniquely
Quiver-native." **Setup:** g5.xlarge, ESM-2 650M; funNCion's labelled ion-channel GoF/LoF set. ~$0.4.

## Verdict: **funNCion (open, Apache-2.0, paper AUROC 0.897) is the adoptable model for ion-channel GoF/LoF. MissION (0.925) is marginally better but PORTAL-ONLY (no repo/weights) → not adoptable. A generic pLM (ESM-2 LLR) is INSUFFICIENT (0.665) — it scores deleteriousness, not direction. And Nav1.8 isn't in any public set — the gap Quiver's own V1-T data is positioned to fill.**

### MissION — not offline-usable (documented)
MissION (medRxiv 2025.10.16.25337735, Synaptica) reports AUROC **0.925** on 3,176 channel GoF/LoF variants
(ESM-2 + GO/HPO features). But it ships **no public repo and no downloadable checkpoint** — reachable only
via the web portal `synaptica.nl/variant-interpreter` (per-variant lookups, no batch API), and its variant
set isn't distributed. **Verdict: not adoptable** for a Quiver pipeline as-is (portal demo only).

### funNCion — the open, adoptable reference
The paper MissION benchmarks against: **funNCion** (`github.com/heyhen/funNCion`, Apache-2.0) ships the real
labelled data (used here) and reports **AUROC 0.897** on ion-channel GoF/LoF. Open, downloadable, and only
~0.03 AUROC behind MissION. **This is the off-the-shelf winner for channelopathy variant interpretation.**

### Generic pLM baseline (ESM-2 650M masked-marginal LLR) — insufficient
On funNCion's functional GoF/LoF set (1,008 variants, 385 GoF / 623 LoF, 12 channel genes):
| Scope | AUROC | n | note |
|---|---|---|---|
| **Overall** | **0.665** | 1,008 | directional strength 0.165; balanced-acc 0.64 |
| SCN5A (Nav1.5) | 0.737 | 67 | best Quiver channel |
| SCN1A (Nav1.1) | 0.684 | 448 | (10 GoF / 438 LoF — imbalanced) |
| SCN2A (Nav1.2) | 0.582 | 116 | near chance |
| SCN4A (non-Quiver) | 0.886 | 54 | — |
| SCN8A/Nav1.6, SCN9A/Nav1.7, CACNA1C/Cav1.2 | — | — | single-class (all GoF) → no AUROC |

ESM-2's LLR is a **conservation/deleteriousness** signal, not a **direction** signal — so it lands at a
modest 0.665 overall (weakly above chance because GoF and LoF variants differ somewhat in conservation),
far below funNCion's 0.897. **This is the motivating result: a generic protein LM is not enough to call
GoF-vs-LoF on Quiver's channels; a channel-specialized model is required.**

### The Quiver-specific gaps (and the moat)
- **Nav1.8 (SCN10A) and SCN3A are ABSENT** from funNCion's functional set. So *no public model* — funNCion
  or MissION — is trained to call GoF/LoF on **Nav1.8**, Quiver's flagship channel.
- The two-class validatable Quiver channels here are **SCN1A, SCN2A, SCN5A**; SCN8A/SCN9A/CACNA1C are
  single-class in this set (all-GoF), so even funNCion's per-gene reliability on them is unestablished publicly.
- **This is precisely where Quiver's V1-T is the moat:** Quiver measures variant *function* directly. A
  variant-effect model fine-tuned on Quiver's own Nav1.8 (and SCN8A/9A) functional readouts would cover the
  exact channels the public models miss — the same "Quiver-data fine-tune on targets IBM/public models
  have no head for" thesis as the Nav binder fine-tune.

## Scorecard impact
Adds a **new capability row — "Variant effect / channelopathy GoF-LoF"**: **winner = funNCion** (Apache-2.0,
0.897) for the public channels; **MissION not adoptable** (portal-only); **generic pLM insufficient** (ESM-2
LLR 0.665). **Build-don't-buy for Nav1.8** specifically (absent from public training data → Quiver V1-T
fine-tune). Does not change Tracks 1-9 winners.

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/mission/mission_result.json`; eval
`aws/mission_eval.py` (funNCion data + ESM-2 LLR; MissION section SKIPs cleanly — no public artifact);
instance `i-03dd06bf454c1f1b0` self-terminated; no strays.
