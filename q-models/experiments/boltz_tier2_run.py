#!/usr/bin/env python3
"""Boltz-API Tier-2 runner — ADME / library-screen / de-novo design, via the hosted boltz-api CLI.

T4 ADME    : 11 Nav1.8-panel CNS drugs -> solubility/permeability/lipophilicity ($0.01/mol).
T5 SCREEN  : Nav1.8 target vs {panel 11} + {sampled SCN10A strong actives pChEMBL>=7} +
             {measured inactives pChEMBL<5} -> enrichment AUROC (the scaled, cheaper Q1) ($0.025/mol).
T6 DESIGN  : generate N novel Nav1.8 binders in Enamine REAL -> validity + scaffold-novelty vs
             known binders; report Boltz optimization_score ($0.025/mol).

Modes:
  --mode estimate : estimate-cost every job (FREE, no GPU); print per-job + grand total. Run FIRST.
  --mode run      : run each job (stable idempotency key), parse results -> results/boltz_tier2_result.json.
  --ts T4,T5,T6   : filter which jobs to run.

Uses the `boltz-api` CLI (on PATH; BOLTZ_API_KEY set). Screen/design model=boltz-2.1; ADME model=adme-v1.
"""
import json, os, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOLTZ = os.environ.get("BOLTZ_BIN", "boltz-api")
RUNROOT = REPO / "results" / "boltz_tier2_runs"
N_ACT, N_INACT, N_DESIGN = 20, 20, 24          # screen sample sizes / design count
ACT_THR, INACT_THR = 7.0, 5.0                  # pChEMBL active / inactive cutoffs
SCN10A_CACHE = REPO / "data/cns_dti_cache/CHEMBL5451.json"


def sanitize(s): return re.sub(r"[^A-Za-z0-9_.-]", "-", str(s))[:48]


def nav18():
    cm = json.loads((REPO / "aws/crossmodal_panels.json").read_text())["nav18"]
    return cm["protein_seq"], cm["compounds"]


def target_block(seq):
    return {"entities": [{"type": "protein", "value": seq, "chain_ids": ["A"]}]}


def sample_screen_mols():
    """panel (labeled) + strong actives (1) + measured inactives (0) from the cached SCN10A set."""
    seq, panel = nav18()
    mols, seen = [], set()

    def add(smiles, ident, label, src):
        key = smiles.strip()
        if key in seen or not key:
            return
        seen.add(key)
        mols.append({"smiles": key, "id": ident, "label": label, "src": src})

    for c in panel:
        nm = c.get("drug") or c.get("name")
        add(c["smiles"], f"panel-{sanitize(nm)}", int(c["label"]), "panel")
    cache = json.loads(SCN10A_CACHE.read_text())
    acts = sorted([(s, v) for s, v in cache.items() if v >= ACT_THR], key=lambda x: -x[1])
    inacts = sorted([(s, v) for s, v in cache.items() if v < INACT_THR], key=lambda x: x[1])
    for i, (s, v) in enumerate(acts[:N_ACT]):
        add(s, f"act-{i}-p{v:.1f}", 1, "chembl_active")
    for i, (s, v) in enumerate(inacts[:N_INACT]):
        add(s, f"inact-{i}-p{v:.1f}", 0, "chembl_inactive")
    return seq, mols


def cli_json(args, timeout=120):
    p = subprocess.run([BOLTZ] + args + ["--format", "json"], capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or "").strip()
    try:
        return json.loads(out), p.returncode, (p.stderr or "")[-500:]
    except Exception:
        return None, p.returncode, ((p.stderr or "") + out)[-500:]


# ---- job specs -------------------------------------------------------------
def adme_payload():
    seq, panel = nav18()
    mols = [{"smiles": c["smiles"], "id": sanitize(c.get("drug") or c.get("name"))} for c in panel]
    return {"molecules": mols}, len(mols)


def screen_payload():
    seq, mols = sample_screen_mols()
    return {"molecules": [{"smiles": m["smiles"], "id": m["id"]} for m in mols],
            "target": target_block(seq)}, mols


