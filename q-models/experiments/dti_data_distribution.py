"""NEXT_STEPS 1c — Graham's data-distribution audit of MAMMAL's DTI training set.

Characterizes BindingDB_Kd (the dataset MAMMAL's DTI binding head was fine-tuned
on, pulled via PyTDC). Headline question: are ion channels / Nav (voltage-gated
sodium channels, SCN family) represented in the training data at all?

We mirror the MAMMAL data module's preprocessing:
    mammal/examples/dti_bindingdb_kd/pl_data_module.py
      data = DTI(name="BindingDB_Kd")
      data.harmonize_affinities(mode="max_affinity")   # collapse dup (drug,target) -> 1 row
      data.convert_to_log(form="binding")
      data.get_split(method=..., column_name=["Drug","Target"])
The published head used split_type="cold_split"; the PEER checkpoint (the one we
deploy) used a PEER split. BOTH draw from the SAME harmonized BindingDB_Kd pool —
so the composition / coverage audit below (what proteins exist, ion-channel
coverage) is identical regardless of split. We report on the full harmonized pool;
that is the universe the training share is sampled from.

KEY FINDING re schema: TDC's Target_ID for BindingDB_Kd IS a UniProt accession
(e.g. P00918 = carbonic anhydrase II). This lets us classify by REAL UniProt
annotations (Keywords + Protein families) fetched from the UniProt REST API, not
just name-keyword guessing on the dataset. Targets we cannot annotate (network
miss, obsolete accession) fall back to name-keyword matching and are labeled as such.

Run:  /opt/anaconda3/envs/mammal/bin/python experiments/dti_data_distribution.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # make the mammal_quiver package importable
RESULTS = REPO / "results"
CACHE = RESULTS / "_uniprot_dti_meta_cache.json"

from tdc.multi_pred import DTI  # noqa: E402

NAV1_8 = "Q9Y5Y9"  # SCN10A, the suzetrigine target


# --------------------------------------------------------------------------- #
# UniProt metadata (real annotations) — batched, cached.
# --------------------------------------------------------------------------- #
def load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def fetch_uniprot_meta(accessions: list[str], cache: dict) -> dict:
    """Return {accession: {protein, gene, keywords[], families}} via UniProt REST.

    Batched OR-query over the accession; results cached to disk so reruns are free.
    Accessions UniProt can't resolve are simply absent from the returned map.
    """
    todo = [a for a in accessions if a not in cache]
    base = "https://rest.uniprot.org/uniprotkb/search"
    fields = "accession,protein_name,gene_primary,keyword,protein_families"
    batch = 80
    for i in range(0, len(todo), batch):
        chunk = todo[i : i + batch]
        query = " OR ".join(f"accession:{a}" for a in chunk)
        params = urllib.parse.urlencode(
            {"query": query, "fields": fields, "format": "tsv", "size": str(batch)}
        )
        url = f"{base}?{params}"
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=90) as r:
                    text = r.read().decode()
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    print(f"  UniProt batch {i} failed after retries: {e}")
                    text = ""
                    break
                time.sleep(2 * (attempt + 1))
        rows = text.splitlines()
        if not rows:
            continue
        for line in rows[1:]:  # skip header
            cols = line.split("\t")
            if len(cols) < 5:
                continue
            acc, pname, gene, kw, fam = cols[0], cols[1], cols[2], cols[3], cols[4]
            cache[acc] = {
                "protein": pname,
                "gene": gene,
                "keywords": [k.strip() for k in kw.split(";") if k.strip()],
                "families": fam,
            }
        print(f"  fetched UniProt batch {i // batch + 1}/{-(-len(todo)//batch)} "
              f"({len(chunk)} accessions)")
        CACHE.write_text(json.dumps(cache))  # checkpoint after every batch
    return cache


# --------------------------------------------------------------------------- #
# Classification.
# --------------------------------------------------------------------------- #
# Keyword-based coarse class from REAL UniProt keywords (preferred), ordered by
# precedence. Each entry: (class_label, set-of-uniprot-keywords-that-imply-it).
UNIPROT_CLASS_RULES = [
    ("ion_channel", {"Ion channel", "Voltage-gated channel", "Sodium channel",
                     "Potassium channel", "Calcium channel", "Chloride channel",
                     "Ligand-gated ion channel", "Ion transport"}),
    ("kinase", {"Kinase", "Serine/threonine-protein kinase",
                "Tyrosine-protein kinase"}),
    ("gpcr", {"G-protein coupled receptor"}),
    ("protease", {"Protease", "Serine protease", "Metalloprotease",
                  "Aspartyl protease", "Thiol protease", "Hydrolase"}),
    ("nuclear_receptor", {"Receptor", "Nuclear receptor"}),  # refined below by family
    ("phosphatase", {"Hydrolase", "Protein phosphatase"}),
]

# Fallback: name-keyword classification (HEURISTIC — used only when no UniProt
# annotation is available). Order matters; first hit wins.
NAME_CLASS_RULES = [
    ("ion_channel", re.compile(
        r"sodium channel|potassium channel|calcium channel|chloride channel|"
        r"\bchannel\b|voltage-gated|SCN\d|CACNA|KCN", re.I)),
    ("kinase", re.compile(r"kinase", re.I)),
    ("gpcr", re.compile(r"G-protein coupled|G protein-coupled|receptor.*adrenergic|"
                        r"dopamine receptor|serotonin receptor|muscarinic", re.I)),
    ("protease", re.compile(r"protease|peptidase|cathepsin|caspase|elastase|"
                            r"thrombin|factor x", re.I)),
    ("nuclear_receptor", re.compile(r"nuclear receptor|estrogen receptor|androgen "
                                    r"receptor|glucocorticoid|retinoic acid receptor|"
                                    r"PPAR", re.I)),
    ("phosphatase", re.compile(r"phosphatase", re.I)),
]

ION_CHANNEL_KEYWORDS = {"Ion channel", "Voltage-gated channel", "Sodium channel",
                        "Potassium channel", "Calcium channel", "Chloride channel",
                        "Ligand-gated ion channel"}


def classify_uniprot(meta: dict) -> tuple[str, str]:
    """(class, method). Uses real UniProt keywords/families; refined for kinase/NR."""
    kws = set(meta.get("keywords", []))
    fam = (meta.get("families") or "").lower()
    pname = (meta.get("protein") or "").lower()

    # Ion channel: strongest, most specific signal — check first.
    if kws & ION_CHANNEL_KEYWORDS or "channel" in fam:
        return "ion_channel", "uniprot_keyword"
    if "kinase" in kws or "kinase" in fam or "protein kinase" in pname:
        return "kinase", "uniprot_keyword"
    if "G-protein coupled receptor" in kws or "g-protein coupled receptor" in fam:
        return "gpcr", "uniprot_keyword"
    if "Nuclear receptor" in kws or "nuclear hormone receptor" in fam:
        return "nuclear_receptor", "uniprot_keyword"
    if "protein phosphatase" in fam or "phosphatase" in pname:
        return "phosphatase", "uniprot_keyword"
    if kws & {"Protease"} or "peptidase" in fam or "protease" in pname:
        return "protease", "uniprot_keyword"
    return "other", "uniprot_keyword"


def classify_name(name: str) -> tuple[str, str]:
    for label, rx in NAME_CLASS_RULES:
        if rx.search(name or ""):
            return label, "name_heuristic"
    return "other", "name_heuristic"


def gini(counts: list[int]) -> float:
    xs = sorted(counts)
    n = len(xs)
    if n == 0:
        return float("nan")
    cum = 0
    total = sum(xs)
    if total == 0:
        return 0.0
    for i, x in enumerate(xs, 1):
        cum += i * x
    return (2 * cum) / (n * total) - (n + 1) / n


# --------------------------------------------------------------------------- #
def main() -> None:
    print("Loading BindingDB_Kd via PyTDC ...")
    data = DTI(name="BindingDB_Kd")

    raw = data.get_data()
    raw_pairs = len(raw)
    raw_drugs = raw.Drug.nunique()
    raw_targets = raw.Target_ID.nunique()
    print(f"RAW: {raw_pairs} pairs, {raw_drugs} drugs, {raw_targets} unique Target_ID")

    # Mirror the MAMMAL data module: harmonize duplicate (drug,target) measurements.
    data.harmonize_affinities(mode="max_affinity")
    df = data.get_data()
    h_pairs = len(df)
    h_drugs = df.Drug.nunique()
    h_targets = df.Target_ID.nunique()
    print(f"HARMONIZED (max_affinity): {h_pairs} pairs, {h_drugs} drugs, "
          f"{h_targets} unique Target_ID")

    df["Target_ID"] = df["Target_ID"].astype(str)
    df["seq_len"] = df["Target"].str.len()

    # ---- Target_ID schema check (is it a UniProt accession?) ----------------
    acc_re = re.compile(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$|"
                        r"^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$")
    uniq_ids = sorted(df["Target_ID"].unique())
    acc_ids = [x for x in uniq_ids if acc_re.match(x)]
    nonacc_ids = [x for x in uniq_ids if not acc_re.match(x)]
    print(f"Target_ID: {len(uniq_ids)} unique; {len(acc_ids)} look like UniProt "
          f"accessions; non-accession: {nonacc_ids}")

    # ---- Per-target pair counts --------------------------------------------
    counts = df.groupby("Target_ID").size().sort_values(ascending=False)
    seqlen_by_id = df.groupby("Target_ID")["seq_len"].first()

    # ---- Fetch UniProt metadata for all accession-style IDs -----------------
    print("Fetching UniProt metadata (cached) ...")
    cache = load_cache()
    cache = fetch_uniprot_meta(acc_ids, cache)

    # ---- Skew metrics -------------------------------------------------------
    n_targets = len(counts)
    total = int(counts.sum())
    top1pct_n = max(1, round(n_targets * 0.01))
    top10pct_n = max(1, round(n_targets * 0.10))
    top1pct_share = counts.head(top1pct_n).sum() / total
    top10pct_share = counts.head(top10pct_n).sum() / total
    g = gini(counts.tolist())
    max_med = counts.max() / counts.median()

    # ---- Top-20 targets -----------------------------------------------------
    top20 = []
    for acc, c in counts.head(20).items():
        m = cache.get(acc, {})
        top20.append({
            "accession": acc,
            "pairs": int(c),
            "gene": m.get("gene", ""),
            "protein": (m.get("protein", "") or "")[:70],
            "seq_len": int(seqlen_by_id.get(acc, 0)),
        })

    # ---- Class breakdown ----------------------------------------------------
    class_pairs: dict[str, int] = {}
    class_targets: dict[str, int] = {}
    method_used = {"uniprot_keyword": 0, "name_heuristic": 0}
    per_target_class = {}
    for acc, c in counts.items():
        m = cache.get(acc)
        if m and (m.get("keywords") or m.get("families") or m.get("protein")):
            label, method = classify_uniprot(m)
        else:
            # No UniProt annotation — fall back to whatever name we might have.
            label, method = classify_name(m.get("protein", "") if m else "")
        method_used[method] = method_used.get(method, 0) + 1
        class_pairs[label] = class_pairs.get(label, 0) + int(c)
        class_targets[label] = class_targets.get(label, 0) + 1
        per_target_class[acc] = label

    # ---- ION CHANNEL / NAV — THE HEADLINE -----------------------------------
    # (a) UniProt-annotation angle: which targets are ion channels?
    ic_targets = [a for a in counts.index if per_target_class.get(a) == "ion_channel"]
    ic_pairs = int(counts[ic_targets].sum()) if ic_targets else 0
    ic_detail = []
    for a in sorted(ic_targets, key=lambda x: -counts[x]):
        m = cache.get(a, {})
        ic_detail.append({
            "accession": a, "pairs": int(counts[a]),
            "gene": m.get("gene", ""), "protein": (m.get("protein", "") or "")[:80],
            "families": m.get("families", ""), "seq_len": int(seqlen_by_id.get(a, 0)),
        })

    # (b) Name-keyword angle on UniProt protein names (independent cross-check).
    name_channel_rx = re.compile(
        r"sodium channel|potassium channel|calcium channel|chloride channel|"
        r"voltage-gated|voltage-dependent.*channel|\bSCN\d|CACNA|KCN", re.I)
    name_hits = []
    for a in counts.index:
        m = cache.get(a, {})
        nm = m.get("protein", "") or ""
        if name_channel_rx.search(nm):
            name_hits.append((a, int(counts[a]), m.get("gene", ""), nm[:80]))

    # (c) Nav / SCN specific.
    nav_present = NAV1_8 in df["Target_ID"].values
    scn_hits = []
    for a in counts.index:
        m = cache.get(a, {})
        gene = (m.get("gene", "") or "")
        fam = (m.get("families", "") or "")
        nm = (m.get("protein", "") or "")
        if (re.match(r"SCN\d", gene, re.I) or "nav1." in fam.lower()
                or "sodium channel" in nm.lower() or "nav1." in nm.lower()):
            scn_hits.append((a, int(counts[a]), gene, nm[:80]))

    # (d) Sequence angle: is the Nav1.8 sequence (or a 50-aa probe of it) present
    #     among target sequences? And how many long (>1500 aa) multidomain targets?
    nav_seq_in_data = False
    nav_probe_hit = False
    try:
        from mammal_quiver.sequences import fetch_uniprot_sequence
        nav_seq = fetch_uniprot_sequence(NAV1_8)
        probe = nav_seq[500:550]  # an internal 50-aa window
        all_seqs = df["Target"].unique()
        nav_seq_in_data = any(nav_seq == s for s in all_seqs)
        nav_probe_hit = any(probe in s for s in all_seqs)
        nav_len = len(nav_seq)
    except Exception as e:  # noqa: BLE001
        nav_len = None
        print(f"  (Nav sequence probe skipped: {e})")
    long_targets = int((seqlen_by_id > 1500).sum())
    very_long_targets = int((seqlen_by_id > 1900).sum())

    # ----------------------------------------------------------------------- #
    # Print summary.
    # ----------------------------------------------------------------------- #
    print("\n" + "=" * 70)
    print("SKEW")
    print("=" * 70)
    print(f"targets={n_targets}  total_pairs={total}")
    print(f"top 1% targets ({top1pct_n}) hold {top1pct_share:.1%} of pairs")
    print(f"top 10% targets ({top10pct_n}) hold {top10pct_share:.1%} of pairs")
    print(f"Gini={g:.3f}   max/median pairs-per-target = {counts.max()}/{counts.median():.0f} = {max_med:.0f}x")

    print("\nTOP 20 TARGETS")
    for t in top20:
        print(f"  {t['pairs']:5d}  {t['accession']:8s} {t['gene']:10s} "
              f"{t['protein']} (len {t['seq_len']})")

    print("\nCLASS BREAKDOWN (UniProt keywords; name-heuristic fallback)")
    print(f"  classification method: uniprot_keyword={method_used.get('uniprot_keyword',0)} "
          f"targets, name_heuristic={method_used.get('name_heuristic',0)} targets")
    for label in sorted(class_pairs, key=lambda k: -class_pairs[k]):
        print(f"  {label:18s} {class_targets[label]:4d} targets  "
              f"{class_pairs[label]:6d} pairs ({class_pairs[label]/total:.1%})")

    print("\n" + "=" * 70)
    print("ION CHANNEL / NAV — HEADLINE")
    print("=" * 70)
    print(f"(a) UniProt-keyword ion channels: {len(ic_targets)} targets, {ic_pairs} pairs "
          f"({ic_pairs/total:.2%} of all pairs)")
    for d in ic_detail:
        print(f"     {d['pairs']:4d}  {d['accession']} {d['gene']:8s} {d['protein']}")
    print(f"(b) name-keyword channel hits on UniProt names: {len(name_hits)} targets")
    for a, c, g_, nm in sorted(name_hits, key=lambda x: -x[1]):
        print(f"     {c:4d}  {a} {g_:8s} {nm}")
    print(f"(c) Nav / SCN-family targets: {len(scn_hits)}  -> {scn_hits}")
    print(f"    Nav1.8 (Q9Y5Y9 / SCN10A) present as a target? {nav_present}")
    print(f"(d) Nav1.8 full sequence present in target sequences? {nav_seq_in_data}; "
          f"50-aa probe substring present? {nav_probe_hit}  (Nav1.8 len={nav_len})")
    print(f"    targets >1500 aa: {long_targets};  >1900 aa: {very_long_targets}")

    # ----------------------------------------------------------------------- #
    # Write artifacts.
    # ----------------------------------------------------------------------- #
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Per-target CSV (the raw artifact).
    csv_path = RESULTS / "dti_train_data_per_target.csv"
    import csv as _csv
    with csv_path.open("w", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["accession", "pairs", "gene", "protein", "seq_len",
                    "class", "is_ion_channel"])
        for acc, c in counts.items():
            m = cache.get(acc, {})
            w.writerow([acc, int(c), m.get("gene", ""),
                        (m.get("protein", "") or "").replace("\n", " "),
                        int(seqlen_by_id.get(acc, 0)),
                        per_target_class.get(acc, "other"),
                        per_target_class.get(acc) == "ion_channel"])
    print(f"\nWrote {csv_path}")

    summary = {
        "generated_utc": ts,
        "dataset": "BindingDB_Kd (PyTDC) — MAMMAL DTI head training pool",
        "preprocessing": "harmonize_affinities(max_affinity); same pool feeds cold_split & PEER split",
        "raw": {"pairs": raw_pairs, "drugs": raw_drugs, "targets": raw_targets},
        "harmonized": {"pairs": h_pairs, "drugs": h_drugs, "targets": h_targets},
        "target_id_is_uniprot_accession": {
            "unique_ids": len(uniq_ids), "accession_like": len(acc_ids),
            "non_accession": nonacc_ids},
        "skew": {
            "n_targets": n_targets, "total_pairs": total,
            "top_1pct_n": top1pct_n, "top_1pct_share": round(top1pct_share, 4),
            "top_10pct_n": top10pct_n, "top_10pct_share": round(top10pct_share, 4),
            "gini": round(g, 4),
            "max_pairs": int(counts.max()), "median_pairs": float(counts.median()),
            "max_over_median": round(max_med, 1)},
        "top20_targets": top20,
        "class_breakdown": {
            "method_targets": method_used,
            "pairs": class_pairs, "targets": class_targets,
            "pairs_pct": {k: round(v / total, 4) for k, v in class_pairs.items()}},
        "ion_channel_headline": {
            "uniprot_keyword_ion_channels": {
                "n_targets": len(ic_targets), "n_pairs": ic_pairs,
                "pct_of_pairs": round(ic_pairs / total, 4), "detail": ic_detail},
            "name_keyword_channel_hits": [
                {"accession": a, "pairs": c, "gene": g_, "protein": nm}
                for a, c, g_, nm in sorted(name_hits, key=lambda x: -x[1])],
            "nav_scn": {
                "nav1_8_present_as_target": bool(nav_present),
                "scn_family_targets": scn_hits,
                "nav1_8_sequence_in_data": bool(nav_seq_in_data),
                "nav1_8_50aa_probe_substring_present": bool(nav_probe_hit),
                "nav1_8_length": nav_len},
            "long_multidomain_targets": {
                "gt_1500aa": long_targets, "gt_1900aa": very_long_targets}},
    }
    json_path = RESULTS / f"dti_data_distribution_{ts}.json"
    json_path.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
