"""ULTRA Track-6 KG characterization — head-to-head vs PROTON on Quiver drug<->target links.

ULTRA is a 168k-param KG FOUNDATION MODEL (ICLR 2024): one pretrained checkpoint does ZERO-SHOT
inductive link prediction on ANY multi-relational graph with ANY entity/relation vocabulary. It is
the direct attack on PROTON's two documented Track-6 failures (proton_operating_envelope memory):
  (1) hub bias  — PROTON ranks the SAME promiscuous drug (Bepridil) #1 for 9 unrelated targets;
  (2) novel target — PROTON's binder_not_in_kg = zero capability (no inductive transfer).
Baseline to beat: PROTON median known-binder rank percentile 4.3% (rank-known-drugs protocol).

================================ VERIFIED REPO API (do not guess) ================================
Repo:    https://github.com/DeepGraphLearning/ULTRA   (MIT License)
Weights: repo ships ckpts/ultra_4g.pth, ckpts/ultra_3g.pth, ckpts/ultra_50g.pth (~2 MB each);
         mirror on HF mgalkin/ultra_4g. We use the repo checkpoint (cloned on-instance).
Deps:    torch + torch-geometric (+ torch-scatter); the model is pure-PyG (no .bin torch.load gate).

Model construction (verbatim, script/run.py):
    from ultra.models import Ultra
    model = Ultra(rel_model_cfg=cfg.model.relation_model, entity_model_cfg=cfg.model.entity_model)
  where the inference.yaml model cfg is:
    relation_model: {class: RelNBFNet, input_dim: 64, hidden_dims: [64]*6,
                     message_func: distmult, aggregate_func: sum, short_cut: yes, layer_norm: yes}
    entity_model:   {class: EntityNBFNet, input_dim: 64, hidden_dims: [64]*6,
                     message_func: distmult, aggregate_func: sum, short_cut: yes, layer_norm: yes}

Checkpoint load (verbatim, script/run.py):
    state = torch.load(cfg.checkpoint, map_location="cpu")
    model.load_state_dict(state["model"])

Forward (verbatim, ultra/models.py + HF modeling.py wrapper):
    def forward(self, data, batch): ...   # returns score logits
  data  = PyG Data with fields edge_index, edge_type, num_nodes, num_relations, relation_graph
          (relation_graph is built by ultra.tasks.build_relation_graph(data)).
  batch = LongTensor of shape (B, 1+num_neg, 3); LAST DIM COLUMN ORDER IS [head, tail, relation].

Ranking protocol (verbatim, script/run.py test()):
    t_batch, h_batch = tasks.all_negative(test_data, batch)   # expands each (h,t,r) over ALL tails/heads
    t_pred = model(test_data, t_batch)                         # score every candidate tail
    t_ranking = tasks.compute_ranking(t_pred, pos_t_index, t_mask)  # rank of the true entity (1=best)
  all_negative builds t_batch columns as [h, all_tails, r] (we use this to rank the true target among
  all entities for a given drug+relation, i.e. drug->target). rank_percentile = rank / num_nodes.

Dataset (verbatim, ultra/datasets.py):
    from ultra.datasets import Hetionet         # TransductiveDataset, auto-downloads train/valid/test.txt
    ds = Hetionet(root=...); ds[0] -> PyG Data with target_edge_index/target_edge_type, inv_entity_vocab,
    inv_rel_vocab. Triples are whitespace 'head relation tail'; entity/relation strings -> int IDs.
    Hetionet (Himmelstein Rephetio) node scheme: 'Compound::DB#####' (DrugBank), 'Gene::<Entrez>';
    metaedges incl. CbG (Compound-binds-Gene), CtD, CdG, CuG. We DISCOVER the exact vocab at runtime
    (regex against the loaded inv_entity_vocab) rather than hardcoding — robust to scheme drift.
==================================================================================================

Analyses (each independently try/except-guarded so one failure still banks the rest):
  A. Known-binder rank percentile per Quiver target (mirror PROTON; head-to-head vs 4.3% median).
  B. Hub-bias check — across targets, do the SAME drugs top the drug->target ranking (Bepridil-for-9)?
     Report top-k drug overlap / Jaccard across targets + most-promiscuous-top drugs.
  C. Inductive novel-target case — hold a (drug,target) edge OUT of the KG, then ask ULTRA to rank it
     zero-shot. PROTON's binder_not_in_kg = 0 capability; ULTRA's design claim is it can still rank.
"""
from __future__ import annotations
import json, os, re, sys, traceback
from pathlib import Path
import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
OUT = Path(os.environ.get("OUT", "/root/ultra_out/ultra_kg_result.json"))
ULTRA_DIR = Path(os.environ.get("ULTRA_DIR", "/opt/ULTRA"))
CKPT = os.environ.get("ULTRA_CKPT", str(ULTRA_DIR / "ckpts" / "ultra_4g.pth"))
DATA_ROOT = os.environ.get("ULTRA_DATA_ROOT", "/opt/kg-datasets")
TOPK = int(os.environ.get("HUB_TOPK", "10"))

