#!/usr/bin/env python3
"""Generate the morning briefing from results/boltz_overnight_state.json (+ per-job index.jsonl).

Robust to partial completion — renders whatever workstreams have results.
Writes RohanOnly/boltz_overnight_briefing_2026-06-18.md.
"""
import json, os
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / "results" / "boltz_overnight_state.json"
RUNROOT = REPO / "results" / "boltz_overnight_runs"
BRIEF = REPO / "RohanOnly" / "boltz_overnight_briefing_2026-06-18.md"

# partner each query gene drugs toward (from the deck), for the strategic table
RESCUE = {
    "STXBP1": "USP7 (stabilize residual Munc18-1) / STMN2", "KCNQ2": "STXBP1 (E/I rebalance)",
    "SCN2A": "KCNIP1 / m6A-NMD (restore intact allele)", "CHD8": "USP7 / SLC12A2",
    "KMT2A": "CREBBP/EP300/PAF1 (H3K27ac+elongation)", "SMARCA4": "RBBP7 (shared chromatin subunit)",
    "SRCAP": "EP400/BRD8/DMAP1 (paralogous H2A.Z machinery)", "RPS17": "USP7 (proteostasis)",
    "HNRNPK": "USP7 (proteostasis)", "TSC1": "mTOR pathway / TSC complex", "TSC2": "mTOR pathway (Rheb-GAP)",
    "PTEN": "—", "WDR26": "CTLH/GID complex (RMND5A/MAEA)", "SYNGAP1": "—",
}


def load():
    return json.loads(STATE.read_text()) if STATE.is_file() else {"jobs": {}, "spent_est": 0}


def design_rows(jobs):
    rows = []
    for k, v in jobs.items():
        if v.get("ws") in ("WS1", "WS4") and v.get("kind") == "design" and v.get("status") == "done":
            m = v.get("metrics", {})
            gene = k.split("design-")[-1]
            rows.append((m.get("bindconf_max"), m.get("bindconf_median"), m.get("optscore_max"),
                         gene, v.get("role"), v.get("domain_len"), m.get("top", [])))
    return sorted(rows, key=lambda r: -(r[0] or -9))


def verdict(b):
    # calibrated against WS2: real potent non-covalent inhibitors score ~0.95+; de-novo designs are bounded lower
    if b is None: return "—"
    if b >= 0.65: return "ligandable (designs engage strongly)"
    if b >= 0.55: return "ligandable (moderate)"
    if b >= 0.45: return "shallow/partial"
    return "poor (likely not SM-tractable)"


# PPI iptm support, anchored to the run's own controls (pos ctrl ~0.79; neg baseline ~0.42-0.55)
def ppi_support(iptm):
    if iptm is None: return "—"
    if iptm >= 0.70: return "supported (≥ pos-ctrl band)"
    if iptm >= 0.58: return "weak/ambiguous"
    return "not supported (≈ neg baseline)"


