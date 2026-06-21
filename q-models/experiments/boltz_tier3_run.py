#!/usr/bin/env python3
"""Boltz-API Tier-3 — round off the last 2 capabilities + the deferred selectivity question.

T7 SELECTIVITY  : suzetrigine vs 9 Nav paralogs via 1-molecule small-molecule:library-screen
                  (10x cheaper than per-fold Q2). Is Nav1.8 ranked #1? ($0.025/paralog)
T8 PROTEIN-SCREEN: 3 Nav-VSD gating toxins (ProTx-II/HwTx-IV/ProTx-I) vs 3 K-channel toxins
                  (apamin/charybdotoxin/iberiotoxin) -> Nav1.7 DII crop. Rank Nav toxins higher? AUROC.
T9 PROTEIN-DESIGN: 10 de-novo peptide binders to Nav1.7 DII; binding_confidence vs the real toxins (T8) + novelty.

Protein endpoints cap the target at 1300 residues -> use a Nav1.7 domain-II crop (the ProTx-II/HwTx-IV
gating-modifier site). SM-screen takes full-length Nav. Modes: --mode estimate|run ; --ts T7,T8,T9.
"""
import json, os, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOLTZ = os.environ.get("BOLTZ_BIN", "boltz-api")
RUNROOT = REPO / "results" / "boltz_tier3_runs"
SEL = REPO / "docs/boltz_handoff/data/04_suzetrigine_selectivity.json"
DII_LO, DII_HI = 735, 1000   # approx Nav1.7 domain-II window (incl. S3b-S4 paddle)

# Nav-channel VSD gating-modifier toxins (positives) vs K-channel toxins (negatives, same disulfide-rich fold)
NAV_TOXINS = {
    "ProTx-II": "YCQKWMWTCDSERKCCEGMVCRLWCKKKLW",
    "HwTx-IV": "ECLEIFKACNPSNDQCCKSSKLVCSRKTRWCKYQI",
    "ProTx-I": "ECRYWLGGCSAGQTCCKHLVCSRRHGWCVWDGTFS",
}
K_TOXINS = {
    "Apamin-SK": "CNCKAPETALCARRCQQH",
    "Charybdotoxin-Kv": "EFTNVSCTTSKECWSVCQRLHNTSRGKCMNKKCRCYS",
    "Iberiotoxin-BK": "EFTDVDCSVSKECWSVCKDLFGVDRGKCMGKKCRCYQ",
}


def sanitize(s): return re.sub(r"[^A-Za-z0-9_.-]", "-", str(s))[:48]


def sel_panel():
    return {e["target"]: e for e in json.loads(SEL.read_text())}


def nav17_dii():
    return sel_panel()["Nav1.7"]["protein_seq"][DII_LO:DII_HI]


def tgt(seq):
    return {"type": "no_template", "entities": [{"type": "protein", "chain_ids": ["A"], "value": seq}]}


