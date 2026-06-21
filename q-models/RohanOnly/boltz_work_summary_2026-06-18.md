# Boltz Work — Summary

*Quiver Bioscience · 2026-06-18 · what we tested with Boltz and what it's worth*

## What Boltz is, and the unlock

Boltz-2 is an open structure-and-binding model (MIT) — it co-folds a protein–ligand complex from
sequence and scores the binding. We run it through the **hosted boltz-api**, which removes the local
CUDA/GPU install blocker entirely: **no GPU, no toolchain, pay per molecule.** That made a broad,
cheap sweep of every Boltz capability possible.

## The six capabilities — what works

| Capability | Verdict | Best readout | Cost |
|---|---|---|---|
| Structure-and-binding (co-fold one complex) | ✅ works | `ligand_iptm` | ~$0.20 / fold |
| **Library-screen** (rank a compound set vs a target) | ✅ **the workhorse** | `optimization_score` | **$0.025 / molecule** |
| Small-molecule de-novo design | ✅ works (real, novel, synthesizable) | `optimization_score` | $0.025 / molecule |
| ADME (solubility / permeability / logD) | ✅ directional; **free inside every screen** | — | $0.01 / molecule |
| Protein library-screen (rank protein binders) | ◑ exploratory only | `iptm` (weak) | per-fold |
| Protein de-novo design (peptides/binders) | ◑ exploratory only | `iptm` (unreliable) | per-fold |

**Plain version:** Boltz's small-molecule side is reliable and cheap; its protein-binder side is not
yet trustworthy. The everyday tool is **library-screen** — same accuracy as per-fold at ~8× lower cost,
and it returns a free ADME column on every row.

## What we ran (5 campaigns, ~$51 total)

1. **Tiers 1–3 — capability characterization (~$6.7).** Established the table above on Quiver substrate.
   Nav1.8 binder-vs-decoy: AUROC **0.89** (`ligand_iptm`). De-novo: **24/24 valid, 22/24 novel scaffolds**.
   Key negative: in a selectivity test, Boltz ranked the Nav1.8-selective drug suzetrigine **last of 9
   Nav paralogs** — so it is *not* a selectivity oracle.
2. **Library-screen enrichment.** On a 44-compound Nav1.8 set (actives + decoys), enrichment AUROC **0.81**
   — at $0.025/molecule. This is the operational triage workflow.
3. **OOD rescue (the complement story).** Our per-target ligand fine-tune scored suzetrigine as a false
   negative (novel 2024 scaffold). Boltz scored it 2nd-highest of 11, above every decoy. **Structure
   catches the novel scaffolds the ligand model misses** — they're complementary, not competing.
4. **Overnight druggability map (~$19).** Ranked **23 CNS-program targets** by how ligandable their pocket
   is. Most ligandable: **SCN2A, TSC1, SRCAP, EP300/EP400**. Least: **KMT2A** (shallow). For TSC2, the
   Rheb-GAP domain is more ligandable than the full protein.
5. **Partner-target validate-then-deploy (~$26).** The headline result. On the 6 druggable "rescue
   partner" enzymes from the CNS deck (USP7, LSD1, DOT1L, WDR5, HDAC1, BRD4):
   - **Triage works on all 6** (AUROC 0.79–0.99; WDR5 0.99, BRD4 0.97).
   - **Potency ranking works on some** (WDR5 Spearman 0.92, LSD1 0.72) — the first time we've shown Boltz
     can rank *how potent*, not just bind-or-not.
   - **Selectivity works here** (3/4 selective tool compounds put the true target/isoform top) — the
     opposite of the ion-channel failure, because these enzymes have distinct pockets.
   - Then **deployed** it: de-novo design + a 150-compound CNS-drug repurposing screen on the top targets
     (WDR5/KDM1A/BRD4) → ranked candidate inhibitors with free ADME.

## Bottom line — where Boltz is useful for Quiver

- **Use it for:** binder triage at scale (library-screen), novel-scaffold rescue, druggability mapping of
  new targets, and **finding inhibitors of the soluble "rescue partner" enzymes** in the CNS program —
  where it triages, ranks potency, *and* gets selectivity right.
- **Don't use it for:** ion-channel binder triage (chance off-the-shelf — that's the fine-tune's job),
  subtype selectivity, absolute affinity, or protein-binder design.
- **One rule to remember:** Boltz scores are *relative pocket ligandability*, not affinity or selectivity.
  Always calibrate against a known inhibitor (e.g. WDR5 + OICR-9429 scores 0.98) before trusting a number.

## Where the detail lives
`results/boltz_tier{1,2,3}_characterization.md` (capabilities) · `RohanOnly/boltz_overnight_briefing_2026-06-18.md`
(druggability map) · `RohanOnly/boltz_partner_target_hits_2026-06-18.md` (partner targets + deployed hits).
