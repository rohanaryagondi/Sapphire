#!/usr/bin/env python3
"""WS5 adaptive deepening — launched AFTER WS1-4 finish (writes the same state.json; never run concurrently).

Driven by the WS1-3 results:
  - WS3 positive control (STXBP1:syntaxin iptm 0.79) validated the protein-screen interface readout -> EXPAND
    rescue-pair PPI, focused on the USP7 proteostasis hub for the user's genes + the TSC2-GAP / WDR26 complexes.
  - Deepen de-novo design (N=48) on the user's priority targets TSC2-GAP and WDR26 for better candidate hits.
All pairs curated to fit the protein-screen cap (target+binder <= 1300 residues). Estimate-gated, idempotent.
"""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments"))
import boltz_overnight as ovn

# (label, (target_acc, crop|None), (binder_acc, crop|None), role) — USP7-TRAF = substrate-recognition domain
USP7_TRAF = ("Q93009", (53, 205))
WS5_PPI = [
    ("HNRNPK↔USP7-TRAF", ("P61978", None), USP7_TRAF, "test"),        # proteostasis rescue (deck)
    ("STXBP1↔USP7-TRAF", ("P61764", None), USP7_TRAF, "test"),        # proteostasis rescue (deck)
    ("PTEN↔USP7-TRAF", ("P60484", None), USP7_TRAF, "test"),          # USP7 stabilizes PTEN (literature)
    ("KCNQ2↔STXBP1(neg-size)", ("O43526", (1, 360)), ("P61764", None), "test"),  # KCNQ2 N-term vs Munc18
    ("TSC2gap↔TBC1D7", ("P49815", (1525, 1755)), ("Q9P0N9", None), "test"),      # TSC complex
    ("WDR26↔GID8", ("Q9H7D7", None), ("Q9NWU2", None), "test"),       # CTLH/GID partner
    ("HNRNPK↔STMN2(neg)", ("P61978", None), ("Q93045", None), "neg"), # negative control
    ("PTEN↔TBC1D7(neg)", ("P60484", None), ("Q9P0N9", None), "neg"),  # negative control
]
# deepen design (N=48) on the user's priority deep-dive targets
WS5_DESIGN = [
    ("ovn-ws5-design48-TSC2_GAP", ("P49815", (1525, 1755)), "TSC2-GAP"),
    ("ovn-ws5-design48-WDR26", ("Q9H7D7", None), "WDR26"),
]
DESIGN_N = 48
MAX_SPEND = 50.0


def run():
    ovn.RUNROOT.mkdir(parents=True, exist_ok=True)
    state = ovn.load_state()

    def gate_and_run(key, ws, cmd, inp, model, kind, meta):
        if state["jobs"].get(key, {}).get("status") == "done":
            return
        est, err = ovn.estimate_one(cmd, inp, model)
        if est is None:
            state["jobs"][key] = {"ws": ws, "status": "estimate_failed", "err": err, **meta}
            ovn.save_state(state); print(f"  {key}: EST FAIL {err}"); return
        if state["spent_est"] + est > MAX_SPEND:
            print(f"  BUDGET STOP at {key}"); return
        (ovn.RUNROOT / key).mkdir(parents=True, exist_ok=True)
        args = cmd + ["run"] + (["--model", model] if model else []) + [
            "--idempotency-key", key, "--input", json.dumps(inp),
            "--root-dir", str(ovn.RUNROOT), "--name", key, "--poll-interval-seconds", "10"]
        ovn.cli_json(args, timeout=5400)
        m = ovn.parse_job(key, kind)
        ok = any(v is not None for v in m.values()) if m else False
        state["jobs"][key] = {"ws": ws, "status": "done" if ok else "ran_no_metrics", "est": est, "kind": kind, "metrics": m, **meta}
        if ok:
            state["spent_est"] = round(state["spent_est"] + est, 4)
        ovn.save_state(state)
        print(f"  {key}: ${est} -> {m} | spent~${state['spent_est']}")

    # deepened design first (priority targets)
    for key, (acc, crop), gene in WS5_DESIGN:
        seq = ovn.fetch_seq(acc)
        seq = seq[crop[0]:crop[1]] if crop else seq
        inp = {"num_molecules": DESIGN_N, "target": ovn.smtgt(seq), "chemical_space": "enamine_real",
               "molecule_filters": {"boltz_smarts_catalog_filter_level": "recommended"}}
        gate_and_run(key, "WS5", ["small-molecule:design"], inp, None, "design", {"gene": gene, "role": "deep-deepen", "domain_len": len(seq)})

    # expanded PPI
    for label, tgt, binder, role in WS5_PPI:
        ts = ovn.fetch_seq(tgt[0]); ts = ts[tgt[1][0]:tgt[1][1]] if tgt[1] else ts
        bs = ovn.fetch_seq(binder[0]); bs = bs[binder[1][0]:binder[1][1]] if binder[1] else bs
        key = f"ovn-ws5-{ovn.sanitize(label)}"
        if len(ts) + len(bs) > ovn.PROT_COMBINED_MAX:
            state["jobs"][key] = {"ws": "WS5", "status": "skipped", "label": label, "role": role,
                                  "skip": f"combined {len(ts)+len(bs)}>{ovn.PROT_COMBINED_MAX}"}
            ovn.save_state(state); print(f"  SKIP {label} (combined {len(ts)+len(bs)})"); continue
        inp = {"proteins": [{"id": "binder", "entities": [{"type": "protein", "chain_ids": ["B"], "value": bs}]}],
               "target": {"type": "no_template", "entities": [{"type": "protein", "chain_ids": ["A"], "value": ts}]}}
        gate_and_run(key, "WS5", ["protein:library-screen"], inp, None, "screen", {"label": label, "role": role})

    print(f"\n=== WS5 done. spent_est ~${state['spent_est']} ===")


if __name__ == "__main__":
    run()
