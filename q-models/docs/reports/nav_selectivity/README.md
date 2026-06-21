# Nav-Subtype Selectivity Screen — Suzetrigine & Vixotrigine (MAMMAL DTI)

Deliverables for Ben's request (June 2, 2026): run IBM MAMMAL's drug–target binding (DTI)
head for two selective Nav channel blockers against **all nine human Nav α-subunits**
(Nav1.1–Nav1.9) as a **selectivity check** — a faithful model should score each compound's
on-target subtype high and the other eight low.

- **Suzetrigine** (VX-548 / Journavx) — selective for **Nav1.8** (~30,000-fold).
- **Vixotrigine** (BIIB074) — selective for **Nav1.7**.

## Reports

| # | Report | What it is |
|---|--------|------------|
| 1 | [**Standard run (1,250-aa truncation)**](1_Nav_selectivity_truncated_1250aa.docx) | The canonical screen on the PEER checkpoint. Result: flat ~6.8–7.5 pKD across the panel; **both compounds' true on-targets score among the lowest** → both **FAIL**. |
| 2 | [**Full-length re-run (truncation removed)**](2_Nav_selectivity_full_length_no_truncation.docx) | Companion: both DTI length caps raised so the full 1,791–2,016 aa channels are scored (verified — zero truncation). Scores inflate across the panel; suzetrigine→Nav1.8 edges up by a meaningless **+0.03**, vixotrigine still **FAILS**. |

## Bottom line

MAMMAL's off-the-shelf DTI head **cannot read Nav-subtype selectivity** for these compounds.
Run 1 shows the flat result under the default 1,250-aa truncation; Run 2 removes the
truncation and gets the same verdict (one statistically meaningless "pass," one clear fail, all
scores inflated out-of-distribution). So **truncation was not the cause** — the head simply
lacks single-target resolution. A real computational selectivity readout here would need a
Quiver-data fine-tune on the binding-domain windows, not this head.

## How it was produced

Artifacts live on the main project branch (`ui-naming-lowmem-windows`):

| Artifact | Path |
|---|---|
| Standard-run script | `experiments/phase8_nav_selectivity.py` |
| Full-length script | `experiments/phase8b_nav_selectivity_fullseq.py` |
| Authoritative writeups | `results/phase8_nav_selectivity.md`, `results/phase8b_nav_selectivity_fullseq.md` |
| Raw run outputs (JSON) | `results/phase8_nav_selectivity_*.json`, `results/phase8b_nav_selectivity_fullseq_*.json` |
| Targets + compounds | `mammal_quiver/sequences.py` (`NAV_PANEL`, `DRUGS["vixotrigine"]`) |

Checkpoint: `models/dti_bindingdb_pkd_peer` (PEER, norms 6.286 / 1.542). Nav sequences fetched
from UniProt. See each report's Reproducibility section for exact commands.