def design_payload():
    seq, _ = nav18()
    return {"num_molecules": N_DESIGN, "target": target_block(seq),
            "chemical_space": "enamine_real",
            "molecule_filters": {"boltz_smarts_catalog_filter_level": "recommended"}}, N_DESIGN


JOBS = {  # screen/design have a fixed model (no --model flag); only ADME takes --model adme-v1
    "T4": dict(cmd=["predictions:adme"], model="adme-v1", key="tier2-t4-adme-navpanel"),
    "T5": dict(cmd=["small-molecule:library-screen"], model=None, key="tier2-t5-screen-nav18"),
    "T6": dict(cmd=["small-molecule:design"], model=None, key="tier2-t6-design-nav18"),
}


def model_flag(j):
    return ["--model", j["model"]] if j.get("model") else []


def payload_for(t):
    if t == "T4": p, _ = adme_payload(); return p
    if t == "T5": p, _ = screen_payload(); return p
    return design_payload()[0]


def estimate(ts):
    total = 0.0
    for t in ts:
        j = JOBS[t]
        d, rc, err = cli_json(j["cmd"] + ["estimate-cost"] + model_flag(j) +
                                          ["--input", json.dumps(payload_for(t))])
        cost = float(d["estimated_cost_usd"]) if d and d.get("estimated_cost_usd") is not None else None
        if cost is not None:
            total += cost
        print(f"  {t}  {j['cmd'][0]:34s} ${cost if cost is not None else '??'}   {err if cost is None else ''}")
    print(f"\n=== TIER-2 ESTIMATED TOTAL ({','.join(ts)}): ${total:.4f} ===")
    return total


def run_one(t):
    j = JOBS[t]
    rundir = RUNROOT / j["key"]
    rundir.mkdir(parents=True, exist_ok=True)
    args = j["cmd"] + ["run"] + model_flag(j) + ["--idempotency-key", j["key"],
                       "--input", json.dumps(payload_for(t)),
                       "--root-dir", str(RUNROOT), "--name", j["key"], "--poll-interval-seconds", "10"]
    d, rc, err = cli_json(args, timeout=5400)
    return d, rc, err, rundir


def load_run_file(rundir, names):
    for n in names:
        hits = sorted(rundir.rglob(n), key=lambda p: len(p.parts))
        if hits:
            try:
                return json.loads(hits[0].read_text())
            except Exception:
                pass
    return None


def auroc(labels, scores):
    pos = [s for s, l in zip(scores, labels) if l == 1 and s is not None]
    neg = [s for s, l in zip(scores, labels) if l == 0 and s is not None]
    if not pos or not neg:
        return None
    n = c = 0
    for p in pos:
        for q in neg:
            n += 1; c += 1 if p > q else (0.5 if p == q else 0)
    return round(c / n, 4)


def parse_screen_rows(rec):
    """results.json may store rows under .results / .results.data / top-level list."""
    if rec is None:
        return []
    for path in (("results", "data"), ("results",), ("data",)):
        cur = rec
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
        if isinstance(cur, list):
            return cur
    return rec if isinstance(rec, list) else []


def scaffold_novelty(gen_smiles, ref_smiles):
    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
        from rdkit.Chem import AllChem, DataStructs
    except Exception:
        return None
    def fp(s):
        m = Chem.MolFromSmiles(s)
        return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m else None
    ref_fps = [f for f in (fp(s) for s in ref_smiles) if f is not None]
    ref_scaf = set()
    for s in ref_smiles:
        m = Chem.MolFromSmiles(s)
        if m:
            ref_scaf.add(Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(m)))
    out = []
    for s in gen_smiles:
        m = Chem.MolFromSmiles(s)
        if not m:
            out.append({"smiles": s, "valid": False}); continue
        f = AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048)
        mx = max((DataStructs.TanimotoSimilarity(f, r) for r in ref_fps), default=0.0)
        scaf = Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(m))
        out.append({"smiles": s, "valid": True, "max_tanimoto_to_known": round(mx, 3),
                    "novel_scaffold": scaf not in ref_scaf})
    return out


