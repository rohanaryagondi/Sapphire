"""On-instance PROTON eval — embed the 40-gene CRISPR-N panel.

Reads the pretrained PROTON embedding tensor (no GPU inference needed — the
embeddings ship with the download), looks up our 40 panel genes by node_name
in nodes.csv, and reports NN-recall + family-separation gap. Same protocol
as the MAMMAL / ESM-2-650M comparison so the numbers are directly comparable.

V3 hardening (vs v2 which crashed on a print f-string):
  - No more clever quote-escapes in f-strings; status string built normally.
  - Robust tensor pickup from dict (matches shape[0] == n_nodes, not just dim==2).
  - Shape asserts (embeddings rows must equal nodes rows).
  - Handles multi-row name matches by preferring protein-typed hits.
  - Drops NaN/Inf rows before metrics.
  - Always writes results.json with status (even on partial / crash).
  - Adds per-gene NN detail + per-family recall so the JSON drops into the head-to-head table directly.
  - Wraps everything in try/except so a crash leaves crash.log + partial_results.json.
  - Mirrors output to ~/proton_out so it's retrievable even if /mnt/rohan isn't mounted.

Usage on the instance:
    cd ~/PROTON
    uv run python ~/proton_eval.py
"""
import json
import os
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

# Force unbuffered stdout so `uv run` + `tee` show progress live.
os.environ.setdefault("PYTHONUNBUFFERED", "1")

# Allow override via env; mirror to ~/proton_out so retrieval works even if
# the /mnt/rohan volume isn't mounted on this run.
OUT_PRIMARY = Path(os.environ.get("PROTON_OUT", "/mnt/rohan/proton_out"))
OUT_MIRROR  = Path.home() / "proton_out"
for d in (OUT_PRIMARY, OUT_MIRROR):
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not create {d}: {e}", flush=True)


# Same 40-gene CRISPR-N panel used in:
#   - results/phase5_crispr_panel_*.json   (MAMMAL 0.750 NN-recall)
#   - results/compare_esm2_650m.json       (ESM-2-650M 0.750 NN-recall, centered)
PANEL = [
    # Kinases — 10
    ("P00533", "EGFR",   "kinase"),
    ("P15056", "BRAF",   "kinase"),
    ("P24941", "CDK2",   "kinase"),
    ("P00519", "ABL1",   "kinase"),
    ("P28482", "MAPK1",  "kinase"),
    ("P17948", "FLT1",   "kinase"),
    ("P36888", "FLT3",   "kinase"),
    ("Q00534", "CDK6",   "kinase"),
    ("P45984", "MAPK9",  "kinase"),
    ("P06213", "INSR",   "kinase"),
    # GPCRs — 8
    ("P14416", "DRD2",   "gpcr"),
    ("P07550", "ADRB2",  "gpcr"),
    ("P28223", "HTR2A",  "gpcr"),
    ("P21554", "CNR1",   "gpcr"),
    ("P35372", "OPRM1",  "gpcr"),
    ("P34969", "HTR7",   "gpcr"),
    ("P30542", "ADORA1", "gpcr"),
    ("P29274", "ADORA2A","gpcr"),
    # Ion channels — 8
    ("Q15858", "SCN9A",  "ion_channel"),
    ("Q9Y5Y9", "SCN10A", "ion_channel"),
    ("O43526", "KCNQ2",  "ion_channel"),
    ("O60353", "HCN1",   "ion_channel"),
    ("Q8NER1", "TRPV1",  "ion_channel"),
    ("Q9ULD8", "KCNQ5",  "ion_channel"),
    ("P35498", "SCN1A",  "ion_channel"),
    ("Q14524", "SCN5A",  "ion_channel"),
    # Nuclear receptors — 6
    ("P37231", "PPARG",  "nuclear_receptor"),
    ("P19793", "RXRA",   "nuclear_receptor"),
    ("P11473", "VDR",    "nuclear_receptor"),
    ("P03372", "ESR1",   "nuclear_receptor"),
    ("P10275", "AR",     "nuclear_receptor"),
    ("P04637", "TP53",   "nuclear_receptor"),
    # E3 ligases — 4
    ("Q9NWF9", "MDM2",   "e3_ligase"),
    ("P46937", "YAP1",   "e3_ligase"),
    ("P10276", "RARA",   "e3_ligase"),
    ("Q15637", "SF3B1",  "e3_ligase"),
    # Diverse others — 4
    ("P27361", "MAPK3",  "kinase"),
    ("P42336", "PIK3CA", "lipid_kinase"),
    ("P60484", "PTEN",   "phosphatase"),
    ("O15111", "IKBKA",  "kinase"),
]