# Quiver target set (gene symbol -> Entrez gene id, used to locate the node in Hetionet's 'Gene::<entrez>').
QUIVER_TARGETS = {
    "SCN10A": "6336",   # Nav1.8
    "SCN9A":  "6335",   # Nav1.7
    "SCN5A":  "6331",   # Nav1.5
    "MTOR":   "2475",
    "EGFR":   "1956",
    "DRD2":   "1813",
    "BRAF":   "673",
    "HTR2A":  "3356",
    "GRIN1":  "2902",
    "CACNA1C": "775",   # Cav1.2
}


# ---------------------------------- helpers ----------------------------------
def section(fn, name, results):
    try:
        results[name] = fn()
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1200]}", flush=True)


def relation_match(inv_rel_vocab, prefer=("CbG", "CuG", "CdG", "BindsGene", "binds")):
    """Find the Compound->Gene binding relation id; prefer CbG, else any rel touching both C and G."""
    keys = list(inv_rel_vocab.keys())
    for p in prefer:
        for k in keys:
            if k == p or k.lower() == p.lower():
                return k, inv_rel_vocab[k]
    # fallback: any relation whose name suggests compound-gene binding
    for k in keys:
        kl = k.lower()
        if "g" in kl and ("c" in kl or "compound" in kl or "drug" in kl) and "bind" in kl:
            return k, inv_rel_vocab[k]
    return None, None


def build_id_indexes(inv_entity_vocab):
    """Index the entity vocab so we can resolve Quiver genes / drugs whatever the literal scheme is."""
    gene_by_entrez, drug_by_db, all_compounds = {}, {}, []
    ent_re = re.compile(r"(\d+)\s*$")
    db_re = re.compile(r"(DB\d{3,})", re.IGNORECASE)
    for name, idx in inv_entity_vocab.items():
        low = name.lower()
        if low.startswith("gene") or "gene::" in low:
            m = ent_re.search(name)
            if m:
                gene_by_entrez[m.group(1)] = (name, idx)
        if low.startswith("compound") or "compound::" in low or db_re.search(name):
            all_compounds.append((name, idx))
            m = db_re.search(name)
            if m:
                drug_by_db[m.group(1).upper()] = (name, idx)
    return gene_by_entrez, drug_by_db, all_compounds


