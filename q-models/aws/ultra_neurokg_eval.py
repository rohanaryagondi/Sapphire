"""ULTRA on NeuroKG (PrimeKG + Quiver neuro augmentation) — TRUE same-substrate head-to-head vs PROTON.

PROTON was trained on this exact graph (147,020 nodes; the Quiver "NeuroKG"). This runs ULTRA's
ZERO-SHOT inductive link prediction on the SAME graph, so the comparison is finally apples-to-apples
(the Hetionet run, `results/ultra_kg_characterization.md`, was a like-metric / different-graph proxy).

Reuses the verified ULTRA API + the make_data CPU-relation-graph-build fix from aws/ultra_kg_eval.py.
The ONLY differences vs the Hetionet eval:
  - data comes from NeuroKG's nodes.csv + edges.csv (PrimeKG dataverse schema), NOT ULTRA's Hetionet class;
  - node_index is already a contiguous integer entity vocab (0..N-1) -> no PyG-reload vocab rebuild needed;
  - binding relation = `drug_protein`; targets resolved directly by node_name (SCN10A=Nav1.8, ...);
  - by default we DROP the 4.1M anatomy_protein_present/absent edges (protein-expression-in-tissue;
    irrelevant to "which drug binds this target") so the ~8M-edge graph fits the 24GB A10G. Set
    NEUROKG_KEEP_ALL=1 to use the full graph (needs CPU or a bigger GPU).

NeuroKG schema (verified):
  nodes.csv: node_index,node_id,node_type,node_name,node_source  (147020 rows; node_type incl.
             gene/protein, drug, disease, brain_structure, brain_region, cell_subtype_PD, ...)
  edges.csv: edge_index,index_label,direction,relation,display_relation,full_relation,
             x_index,x_id,x_type,x_name,x_source, y_index,...  (direction in {forward,reverse};
             we keep forward only -> ULTRA adds inverse relations itself in make_data)
  drug_protein = 28,774 forward edges (x=drug, y=gene/protein) = the binder relation.
"""
from __future__ import annotations
import json, os, sys, traceback
from pathlib import Path
import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
OUT = Path(os.environ.get("OUT", "/root/ultra_out/ultra_neurokg_result.json"))
ULTRA_DIR = Path(os.environ.get("ULTRA_DIR", "/opt/ULTRA"))
CKPT = os.environ.get("ULTRA_CKPT", str(ULTRA_DIR / "ckpts" / "ultra_4g.pth"))
NODES_CSV = os.environ.get("NODES_CSV", "/opt/neurokg/nodes.csv")
EDGES_CSV = os.environ.get("EDGES_CSV", "/opt/neurokg/edges.csv")
TOPK = int(os.environ.get("HUB_TOPK", "10"))
MAX_BINDERS = int(os.environ.get("MAX_BINDERS", "30"))     # cap scored binders/target (runtime)
KEEP_ALL = os.environ.get("NEUROKG_KEEP_ALL", "0") == "1"
BULK_DROP = {"anatomy_protein_present", "anatomy_protein_absent"}  # expression edges, not binding-relevant
BINDING_REL = "drug_protein"

# Quiver targets by gene symbol (resolved directly against nodes.csv node_name).
QUIVER_TARGETS = ["SCN10A", "SCN9A", "SCN5A", "CACNA1C", "MTOR", "DRD2", "HTR2A", "EGFR", "BRAF", "GRIN1"]
TARGET_LABEL = {"SCN10A": "Nav1.8", "SCN9A": "Nav1.7", "SCN5A": "Nav1.5", "CACNA1C": "Cav1.2"}


def section(fn, name, results):
    try:
        results[name] = fn()
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1200]}", flush=True)


