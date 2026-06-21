#!/usr/bin/env python3
"""CNS fine-tune readiness map — which Quiver CNS targets can be fine-tuned TODAY on public
data vs which need Quiver-generated data. Operationalizes the campaign's central finding:
a per-target binder fine-tune hits ~0.9-0.98 WHERE DATA EXISTS (trunc_test 0.92, ion-channel
fine-tune 0.98), but off-the-shelf zero-shot is at chance on data-poor families, and cross-target
transfer fails (so each target needs its own data).

For each target: query ChEMBL active-count (pChEMBL>=6) headless (total_count only, fast), and
cross-reference the measured zero-shot family AUROC, into a recommendation. Local, $0, no AWS.
Output: docs/cns_finetune_readiness.md + results/cns_finetune_readiness.json
"""
import json, os, time, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://www.ebi.ac.uk/chembl/api/data/activity.json"

# gene -> (chembl_id, family, alias). From aws/cns_new_models_eval.py + tsc2 panel.
TARGETS = [
    ("MTOR","CHEMBL2842","mtor_pathway","mTOR"),
    ("PKM","CHEMBL2107","mtor_pathway","PKM2"),
    ("PPARD","CHEMBL3979","mtor_pathway","PPARD"),
    ("AKT1","CHEMBL4282","mtor_pathway","AKT1"),
    ("RPS6KB1","CHEMBL4501","mtor_pathway","S6K1"),
    ("SCN1A","CHEMBL5277","ion_channel","Nav1.1"),
    ("SCN2A","CHEMBL4076","ion_channel","Nav1.2"),
    ("SCN8A","CHEMBL4960","ion_channel","Nav1.6"),
    ("SCN9A","CHEMBL4296","ion_channel","Nav1.7"),
    ("SCN10A","CHEMBL5451","ion_channel","Nav1.8"),
    ("SCN5A","CHEMBL1980","ion_channel","Nav1.5"),
    ("CACNA1C","CHEMBL1940","ion_channel","Cav1.2"),
    ("KCNQ2","CHEMBL4304","ion_channel","Kv7.2"),
    ("GRIN1","CHEMBL1907594","ion_channel","NMDA-NR1"),
    ("GRIN2B","CHEMBL1907600","ion_channel","NMDA-NR2B"),
    ("DRD2","CHEMBL217","gpcr","DRD2"),
    ("HTR2A","CHEMBL224","gpcr","5HT2A"),
    ("GSK3B","CHEMBL262","kinase","GSK3B"),
    ("LRRK2","CHEMBL1075104","kinase","LRRK2"),
    ("BACE1","CHEMBL4822","kinase","BACE1"),
]
# measured zero-shot binder-triage AUROC by family (BALM, from cns_dti_characterization.md)
ZS_FAMILY = {"kinase":0.80,"mtor_pathway":0.72,"gpcr":0.58,"ion_channel":0.50}


def count(chembl_id, extra):
    url = f"{BASE}?target_chembl_id={chembl_id}&{extra}&limit=1"
    for a in range(4):
        try:
            req=urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"quiver/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d=json.loads(r.read().decode())
                return d.get("page_meta",{}).get("total_count")
        except Exception:
            time.sleep(1.5*(a+1))
    return None


def recommend(actives, zs):
    if actives is None:
        return "UNKNOWN", "ChEMBL query failed"
    if actives >= 200:
        return "FINE-TUNE NOW", f"{actives} actives -> per-target fine-tune expected ~0.9+ (proven lever); off-the-shelf zero-shot ~{zs}"
    if actives >= 50:
        return "FINE-TUNE (marginal)", f"{actives} actives -> small per-target probe (~0.7-0.9); supplement w/ GtoPdb/PubChem or Quiver data"
    return "BUILD / QUIVER DATA", f"{actives} actives -> too sparse for a reliable public fine-tune; generate Quiver screening data (transfer from other targets fails)"


def main():
    rows=[]
    print("=== CNS fine-tune readiness (ChEMBL active counts) ===")
    for gene, cid, fam, alias in TARGETS:
        nact = count(cid, "pchembl_value__gte=6")
        zs = ZS_FAMILY.get(fam)
        rec, why = recommend(nact, zs)
        rows.append({"gene":gene,"alias":alias,"chembl":cid,"family":fam,
                     "chembl_actives_pchembl6":nact,"zeroshot_family_auroc":zs,
                     "recommendation":rec,"rationale":why})
        print(f"  {alias:10s} {gene:9s} {fam:13s} actives={str(nact):>6s}  zs~{zs}  -> {rec}")
        time.sleep(0.2)

    # write json + md
    json.dump({"targets":rows,"zeroshot_family_auroc":ZS_FAMILY,
               "thresholds":"actives>=200 fine-tune-now; 50-199 marginal; <50 build/Quiver-data",
               "basis":"per-target fine-tune ~0.92-0.98 where data exists (trunc_test, ionchannel_finetune); cross-target transfer fails (LOCO 0/4)"},
              open(os.path.join(REPO,"results","cns_finetune_readiness.json"),"w"), indent=2)

    by_rec={}
    for r in rows: by_rec.setdefault(r["recommendation"],[]).append(r)
    md=["# CNS fine-tune readiness map — where Quiver can fine-tune today vs must generate data",
        "",
        "**Generated 2026-06-15** (`experiments/cns_finetune_readiness.py`, ChEMBL active counts, headless, $0).",
        "Operationalizes the campaign's central finding: a per-target binder fine-tune hits **0.92-0.98 where",
        "data exists** (`trunc_test`, `ionchannel_finetune`), off-the-shelf zero-shot is family-specific",
        "(kinase 0.80 / mTOR 0.72 / GPCR 0.58 / **ion-channel 0.50**), and **cross-target transfer fails**",
        "(LOCO 0/4) — so each target needs its own data. Active-count thresholds: **>=200 fine-tune now**,",
        "50-199 marginal, **<50 build/Quiver-data**.","",
        "| Target | Gene | Family | ChEMBL actives (pChEMBL>=6) | Zero-shot (family) | Recommendation |",
        "|---|---|---|---:|---:|---|"]
    for r in sorted(rows, key=lambda x:-(x["chembl_actives_pchembl6"] or -1)):
        md.append(f"| {r['alias']} | {r['gene']} | {r['family']} | {r['chembl_actives_pchembl6']} | {r['zeroshot_family_auroc']} | **{r['recommendation']}** |")
    md+=["","## Read",
         "- **FINE-TUNE NOW** targets have enough public data that a per-target model should reach ~0.9+ today",
         "  (the proven lever) — deploy the `ionchannel_finetune`/`trunc_test` recipe per target.",
         "- **BUILD / QUIVER DATA** targets are data-poor; since transfer from other targets fails, the only",
         "  path is Quiver-generated screening data — this is where the moat is and where data-generation ROI is highest.",
         "- Off-the-shelf zero-shot is only trustworthy for the **kinase/mTOR-pathway** families (0.72-0.80);",
         "  never rely on it for ion channels (0.50).",]
    open(os.path.join(REPO,"docs","cns_finetune_readiness.md"),"w").write("\n".join(md))
    print("\nSummary by recommendation:", {k:len(v) for k,v in by_rec.items()})
    print("wrote docs/cns_finetune_readiness.md + results/cns_finetune_readiness.json")


if __name__=="__main__":
    main()
