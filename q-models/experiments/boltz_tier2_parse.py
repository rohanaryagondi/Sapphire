#!/usr/bin/env python3
"""Re-parse Tier-2 local results (no re-run / no re-bill) -> results/boltz_tier2_result.json.

Screen/design results land in <run>/results/index.jsonl (one JSON per line; external_id, smiles,
metrics.{optimization_score,binding_confidence,iptm}). ADME in <run>/run.json (output.molecules[].adme).
"""
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments"))
from boltz_tier2_run import screen_payload, nav18, scaffold_novelty, auroc, ACT_THR, SCN10A_CACHE
RUN = REPO / "results/boltz_tier2_runs"


def read_index(tag):
    f = RUN / tag / "results/index.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.is_file() else []


out = {}

# ---- T4 ADME ----
r = json.loads((RUN / "tier2-t4-adme-navpanel/run.json").read_text())
out["T4_adme"] = [{"id": m.get("external_id"), "status": m.get("status"), **(m.get("adme") or {})}
                  for m in r.get("output", {}).get("molecules", [])]

# ---- T5 screen enrichment ----
_, mols = screen_payload()
label = {m["id"]: m["label"] for m in mols}
src = {m["id"]: m["src"] for m in mols}
rows = read_index("tier2-t5-screen-nav18")
scored = []
for r in rows:
    eid = r.get("external_id")
    mt = r.get("metrics", {})
    scored.append({"id": eid, "label": label.get(eid), "src": src.get(eid),
                   "optimization_score": mt.get("optimization_score"),
                   "binding_confidence": mt.get("binding_confidence"),
                   "iptm": mt.get("iptm")})
present = {s["id"] for s in scored}
out["T5_submitted"] = len(mols)
out["T5_returned"] = len(scored)
out["T5_dropped"] = sorted(set(label) - present)
labs = [s["label"] for s in scored if s["label"] is not None]
for metric in ("optimization_score", "binding_confidence", "iptm"):
    out[f"T5_auroc_{metric}"] = auroc(labs, [s[metric] for s in scored if s["label"] is not None])
# subgroup: panel-only binder/decoy AUROC (Q1 comparison) and chembl-only
for grp, keep in (("panel", lambda s: s["src"] == "panel"),
                  ("chembl", lambda s: s["src"] in ("chembl_active", "chembl_inactive"))):
    sub = [s for s in scored if keep(s) and s["label"] is not None]
    out[f"T5_auroc_optscore_{grp}"] = auroc([s["label"] for s in sub], [s["optimization_score"] for s in sub])
    out[f"T5_n_{grp}"] = len(sub)
out["T5_rows"] = sorted(scored, key=lambda s: -(s["optimization_score"] or -9))

# ---- T6 design novelty ----
rows = read_index("tier2-t6-design-nav18")
gen = [{"smiles": r.get("smiles"),
        "optimization_score": r.get("metrics", {}).get("optimization_score"),
        "binding_confidence": r.get("metrics", {}).get("binding_confidence")} for r in rows]
seq, panel = nav18()
known = [c["smiles"] for c in panel if int(c["label"]) == 1]
cache = json.loads(SCN10A_CACHE.read_text())
known += [s for s, v in sorted(cache.items(), key=lambda x: -x[1])[:200] if v >= ACT_THR]
nov = scaffold_novelty([g["smiles"] for g in gen if g["smiles"]], known) or []
byk = {n["smiles"]: n for n in nov}
for g in gen:
    g.update({k: v for k, v in byk.get(g["smiles"], {}).items() if k != "smiles"})
out["T6_n"] = len(gen)
out["T6_valid"] = sum(1 for g in gen if g.get("valid"))
out["T6_novel_scaffold"] = sum(1 for g in gen if g.get("novel_scaffold"))
tans = [g["max_tanimoto_to_known"] for g in gen if g.get("max_tanimoto_to_known") is not None]
out["T6_median_max_tanimoto"] = round(sorted(tans)[len(tans) // 2], 3) if tans else None
out["T6_generated"] = sorted(gen, key=lambda x: -(x.get("optimization_score") or -9))

(REPO / "results/boltz_tier2_result.json").write_text(json.dumps(out, indent=2))

print("== T5 SCREEN (Nav1.8 enrichment) ==")
print(f"  submitted {out['T5_submitted']} -> returned {out['T5_returned']}  (dropped {len(out['T5_dropped'])}: {out['T5_dropped']})")
print(f"  AUROC  optimization_score={out['T5_auroc_optimization_score']}  binding_confidence={out['T5_auroc_binding_confidence']}  iptm={out['T5_auroc_iptm']}")
print(f"  AUROC(optscore) panel-only={out['T5_auroc_optscore_panel']} (n={out['T5_n_panel']})  chembl-only={out['T5_auroc_optscore_chembl']} (n={out['T5_n_chembl']})")
print("  top-8 by optimization_score:")
for s in out["T5_rows"][:8]:
    print(f"    {str(s['id'])[:22]:22s} lab={s['label']} src={s['src']:14s} opt={s['optimization_score']}")
print("\n== T6 DESIGN (de-novo Nav1.8, Enamine REAL) ==")
print(f"  generated {out['T6_n']} | valid {out['T6_valid']} | novel-scaffold {out['T6_novel_scaffold']} | median max-Tanimoto-to-known {out['T6_median_max_tanimoto']}")
for g in out["T6_generated"][:5]:
    print(f"    opt={g.get('optimization_score')} tan={g.get('max_tanimoto_to_known')} novel={g.get('novel_scaffold')} {str(g['smiles'])[:46]}")
print("\nwrote results/boltz_tier2_result.json")