def run(ts):
    RUNROOT.mkdir(parents=True, exist_ok=True)
    out = {}
    for t in ts:
        d, rc, err, rundir = run_one(t)
        print(f"\n--- {t} rc={rc} ---\n  {err[:200]}")
        if t == "T4":
            rec = load_run_file(rundir, ["run.json"])
            mols = (rec or {}).get("output", {}).get("molecules", []) if rec else []
            rows = [{"id": m.get("external_id") or m.get("smiles"), "status": m.get("status"),
                     **(m.get("adme") or {})} for m in mols]
            out["T4_adme"] = rows
            for r in rows:
                print(f"  {str(r['id'])[:24]:24s} sol={r.get('solubility')} perm={r.get('permeability')} lipo={r.get('lipophilicity')}")
        elif t == "T5":
            _, mols = screen_payload()
            label = {m["id"]: m["label"] for m in mols}
            src = {m["id"]: m["src"] for m in mols}
            rec = load_run_file(rundir, ["results.json"])
            rows = parse_screen_rows(rec)
            scored = []
            for r in rows:
                ident = r.get("external_id") or r.get("id")
                mt = r.get("metrics", {})
                scored.append({"id": ident, "label": label.get(ident), "src": src.get(ident),
                               "optimization_score": mt.get("optimization_score"),
                               "binding_confidence": mt.get("binding_confidence"),
                               "ligand_iptm": mt.get("ligand_iptm") or mt.get("iptm")})
            labs = [s["label"] for s in scored if s["label"] is not None]
            for metric in ("optimization_score", "binding_confidence", "ligand_iptm"):
                sc = [s[metric] for s in scored if s["label"] is not None]
                out[f"T5_auroc_{metric}"] = auroc(labs, sc)
            out["T5_n"] = len(scored)
            out["T5_rows"] = scored
            print(f"  screened {len(scored)} | AUROC opt={out.get('T5_auroc_optimization_score')} "
                  f"bind={out.get('T5_auroc_binding_confidence')} iptm={out.get('T5_auroc_ligand_iptm')}")
        elif t == "T6":
            rec = load_run_file(rundir, ["results.json"])
            rows = parse_screen_rows(rec)
            gen = [{"smiles": r.get("smiles"), "optimization_score": r.get("metrics", {}).get("optimization_score"),
                    "binding_confidence": r.get("metrics", {}).get("binding_confidence")} for r in rows]
            seq, panel = nav18()
            known = [c["smiles"] for c in panel if int(c["label"]) == 1]
            cache = json.loads(SCN10A_CACHE.read_text())
            known += [s for s, v in sorted(cache.items(), key=lambda x: -x[1])[:200] if v >= ACT_THR]
            nov = scaffold_novelty([g["smiles"] for g in gen if g["smiles"]], known)
            byk = {n["smiles"]: n for n in (nov or [])}
            for g in gen:
                g.update({k: v for k, v in byk.get(g["smiles"], {}).items() if k != "smiles"})
            out["T6_n"] = len(gen)
            out["T6_valid"] = sum(1 for g in gen if g.get("valid"))
            out["T6_novel_scaffold"] = sum(1 for g in gen if g.get("novel_scaffold"))
            out["T6_generated"] = gen
            print(f"  generated {len(gen)} | valid {out['T6_valid']} | novel-scaffold {out['T6_novel_scaffold']}")
            for g in sorted(gen, key=lambda x: -(x.get("optimization_score") or -9))[:5]:
                print(f"    opt={g.get('optimization_score')} tanimoto={g.get('max_tanimoto_to_known')} {str(g['smiles'])[:48]}")
    (REPO / "results/boltz_tier2_result.json").write_text(json.dumps(out, indent=2))
    print("\n=== wrote results/boltz_tier2_result.json ===")


if __name__ == "__main__":
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "estimate"
    ts = sys.argv[sys.argv.index("--ts") + 1].split(",") if "--ts" in sys.argv else ["T4", "T5", "T6"]
    print(f"tier-2 jobs={ts} mode={mode}\n")
    (estimate if mode == "estimate" else run)(ts)
