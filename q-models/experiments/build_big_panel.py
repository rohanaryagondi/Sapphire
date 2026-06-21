"""Build a LARGER, balanced protein-family panel to DE-SATURATE Track 1.

The 40-gene CRISPR-N panel is saturated (~0.85-0.875 for everything; ceiling capped by 2
singleton families). To exhaustively rank the candidate embeddings we need a harder panel:
~12 real druggable families x ~14 reviewed human members each (no singletons), spanning both
clean fold-defined families (kinases, GPCRs, ion channels, NRs, proteases, carbonic anhydrases)
and harder function-defined ones (E3 ligases, SLC transporters) where pure-sequence models fail.

Pulls reviewed human members per family from the UniProt REST API + sequences (cached).
Out: results/big_panel.json  ({accession,name,family,sequence} list).
"""
from __future__ import annotations
import json, time, sys
from pathlib import Path
import requests

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "big_panel.json"
SEQ_CACHE = REPO / "results" / "_uniprot_cache.json"
PER_FAMILY = 14

# (family label, UniProt query). Queries target reviewed human members of each family.
FAMILIES = [
    ("kinase",            'family:"protein kinase superfamily" AND reviewed:true AND organism_id:9606'),
    ("gpcr",              'family:"g-protein coupled receptor 1 family" AND reviewed:true AND organism_id:9606'),
    ("ion_channel",       'keyword:"Voltage-gated channel" AND reviewed:true AND organism_id:9606'),
    ("nuclear_receptor",  'family:"nuclear hormone receptor family" AND reviewed:true AND organism_id:9606'),
    ("serine_protease",   'family:"peptidase S1 family" AND reviewed:true AND organism_id:9606'),
    ("carbonic_anhydrase",'family:"alpha-carbonic anhydrase family" AND reviewed:true AND organism_id:9606'),
    ("cytochrome_p450",   'family:"cytochrome P450 family" AND reviewed:true AND organism_id:9606'),
    ("phosphatase",       'keyword:"Protein phosphatase" AND reviewed:true AND organism_id:9606'),
    ("abc_transporter",   'family:"ABC transporter superfamily" AND reviewed:true AND organism_id:9606'),
    ("e3_ligase",         'keyword:"Ubl conjugation pathway" AND keyword:"Transferase" AND reviewed:true AND organism_id:9606'),
    ("bromodomain",       'keyword:"Bromodomain" AND reviewed:true AND organism_id:9606'),
    ("matrix_metallo",    'family:"peptidase M10A family" AND reviewed:true AND organism_id:9606'),
]


def query_family(q, n):
    url = ("https://rest.uniprot.org/uniprotkb/search?"
           f"query=({q})&format=tsv&fields=accession,gene_primary,length&size={n*2}")
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  query {r.status_code}: {q[:40]}", flush=True); return []
        rows = [l.split("\t") for l in r.text.strip().split("\n")[1:] if l.strip()]
        # prefer 200-1500 aa (avoid tiny fragments / giant multidomain) for clean embeddings
        out = []
        for acc, gene, length in rows:
            try:
                L = int(length)
            except Exception:
                continue
            if 150 <= L <= 1600 and gene:
                out.append((acc, gene))
            if len(out) >= n:
                break
        return out
    except Exception as e:
        print(f"  query err {q[:40]}: {e}", flush=True); return []


def fetch_seq(acc, cache):
    if cache.get(acc):
        return cache[acc]
    try:
        r = requests.get(f"https://rest.uniprot.org/uniprotkb/{acc}.fasta", timeout=20)
        if r.status_code == 200:
            seq = "".join(r.text.strip().split("\n")[1:])
            cache[acc] = seq
            return seq
    except Exception:
        pass
    return None


def main():
    cache = json.loads(SEQ_CACHE.read_text()) if SEQ_CACHE.is_file() else {}
    panel = []
    seen = set()
    for fam, q in FAMILIES:
        members = query_family(q, PER_FAMILY)
        got = 0
        for acc, gene in members:
            if acc in seen:
                continue
            seq = fetch_seq(acc, cache)
            if not seq:
                continue
            seen.add(acc)
            panel.append({"accession": acc, "name": gene, "family": fam, "length": len(seq), "sequence": seq})
            got += 1
        print(f"{fam:18}: {got} members", flush=True)
        time.sleep(0.5)
    SEQ_CACHE.write_text(json.dumps(cache, indent=2))
    OUT.write_text(json.dumps(panel, indent=2))
    from collections import Counter
    dist = Counter(p["family"] for p in panel)
    print(f"\nTOTAL: {len(panel)} genes across {len(dist)} families")
    print("per-family:", dict(dist))
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
