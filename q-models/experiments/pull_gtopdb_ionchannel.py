#!/usr/bin/env python3
"""Pull a CNS ion-channel ligand-affinity corpus from the Guide to PHARMACOLOGY
(IUPHAR/BPS) REST API — headless, no auth, CC-BY-SA 4.0.

This is the substrate the campaign's ion-channel binder fine-tune has been
justifying: real measured affinities (pKd / pIC50 / pKi) for small molecules
against the CNS-relevant voltage-gated (Nav/Cav/Kv) and ligand-gated (NMDA/GRIN)
channels, with ligand SMILES. Off-the-shelf DTI is at chance on exactly these
targets; a supervised scaffold-split probe hits 0.92 — so a labelled
binder/affinity corpus on these channels is the missing ingredient.

Output: data/cns_ionchannel/
  gtopdb_ionchannel_affinities.csv   one row per (target, ligand, affinity) interaction
  gtopdb_ionchannel_targets.csv      the channel targets pulled (+ family tag)
  gtopdb_pull_summary.json           counts per family / per target / affinity-type

Polite: short sleeps, retries with backoff, hard per-request timeout. ~a few min.
"""
import csv
import json
import os
import time
import urllib.request
import urllib.error

BASE = "https://www.guidetopharmacology.org/services"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "cns_ionchannel")
os.makedirs(OUT_DIR, exist_ok=True)

# CNS-relevant channel families by HGNC-style gene prefix in the GtoPdb name.
# We pull both VGIC (voltage-gated) and LGIC (ligand-gated) target types, then
# tag each target into a CNS family for downstream per-family splits.
FAMILY_RULES = [
    ("nav", ["Na_v", "Nav", "Na<sub>v"]),     # SCN* — Quiver flagship
    ("cav", ["Ca_v", "Cav", "Ca<sub>v"]),     # CACNA* — Cav1.2 etc.
    ("kv",  ["K_v", "Kv", "K<sub>v", "KCNQ", "K_Ca", "K<sub>Ca"]),  # incl. KCNQ epilepsy
    ("nmda", ["NMDA", "GluN", "GRIN"]),         # ligand-gated glutamate (NMDA)
    ("other_lgic", ["GABA", "nACh", "5-HT3", "Glycine", "GluA", "GluK", "P2X"]),
]


def _family(name: str) -> str:
    for fam, keys in FAMILY_RULES:
        if any(k.lower() in name.lower() for k in keys):
            return fam
    return "other_channel"


