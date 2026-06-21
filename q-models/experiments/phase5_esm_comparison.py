"""
Phase 5 — ESM-2 vs MAMMAL protein embeddings: head-to-head on family recovery.

MAMMAL phase 2c showed protein embedding NN same-family recall = 0.92.
This is only useful if it beats (or adds to) ESM-2, the standard protein embedding baseline.

Test:
  - 5 protein families × 5 proteins each = 25 proteins
  - Families: kinases, GPCRs, ion channels, nuclear receptors, serine proteases
  - Metric: same-family nearest-neighbor recall (leave-one-out, cosine)
  - Models: MAMMAL base_458m vs ESM-2 (facebook/esm2_t6_8M_UR50D, 8M params, fast)
  - Also: intra-family vs inter-family cosine gap

Why ESM-2 t6_8M: it's the smallest HF ESM-2 variant, loads in seconds, still a competitive baseline.
If MAMMAL is within noise of a 8M-param ESM-2, the 458M param advantage is not in embeddings.
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
OUT = os.path.join(REPO, "results", f"phase5_esm_comparison_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json")

# 5 families × 5 proteins (UniProt accessions + short names)
PANEL = {
    "kinase": [
        ("P00533", "EGFR"),
        ("P15056", "BRAF"),
        ("P24941", "CDK2"),
        ("P00519", "ABL1"),
        ("P28482", "MAPK1"),
    ],
    "gpcr": [
        ("P14416", "DRD2"),
        ("P07550", "ADRB2"),
        ("P28223", "HTR2A"),
        ("P21554", "CNR1"),
        ("P35372", "OPRM1"),
    ],
    "ion_channel": [
        ("Q15858", "Nav1.7"),
        ("Q9Y5Y9", "Nav1.8"),
        ("O43526", "KCNQ2"),
        ("O60353", "HCN1"),
        ("Q8NER1", "TRPV1"),
    ],
    "nuclear_receptor": [
        ("P37231", "PPARG"),
        ("P19793", "RXRA"),
        ("P11473", "VDR"),
        ("P03372", "ESR1"),
        ("P10275", "AR"),
    ],
    "serine_protease": [
        ("P00734", "THROMBIN"),
        ("P00750", "tPA"),
        ("P00747", "PLASMIN"),
        ("P07477", "TRYPSIN"),
        ("P29622", "KALLIKREIN"),
    ],
}

# Build flat list
PROTEINS = []
for family, members in PANEL.items():
    for acc, name in members:
        PROTEINS.append({"accession": acc, "name": name, "family": family})

FAMILY_LABELS = [p["family"] for p in PROTEINS]


def fetch_sequence(accession: str) -> str | None:
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        return None
    lines = r.text.strip().split("\n")
    return "".join(lines[1:])


def cosine_sim_matrix(embs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
    normed = embs / norms
    return normed @ normed.T


def same_family_nn_recall(sim_matrix: np.ndarray, labels: list[str]) -> float:
    n = len(labels)
    correct = 0
    for i in range(n):
        row = sim_matrix[i].copy()
        row[i] = -np.inf  # exclude self
        nn = int(np.argmax(row))
        if labels[nn] == labels[i]:
            correct += 1
    return correct / n


def intra_inter_gap(sim_matrix: np.ndarray, labels: list[str]) -> dict:
    n = len(labels)
    intra, inter = [], []
    for i in range(n):
        for j in range(i + 1, n):
            if labels[i] == labels[j]:
                intra.append(sim_matrix[i, j])
            else:
                inter.append(sim_matrix[i, j])
    return {"intra_mean": float(np.mean(intra)), "inter_mean": float(np.mean(inter)),
            "gap": float(np.mean(intra) - np.mean(inter))}


# ---- MAMMAL embeddings ----
def mammal_embeddings(sequences: list[str], device: str = "mps") -> np.ndarray:
    from mammal_quiver.embed import load_base_model, embed as mammal_embed
    print("Loading MAMMAL base model...")
    model, tok, device = load_base_model(device=device)
    embs = []
    for i, seq in enumerate(sequences):
        e = mammal_embed(model, tok, seq, kind="protein")
        embs.append(e.cpu().numpy())
        if (i + 1) % 5 == 0:
            print(f"  MAMMAL {i+1}/{len(sequences)}")
    return np.array(embs)


# ---- ESM-2 embeddings ----
def esm2_embeddings(sequences: list[str], model_name: str = "facebook/esm2_t6_8M_UR50D",
                    device: str = "mps") -> np.ndarray:
    from transformers import AutoTokenizer, AutoModel
    print(f"Loading ESM-2 ({model_name})...")
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device)
    model.eval()
    embs = []
    with torch.no_grad():
        for i, seq in enumerate(sequences):
            # Truncate to 1024 tokens (ESM-2 limit)
            truncated = seq[:1022]
            inputs = tok(truncated, return_tensors="pt", add_special_tokens=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            out = model(**inputs)
            # Mean pool over sequence positions (exclude CLS/EOS)
            hidden = out.last_hidden_state[0, 1:-1, :]  # [L, D]
            e = hidden.mean(dim=0).cpu().numpy()
            embs.append(e)
            if (i + 1) % 5 == 0:
                print(f"  ESM-2 {i+1}/{len(sequences)}")
    return np.array(embs)


def main():
    # Fetch sequences
    print("Fetching sequences from UniProt...")
    sequences = []
    valid_proteins = []
    for p in PROTEINS:
        seq = fetch_sequence(p["accession"])
        if seq:
            sequences.append(seq)
            valid_proteins.append(p)
            print(f"  {p['name']} ({p['accession']}): {len(seq)} aa")
        else:
            print(f"  FAILED: {p['name']} ({p['accession']})")

    labels = [p["family"] for p in valid_proteins]
    names = [p["name"] for p in valid_proteins]
    print(f"\n{len(valid_proteins)}/25 sequences fetched")

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Device: {device}")

    # MAMMAL embeddings
    print("\n--- MAMMAL embeddings ---")
    mammal_embs = mammal_embeddings(sequences, device=device)
    mammal_sim = cosine_sim_matrix(mammal_embs)
    mammal_recall = same_family_nn_recall(mammal_sim, labels)
    mammal_gap = intra_inter_gap(mammal_sim, labels)

    # ESM-2 embeddings
    print("\n--- ESM-2 embeddings ---")
    esm2_embs = esm2_embeddings(sequences, device=device)
    esm2_sim = cosine_sim_matrix(esm2_embs)
    esm2_recall = same_family_nn_recall(esm2_sim, labels)
    esm2_gap = intra_inter_gap(esm2_sim, labels)

    print("\n=== ESM-2 vs MAMMAL protein embeddings ===")
    print(f"  {'Model':<25} {'NN recall':>10}  {'intra':>7}  {'inter':>7}  {'gap':>7}")
    print(f"  {'MAMMAL (458M)':<25} {mammal_recall:>10.3f}  {mammal_gap['intra_mean']:>7.3f}  {mammal_gap['inter_mean']:>7.3f}  {mammal_gap['gap']:>7.3f}")
    print(f"  {'ESM-2 (8M)':<25} {esm2_recall:>10.3f}  {esm2_gap['intra_mean']:>7.3f}  {esm2_gap['inter_mean']:>7.3f}  {esm2_gap['gap']:>7.3f}")

    # Per-protein NN analysis
    print("\n  MAMMAL nearest neighbors (LOO):")
    mammal_sim_copy = mammal_sim.copy()
    for i in range(len(valid_proteins)):
        row = mammal_sim_copy[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        match = "✓" if labels[nn] == labels[i] else "✗"
        print(f"    {match} {names[i]:12} ({labels[i][:8]}) → {names[nn]:12} ({labels[nn][:8]})  sim={mammal_sim[i,nn]:.3f}")

    print("\n  ESM-2 nearest neighbors (LOO):")
    esm2_sim_copy = esm2_sim.copy()
    for i in range(len(valid_proteins)):
        row = esm2_sim_copy[i].copy()
        row[i] = -np.inf
        nn = int(np.argmax(row))
        match = "✓" if labels[nn] == labels[i] else "✗"
        print(f"    {match} {names[i]:12} ({labels[i][:8]}) → {names[nn]:12} ({labels[nn][:8]})  sim={esm2_sim[i,nn]:.3f}")

    result = {
        "test": "esm2_vs_mammal_protein_embeddings",
        "n_proteins": len(valid_proteins),
        "proteins": [{"name": p["name"], "accession": p["accession"], "family": p["family"]}
                     for p in valid_proteins],
        "mammal": {"nn_recall": float(mammal_recall), **mammal_gap,
                   "embedding_dim": int(mammal_embs.shape[1])},
        "esm2": {"model": "facebook/esm2_t6_8M_UR50D", "nn_recall": float(esm2_recall),
                 **esm2_gap, "embedding_dim": int(esm2_embs.shape[1])},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