def make_data(torch, Data, edge_index, edge_type, num_nodes, num_relations, build_relation_graph):
    """Build a ULTRA-ready PyG Data (bidirectional edges + inverse relations + relation_graph)."""
    # build_relation_graph (ultra/tasks.py:186) creates tensors on the DEFAULT (CPU) device and cats
    # them with data's edge tensors -> if data is already on CUDA the cat hits "two devices cuda:0 and
    # cpu" DURING the build (moving the result afterward is too late). So build the WHOLE relation graph
    # on CPU, THEN move data + the nested relation_graph sub-Data to DEVICE (PyG Data.to() does not
    # recurse into the relation_graph attribute, so move it explicitly).  [UNVALIDATED on AWS — applied
    # after the ULTRA relaunch cap (run2 vocab, run3 device-move) was reached; see characterization.]
    edge_index = edge_index.cpu(); edge_type = edge_type.cpu()
    fact_index = torch.cat([edge_index, edge_index.flip(0)], dim=1)
    fact_type = torch.cat([edge_type, edge_type + num_relations])
    data = Data(edge_index=fact_index, edge_type=fact_type, num_nodes=num_nodes,
                num_relations=num_relations * 2)
    data = build_relation_graph(data)          # all-CPU -> no device mismatch during the cat
    data = data.to(DEVICE)
    rg = getattr(data, "relation_graph", None)
    if rg is not None:
        data.relation_graph = rg.to(DEVICE)
    return data


def rank_target_for_drug(torch, tasks, model, data, drug_idx, rel_idx, target_idx):
    """Score drug->? over ALL entities; return (rank, percentile) of the true target (1=best)."""
    # batch shape (1, 1, 3) columns [h, t, r]; tail is the entity we rank.
    batch = torch.tensor([[[drug_idx, target_idx, rel_idx]]], dtype=torch.long, device=DEVICE)
    t_batch, _ = tasks.all_negative(data, batch.squeeze(0))   # (1, num_nodes, 3)
    with torch.no_grad():
        pred = model(data, t_batch)                            # (1, num_nodes)
    pos_score = pred[0, target_idx]
    rank = int((pred[0] >= pos_score).sum().item())            # #candidates scoring >= true (1=best)
    return rank, float(rank) / float(data.num_nodes)


def topk_targets_for_drug(torch, tasks, model, data, drug_idx, rel_idx, k):
    """For hub-bias: which entities does ULTRA rank highest as drug's binding partner."""
    batch = torch.tensor([[[drug_idx, 0, rel_idx]]], dtype=torch.long, device=DEVICE)
    t_batch, _ = tasks.all_negative(data, batch.squeeze(0))
    with torch.no_grad():
        pred = model(data, t_batch)[0]
    top = torch.topk(pred, min(k, pred.numel())).indices.tolist()
    return top