def fetch(path: str, tries: int = 4, timeout: int = 30):
    """GET <BASE>/<path> as JSON, with retry/backoff. Returns parsed JSON or None."""
    url = f"{BASE}/{path}"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "quiver-cns-eval/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
            if attempt == tries - 1:
                print(f"[warn] giving up on {path}: {e}")
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def parse_affinity(val):
    """GtoPdb affinity may be a single number or a 'lo - hi' median range string.
    Return a float midpoint or None."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        if "-" in s and not s.startswith("-"):
            lo, hi = s.split("-")[:2]
            return round((float(lo) + float(hi)) / 2.0, 3)
        return float(s)
    except ValueError:
        return None


def main():
    print("=== GtoPdb ion-channel pull start ===")
    targets = []
    for ttype in ("VGIC", "LGIC"):
        rows = fetch(f"targets?type={ttype}") or []
        print(f"[targets] type={ttype}: {len(rows)}")
        for t in rows:
            nm = (t.get("name") or "").replace("<sub>", "").replace("</sub>", "")
            t["_clean_name"] = nm
            t["_family"] = _family(t.get("name") or "")
            t["_type"] = ttype
            targets.append(t)
        time.sleep(0.3)

    # Keep CNS-relevant families (drop the broad 'other_lgic'/'other_channel' noise
    # only if they have no affinity data — but pull all; tagging lets us filter later).
    print(f"[targets] total channel targets: {len(targets)}")

    interactions = []          # affinity rows
    ligand_ids = set()
    per_target = {}
    for i, t in enumerate(targets):
        tid = t.get("targetId")
        if tid is None:
            continue
        ints = fetch(f"targets/{tid}/interactions") or []
        kept = 0
        for x in ints:
            aff = parse_affinity(x.get("affinity"))
            lig = x.get("ligandId")
            if aff is None or lig is None:
                continue
            interactions.append({
                "family": t["_family"], "target_type": t["_type"],
                "target_id": tid, "target_name": t["_clean_name"],
                "target_species": x.get("targetSpecies"),
                "ligand_id": lig, "ligand_name": x.get("ligandName"),
                "affinity_type": x.get("affinityParameter"),
                "affinity_median": aff,
                "original_affinity": x.get("originalAffinity"),
                "original_type": x.get("originalAffinityType"),
                "action": x.get("action"),
                "interaction_type": x.get("type"),
                "primary_target": x.get("primaryTarget"),
                "interaction_id": x.get("interactionId"),
            })
            ligand_ids.add(lig)
            kept += 1
        if kept:
            per_target[t["_clean_name"]] = {"family": t["_family"], "n_affinity": kept}
        if i % 25 == 0:
            print(f"[interactions] {i}/{len(targets)} targets scanned, "
                  f"{len(interactions)} affinity rows, {len(ligand_ids)} ligands")
        time.sleep(0.15)

    print(f"[interactions] total affinity rows: {len(interactions)}; "
          f"unique ligands: {len(ligand_ids)}")

    # Resolve ligand SMILES.
    smiles = {}
    lig_list = sorted(ligand_ids)
    for j, lig in enumerate(lig_list):
        st = fetch(f"ligands/{lig}/structure")
        if st and st.get("smiles"):
            smiles[lig] = st["smiles"]
        if j % 100 == 0:
            print(f"[smiles] {j}/{len(lig_list)} ligands resolved ({len(smiles)} with SMILES)")
        time.sleep(0.1)
    print(f"[smiles] resolved {len(smiles)}/{len(lig_list)} ligand SMILES")

    # Write affinity CSV (only rows with a resolvable small-molecule SMILES).
    aff_path = os.path.join(OUT_DIR, "gtopdb_ionchannel_affinities.csv")
    n_written = 0
    with open(aff_path, "w", newline="") as f:
        cols = ["family", "target_type", "target_id", "target_name", "target_species",
                "ligand_id", "ligand_name", "smiles", "affinity_type", "affinity_median",
                "original_affinity", "original_type", "action", "interaction_type",
                "primary_target", "interaction_id"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in interactions:
            smi = smiles.get(row["ligand_id"])
            if not smi:
                continue
            row["smiles"] = smi
            w.writerow(row)
            n_written += 1
    print(f"[write] {n_written} affinity rows w/ SMILES -> {aff_path}")

    # Write target list.
    tgt_path = os.path.join(OUT_DIR, "gtopdb_ionchannel_targets.csv")
    with open(tgt_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["target_id", "target_name", "family",
                                          "target_type", "n_affinity"])
        w.writeheader()
        for t in targets:
            nm = t["_clean_name"]
            w.writerow({"target_id": t.get("targetId"), "target_name": nm,
                        "family": t["_family"], "target_type": t["_type"],
                        "n_affinity": per_target.get(nm, {}).get("n_affinity", 0)})

    # Summary.
    fam_counts = {}
    type_counts = {}
    for row in interactions:
        smi = smiles.get(row["ligand_id"])
        if not smi:
            continue
        fam_counts[row["family"]] = fam_counts.get(row["family"], 0) + 1
        at = row["affinity_type"] or "?"
        type_counts[at] = type_counts.get(at, 0) + 1
    summary = {
        "source": "Guide to PHARMACOLOGY (IUPHAR/BPS) REST API, CC-BY-SA 4.0",
        "pulled_target_types": ["VGIC", "LGIC"],
        "n_channel_targets": len(targets),
        "n_targets_with_affinity": len(per_target),
        "n_affinity_rows_with_smiles": n_written,
        "n_unique_ligands_with_smiles": len(smiles),
        "rows_per_family": fam_counts,
        "rows_per_affinity_type": type_counts,
        "cns_priority_families": {k: fam_counts.get(k, 0) for k in
                                  ("nav", "cav", "kv", "nmda")},
    }
    sum_path = os.path.join(OUT_DIR, "gtopdb_pull_summary.json")
    with open(sum_path, "w") as f:
        json.dump(summary, f, indent=2)
    print("=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"=== GtoPdb ion-channel pull done -> {OUT_DIR} ===")


if __name__ == "__main__":
    main()