def _clean_nans(obj):
    """Recursively replace NaN/Inf floats with None so json.dumps(allow_nan=False)
    doesn't crash and the JSON is valid (NaN/Inf are not legal JSON)."""
    import math
    if isinstance(obj, dict):
        return {k: _clean_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nans(x) for x in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def _save(payload, name):
    """Write to both primary and mirror; never crash."""
    try:
        js = json.dumps(_clean_nans(payload), indent=2, default=str, allow_nan=False)
    except Exception as e:  # noqa: BLE001
        # Last-resort: write with allow_nan=True (non-standard but parses in Python).
        print(f"[warn] strict json.dumps failed ({e}); using allow_nan=True", flush=True)
        js = json.dumps(payload, indent=2, default=str, allow_nan=True)
    for d in (OUT_PRIMARY, OUT_MIRROR):
        try:
            p = d / name
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_text(js)
            os.replace(tmp, p)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] save to {d / name} failed: {e}", flush=True)


def main():
    import numpy as np
    import pandas as pd
    import torch
    from sklearn.metrics.pairwise import cosine_similarity

    sys.path.insert(0, ".")
    # Conf import can pull in heavy modules. Wrap with explicit fallback paths.
    try:
        from src.config import conf
        nodes_path = conf.paths.kg.nodes_path
        emb_path = conf.paths.checkpoint.embeddings_path
    except Exception as e:
        print(f"  [warn] src.config import failed ({type(e).__name__}: {e}); "
              "falling back to default relative paths", flush=True)
        nodes_path = Path("data/neurokg/nodes.csv")
        emb_path = Path("data/checkpoints/embeddings.pt")

    print(f"OUT primary: {OUT_PRIMARY.resolve()}", flush=True)
    print(f"OUT mirror:  {OUT_MIRROR.resolve()}", flush=True)
    print(f"nodes path:  {nodes_path}", flush=True)
    print(f"emb path:    {emb_path}", flush=True)

    t0 = time.time()
    print("\nLoading nodes.csv + embeddings.pt ...", flush=True)
    nodes = pd.read_csv(nodes_path, dtype={"node_index": int}, low_memory=False)
    print(f"  nodes.csv columns: {list(nodes.columns)[:12]}", flush=True)
    print(f"  nodes.csv shape:   {nodes.shape}", flush=True)
    print(f"  node_type values:  {sorted(nodes['node_type'].unique())[:20]}", flush=True)

    # weights_only=True: PROTON's embeddings file is a trusted local artefact we
    # just downloaded via `uv run cli download-proton`. Try the safe loader
    # first; fall back silently to the legacy loader if torch 2.3 rejects the
    # file structure (it usually does for dict-of-tensors checkpoints).
    try:
        embeddings = torch.load(emb_path, map_location="cpu", weights_only=True)
    except Exception:
        embeddings = torch.load(emb_path, map_location="cpu", weights_only=False)

    n_nodes = len(nodes)

    # If it's a dict, find the embedding tensor by SHAPE (shape[0] == n_nodes),
    # not just "first 2D". Recurse into nested dicts (future PROTON checkpoints
    # may use HeteroData-style {"x_dict": {...}} layout).
    def _find_emb_tensor(d, n_target, max_depth=3, depth=0):
        if depth > max_depth:
            return None
        if not isinstance(d, dict):
            return None
        for k, v in d.items():
            if isinstance(v, torch.Tensor) and v.dim() == 2 and v.shape[0] == n_target:
                return (k, v)
            if isinstance(v, dict):
                hit = _find_emb_tensor(v, n_target, max_depth, depth + 1)
                if hit:
                    return hit
        return None

    if isinstance(embeddings, dict):
        print(f"  embeddings dict keys: {list(embeddings.keys())[:10]}", flush=True)
        chosen = _find_emb_tensor(embeddings, n_nodes)
        if chosen is None:
            # Last resort: largest 2D tensor anywhere in the tree.
            cands = []
            def _collect(d, depth=0):
                if depth > 3 or not isinstance(d, dict):
                    return
                for k, v in d.items():
                    if isinstance(v, torch.Tensor) and v.dim() == 2:
                        cands.append((k, v))
                    elif isinstance(v, dict):
                        _collect(v, depth + 1)
            _collect(embeddings)
            if not cands:
                raise RuntimeError(f"No 2D tensor found in checkpoint dict; "
                                   f"top keys={list(embeddings.keys())[:20]}")
            # Deterministic tiebreak by (rows desc, key asc).
            chosen = max(cands, key=lambda kv: (kv[1].shape[0], -ord(kv[0][0]) if kv[0] else 0))
            print(f"  [warn] no shape-matching tensor; falling back to largest 2D: "
                  f"key={chosen[0]} shape={tuple(chosen[1].shape)}", flush=True)
        else:
            print(f"  using key {chosen[0]!r} shape={tuple(chosen[1].shape)}", flush=True)
        embeddings = chosen[1]

    embeddings = embeddings.detach().cpu()
    print(f"  embeddings shape: {tuple(embeddings.shape)}", flush=True)
    assert embeddings.shape[0] == n_nodes, (
        f"row mismatch: embeddings={embeddings.shape[0]} vs nodes={n_nodes}"
    )

    # ---- map our panel to node_index ----
    name_col = "node_name" if "node_name" in nodes.columns else None
    if name_col is None:
        for c in nodes.columns:
            if "name" in c.lower():
                name_col = c
                break
    print(f"  using name column: {name_col!r}", flush=True)

    # Filter to protein-like rows before lookup; drop NaN names.
    protein_like_types = [t for t in nodes["node_type"].unique()
                          if any(k in str(t).lower() for k in ("gene", "protein"))]
    print(f"  protein-like node types: {protein_like_types}", flush=True)
    cand_mask = nodes[name_col].notna()
    candidate = nodes.loc[cand_mask].copy()
    if protein_like_types:
        prot_candidate = candidate[candidate["node_type"].isin(protein_like_types)]
    else:
        prot_candidate = candidate
    candidate_upper = prot_candidate.assign(_n=prot_candidate[name_col].astype(str).str.upper())
    full_upper = candidate.assign(_n=candidate[name_col].astype(str).str.upper())

    panel_rows = []
    for acc, gene, family in PANEL:
        g = gene.upper()
        hits = candidate_upper[candidate_upper["_n"] == g]
        if len(hits) == 0:
            # Fallback: search all rows (different node_type)
            hits = full_upper[full_upper["_n"] == g]
        rec = {"accession": acc, "gene": gene, "family": family,
               "node_index": None, "node_type": None, "n_matches": int(len(hits))}
        if len(hits) >= 1:
            if len(hits) > 1:
                print(f"    [warn] {gene}: {len(hits)} matches; preferring first protein-typed",
                      flush=True)
            row = hits.iloc[0]
            rec["node_index"] = int(row["node_index"])
            rec["node_type"]  = str(row["node_type"])
        panel_rows.append(rec)
        if rec["node_index"] is None:
            status = "MISS"
        else:
            status = f"node {rec['node_index']} type={rec['node_type']}"
        print(f"  {gene:8s} ({family:18s}) -> {status}", flush=True)

    n_hit = sum(1 for r in panel_rows if r["node_index"] is not None)
    print(f"\nResolved: {n_hit}/{len(panel_rows)} panel genes found in NeuroKG", flush=True)
    resolved_by_fam = defaultdict(int)
    for r in panel_rows:
        if r["node_index"] is not None:
            resolved_by_fam[r["family"]] += 1
    print(f"Resolved by family: {dict(resolved_by_fam)}", flush=True)

    # ALWAYS write at least the partial state so an early-exit run is still
    # debuggable from the JSON alone (don't need to grep the log).
    base_out = {
        "status": None,  # filled below
        "model": "PROTON (mims-harvard/PROTON, NeuroKG pretrain embeddings)",
        "panel_size": len(panel_rows),
        "n_resolved": n_hit,
        "resolved_by_family": dict(resolved_by_fam),
        "comparable_to_mammal_esm": (n_hit == len(panel_rows)),
        "embedding_dim": int(embeddings.shape[1]),
        "panel": panel_rows,
    }

    if n_hit < 8:
        base_out["status"] = "insufficient_genes_resolved"
        base_out["wall_time_sec"] = round(time.time() - t0, 1)
        _save(base_out, "results.json")
        print(f"\nFAIL: too few genes resolved ({n_hit}/{len(panel_rows)}).", flush=True)
        return

    # ---- pull embeddings ----
    found = [r for r in panel_rows if r["node_index"] is not None]
    idx = [r["node_index"] for r in found]
    families = [r["family"] for r in found]
    genes = [r["gene"] for r in found]

    embs = embeddings[idx].numpy().astype("float32")
    print(f"\nEmbeddings extracted: {embs.shape}", flush=True)

    # Screen NaN/Inf rows
    finite_mask = np.isfinite(embs).all(axis=1)
    if not finite_mask.all():
        bad = [genes[i] for i in np.where(~finite_mask)[0]]
        print(f"  [warn] dropping {len(bad)} rows with NaN/Inf: {bad}", flush=True)
        embs = embs[finite_mask]
        families = [f for f, k in zip(families, finite_mask) if k]
        genes    = [g for g, k in zip(genes,    finite_mask) if k]

    EXPECTED_DIM = 512
    if embs.shape[1] != EXPECTED_DIM:
        print(f"  [warn] expected dim {EXPECTED_DIM}, got {embs.shape[1]}", flush=True)

    def compute(embs, families, genes):
        if len(embs) < 2:
            return {"nn_recall": float("nan"), "intra_cos": float("nan"),
                    "inter_cos": float("nan"), "family_gap": float("nan"),
                    "knn_k3_accuracy": float("nan"),
                    "per_family_nn_recall": {}, "nn_detail": []}
        sim = cosine_similarity(embs)
        sim_nn = sim.copy()
        np.fill_diagonal(sim_nn, -np.inf)
        n = len(genes)
        nn_idx = sim_nn.argmax(axis=1)
        same_family = sum(1 for i in range(n) if families[i] == families[nn_idx[i]])
        nn_recall = same_family / n
        # kNN k=3 — deterministic tie-break by similarity rank, not by set() hash order.
        k = min(3, n - 1)
        top_k = np.argsort(sim_nn, axis=1)[:, ::-1][:, :k]
        knn_correct = 0
        for i in range(n):
            votes = [families[j] for j in top_k[i]]  # ordered by descending similarity
            from collections import Counter
            counts = Counter(votes)
            # Tie-break: prefer the family with highest vote count;
            # then the one whose first occurrence is earliest in `votes` (i.e. nearest neighbour).
            best = max(counts, key=lambda f: (counts[f], -votes.index(f)))
            if best == families[i]:
                knn_correct += 1
        # intra / inter (use sim, not sim_nn — diagonal excluded by i<j)
        intra, inter = [], []
        for i in range(n):
            for j in range(i + 1, n):
                v = float(sim[i, j])
                (intra if families[i] == families[j] else inter).append(v)
        gap = (float(np.mean(intra)) - float(np.mean(inter))) if intra and inter else float("nan")
        # per-family recall
        by_fam = defaultdict(list)
        for i in range(n):
            by_fam[families[i]].append(int(families[i] == families[nn_idx[i]]))
        per_family = {f: float(np.mean(v)) for f, v in by_fam.items()}
        # NN detail for the writeup
        nn_detail = [
            {"gene": genes[i], "family": families[i],
             "nn": genes[int(nn_idx[i])], "nn_family": families[int(nn_idx[i])],
             "match": bool(families[i] == families[int(nn_idx[i])]),
             "sim": float(sim_nn[i, int(nn_idx[i])])}
            for i in range(n)
        ]
        return {"nn_recall": nn_recall, "intra_cos": float(np.mean(intra)) if intra else float("nan"),
                "inter_cos": float(np.mean(inter)) if inter else float("nan"),
                "family_gap": gap, "knn_k3_accuracy": knn_correct / n,
                "per_family_nn_recall": per_family, "nn_detail": nn_detail}

    raw = compute(embs, families, genes)
    print("\n=== Raw cosine ===", flush=True)
    for k, v in raw.items():
        if isinstance(v, (int, float)):
            print(f"  {k:22s}: {v:.3f}", flush=True)

    centered = embs - embs.mean(axis=0, keepdims=True)
    cen = compute(centered, families, genes)
    print("\n=== Centered (anisotropy fix) ===", flush=True)
    for k, v in cen.items():
        if isinstance(v, (int, float)):
            print(f"  {k:22s}: {v:.3f}", flush=True)

    base_out["status"] = "ok"
    base_out["raw_cosine"]      = raw
    base_out["centered_cosine"] = cen
    base_out["reference_baselines"] = {
        "MAMMAL_458M_NN_recall":        0.750,
        "ESM2_650M_raw_NN_recall":      0.725,
        "ESM2_650M_centered_NN_recall": 0.750,
    }
    base_out["wall_time_sec"] = round(time.time() - t0, 1)
    ts = time.strftime("%Y%m%d_%H%M%S")
    _save(base_out, "results.json")
    _save(base_out, f"results_{ts}.json")

    print(f"\nsaved -> {OUT_PRIMARY}/results.json (and ~/proton_out mirror)", flush=True)
    print("\n=== HEAD-TO-HEAD ===", flush=True)
    print(f"  MAMMAL 458M               NN-recall = 0.750", flush=True)
    print(f"  ESM-2 650M (raw)          NN-recall = 0.725", flush=True)
    print(f"  ESM-2 650M (centered)     NN-recall = 0.750", flush=True)
    print(f"  PROTON (raw)              NN-recall = {raw['nn_recall']:.3f}", flush=True)
    print(f"  PROTON (centered)         NN-recall = {cen['nn_recall']:.3f}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, flush=True)
        for d in (OUT_PRIMARY, OUT_MIRROR):
            try:
                (d / "crash.log").write_text(tb)
            except Exception:  # noqa: BLE001
                pass
        # Also save a stub results.json marking the failure
        try:
            _save({"status": "crashed", "error": tb.splitlines()[-1] if tb else "unknown"},
                  "results.json")
        except Exception:  # noqa: BLE001
            pass
        sys.exit(1)
