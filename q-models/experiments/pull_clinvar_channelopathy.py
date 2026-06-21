#!/usr/bin/env python3
"""Pull the clinically-observed missense-variant catalog for the CNS channelopathy
genes from ClinVar via NCBI E-utilities — headless, no auth (public rate limit), free.

Why: Track 9 (variant effect / GoF-LoF). funNCion covers some public channels but
SCN10A (Nav1.8) + SCN3A are ABSENT from every public functional set. ClinVar is the
canonical clinical-variant catalog: it gives, per channelopathy gene, the universe of
observed missense variants with their clinical significance (pathogenic / likely-path /
benign / VUS), protein change, and associated condition. This is NOT GoF/LoF labels
(ClinVar doesn't carry functional direction) — it is (a) the variant universe to score,
(b) a pathogenicity baseline, and (c) the scaffold a Quiver functional-data model fills in
with direction. Especially valuable for SCN10A where no public model has any variants.

Output: data/cns_variants/
  clinvar_channelopathy_variants.csv   one row per (gene, variant) with protein change + clin sig
  clinvar_pull_summary.json            counts per gene / per clinical-significance bucket

Polite: batched esummary, sleeps under the 3 req/s anon limit, retries.
"""
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "cns_variants")
os.makedirs(OUT_DIR, exist_ok=True)

# CNS channelopathy genes. SCN10A (Nav1.8) + SCN3A are the Quiver-flagship gaps.
GENES = {
    "SCN10A": "nav (Nav1.8 — Quiver flagship, absent from public functional sets)",
    "SCN3A":  "nav (Nav1.3 — also absent from public sets)",
    "SCN1A":  "nav (Nav1.1 — Dravet)",
    "SCN2A":  "nav (Nav1.2)",
    "SCN8A":  "nav (Nav1.6)",
    "SCN9A":  "nav (Nav1.7 — pain)",
    "SCN5A":  "nav (Nav1.5 — cardiac ref)",
    "CACNA1C": "cav (Cav1.2 — Timothy)",
    "CACNA1A": "cav (Cav2.1 — ataxia/migraine)",
    "GRIN1":  "nmda (NR1)",
    "GRIN2A": "nmda (NR2A — epilepsy-aphasia)",
    "GRIN2B": "nmda (NR2B)",
    "KCNQ2":  "kv (epilepsy)",
}

PROT_RE = re.compile(r"\(p\.([A-Za-z]{3})(\d+)([A-Za-z]{3}|=|\*|fs|del|dup|ins)?\)")


def http_json(url: str, tries: int = 4, timeout: int = 40):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quiver-cns-eval/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
            if attempt == tries - 1:
                print(f"[warn] giving up: {e}")
                return None
            time.sleep(2.0 * (attempt + 1))
    return None


def esearch(gene: str, retmax: int = 800):
    term = f"{gene}[gene] AND single_nucleotide_variant[Type of variation] AND missense_variant[molecular consequence]"
    url = f"{EUTILS}/esearch.fcgi?db=clinvar&term={urllib.parse.quote(term)}&retmode=json&retmax={retmax}"
    d = http_json(url)
    if not d:
        return []
    return d.get("esearchresult", {}).get("idlist", []) or []


def parse_protein_change(name: str):
    m = PROT_RE.search(name or "")
    if not m:
        return None
    ref, pos, alt = m.group(1), m.group(2), m.group(3) or ""
    return f"p.{ref}{pos}{alt}"


def esummary(ids):
    out = []
    for k in range(0, len(ids), 200):
        batch = ids[k:k + 200]
        url = (f"{EUTILS}/esummary.fcgi?db=clinvar&id={','.join(batch)}&retmode=json")
        d = http_json(url)
        if not d:
            time.sleep(0.5)
            continue
        res = d.get("result", {})
        for uid in res.get("uids", []):
            rec = res.get(uid, {})
            # germline classification (clinical significance) — v2 esummary
            germ = rec.get("germline_classification", {}) or {}
            clin = germ.get("description") or rec.get("clinical_significance", {}).get("description") or ""
            review = germ.get("review_status") or ""
            title = rec.get("title", "")
            varset = rec.get("variation_set", []) or [{}]
            vname = varset[0].get("variation_name", title) if varset else title
            traits = rec.get("trait_set", []) or germ.get("trait_set", []) or []
            cond = "; ".join(t.get("trait_name", "") for t in traits[:3])
            out.append({"uid": uid, "variation_name": vname,
                        "protein_change": parse_protein_change(vname or title),
                        "clinical_significance": clin, "review_status": review,
                        "condition": cond})
        time.sleep(0.4)
    return out


def bucket(sig: str) -> str:
    s = (sig or "").lower()
    if "pathogenic" in s and "likely" in s:
        return "likely_pathogenic"
    if "pathogenic" in s and "benign" not in s:
        return "pathogenic"
    if "benign" in s and "likely" in s:
        return "likely_benign"
    if "benign" in s:
        return "benign"
    if "uncertain" in s or "conflicting" in s or not s:
        return "vus_or_conflicting"
    return "other"


def main():
    print("=== ClinVar channelopathy pull start ===")
    rows = []
    per_gene = {}
    for gene, tag in GENES.items():
        ids = esearch(gene)
        print(f"[esearch] {gene}: {len(ids)} missense SNV records")
        recs = esummary(ids) if ids else []
        kept = 0
        for r in recs:
            r["gene"] = gene
            r["family_tag"] = tag
            r["sig_bucket"] = bucket(r["clinical_significance"])
            rows.append(r)
            kept += 1
        per_gene[gene] = kept
        time.sleep(0.5)

    csv_path = os.path.join(OUT_DIR, "clinvar_channelopathy_variants.csv")
    cols = ["gene", "family_tag", "protein_change", "clinical_significance",
            "sig_bucket", "review_status", "condition", "variation_name", "uid"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    print(f"[write] {len(rows)} variant rows -> {csv_path}")

    buckets = {}
    for r in rows:
        buckets[r["sig_bucket"]] = buckets.get(r["sig_bucket"], 0) + 1
    summary = {
        "source": "ClinVar via NCBI E-utilities (public domain)",
        "query": "<gene>[gene] AND single_nucleotide_variant AND missense_variant",
        "genes": GENES,
        "n_variants_total": len(rows),
        "variants_per_gene": per_gene,
        "variants_per_significance_bucket": buckets,
        "note": "Clinical significance only — NOT functional GoF/LoF direction. "
                "SCN10A/SCN3A counts are the Quiver-flagship gap funNCion can't cover.",
    }
    with open(os.path.join(OUT_DIR, "clinvar_pull_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"=== ClinVar pull done -> {OUT_DIR} ===")


if __name__ == "__main__":
    main()