def make_data(torch, Data, edge_index, edge_type, num_nodes, num_relations, build_relation_graph):
    """Build a ULTRA-ready PyG Data (bidirectional + inverse relations + relation_graph). Build the
    relation graph entirely on CPU then move to DEVICE — build_relation_graph makes CPU tensors and cats
    them with the edges, so feeding CUDA edges crashes 'two devices' during the build (verified fix)."""
    edge_index = edge_index.cpu(); edge_type = edge_type.cpu()
    fact_index = torch.cat([edge_index, edge_index.flip(0)], dim=1)
    fact_type = torch.cat([edge_type, edge_type + num_relations])
    data = Data(edge_index=fact_index, edge_type=fact_type, num_nodes=num_nodes,
                num_relations=num_relations * 2)
    data = build_relation_graph(data)
    data = data.to(DEVICE)
    rg = getattr(data, "relation_graph", None)
    if rg is not None:
        data.relation_graph = rg.to(DEVICE)
    return data


def rank_target_for_drug(torch, tasks, model, data, drug_idx, rel_idx, target_idx):
    batch = torch.tensor([[[drug_idx, target_idx, rel_idx]]], dtype=torch.long, device=DEVICE)
    t_batch, _ = tasks.all_negative(data, batch.squeeze(0))
    with torch.no_grad():
        pred = model(data, t_batch)
    pos_score = pred[0, target_idx]
    rank = int((pred[0] >= pos_score).sum().item())
    return rank, float(rank) / float(data.num_nodes)


# ---------------------------------- data loading ----------------------------------
def load_neurokg():
    """Return (num_nodes, node_name, node_type, edge_index[2,E], edge_type[E], rel_vocab, drug_set, meta)."""
    import pandas as pd
    nodes = pd.read_csv(NODES_CSV, usecols=["node_index", "node_type", "node_name"])
    num_nodes = int(nodes["node_index"].max()) + 1
    node_name = dict(zip(nodes["node_index"].astype(int), nodes["node_name"].astype(str)))
    node_type = dict(zip(nodes["node_index"].astype(int), nodes["node_type"].astype(str)))
    drug_set = {int(i) for i, t in node_type.items() if t == "drug"}
    name_to_idx = {}
    for i, t in node_type.items():
        if t == "gene/protein":
            name_to_idx[node_name[i]] = int(i)

    # stream edges.csv in chunks; keep forward only; drop bulk relations unless KEEP_ALL.
    rel_vocab = {}
    xs, ys, ets = [], [], []
    kept_rel_counts = {}
    usecols = ["direction", "relation", "x_index", "y_index"]
    for chunk in pd.read_csv(EDGES_CSV, usecols=usecols, chunksize=1_000_000):
        fwd = chunk[chunk["direction"] == "forward"]
        if not KEEP_ALL:
            fwd = fwd[~fwd["relation"].isin(BULK_DROP)]
        for rel, x, y in zip(fwd["relation"].astype(str), fwd["x_index"].astype(int), fwd["y_index"].astype(int)):
            rid = rel_vocab.get(rel)
            if rid is None:
                rid = len(rel_vocab); rel_vocab[rel] = rid
            xs.append(x); ys.append(y); ets.append(rid)
            kept_rel_counts[rel] = kept_rel_counts.get(rel, 0) + 1
    import torch
    edge_index = torch.tensor([xs, ys], dtype=torch.long)
    edge_type = torch.tensor(ets, dtype=torch.long)
    meta = {"num_nodes": num_nodes, "num_relations": len(rel_vocab), "num_forward_edges": len(xs),
            "n_drugs": len(drug_set), "kept_all_relations": KEEP_ALL,
            "dropped_bulk": sorted(BULK_DROP) if not KEEP_ALL else [],
            "top_relations": dict(sorted(kept_rel_counts.items(), key=lambda kv: -kv[1])[:12])}
    return num_nodes, node_name, node_type, edge_index, edge_type, rel_vocab, drug_set, name_to_idx, meta


