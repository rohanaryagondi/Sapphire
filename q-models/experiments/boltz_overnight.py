#!/usr/bin/env python3
"""Boltz overnight autonomous run — structural layer for the antipodal-rescue CNS program.

Two questions per target/pair (the deck's "data-layer confirmation" of plausible-unconfirmed pairs):
  Q1 DRUGGABILITY  : does the target have a pocket Boltz can design a small molecule into?
  Q2 INTERACTION   : do the claimed physical-interaction rescue pairs co-fold with a confident interface?

Workstreams:
  WS1 druggability  : small-molecule:design (Enamine REAL) on each target's structured domain -> max binding_confidence + hits
  WS2 calibration   : structure-and-binding of known inhibitors vs partner enzymes (+ a decoy) -> is Boltz trustworthy per class
  WS3 ppi (light)   : protein:library-screen of curated rescue pairs (iptm readout only; binding_confidence degenerate for PPI) + neg ctrls
  WS4 deep          : TSC2 (GAP domain + Rheb interface) and WDR26 (WD40 + CTLH partners)
  WS5 deepen        : (driven by the agent at wake-time) more design on the most-ligandable targets

Modes: --mode estimate|run|brief   --ws WS1,WS2,...   --max-spend 50   --design-n 24
Estimate-gated: every job free-estimated first; stops launching a job if it would breach --max-spend.
Idempotent keys (no re-bill on retry). State + briefing regenerated from results/boltz_overnight_state.json.
"""
import json, os, re, subprocess, sys, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOLTZ = os.environ.get("BOLTZ_BIN", "boltz-api")
RUNROOT = REPO / "results" / "boltz_overnight_runs"
STATE = REPO / "results" / "boltz_overnight_state.json"
SEQCACHE = REPO / "data" / "overnight_seqs.json"
BRIEF = REPO / "RohanOnly" / "boltz_overnight_briefing_2026-06-18.md"
SM_MAX, PROT_COMBINED_MAX = 2500, 1300

# ---- panel ----
QUERY = {  # CNS haploinsufficiency disease genes (the user's list)
    "TSC2": "P49815", "WDR26": "Q9H7D7", "TSC1": "Q92574", "PTEN": "P60484",
    "STXBP1": "P61764", "SCN2A": "Q99250", "KCNQ2": "O43526", "SYNGAP1": "Q96PV0",
    "CHD8": "Q9HCK8", "KMT2A": "Q03164", "SMARCA4": "P51532", "SRCAP": "Q6ZRS2",
    "RPS17": "P08708", "HNRNPK": "P61978",
}
PARTNER = {  # druggable partner targets named in the deck
    "USP7": "Q93009", "KDM1A": "O60341", "DOT1L": "Q8TEK3", "WDR5": "P61964",
    "EP300": "Q09472", "CREBBP": "Q92793", "RBBP7": "Q16576", "EP400": "Q96L91",
}
# catalytic/structured-domain crops (0-based slice) for proteins too big or too multidomain to fold whole well
CROPS = {
    "CHD8": (780, 1300), "KMT2A": (3700, 3969), "SRCAP": (650, 1150), "EP400": (750, 1300),
    "EP300": (1280, 1670), "CREBBP": (1080, 1660),                      # HAT (+bromo) domains
    "TSC2_GAP": ("P49815", 1525, 1755),                                 # Rheb-GAP domain
    "DOT1L_CAT": ("Q8TEK3", 0, 416), "USP7_TRAF": ("Q93009", 53, 205),  # catalytic / TRAF substrate domain
}
# WS2 known inhibitors (PubChem name -> SMILES) for partner enzymes; decoy = a generic non-binder
KNOWN_INH = {"DOT1L": "pinometostat", "KDM1A": "tranylcypromine", "EP300": "A-485",
             "CREBBP": "A-485", "WDR5": "OICR-9429"}