def cli_json(args, timeout=5400):
    p = subprocess.run([BOLTZ] + args + ["--format", "json"], capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(p.stdout), p.returncode, (p.stderr or "")[-400:]
    except Exception:
        return None, p.returncode, ((p.stderr or "") + (p.stdout or ""))[-400:]


def read_index(key):
    f = RUNROOT / key / "results/index.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.is_file() else []


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


# ---- job builders -> list of (key, cmd, input) ----
def t7_jobs():
    panel = sel_panel()
    suz = panel["Nav1.8"]["smiles"]
    out = []
    for tg, e in panel.items():
        inp = {"molecules": [{"smiles": suz, "id": "suzetrigine"}],
               "target": {"entities": [{"type": "protein", "chain_ids": ["A"], "value": e["protein_seq"]}]}}
        out.append((f"tier3-t7-sel-{sanitize(tg)}", ["small-molecule:library-screen"], inp, {"target": tg, "label": e["label"]}))
    return out


def t8_jobs():
    peps = {**NAV_TOXINS, **K_TOXINS}
    prot = [{"id": k, "entities": [{"type": "protein", "chain_ids": ["B"], "value": v}]} for k, v in peps.items()]
    inp = {"proteins": prot, "target": tgt(nav17_dii())}
    return [("tier3-t8-protscreen-nav17dii", ["protein:library-screen"], inp, {})]


def t9_jobs():
    bs = {"type": "no_template", "modality": "peptide",
          "entities": [{"type": "designed_protein", "chain_ids": ["B"], "value": "25..35"}]}
    inp = {"num_proteins": 10, "binder_specification": bs, "target": tgt(nav17_dii())}
    return [("tier3-t9-design-nav17dii", ["protein:design"], inp, {})]


BUILDERS = {"T7": t7_jobs, "T8": t8_jobs, "T9": t9_jobs}


def estimate(ts):
    total = 0.0
    for t in ts:
        sub = 0.0
        for key, cmd, inp, meta in BUILDERS[t]():
            d, rc, err = cli_json(cmd + ["estimate-cost", "--input", json.dumps(inp)], timeout=120)
            c = float(d["estimated_cost_usd"]) if d and d.get("estimated_cost_usd") is not None else None
            if c is not None:
                sub += c
            else:
                print(f"    {key}: ?? {err}")
        print(f"  {t}: ${sub:.4f}")
        total += sub
    print(f"\n=== TIER-3 ESTIMATED TOTAL ({','.join(ts)}): ${total:.4f} ===")


def run(ts):
    RUNROOT.mkdir(parents=True, exist_ok=True)
    out = {}
    # T7 selectivity
    if "T7" in ts:
        rows = []
        for key, cmd, inp, meta in t7_jobs():
            (RUNROOT / key).mkdir(parents=True, exist_ok=True)
            d, rc, err = cli_json(cmd + ["run", "--idempotency-key", key, "--input", json.dumps(inp),
                                         "--root-dir", str(RUNROOT), "--name", key, "--poll-interval-seconds", "10"])
            idx = read_index(key)
            m = (idx[0].get("metrics", {}) if idx else {})
            rows.append({"target": meta["target"], "label": meta["label"],
                         "optimization_score": m.get("optimization_score"),
                         "binding_confidence": m.get("binding_confidence")})
            print(f"  T7 {meta['target']:7s} opt={m.get('optimization_score')} bind={m.get('binding_confidence')}")
        rows_s = sorted([r for r in rows if r["binding_confidence"] is not None], key=lambda r: -r["binding_confidence"])
        out["T7_rows"] = rows
        out["T7_nav18_rank_by_bindconf"] = next((i + 1 for i, r in enumerate(rows_s) if r["target"] == "Nav1.8"), None)
        out["T7_auroc_bindconf"] = auroc([r["label"] for r in rows], [r["binding_confidence"] for r in rows])
        out["T7_auroc_optscore"] = auroc([r["label"] for r in rows], [r["optimization_score"] for r in rows])
        print(f"  -> Nav1.8 rank {out['T7_nav18_rank_by_bindconf']}/9 ; AUROC bind={out['T7_auroc_bindconf']} opt={out['T7_auroc_optscore']}")
    # T8 protein-screen
    if "T8" in ts:
        key = "tier3-t8-protscreen-nav17dii"
        (RUNROOT / key).mkdir(parents=True, exist_ok=True)
        _, cmd, inp, _ = t8_jobs()[0]
        cli_json(cmd + ["run", "--idempotency-key", key, "--input", json.dumps(inp),
                        "--root-dir", str(RUNROOT), "--name", key, "--poll-interval-seconds", "10"])
        lab = {**{k: 1 for k in NAV_TOXINS}, **{k: 0 for k in K_TOXINS}}
        rows = []
        for r in read_index(key):
            eid = r.get("external_id") or r.get("id")
            m = r.get("metrics", {})
            rows.append({"id": eid, "label": lab.get(eid), "binding_confidence": m.get("binding_confidence"),
                         "optimization_score": m.get("optimization_score"), "iptm": m.get("iptm")})
        out["T8_rows"] = sorted(rows, key=lambda r: -(r["binding_confidence"] or -9))
        out["T8_auroc_bindconf"] = auroc([r["label"] for r in rows], [r["binding_confidence"] for r in rows])
        out["T8_auroc_iptm"] = auroc([r["label"] for r in rows], [r["iptm"] for r in rows])
        print(f"  T8 protein-screen AUROC bind={out['T8_auroc_bindconf']} iptm={out['T8_auroc_iptm']}")
        for r in out["T8_rows"]:
            print(f"    {str(r['id']):18s} lab={r['label']} bind={r['binding_confidence']} iptm={r['iptm']}")
    # T9 protein-design
    if "T9" in ts:
        key = "tier3-t9-design-nav17dii"
        (RUNROOT / key).mkdir(parents=True, exist_ok=True)
        _, cmd, inp, _ = t9_jobs()[0]
        cli_json(cmd + ["run", "--idempotency-key", key, "--input", json.dumps(inp),
                        "--root-dir", str(RUNROOT), "--name", key, "--poll-interval-seconds", "10"])
        designs = []
        for r in read_index(key):
            m = r.get("metrics", {})
            # binder entity comes back as type protein on chain B; grab its resolved sequence
            seq = next((e.get("value") for e in r.get("entities", []) if "B" in (e.get("chain_ids") or [])), None)
            designs.append({"seq": seq, "binding_confidence": m.get("binding_confidence"),
                            "optimization_score": m.get("optimization_score"), "iptm": m.get("iptm")})
        designs.sort(key=lambda d: -(d["binding_confidence"] or -9))
        out["T9_n"] = len(designs)
        out["T9_designs"] = designs
        bc = [d["binding_confidence"] for d in designs if d["binding_confidence"] is not None]
        out["T9_bindconf_max"] = max(bc) if bc else None
        out["T9_bindconf_median"] = sorted(bc)[len(bc) // 2] if bc else None
        print(f"  T9 design n={len(designs)} bind_conf max={out['T9_bindconf_max']} median={out['T9_bindconf_median']}")
        for d in designs[:4]:
            print(f"    bind={d['binding_confidence']} iptm={d['iptm']} {str(d['seq'])[:42]}")
    (REPO / "results/boltz_tier3_result.json").write_text(json.dumps(out, indent=2))
    print("\n=== wrote results/boltz_tier3_result.json ===")


if __name__ == "__main__":
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "estimate"
    ts = sys.argv[sys.argv.index("--ts") + 1].split(",") if "--ts" in sys.argv else ["T7", "T8", "T9"]
    print(f"tier-3 jobs={ts} mode={mode}\n")
    (estimate if mode == "estimate" else run)(ts)