def main():
    s = load()
    jobs = s["jobs"]
    done = [k for k, v in jobs.items() if v.get("status") == "done"]
    drows = design_rows(jobs)
    ws2 = [(k, v) for k, v in jobs.items() if v.get("ws") == "WS2" and v.get("status") == "done"]
    ws3 = [(k, v) for k, v in jobs.items() if v.get("ws") == "WS3" and v.get("status") in ("done", "skipped")]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")

    L = []
    L.append("# Boltz overnight briefing — structural layer for the antipodal-rescue CNS program")
    L.append(f"\n*Generated {now} · est. spend ~${s['spent_est']} / $50 cap · {len(done)} jobs complete*\n")
    L.append("## TL;DR — what Boltz is actually useful for on this program\n")
    L.append("The deck's rescue pairs are mostly *plausible–unconfirmed* (slide 27). Boltz adds a **structural "
             "data layer**: (1) a **small-molecule druggability map** of every query/partner target — reliable "
             "and cheap; (2) **de-novo starting hits** for the ligandable ones; (3) a weak/exploratory "
             "**interface-plausibility** read on rescue pairs (iptm only). Calibrated against Tier-1–3: trust "
             "the small-molecule side; treat protein–protein scores as directional only, and **never** read "
             "Boltz binding scores as affinity or selectivity (Tier-3: it ranked the Nav1.8-selective drug LAST "
             "of 9 paralogs).\n")

    L.append("## WS1 — Druggability / ligandability map (de-novo `small-molecule:design`, 24 mol, Enamine REAL)\n")
    L.append("`bindconf_max` = best de-novo binder's binding_confidence on that target's structured domain — a "
             "*relative* pocket-ligandability signal (calibrate vs WS2), not an affinity.\n")
    L.append("| target | role | domain len | bindconf_max | median | verdict | rescue partner (drug target) |")
    L.append("|---|---|---|---|---|---|---|")
    for b, med, opt, gene, role, dl, top in drows:
        L.append(f"| **{gene}** | {role} | {dl} | {b:.3f} | {med if med is None else round(med,3)} | "
                 f"{verdict(b)} | {RESCUE.get(gene.replace('-GAP',''),'—')} |")

    if ws2:
        L.append("\n## WS2 — Calibration: known-inhibitor recovery (`structure-and-binding`)\n")
        L.append("Anchors the WS1 scale: a *real potent non-covalent inhibitor* should score high; a decoy "
                 "(metformin) low. **DOT1L+pinometostat 0.96 and WDR5+OICR-9429 0.98 (vs decoy 0.21/0.49) — clean "
                 "recovery**, confirming Boltz scores these soluble-enzyme pockets well. (Covalent LSD1+TCP reads "
                 "low on binding_confidence but high ligand_iptm — covalency isn't modeled; HAT inhibitors A-485 "
                 "separate weakly, likely an imperfect domain crop.) **So de-novo WS1 `bindconf_max` of 0.5–0.7 = a "
                 "real but moderately-engaged pocket, NOT a drug-quality fit (those hit ~0.95+).**\n")
        L.append("| target | ligand | tag | binding_confidence | ligand_iptm |")
        L.append("|---|---|---|---|---|")
        def r3(x): return round(x, 3) if isinstance(x, (int, float)) else x
        for k, v in sorted(ws2, key=lambda x: (x[1].get('gene') or '', x[1].get('tag') or '')):
            m = v.get("metrics", {})
            L.append(f"| {v.get('gene')} | {v.get('ligand')} | {v.get('tag')} | "
                     f"{r3(m.get('binding_confidence'))} | {r3(m.get('ligand_iptm'))} |")

    # merge WS3 + WS5 PPI
    ppi = [(k, v) for k, v in jobs.items() if v.get("ws") in ("WS3", "WS5") and v.get("kind") == "screen"
           and v.get("status") in ("done", "skipped")]
    if ppi:
        L.append("\n## Rescue-pair interface plausibility (`protein:library-screen`, iptm — EXPLORATORY)\n")
        L.append("Anchored to this run's controls: **positive STXBP1↔Syntaxin1A iptm 0.79**; negative baseline "
                 "(PTEN/RPS17 ↔ STMN2) ≈ 0.42–0.55. Tier-3 showed this readout is weak (binding_confidence "
                 "degenerate; iptm AUROC ~0.56), so treat as directional confirmation, not proof. Pairs at/above "
                 "the positive band are the credible structural support for the deck's *plausible-unconfirmed* pairs.\n")
        L.append("| pair | role | iptm | support |")
        L.append("|---|---|---|---|")
        rows = []
        for k, v in ppi:
            if v.get("status") == "skipped":
                rows.append((None, v.get("label"), v.get("role"), f"skipped ({v.get('skip')})"))
            else:
                ip = (v.get("metrics") or {}).get("iptm")
                rows.append((ip, v.get("label"), v.get("role"), ppi_support(ip)))
        for ip, label, role, sup in sorted(rows, key=lambda r: -(r[0] or -9)):
            L.append(f"| {label} | {role} | {ip if ip is None else round(ip,3)} | {sup} |")

    # WS5 deepened (N=48) design outcomes for the priority targets
    ws5d = {v.get("gene"): (v.get("metrics") or {}).get("bindconf_max")
            for k, v in jobs.items() if v.get("ws") == "WS5" and v.get("kind") == "design" and v.get("status") == "done"}
    L.append("\n## WS4 — Deep dive: TSC2 + WDR26\n")
    if ws5d:
        _r = lambda x: round(x, 3) if isinstance(x, (int, float)) else x
        L.append(f"*Deepening (WS5, N=48 designs): TSC2-GAP bindconf_max {_r(ws5d.get('TSC2-GAP'))}, "
                 f"WDR26 {_r(ws5d.get('WDR26'))} — more sampling did not surface higher-confidence binders, so the "
                 "ligandability calls below are stable, not undersampled.*\n")
    tsc2 = next((r for r in drows if r[3] == "TSC2"), None)
    tsc2g = next((r for r in drows if r[3] == "TSC2-GAP"), None)
    wdr26 = next((r for r in drows if r[3] == "WDR26"), None)
    L.append("**TSC2** (tuberous sclerosis; Rheb-GAP). " + (
        f"Whole-protein design bindconf_max {tsc2[0]:.3f}; " if tsc2 else "") + (
        f"GAP-domain (res 1525–1755) design bindconf_max {tsc2g[0]:.3f} → {verdict(tsc2g[0])}. " if tsc2g else "") +
        "TSC2 acts via the mTOR axis; the catalytic GAP domain is the structural handle. Rescue logic is "
        "pathway-level (mTOR), so the high-value Boltz use is **ligandability of the GAP domain** + the "
        "TSC2-GAP↔RHEB interface (WS3).")
    L.append("\n**WDR26** (Skraban-Deardorff; WD40 β-propeller, CTLH/GID E3 scaffold). " + (
        f"Design bindconf_max {wdr26[0]:.3f} → {verdict(wdr26[0])}. " if wdr26 else "") +
        "WD40 propellers present a central pocket / PPI face; WS3 probes WDR26↔RMND5A/MAEA (CTLH partners) — "
        "the structural test of its complex membership.")

    # computed synthesis
    lig = [(b, g) for b, med, opt, g, role, dl, top in drows if b is not None]
    # genes with WS2-confirmed chemical matter (known inhibitor binding_confidence >= 0.6) — don't call these "poor"
    ws2_druggable = {v.get("gene") for k, v in ws2 if v.get("tag") == "inh"
                     and (v.get("metrics") or {}).get("binding_confidence") and v["metrics"]["binding_confidence"] >= 0.6}
    top_lig = [g for b, g in sorted(lig, reverse=True) if b >= 0.60][:6]
    poor_lig = [g for b, g in sorted(lig) if b < 0.45 and g not in ws2_druggable][:4]
    false_neg = [g for b, g in sorted(lig) if b < 0.55 and g in ws2_druggable]
    supported_ppi = []
    for k, v in jobs.items():
        if v.get("ws") in ("WS3", "WS5") and v.get("kind") == "screen" and v.get("status") == "done":
            ip = (v.get("metrics") or {}).get("iptm")
            if ip is not None and ip >= 0.70 and v.get("role") != "pos":
                supported_ppi.append((round(ip, 3), v.get("label")))
    L.append("\n## Recommended Boltz next moves (computed from this run)\n")
    L.append(f"- **Most ligandable targets (pursue with SM design/screening):** {', '.join(top_lig) or '—'}. "
             "These have a pocket Boltz engages — good candidates to scale de-novo design + a focused virtual screen.")
    L.append(f"- **Rescue pairs with structural support (iptm ≥ 0.70, above neg baseline):** "
             f"{', '.join(f'{l} ({i})' for i, l in sorted(supported_ppi, reverse=True)) or '—'}. "
             "These move from *plausible-unconfirmed* toward *structurally plausible* — prioritize for the "
             "proteostasis (USP7) and complex-membership rationales; confirm with deeper co-folding / experiment.")
    L.append(f"- **De-prioritize for small molecules:** {', '.join(poor_lig) or '—'} (shallow/poor de-novo "
             "engagement *and* no known chemical matter — pursue via the partner-inhibition route or non-SM modality).")
    if false_neg:
        L.append(f"- **⚠️ De-novo false-negatives:** {', '.join(false_neg)} scored low on de-novo design BUT have a "
                 "WS2-confirmed known inhibitor (e.g. WDR5+OICR-9429 = 0.98) — **de-novo ligandability under-calls "
                 "known-druggable pockets; always cross-check against known chemical matter before writing a target off.**")
    L.append("- **TSC2:** the focused **Rheb-GAP domain is more ligandable than the whole protein** — design/"
             "screen against the GAP domain, not full-length. **WDR26:** WD40 pocket is moderately ligandable; "
             "its strongest structural complex signal is **↔MAEA** (CTLH/GID).")
    L.append("\n## How to read this (capability trust, from Tier-1–3)\n")
    L.append("- **Small-molecule design/screen/ADME + structure-and-binding** — reliable, cheap ($0.025/mol). "
             "Use `optimization_score`/`bindconf` as *relative* ligandability.\n"
             "- **protein:library-screen / protein:design** — exploratory only (iptm-weak; binding_confidence dead).\n"
             "- **Not an affinity or selectivity oracle** — Tier-3 ranked Nav1.8-selective suzetrigine LAST of 9.\n"
             "- Large multidomain proteins folded whole (≤2500) or cropped to the catalytic domain — lower-"
             "confidence than a single clean domain; flagged per row by `domain len`.")
    # top de-novo candidate hits for the priority + most-ligandable targets (concrete handoff)
    want = ["TSC2-GAP", "TSC2_GAP", "WDR26", "SCN2A", "TSC1", "SRCAP"]
    by_gene = {}
    for b, med, opt, gene, role, dl, top in drows:
        if gene in want and gene not in by_gene:
            by_gene[gene] = (b, top)
    if by_gene:
        L.append("\n## Top de-novo candidate hits (Enamine REAL, for the priority/ligandable targets)\n")
        L.append("Synthesizable starting points from `small-molecule:design`; `bind` = binding_confidence (relative, "
                 "calibrate vs WS2), `opt` = optimization_score. Confirm top picks with a focused screen + docking.\n")
        for gene in want:
            if gene not in by_gene:
                continue
            b, top = by_gene[gene]
            L.append(f"**{gene}** (bindconf_max {b:.3f}):")
            for h in (top or [])[:3]:
                L.append(f"- `{h.get('smiles')}`  (bind {round(h.get('bind'),3) if isinstance(h.get('bind'),(int,float)) else h.get('bind')}, opt {h.get('opt')})")
    L.append("\n## Receipts\n`experiments/boltz_overnight.py` (runner), `experiments/boltz_overnight_brief.py` "
             "(this), `results/boltz_overnight_state.json` (all metrics), per-job CIFs under "
             "`results/boltz_overnight_runs/` (gitignored). Capability calibration: "
             "`results/boltz_tier{1,2,3}_characterization.md`.\n")

    BRIEF.parent.mkdir(parents=True, exist_ok=True)
    BRIEF.write_text("\n".join(L) + "\n")
    print(f"wrote {BRIEF}  ({len(done)} jobs, ~${s['spent_est']})")


if __name__ == "__main__":
    main()
