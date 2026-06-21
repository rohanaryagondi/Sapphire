# Boltz-API Tier-3 — selectivity + the two protein capabilities, 2026-06-17

Rounds off all 6 Boltz Compute capabilities. ~$1.03 (estimate $1.025). Driver `experiments/boltz_tier3_run.py`,
raw `results/boltz_tier3_result.json`. Protein targets are capped at **≤1300 residues combined (target+binder)**
and small-molecule targets at **≤2500**, so the protein tests use a Nav1.7 domain-II crop (the ProTx-II/HwTx-IV
gating-modifier site).

## T7 — suzetrigine selectivity across 9 Nav paralogs (deferred Q2, run cheaply via 1-molecule screens)

Ran suzetrigine as a 1-molecule `library-screen` against each of the 9 Nav paralogs ($0.025 each, $0.225 total —
~10× cheaper than the per-fold route). **Result: decisively negative.**

| rank by binding_confidence | paralog | binding_confidence |
|---|---|---|
| 1 | Nav1.1 | 0.492 |
| … | Nav1.3 / 1.7 / 1.6 / 1.5 / 1.9 / 1.4 / 1.2 | 0.47 → 0.38 |
| **9 (last)** | **Nav1.8** (the real selective target) | **0.355** |

Suzetrigine is a clinically **Nav1.8-selective** blocker, yet Boltz scores Nav1.8 **last of nine** —
binding_confidence, optimization_score (flat 0.24–0.33), and iptm (Nav1.8 0.421, also lowest) all fail to
prefer the true target. **Zero-shot Boltz scores do not capture ion-channel subtype selectivity** — consistent
with Tier-1 Q1 (binding_confidence missed the weak pore binders) and the broader finding that off-the-shelf
structure is not an affinity/selectivity oracle on Nav-family channels. Read Boltz binding scores as a *relative
pocket/ligandability* signal, not a selectivity ranking.

## T8 — protein:library-screen (Nav-VSD toxins vs K-channel toxins → Nav1.7 DII)

3 Nav-channel gating-modifier toxins (ProTx-II, HwTx-IV, ProTx-I) vs 3 K-channel toxins (apamin, charybdotoxin,
iberiotoxin). **`binding_confidence` is degenerate for protein–protein (0.000 for all 6); `iptm` is the only
usable readout, and it is weak:**

| peptide | class | iptm |
|---|---|---|
| ProTx-II | Nav (+) | **0.799** ✓ top |
| Apamin | K (–) | 0.707 ✗ false-positive |
| HwTx-IV | Nav (+) | 0.592 |
| Iberiotoxin | K (–) | 0.479 |
| Charybdotoxin | K (–) | 0.465 |
| ProTx-I | Nav (+) | 0.237 ✗ miss |

iptm correctly puts the gold-standard Nav1.7 toxin (ProTx-II) on top, but a K-channel decoy (apamin)
false-positives and ProTx-I is missed → **AUROC ≈ 0.56** (barely above chance, n=6, approximate DII crop).
**Verdict: protein-screen works mechanically; use `iptm` not `binding_confidence`; treat interface scores as
low-confidence/exploratory.**

## T9 — protein:design (de-novo peptide binders to Nav1.7 DII)

10 peptides generated; **iptm up to 0.884** (high interface confidence), binding_confidence degenerate (~1e-6).
But the sequences are **generic amphipathic helices** (`…GGLLA…`-type, 26–27-mer, no cysteine framework) — they
dock the VSD groove with high model self-confidence but look nothing like real disulfide-rich gating-modifier
toxins. **Capability works; biological realism is doubtful** — high iptm reflects model self-consistency on a
docked helix, not a designed toxin. Use only as exploratory ideation, never as a standalone design oracle.

## Net — all 6 capabilities now characterized

| capability | verdict | best readout |
|---|---|---|
| structure-and-binding | ✅ works (Nav 0.89 ligand_iptm); not a selectivity oracle | ligand_iptm |
| adme | ✅ directionally sound, cheap | solubility/perm/logD |
| small-molecule:library-screen | ✅ enrichment 0.81; **not** selectivity (T7) | optimization_score |
| small-molecule:design | ✅ valid, novel, synthesizable de-novo | optimization_score |
| protein:library-screen | ◑ weak (iptm-only, ~0.56), binding_confidence dead | iptm |
| protein:design | ◑ mechanically works, realism doubtful | iptm |

**Strategic read:** Boltz's small-molecule side (screen/design/ADME + structure-and-binding) is the reliable,
cheap value; the protein side is exploratory-only. Use binding scores as *relative ligandability* signals
(calibrate against known binders), not absolute affinity or selectivity.

**Receipts:** `experiments/boltz_tier3_run.py`, `results/boltz_tier3_result.json`, per-job files under
`results/boltz_tier3_runs/` (gitignored).