DECOY_SMILES = "CN(C)C(=N)N=C(N)N"  # metformin — generic decoy
# WS3 light PPI pairs (target, binder) by accession+optional crop; iptm readout. role: pos/neg/test
PPI = [
    ("STXBP1↔Syntaxin1A", ("P61764", None), ("Q16623", None), "pos"),   # Munc18-1 binds syntaxin (strong ctrl)
    ("STXBP1↔STMN2", ("P61764", None), ("Q93045", None), "test"),       # rescue pair
    ("RPS17↔USP7-TRAF", ("P08708", None), ("Q93009", (53, 205)), "test"),
    ("WDR26↔RMND5A", ("Q9H7D7", None), ("Q9H871", None), "test"),       # CTLH/GID complex
    ("WDR26↔MAEA", ("Q9H7D7", None), ("Q7L5Y9", None), "test"),
    ("TSC2gap↔RHEB", ("P49815", (1525, 1755)), ("Q15382", None), "test"),
    ("PTEN↔STMN2(neg)", ("P60484", None), ("Q93045", None), "neg"),
    ("RPS17↔STMN2(neg)", ("P08708", None), ("Q93045", None), "neg"),
]


def sanitize(s): return re.sub(r"[^A-Za-z0-9_.-]", "-", str(s))[:60]


def load_seqcache():
    return json.loads(SEQCACHE.read_text()) if SEQCACHE.is_file() else {}


def fetch_seq(acc):
    cache = load_seqcache()
    if acc in cache:
        return cache[acc]
    txt = urllib.request.urlopen(f"https://rest.uniprot.org/uniprotkb/{acc}.fasta", timeout=40).read().decode()
    seq = txt.split("\n", 1)[1].replace("\n", "")
    cache[acc] = seq
    SEQCACHE.parent.mkdir(parents=True, exist_ok=True)
    SEQCACHE.write_text(json.dumps(cache))
    return seq


def pubchem_smiles(name):
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.request.quote(name)}/property/SMILES,IsomericSMILES,CanonicalSMILES/JSON"
        d = json.load(urllib.request.urlopen(url, timeout=40))
        p = d["PropertyTable"]["Properties"][0]
        return p.get("SMILES") or p.get("IsomericSMILES") or p.get("CanonicalSMILES")
    except Exception:
        return None


def target_seq(gene, acc):
    seq = fetch_seq(acc)
    if gene in CROPS and isinstance(CROPS[gene][0], int):
        lo, hi = CROPS[gene]
        return seq[lo:hi]
    return seq


