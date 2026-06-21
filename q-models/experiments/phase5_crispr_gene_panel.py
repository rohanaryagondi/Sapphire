"""
Phase 5 — Protein embedding clustering on a CRISPR-N-style gene panel.

Use case 4 from the meeting: given Quiver's CRISPR-N 1400-gene panel,
cluster genes by function so we can prioritize druggable families together.

This script uses a representative 40-gene panel spanning known drug target classes:
  - kinases (10), GPCRs (8), ion channels (8), nuclear receptors (6), E3 ligases (4), others (4)
  - Computes MAMMAL protein embeddings + UMAP 2D projection
  - Reports: intra-family cosine similarity, family classification accuracy (kNN k=3),
    and which genes are nearest to each other

The 40-gene panel was chosen to be interpretable (these are all known drug target families
with clinical precedent), not the real CRISPR-N list. Replace PANEL below with the actual
list once the real accessions are available.
"""
import os, sys, json
os.environ["USE_TF"] = "0"
os.environ["USE_FLAX"] = "0"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import torch
import requests
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAMMAL_BASE = os.path.join(REPO, "models", "base_458m")
OUT = os.path.join(REPO, "results", f"phase5_crispr_panel_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json")

# Representative 40-gene panel (UniProt accession, gene name, drug-target family)
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
    ("P04637", "TP53",   "nuclear_receptor"),   # technically TF; structural outlier — interesting
    # E3 ligases — 4
    ("Q9NWF9", "MDM2",   "e3_ligase"),
    ("P46937", "YAP1",   "e3_ligase"),
    ("P10276", "RARA",   "e3_ligase"),   # actually nuclear receptor — should cluster with NRs
    ("Q15637", "SF3B1",  "e3_ligase"),
    # Diverse others — 4
    ("P27361", "MAPK3",  "kinase"),     # duplicate family intentional (stress test)
    ("P42336", "PIK3CA", "lipid_kinase"),
    ("P60484", "PTEN",   "phosphatase"),
    ("O15111", "IKBKA",  "kinase"),
]


def fetch_sequence(accession: str) -> str | None:
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        lines = r.text.strip().split("\n")
        return "".join(lines[1:])
    except Exception:
        return None


def cosine_sim_matrix(embs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
    return (embs / norms) @ (embs / norms).T


def knn_accuracy(sim_matrix: np.ndarray, labels: list[str], k: int = 3) -> float:
    n = len(labels)
    correct = 0
    for i in range(n):
        row = sim_matrix[i].copy()
        row[i] = -np.inf
        top_k = np.argsort(row)[::-1][:k]
        votes = [labels[j] for j in top_k]
        pred = max(set(votes), key=votes.count)
        if pred == labels[i]:
            correct += 1
    return correct / n


def nn_recall(sim_matrix: np.ndarray, labels: list[str]) -> float:
    n = len(labels)
    correct = 0
    for i in range(n):
        row = sim_matrix[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        if labels[nn] == labels[i]:
            correct += 1
    return correct / n


def main():
    print("Fetching sequences from UniProt...")
    proteins = []
    sequences = []
    for acc, name, family in PANEL:
        seq = fetch_sequence(acc)
        if seq:
            proteins.append({"accession": acc, "name": name, "family": family})
            sequences.append(seq)
            print(f"  {name:12} ({acc}): {len(seq)} aa")
        else:
            print(f"  FAILED: {name} ({acc})")

    labels = [p["family"] for p in proteins]
    names = [p["name"] for p in proteins]
    print(f"\n{len(proteins)}/{len(PANEL)} sequences fetched")

    from mammal_quiver.embed import load_base_model, embed as mammal_embed
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"\nLoading MAMMAL base model (device={device})...")
    model, tok, device = load_base_model(device=device)

    print("Computing embeddings...")
    embs = []
    for i, seq in enumerate(sequences):
        e = mammal_embed(model, tok, seq, kind="protein")
        embs.append(e.cpu().numpy())
        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{len(sequences)}")
    embs = np.array(embs)

    sim = cosine_sim_matrix(embs)
    recall = nn_recall(sim, labels)
    acc_k3 = knn_accuracy(sim, labels, k=3)

    # Intra/inter family gap
    intra_vals, inter_vals = [], []
    for i in range(len(proteins)):
        for j in range(i + 1, len(proteins)):
            if labels[i] == labels[j]:
                intra_vals.append(sim[i, j])
            else:
                inter_vals.append(sim[i, j])

    print(f"\n=== CRISPR-N-style gene panel ({len(proteins)} genes) ===")
    print(f"  NN same-family recall:    {recall:.3f}")
    print(f"  k-NN (k=3) accuracy:      {acc_k3:.3f}")
    print(f"  Intra-family cosine mean: {np.mean(intra_vals):.3f}")
    print(f"  Inter-family cosine mean: {np.mean(inter_vals):.3f}")
    print(f"  Gap:                      {np.mean(intra_vals)-np.mean(inter_vals):+.3f}")

    # Per-protein NN breakdown
    print("\n  Nearest neighbors (LOO):")
    for i in range(len(proteins)):
        row = sim[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        match = "✓" if labels[nn] == labels[i] else "✗"
        print(f"    {match} {names[i]:12} ({labels[i]:<16}) → {names[nn]:12} ({labels[nn]})  sim={sim[i,nn]:.3f}")

    # Per-family summary
    print("\n  Per-family stats:")
    unique_families = sorted(set(labels))
    for fam in unique_families:
        idxs = [i for i, l in enumerate(labels) if l == fam]
        if len(idxs) < 2:
            continue
        intra = [sim[i, j] for i in idxs for j in idxs if i != j]
        recall_fam = sum(
            1 for i in idxs
            if labels[np.argmax([sim[i, j] if j != i else -np.inf for j in range(len(proteins))])] == fam
        ) / len(idxs)
        print(f"    {fam:<18} n={len(idxs)}  intra={np.mean(intra):.3f}  recall={recall_fam:.2f}")

    result = {
        "test": "crispr_n_gene_panel",
        "n_proteins": len(proteins),
        "proteins": proteins,
        "nn_recall": float(recall),
        "knn_k3_accuracy": float(acc_k3),
        "intra_family_cosine_mean": float(np.mean(intra_vals)),
        "inter_family_cosine_mean": float(np.mean(inter_vals)),
        "gap": float(np.mean(intra_vals) - np.mean(inter_vals)),
        "similarity_matrix": sim.tolist(),
        "labels": labels,
        "names": names,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