# ---------------------------------- main ----------------------------------
def main():
    import torch
    sys.path.insert(0, str(ULTRA_DIR))
    from torch_geometric.data import Data
    from ultra.models import Ultra
    from ultra import tasks
    from ultra.tasks import build_relation_graph
    from ultra.datasets import Hetionet

    R = {}
    meta = {"device": DEVICE, "ckpt": CKPT}

    # ---- load model (verified construction + state-dict load) ----
    rel_cfg = {"class": "RelNBFNet", "input_dim": 64, "hidden_dims": [64] * 6,
               "message_func": "distmult", "aggregate_func": "sum", "short_cut": True, "layer_norm": True}
    ent_cfg = {"class": "EntityNBFNet", "input_dim": 64, "hidden_dims": [64] * 6,
               "message_func": "distmult", "aggregate_func": "sum", "short_cut": True, "layer_norm": True}
    model = Ultra(rel_model_cfg=rel_cfg, entity_model_cfg=ent_cfg)
    # ultra_4g.pth state["model"] is a plain tensor state-dict -> weights_only=True is safe + sufficient.
    try:
        state = torch.load(CKPT, map_location="cpu", weights_only=True)
    except Exception:
        state = torch.load(CKPT, map_location="cpu")  # older torch lacks the kwarg
    model.load_state_dict(state["model"] if isinstance(state, dict) and "model" in state else state)
    model = model.to(DEVICE).eval()
    n_params = sum(p.numel() for p in model.parameters())
    meta["n_params"] = int(n_params)
    print(f"[load] Ultra params={n_params}", flush=True)

    # ---- load Hetionet (auto-download) and resolve vocab ----
    ds = Hetionet(root=DATA_ROOT)
    g = ds[0]
    inv_entity_vocab = getattr(ds, "inv_entity_vocab", getattr(g, "inv_entity_vocab", {})) or {}
    inv_rel_vocab = getattr(ds, "inv_rel_vocab", getattr(g, "inv_rel_vocab", {})) or {}
    # The name->int vocab dicts do NOT survive PyG InMemoryDataset save/reload (only data/slices are
    # persisted), so they come back empty. Rebuild via ULTRA's OWN load_file over the raw
    # train/valid/test.txt in first-seen order -- identical to the dataset's process(), so the indices
    # match the processed Data's edge_type/edge_index.
    if not inv_entity_vocab or not inv_rel_vocab:
        import os as _os
        rp = list(getattr(ds, "raw_paths", []))
        if len(rp) < 3:
            rd = getattr(ds, "raw_dir", _os.path.join(DATA_ROOT, "Hetionet", "raw"))
            rp = [_os.path.join(rd, f) for f in ("train.txt", "valid.txt", "test.txt")]
        print(f"[vocab] rebuilding from raw triple files via ds.load_file: {rp}", flush=True)
        tr = ds.load_file(rp[0], {}, {})
        va = ds.load_file(rp[1], tr["inv_entity_vocab"], tr["inv_rel_vocab"])
        te = ds.load_file(rp[2], va["inv_entity_vocab"], va["inv_rel_vocab"])
        inv_entity_vocab = te["inv_entity_vocab"]; inv_rel_vocab = te["inv_rel_vocab"]
        print(f"[vocab] rebuilt: {len(inv_entity_vocab)} entities, {len(inv_rel_vocab)} relations", flush=True)
    num_nodes = int(g.num_nodes)
    base_num_rel = int(getattr(g, "num_relations", len(inv_rel_vocab)))
    if base_num_rel > len(inv_rel_vocab) and len(inv_rel_vocab):  # g may already be doubled
        base_num_rel = len(inv_rel_vocab)
    full_edge_index = g.target_edge_index if hasattr(g, "target_edge_index") else g.edge_index
    full_edge_type = g.target_edge_type if hasattr(g, "target_edge_type") else g.edge_type
    meta.update({"hetionet_num_nodes": num_nodes, "hetionet_num_relations": base_num_rel,
                 "hetionet_num_edges": int(full_edge_index.size(1)),
                 "rel_vocab_sample": list(inv_rel_vocab.keys())[:40],
                 "entity_vocab_sample": list(inv_entity_vocab.keys())[:8]})

    rel_name, rel_idx = relation_match(inv_rel_vocab)
    gene_by_entrez, drug_by_db, all_compounds = build_id_indexes(inv_entity_vocab)
    meta.update({"binding_relation": rel_name, "binding_relation_idx": rel_idx,
                 "n_genes_indexed": len(gene_by_entrez), "n_compounds_indexed": len(all_compounds)})
    print(f"[vocab] rel={rel_name} genes={len(gene_by_entrez)} comps={len(all_compounds)}", flush=True)

    # resolve Quiver targets to node indices
    target_nodes = {}
    for sym, entrez in QUIVER_TARGETS.items():
        hit = gene_by_entrez.get(entrez)
        if hit:
            target_nodes[sym] = {"entrez": entrez, "node_name": hit[0], "node_idx": int(hit[1])}
    meta["resolved_targets"] = target_nodes

    if rel_idx is None or not target_nodes:
        R["_fatal"] = {"error": "could not resolve binding relation or any Quiver target in Hetionet vocab"}
        payload = {"model": "ULTRA (ultra_4g, 168k-param KG foundation model)", "track": 6,
                   "baseline_proton_median_rank_pct": 4.3, "meta": meta, "results": R}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2, default=str))
        print("[done] fatal vocab miss; wrote partial", flush=True)
        return 0

    # full-graph Data (all known edges in the KG)
    full_data = make_data(torch, Data, full_edge_index.to(DEVICE), full_edge_type.to(DEVICE),
                          num_nodes, base_num_rel, build_relation_graph)

    # build set of TRUE binders per target from the KG (genes bound by compounds via rel_idx)
    ei = full_edge_index.cpu().numpy(); et = full_edge_type.cpu().numpy()
    comp_idx_set = {int(i) for _, i in all_compounds}
    binders_by_target = {}  # target_node_idx -> list of drug node idx that bind it
    for col in range(ei.shape[1]):
        if int(et[col]) != rel_idx:
            continue
        h, t = int(ei[0, col]), int(ei[1, col])
        # Compound-binds-Gene: head is compound, tail is gene (Rephetio CbG direction)
        if h in comp_idx_set:
            binders_by_target.setdefault(t, []).append(h)
        elif t in comp_idx_set:
            binders_by_target.setdefault(h, []).append(t)
    meta["n_targets_with_kg_binders"] = sum(
        1 for tn in target_nodes.values() if binders_by_target.get(tn["node_idx"]))

    # -------- A. known-binder rank percentile per target (drug->target), vs PROTON 4.3% --------
    def known_binder_ranks():
        out = {}
        for sym, tn in target_nodes.items():
            tnode = tn["node_idx"]
            binders = binders_by_target.get(tnode, [])
            if not binders:
                out[sym] = {"skip": "no KG binders for this target node"}
                continue
            pcts, ranks = [], []
            for d in binders[:50]:  # cap for runtime
                rk, pct = rank_target_for_drug(torch, tasks, model, full_data, d, rel_idx, tnode)
                ranks.append(rk); pcts.append(pct)
            out[sym] = {"node": tn["node_name"], "n_known_binders": len(binders),
                        "n_scored": len(pcts),
                        "median_rank_pct": round(float(np.median(pcts)) * 100, 3) if pcts else None,
                        "mean_rank_pct": round(float(np.mean(pcts)) * 100, 3) if pcts else None,
                        "median_rank": int(np.median(ranks)) if ranks else None}
        scored = [v["median_rank_pct"] for v in out.values() if isinstance(v, dict) and v.get("median_rank_pct") is not None]
        out["_overall_median_rank_pct"] = round(float(np.median(scored)), 3) if scored else None
        out["_note"] = "head-to-head vs PROTON median 4.3%; lower is better; pct = rank/num_nodes"
        return out
    section(known_binder_ranks, "A_known_binder_rank_pct", R)

    # -------- B. hub-bias check — same drugs topping many unrelated targets? --------
    def hub_bias():
        # Approach mirrors PROTON's Bepridil-for-9 failure mode: for each target, take the top-k drugs
        # ULTRA ranks as binders (target->drug), then measure cross-target overlap of those top-k sets.
        per_target_topdrugs = {}
        # rank DRUGS for a target: use head-side negatives (all heads as candidate compounds)
        for sym, tn in target_nodes.items():
            tnode = tn["node_idx"]
            batch = torch.tensor([[[0, tnode, rel_idx]]], dtype=torch.long, device=DEVICE)
            _, h_batch = tasks.all_negative(full_data, batch.squeeze(0))  # (1, num_nodes, 3) heads vary
            with torch.no_grad():
                pred = model(full_data, h_batch)[0]
            # restrict ranking to compound nodes only (drugs), mirroring "which drug binds X"
            comp_list = sorted(comp_idx_set)
            comp_scores = pred[torch.tensor(comp_list, device=DEVICE)]
            topk = torch.topk(comp_scores, min(TOPK, comp_scores.numel())).indices.tolist()
            top_nodes = [comp_list[i] for i in topk]
            per_target_topdrugs[sym] = top_nodes
        # cross-target overlap stats
        from collections import Counter
        flat = Counter()
        for tops in per_target_topdrugs.values():
            for d in tops:
                flat[d] += 1
        # promiscuous drugs: appear in top-k for many targets (the Bepridil signature)
        promiscuous = sorted(flat.items(), key=lambda kv: -kv[1])[:TOPK]
        n_targets = len(per_target_topdrugs)
        max_share = max((c for _, c in promiscuous), default=0)
        # mean pairwise Jaccard of top-k sets
        syms = list(per_target_topdrugs.keys()); jac = []
        for i in range(len(syms)):
            for j in range(i + 1, len(syms)):
                a, b = set(per_target_topdrugs[syms[i]]), set(per_target_topdrugs[syms[j]])
                if a or b:
                    jac.append(len(a & b) / len(a | b))
        return {"topk": TOPK, "n_targets": n_targets,
                "mean_pairwise_jaccard_topk": round(float(np.mean(jac)), 4) if jac else None,
                "most_promiscuous_top_drug_target_count": max_share,
                "promiscuous_node_idx_counts": {str(d): c for d, c in promiscuous},
                "per_target_topk_node_idx": per_target_topdrugs,
                "note": "high Jaccard / one drug topping many targets = PROTON-style hub bias; "
                        "low Jaccard = ULTRA discriminates per target"}
    section(hub_bias, "B_hub_bias", R)

    # -------- C. inductive novel-target case — hold an edge OUT, rank zero-shot --------
    def inductive_holdout():
        # Pick a target that HAS a KG binder, remove ALL its binding edges from the graph, rebuild the
        # graph WITHOUT them, and ask ULTRA to rank the held-out true binder zero-shot. This is exactly
        # PROTON's binder_not_in_kg = zero-capability case. ULTRA's FM claim: still rankable.
        cases = {}
        for sym, tn in target_nodes.items():
            tnode = tn["node_idx"]
            binders = binders_by_target.get(tnode, [])
            if not binders:
                continue
            held_drug = binders[0]
            # mask out every edge of relation rel_idx incident to this target node
            keep = []
            for col in range(ei.shape[1]):
                h, t = int(ei[0, col]), int(ei[1, col])
                is_target_bind = (int(et[col]) == rel_idx) and (tnode in (h, t))
                if not is_target_bind:
                    keep.append(col)
            keep_t = torch.tensor(keep, dtype=torch.long)
            sub_ei = full_edge_index[:, keep_t].to(DEVICE)
            sub_et = full_edge_type[keep_t].to(DEVICE)
            sub_data = make_data(torch, Data, sub_ei, sub_et, num_nodes, base_num_rel, build_relation_graph)
            rk, pct = rank_target_for_drug(torch, tasks, model, sub_data, held_drug, rel_idx, tnode)
            cases[sym] = {"held_drug_node_idx": held_drug, "n_edges_removed": ei.shape[1] - len(keep),
                          "inductive_rank": rk, "inductive_rank_pct": round(pct * 100, 3)}
            if len(cases) >= 5:  # cap: rebuilding the relation graph per case is the costly step
                break
        pcts = [c["inductive_rank_pct"] for c in cases.values()]
        return {"cases": cases,
                "median_inductive_rank_pct": round(float(np.median(pcts)), 3) if pcts else None,
                "note": "edge held OUT of KG; PROTON binder_not_in_kg=0 capability. If ULTRA still "
                        "ranks the true target well (<~10%), that is inductive transfer PROTON lacks."}
    section(inductive_holdout, "C_inductive_novel_target", R)

    payload = {"model": "ULTRA (ultra_4g, 168k-param KG foundation model, MIT)",
               "track": 6, "kg": "Hetionet (Rephetio)",
               "baseline_proton": {"median_known_binder_rank_pct": 4.3,
                                   "hub_bias": "Bepridil top-1 for 9 unrelated targets",
                                   "novel_target": "binder_not_in_kg = zero capability"},
               "meta": meta, "results": R}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps({"A_overall_median_rank_pct": R.get("A_known_binder_rank_pct", {}).get("_overall_median_rank_pct"),
                      "B_mean_jaccard": R.get("B_hub_bias", {}).get("mean_pairwise_jaccard_topk"),
                      "C_median_inductive_pct": R.get("C_inductive_novel_target", {}).get("median_inductive_rank_pct")},
                     default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