def load_state():
    return json.loads(STATE.read_text()) if STATE.is_file() else {"jobs": {}, "spent_est": 0.0}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def cli_json(args, timeout=120):
    p = subprocess.run([BOLTZ] + args + ["--format", "json"], capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(p.stdout), (p.stderr or "")[-300:]
    except Exception:
        return None, ((p.stderr or "") + (p.stdout or ""))[-300:]


def estimate_one(cmd, inp, model=None):
    args = cmd + ["estimate-cost"] + (["--model", model] if model else []) + ["--input", json.dumps(inp)]
    d, err = cli_json(args)
    if d and d.get("estimated_cost_usd") is not None:
        return float(d["estimated_cost_usd"]), None
    return None, err


def read_index(key):
    f = RUNROOT / key / "results" / "index.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.is_file() else []


def read_sb_metrics(key):
    f = RUNROOT / key / "outputs" / "files" / "prediction" / "metrics.json"
    return json.loads(f.read_text()) if f.is_file() else {}


# ---- job builders: (key, ws, cmd, input, model, parse_kind, meta) ----
def smtgt(seq): return {"entities": [{"type": "protein", "chain_ids": ["A"], "value": seq}]}


def jobs_ws1(design_n):
    out = []
    for role, panel in (("query", QUERY), ("partner", PARTNER)):
        for gene, acc in panel.items():
            seq = target_seq(gene, acc)
            if len(seq) > SM_MAX:
                continue  # flagged separately; needs crop
            inp = {"num_molecules": design_n, "target": smtgt(seq), "chemical_space": "enamine_real",
                   "molecule_filters": {"boltz_smarts_catalog_filter_level": "recommended"}}
            out.append((f"ovn-ws1-design-{sanitize(gene)}", "WS1", ["small-molecule:design"], inp, None,
                        "design", {"gene": gene, "role": role, "domain_len": len(seq)}))
    return out


def jobs_ws2():
    out = []
    for gene, name in KNOWN_INH.items():
        acc = PARTNER.get(gene) or QUERY.get(gene)
        seq = target_seq(gene, acc)
        if len(seq) > SM_MAX:
            continue
        smi = pubchem_smiles(name)
        if not smi:
            continue
        for tag, lig in (("inh", smi), ("decoy", DECOY_SMILES)):
            inp = {"entities": [{"type": "protein", "chain_ids": ["A"], "value": seq},
                                {"type": "ligand_smiles", "chain_ids": ["B"], "value": lig}],
                   "binding": {"type": "ligand_protein_binding", "binder_chain_id": "B"}, "num_samples": 1}
            out.append((f"ovn-ws2-{sanitize(gene)}-{tag}", "WS2", ["predictions:structure-and-binding"],
                        inp, "boltz-2.1", "sb", {"gene": gene, "tag": tag, "ligand": name if tag == "inh" else "metformin"}))
    return out


def _resolve(spec):
    acc, crop = spec
    seq = fetch_seq(acc)
    return seq[crop[0]:crop[1]] if crop else seq


def jobs_ws3():
    out = []
    for label, tgt, binder, role in PPI:
        ts, bs = _resolve(tgt), _resolve(binder)
        if len(ts) + len(bs) > PROT_COMBINED_MAX:
            out.append(("SKIP:" + label, "WS3", None, None, None, None,
                        {"label": label, "role": role, "skip": f"combined {len(ts)+len(bs)}>{PROT_COMBINED_MAX}"}))
            continue
        inp = {"proteins": [{"id": "binder", "entities": [{"type": "protein", "chain_ids": ["B"], "value": bs}]}],
               "target": {"type": "no_template", "entities": [{"type": "protein", "chain_ids": ["A"], "value": ts}]}}
        out.append((f"ovn-ws3-{sanitize(label)}", "WS3", ["protein:library-screen"], inp, None,
                    "screen", {"label": label, "role": role}))
    return out


def jobs_ws4(design_n):
    out = []
    # TSC2 GAP domain design + Rheb interface (Rheb handled in WS3); WDR26 already in WS1 whole
    acc, lo, hi = CROPS["TSC2_GAP"]
    gap = fetch_seq(acc)[lo:hi]
    inp = {"num_molecules": design_n, "target": smtgt(gap), "chemical_space": "enamine_real",
           "molecule_filters": {"boltz_smarts_catalog_filter_level": "recommended"}}
    out.append(("ovn-ws4-design-TSC2_GAP", "WS4", ["small-molecule:design"], inp, None, "design",
                {"gene": "TSC2-GAP", "role": "deep", "domain_len": len(gap)}))
    return out


ALL_BUILDERS = {"WS1": jobs_ws1, "WS2": jobs_ws2, "WS3": jobs_ws3, "WS4": jobs_ws4}


def build(ws_list, design_n):
    jobs = []
    for ws in ws_list:
        b = ALL_BUILDERS[ws]
        jobs += b(design_n) if ws in ("WS1", "WS4") else b()
    return jobs


def parse_job(key, kind):
    if kind == "sb":
        m = read_sb_metrics(key)
        bm = m.get("binding_metrics", {})
        bs = m.get("best_sample", {}).get("metrics", {})
        return {"binding_confidence": bm.get("binding_confidence"), "ligand_iptm": bs.get("ligand_iptm"),
                "structure_confidence": bs.get("structure_confidence")}
    rows = read_index(key)
    if kind == "design":
        bc = [r.get("metrics", {}).get("binding_confidence") for r in rows]
        bc = [x for x in bc if x is not None]
        opt = [r.get("metrics", {}).get("optimization_score") for r in rows if r.get("metrics", {}).get("optimization_score") is not None]
        top = sorted(rows, key=lambda r: -(r.get("metrics", {}).get("binding_confidence") or -9))[:5]
        return {"n": len(rows), "bindconf_max": max(bc) if bc else None,
                "bindconf_median": sorted(bc)[len(bc) // 2] if bc else None,
                "optscore_max": max(opt) if opt else None,
                "top": [{"smiles": r.get("smiles"), "bind": r.get("metrics", {}).get("binding_confidence"),
                         "opt": r.get("metrics", {}).get("optimization_score")} for r in top]}
    if kind == "screen":
        r = rows[0] if rows else {}
        m = r.get("metrics", {})
        return {"iptm": m.get("iptm"), "binding_confidence": m.get("binding_confidence"),
                "ptm": m.get("ptm"), "structure_confidence": m.get("structure_confidence")}
    return {}


def run(ws_list, design_n, max_spend):
    RUNROOT.mkdir(parents=True, exist_ok=True)
    state = load_state()
    jobs = build(ws_list, design_n)
    for key, ws, cmd, inp, model, kind, meta in jobs:
        if key.startswith("SKIP:"):
            state["jobs"][key] = {"ws": ws, "status": "skipped", **meta}
            save_state(state); continue
        rec = state["jobs"].get(key, {})
        if rec.get("status") == "done":
            continue
        est, err = estimate_one(cmd, inp, model)
        if est is None:
            state["jobs"][key] = {"ws": ws, "status": "estimate_failed", "err": err, **meta}
            save_state(state); print(f"  {key}: EST FAIL {err}"); continue
        if state["spent_est"] + est > max_spend:
            print(f"  BUDGET STOP at {key}: would be ${state['spent_est']+est:.2f} > ${max_spend}")
            break
        (RUNROOT / key).mkdir(parents=True, exist_ok=True)
        args = cmd + ["run"] + (["--model", model] if model else []) + [
            "--idempotency-key", key, "--input", json.dumps(inp),
            "--root-dir", str(RUNROOT), "--name", key, "--poll-interval-seconds", "10"]
        d, err = cli_json(args, timeout=5400)
        metrics = parse_job(key, kind)
        ok = any(v is not None for v in metrics.values()) if metrics else False
        state["jobs"][key] = {"ws": ws, "status": "done" if ok else "ran_no_metrics",
                              "est": est, "kind": kind, "metrics": metrics, **meta}
        if ok:
            state["spent_est"] = round(state["spent_est"] + est, 4)
        save_state(state)
        print(f"  {key}: ${est} -> {metrics if kind!='design' else {k:metrics[k] for k in ('n','bindconf_max','bindconf_median')}} | spent~${state['spent_est']}")
    save_state(state)
    print(f"\n=== overnight run pass done. estimated spend ~${state['spent_est']} ===")


def estimate(ws_list, design_n):
    jobs = build(ws_list, design_n)
    total = 0.0
    per = {}
    for key, ws, cmd, inp, model, kind, meta in jobs:
        if key.startswith("SKIP:"):
            print(f"  SKIP {meta.get('label')} ({meta.get('skip')})"); continue
        est, err = estimate_one(cmd, inp, model)
        if est is None:
            print(f"  {key}: EST FAIL {err}"); continue
        total += est; per[ws] = per.get(ws, 0) + est
    print(f"\n  per-WS: {json.dumps({k: round(v,3) for k,v in per.items()})}")
    print(f"=== ESTIMATED TOTAL ({','.join(ws_list)}, design_n={design_n}): ${total:.4f} ===")


if __name__ == "__main__":
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "estimate"
    ws = sys.argv[sys.argv.index("--ws") + 1].split(",") if "--ws" in sys.argv else ["WS1", "WS2", "WS3", "WS4"]
    dn = int(sys.argv[sys.argv.index("--design-n") + 1]) if "--design-n" in sys.argv else 24
    ms = float(sys.argv[sys.argv.index("--max-spend") + 1]) if "--max-spend" in sys.argv else 50.0
    print(f"overnight ws={ws} mode={mode} design_n={dn} max_spend=${ms}\n")
    if mode == "estimate":
        estimate(ws, dn)
    elif mode == "run":
        run(ws, dn, ms)