def main():
    import torch
    sys.path.insert(0, str(ULTRA_DIR))
    from torch_geometric.data import Data
    from ultra.models import Ultra
    from ultra import tasks
    from ultra.tasks import build_relation_graph

    R = {}
    meta = {"device": DEVICE, "ckpt": CKPT}

    # ---- load ULTRA (verified construction + state-dict load) ----
    rel_cfg = {"class": "RelNBFNet", "input_dim": 64, "hidden_dims": [64] * 6,
               "message_func": "distmult", "aggregate_func": "sum", "short_cut": True, "layer_norm": True}
    ent_cfg = {"class": "EntityNBFNet", "input_dim": 64, "hidden_dims": [64] * 6,
               "message_func": "distmult", "aggregate_func": "sum", "short_cut": True, "layer_norm": True}
    model = Ultra(rel_model_cfg=rel_cfg, entity_model_cfg=ent_cfg)
    try:
        state = torch.load(CKPT, map_location="cpu", weights_only=True)
    except Exception:
        state = torch.load(CKPT, map_location="cpu")
    model.load_state_dict(state["model"] if isinstance(state, dict) and "model" in state else state)
    model = model.to(DEVICE).eval()
    meta["n_params"] = int(sum(p.numel() for p in model.parameters()))
    print(f"[load] Ultra params={meta['n_params']}", flush=True)

    # ---- load NeuroKG ----
    (num_nodes, node_name, node_type, edge_index, edge_type,
     rel_vocab, drug_set, name_to_idx, dmeta) = load_neurokg()
    meta.update(dmeta)
    print(f"[neurokg] nodes={num_nodes} rels={len(rel_vocab)} fwd_edges={edge_index.size(1)} "
          f"drugs={len(drug_set)} keep_all={KEEP_ALL}", flush=True)

    rel_idx = rel_vocab.get(BINDING_REL)
    target_nodes = {}
    for sym in QUIVER_TARGETS:
        if sym in name_to_idx:
            target_nodes[sym] = {"node_idx": name_to_idx[sym], "label": TARGET_LABEL.get(sym, sym)}
    meta.update({"binding_relation": BINDING_REL, "binding_relation_idx": rel_idx,
                 "resolved_targets": {k: v["node_idx"] for k, v in target_nodes.items()}})
    print(f"[neurokg] rel_idx({BINDING_REL})={rel_idx} targets={list(target_nodes)}", flush=True)

    if rel_idx is None or not target_nodes:
        R["_fatal"] = {"error": f"binding relation {BINDING_REL} or targets unresolved",
                       "rels_sample": list(rel_vocab)[:30]}
        _write(meta, R); return 0

    # binders_by_target from drug_protein edges (whichever endpoint is a drug = the drug)
    ei = edge_index.numpy(); et = edge_type.numpy()
    binders_by_target = {}
    for col in np.where(et == rel_idx)[0]:
        h, t = int(ei[0, col]), int(ei[1, col])
        if h in drug_set:
            binders_by_target.setdefault(t, []).append(h)
        elif t in drug_set:
            binders_by_target.setdefault(h, []).append(t)
    meta["n_targets_with_kg_binders"] = sum(1 for tn in target_nodes.values()
                                            if binders_by_target.get(tn["node_idx"]))

    full_data = make_data(torch, Data, edge_index, edge_type, num_nodes, len(rel_vocab), build_relation_graph)

    # -------- A. known-binder rank percentile per target (drug->target), vs PROTON 4.3% --------
    def known_binder_ranks():
        out = {}
        for sym, tn in target_nodes.items():
            tnode = tn["node_idx"]; binders = binders_by_target.get(tnode, [])
            if not binders:
                out[sym] = {"label": tn["label"], "skip": "no drug_protein binders in KG"}; continue
            ranks, pcts = [], []
            for d in binders[:MAX_BINDERS]:
                rk, pct = rank_target_for_drug(torch, tasks, model, full_data, d, rel_idx, tnode)
                ranks.append(rk); pcts.append(pct)
            out[sym] = {"label": tn["label"], "n_known_binders": len(binders), "n_scored": len(pcts),
                        "median_rank_pct": round(float(np.median(pcts)) * 100, 3),
                        "mean_rank_pct": round(float(np.mean(pcts)) * 100, 3),
                        "median_rank": int(np.median(ranks))}
        scored = [v["median_rank_pct"] for v in out.values() if isinstance(v, dict) and "median_rank_pct" in v]
        out["_overall_median_rank_pct"] = round(float(np.median(scored)), 3) if scored else None
        out["_note"] = "same-substrate (NeuroKG) head-to-head vs PROTON 4.3%; lower=better; pct=rank/num_nodes"
        return out
    section(known_binder_ranks, "A_known_binder_rank_pct", R)

    # -------- B. hub-bias check (PROTON's Bepridil-for-9) --------
    def hub_bias():
        per_target = {}; comp_list = sorted(drug_set)
        comp_t = torch.tensor(comp_list, device=DEVICE)
        for sym, tn in target_nodes.items():
            tnode = tn["node_idx"]
            batch = torch.tensor([[[0, tnode, rel_idx]]], dtype=torch.long, device=DEVICE)
            _, h_batch = tasks.all_negative(full_data, batch.squeeze(0))
            with torch.no_grad():
                pred = model(full_data, h_batch)[0]
            comp_scores = pred[comp_t]
            topk = torch.topk(comp_scores, min(TOPK, comp_scores.numel())).indices.tolist()
            per_target[sym] = [comp_list[i] for i in topk]
        from collections import Counter
        flat = Counter(d for tops in per_target.values() for d in tops)
        promiscuous = sorted(flat.items(), key=lambda kv: -kv[1])[:TOPK]
        syms = list(per_target); jac = []
        for i in range(len(syms)):
            for j in range(i + 1, len(syms)):
                a, b = set(per_target[syms[i]]), set(per_target[syms[j]])
                if a or b:
                    jac.append(len(a & b) / len(a | b))
        return {"topk": TOPK, "n_targets": len(per_target),
                "mean_pairwise_jaccard_topk": round(float(np.mean(jac)), 4) if jac else None,
                "most_promiscuous_top_drug_target_count": max((c for _, c in promiscuous), default=0),
                "per_target_top_drug_names": {s: [node_name.get(d, str(d)) for d in tops]
                                              for s, tops in per_target.items()},
                "note": "low Jaccard / no single drug topping many targets = ULTRA avoids PROTON hub bias"}
    section(hub_bias, "B_hub_bias", R)

    # -------- C. inductive novel-target (hold all of a target's binder edges OUT) --------
    def inductive_holdout():
        cases = {}
        for sym, tn in target_nodes.items():
            tnode = tn["node_idx"]; binders = binders_by_target.get(tnode, [])
            if not binders:
                continue
            held = binders[0]
            mask = ~((et == rel_idx) & ((ei[0] == tnode) | (ei[1] == tnode)))
            keep = torch.tensor(np.where(mask)[0], dtype=torch.long)
            sub = make_data(torch, Data, edge_index[:, keep], edge_type[keep], num_nodes,
                            len(rel_vocab), build_relation_graph)
            rk, pct = rank_target_for_drug(torch, tasks, model, sub, held, rel_idx, tnode)
            cases[sym] = {"label": tn["label"], "held_drug": node_name.get(held, str(held)),
                          "n_edges_removed": int((~mask).sum()),
                          "inductive_rank": rk, "inductive_rank_pct": round(pct * 100, 3)}
            if len(cases) >= 5:
                break
        pcts = [c["inductive_rank_pct"] for c in cases.values()]
        return {"cases": cases, "median_inductive_rank_pct": round(float(np.median(pcts)), 3) if pcts else None,
                "note": "all of the target's binder edges held OUT; PROTON binder_not_in_kg=0 capability"}
    section(inductive_holdout, "C_inductive_novel_target", R)

    _write(meta, R)
    print(json.dumps({"A": R.get("A_known_binder_rank_pct", {}).get("_overall_median_rank_pct"),
                      "B_jaccard": R.get("B_hub_bias", {}).get("mean_pairwise_jaccard_topk"),
                      "C_inductive": R.get("C_inductive_novel_target", {}).get("median_inductive_rank_pct")},
                     default=str), flush=True)
    return 0


def _write(meta, R):
    payload = {"model": "ULTRA (ultra_4g, 168k-param KG FM, MIT) on NeuroKG", "track": 6,
               "kg": "NeuroKG (PrimeKG + Quiver neuro augmentation; PROTON's training graph)",
               "baseline_proton": {"median_known_binder_rank_pct": 4.3,
                                   "hub_bias": "Bepridil top-1 for 9 unrelated targets",
                                   "novel_target": "binder_not_in_kg = zero capability",
                                   "note": "PROTON was TRAINED on this graph; ULTRA is zero-shot"},
               "meta": meta, "results": R}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
