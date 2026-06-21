#!/usr/bin/env python3
"""Boltz on the antipodal-rescue DRUGGABLE PARTNER targets — validate-then-deploy + selectivity.

The deck's strategy = inhibit a druggable partner to rescue a haploinsufficient CNS gene. The molecule
we need is a partner INHIBITOR. Partners are the one place Boltz can be validated (known actives+potencies
in ChEMBL) AND where Quiver needs hits. Question 2 of the program: how fast can we get to molecules.

Phases (all via `library-screen`, readout = optimization_score = Boltz binding-strength/affinity proxy):
  P1 VALIDATION : per partner, screen ChEMBL actives (pIC50-spanning, scaffold-diverse) + measured-inactive
                  decoys. Compute (a) enrichment AUROC (active vs decoy) and (b) Spearman(optimization_score,
                  pIC50) within actives = the never-tested POTENCY-RANKING question. Ref-ligand-anchored pocket.
  P4 SELECTIVITY: does Boltz's ion-channel selectivity failure (Tier-3) generalize to soluble enzymes?
                  LSD1 panel (ORY-1001 selective vs tranylcypromine non-sel) x {KDM1A, MAOA, MAOB};
                  HDAC panel (tubastatin-A HDAC6-sel, entinostat classI) x {HDAC1, HDAC6, HDAC8}.
  P2 DEPLOY     : on the targets that PASS P1 (top by AUROC+Spearman): de-novo design (Enamine REAL) +
                  CNS-penetrant approved-drug repurposing screen. Free ADME per row; cross w/ MapLight later.

Estimate-gated, idempotent, continuous state -> results/boltz_partner_state.json.
Modes: --mode estimate|p1|p4|p2|all   --max-spend 45
"""
import json, os, re, subprocess, sys, statistics, urllib.request, urllib.parse
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOLTZ = os.environ.get("BOLTZ_BIN", "boltz-api")
RUNROOT = REPO / "results" / "boltz_partner_runs"
STATE = REPO / "results" / "boltz_partner_state.json"
DATACACHE = REPO / "data" / "partner_chembl_cache.json"
SEQCACHE = REPO / "data" / "overnight_seqs.json"
SM_MAX = 2500
N_ACT, N_DECOY, N_REF = 18, 18, 2        # validation set sizes; ref ligands anchor the pocket (excluded from scored set)
N_DESIGN, N_REPURP = 48, 150
MAX_SPEND_DEFAULT = 45.0
KEYVER = "v3"   # bump to force fresh idempotency keys when payload semantics change

# partner enzymes spanning 6 pocket/mechanism classes; crop = catalytic-domain window (0-based) or None=whole
PARTNERS = {
    "USP7":  {"acc": "Q93009", "crop": (207, 564), "class": "DUB"},
    "KDM1A": {"acc": "O60341", "crop": None,        "class": "FAD amine oxidase (LSD1)"},
    "DOT1L": {"acc": "Q8TEK3", "crop": (0, 416),    "class": "methyltransferase"},
    "WDR5":  {"acc": "P61964", "crop": None,        "class": "WD40 PPI"},
    "HDAC1": {"acc": "Q13547", "crop": None,        "class": "Zn hydrolase"},
    "BRD4":  {"acc": "O60885", "crop": (44, 178),   "class": "bromodomain (BD1)"},
}
# selectivity panel: (compound name -> selectivity note) and per-family target accessions
SEL_LSD1 = {"compounds": {"ORY-1001": "LSD1-selective", "tranylcypromine": "LSD1+MAO non-selective"},
            "targets": {"KDM1A": "O60341", "MAOA": "P21397", "MAOB": "P27338"}, "true": "KDM1A"}
SEL_HDAC = {"compounds": {"Tubastatin A": "HDAC6-selective", "Entinostat": "class-I (HDAC1/2/3)"},
            "targets": {"HDAC1": "Q13547", "HDAC6": "Q9UBN7", "HDAC8": "Q9BY41"}, "true_map": {
                "Tubastatin A": "HDAC6", "Entinostat": "HDAC1"}}


def sanitize(s): return re.sub(r"[^A-Za-z0-9_.-]", "-", str(s))[:60]


# ---------- sequence + chembl + pubchem (cached) ----------
def _seqcache():
    return json.loads(SEQCACHE.read_text()) if SEQCACHE.is_file() else {}


def fetch_seq(acc):
    c = _seqcache()
    if acc in c:
        return c[acc]
    txt = urllib.request.urlopen(f"https://rest.uniprot.org/uniprotkb/{acc}.fasta", timeout=40).read().decode()
    seq = txt.split("\n", 1)[1].replace("\n", "")
    c[acc] = seq; SEQCACHE.parent.mkdir(parents=True, exist_ok=True); SEQCACHE.write_text(json.dumps(c))
    return seq


def target_domain(gene):
    p = PARTNERS[gene]; seq = fetch_seq(p["acc"])
    return seq[p["crop"][0]:p["crop"][1]] if p["crop"] else seq


def _cache():
    return json.loads(DATACACHE.read_text()) if DATACACHE.is_file() else {}


def _save_cache(c):
    DATACACHE.parent.mkdir(parents=True, exist_ok=True); DATACACHE.write_text(json.dumps(c))


def _get(url):
    return json.load(urllib.request.urlopen(url, timeout=60))


def chembl_target_id(gene):
    u = f"https://www.ebi.ac.uk/chembl/api/data/target/search?q={urllib.parse.quote(gene)}&format=json"
    for t in _get(u).get("targets", []):
        if t.get("target_type") == "SINGLE PROTEIN" and t.get("organism") == "Homo sapiens":
            return t["target_chembl_id"]
    return None


def chembl_potency(gene):
    """per-molecule median pIC50 + smiles for a target gene; cached."""
    c = _cache()
    if gene in c:
        return c[gene]
    tid = chembl_target_id(gene)
    rows = []; offset = 0
    while len(rows) < 4000:
        u = (f"https://www.ebi.ac.uk/chembl/api/data/activity?target_chembl_id={tid}"
             f"&pchembl_value__isnull=false&standard_type__in=IC50,Ki,Kd&limit=1000&offset={offset}&format=json")
        d = _get(u); rows += d["activities"]
        if not d["page_meta"]["next"]:
            break
        offset += 1000
    bymol = defaultdict(list); smi = {}
    for a in rows:
        if a.get("canonical_smiles") and a.get("pchembl_value"):
            m = a["molecule_chembl_id"]; bymol[m].append(float(a["pchembl_value"])); smi[m] = a["canonical_smiles"]
    mols = [{"id": m, "pchembl": round(statistics.median(v), 2), "smiles": smi[m]} for m, v in bymol.items()]
    mols.sort(key=lambda x: -x["pchembl"])
    c[gene] = mols; _save_cache(c)
    return mols


def pubchem_smiles(name):
    try:
        u = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(name)}"
             f"/property/SMILES,IsomericSMILES,CanonicalSMILES/JSON")
        p = _get(u)["PropertyTable"]["Properties"][0]
        return p.get("SMILES") or p.get("IsomericSMILES") or p.get("CanonicalSMILES")
    except Exception:
        return None


# ---------- set assembly ----------
def _scaffold(s):
    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
        m = Chem.MolFromSmiles(s)
        return Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(m)) if m else None
    except Exception:
        return s


def _scaffold_diverse(items, n):
    seen, out = set(), []
    for it in items:
        sc = _scaffold(it["smiles"])
        if sc not in seen:
            seen.add(sc); out.append(it)
        if len(out) >= n:
            break
    return out


def _druglike(smiles):
    """Reject oversized / peptide ligands that hang the co-fold (ChEMBL 'small molecules' include
    big peptides, MW>2000). Keep drug-like: parseable, 150<=MW<=700, <=50 heavy atoms."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
        m = Chem.MolFromSmiles(smiles)
        if m is None:
            return False
        return 150.0 <= Descriptors.MolWt(m) <= 700.0 and m.GetNumHeavyAtoms() <= 50
    except Exception:
        return False


def _druglike_filter(mols):
    return [m for m in mols if _druglike(m["smiles"])]


def validation_set(gene):
    """ref ligands (top-2 potent, excluded), actives (pIC50-stratified, scaffold-diverse), decoys (measured pchembl<5)."""
    mols = _druglike_filter(chembl_potency(gene))   # drop oversized/peptide ligands (co-fold hang)
    refs = [m["smiles"] for m in mols[:N_REF]]
    pool = mols[N_REF:]
    actives_all = [m for m in pool if m["pchembl"] >= 6.0]
    # stratify across pIC50 bins, scaffold-diverse within
    bins = {(6, 7): [], (7, 8): [], (8, 20): []}
    for m in actives_all:
        for (lo, hi) in bins:
            if lo <= m["pchembl"] < hi:
                bins[(lo, hi)].append(m); break
    actives = []
    per = max(1, N_ACT // len(bins))
    for b in bins.values():
        actives += _scaffold_diverse(b, per)
    actives = _scaffold_diverse(actives, N_ACT) or _scaffold_diverse(actives_all, N_ACT)
    decoys = _scaffold_diverse([m for m in pool if m["pchembl"] < 5.0], N_DECOY)
    return refs, actives, decoys


def cns_repurposing_library():
    c = _cache()
    if "_cns_lib" in c:
        return c["_cns_lib"]
    rows = []; offset = 0
    while len(rows) < 3000:
        d = _get(f"https://www.ebi.ac.uk/chembl/api/data/molecule?max_phase=4&limit=1000&offset={offset}&format=json")
        rows += d["molecules"]
        if not d["page_meta"]["next"]:
            break
        offset += 1000
    cns = []
    for m in rows:
        p = m.get("molecule_properties") or {}; s = (m.get("molecule_structures") or {}).get("canonical_smiles")
        try:
            mw = float(p.get("full_mwt") or 0); al = float(p.get("alogp") or -9)
            psa = float(p.get("psa") or 999); hbd = int(p.get("hbd") or 9)
        except Exception:
            continue
        if s and 250 <= mw <= 450 and 1 <= al <= 4 and psa <= 90 and hbd <= 2:
            cns.append({"id": m["molecule_chembl_id"], "smiles": s,
                        "name": (m.get("pref_name") or m["molecule_chembl_id"])})
    cns = _scaffold_diverse(cns, N_REPURP)
    c["_cns_lib"] = cns; _save_cache(c)
    return cns


# ---------- cli + state ----------
def load_state():
    return json.loads(STATE.read_text()) if STATE.is_file() else {"jobs": {}, "spent_est": 0.0}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True); STATE.write_text(json.dumps(s, indent=2))


def cli_json(args, timeout=120):
    p = subprocess.run([BOLTZ] + args + ["--format", "json"], capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(p.stdout), (p.stderr or "")[-300:]
    except Exception:
        return None, ((p.stderr or "") + (p.stdout or ""))[-300:]


def screen_input(target_seq, molecules, refs=None):
    target = {"entities": [{"type": "protein", "chain_ids": ["A"], "value": target_seq}]}
    if refs:
        target["reference_ligands"] = refs   # nested in target: seeds pocket detection
    # DISABLE the default SMARTS catalog filter — it silently drops valid actives (e.g. all HDAC
    # hydroxamates) and would bias enrichment/potency. We want every molecule scored.
    return {"molecules": [{"smiles": m["smiles"], "id": m["id"]} for m in molecules], "target": target,
            "molecule_filters": {"boltz_smarts_catalog_filter_level": "disabled"}}


def estimate_one(inp):
    d, err = cli_json(["small-molecule:library-screen", "estimate-cost", "--input", json.dumps(inp)])
    return (float(d["estimated_cost_usd"]) if d and d.get("estimated_cost_usd") is not None else None), err


def read_index(key):
    f = RUNROOT / key / "results" / "index.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.is_file() else []


def run_screen(key, inp, max_spend, state, meta):
    if state["jobs"].get(key, {}).get("status") == "done":
        return read_index(key)
    est, err = estimate_one(inp)
    if est is None:
        state["jobs"][key] = {"status": "estimate_failed", "err": err, **meta}; save_state(state)
        print(f"  {key}: EST FAIL {err}"); return []
    if state["spent_est"] + est > max_spend:
        print(f"  BUDGET STOP at {key} (${state['spent_est']+est:.2f}>{max_spend})"); return None
    (RUNROOT / key).mkdir(parents=True, exist_ok=True)
    cli_json(["small-molecule:library-screen", "run", "--idempotency-key", key, "--input", json.dumps(inp),
              "--root-dir", str(RUNROOT), "--name", key, "--poll-interval-seconds", "10"], timeout=7200)
    rows = read_index(key)
    state["jobs"][key] = {"status": "done" if rows else "ran_no_metrics", "est": est, "n": len(rows), **meta}
    if rows:
        state["spent_est"] = round(state["spent_est"] + est, 4)
    save_state(state); print(f"  {key}: ${est} rows={len(rows)} | spent~${state['spent_est']}")
    return rows


def run_design(key, target_seq, n, max_spend, state, meta):
    if state["jobs"].get(key, {}).get("status") == "done":
        return
    inp = {"num_molecules": n, "target": {"entities": [{"type": "protein", "chain_ids": ["A"], "value": target_seq}]},
           "chemical_space": "enamine_real", "molecule_filters": {"boltz_smarts_catalog_filter_level": "recommended"}}
    d, err = cli_json(["small-molecule:design", "estimate-cost", "--input", json.dumps(inp)])
    est = float(d["estimated_cost_usd"]) if d and d.get("estimated_cost_usd") is not None else None
    if est is None:
        state["jobs"][key] = {"status": "estimate_failed", "err": err, **meta}; save_state(state); return
    if state["spent_est"] + est > max_spend:
        print(f"  BUDGET STOP at {key}"); return
    (RUNROOT / key).mkdir(parents=True, exist_ok=True)
    cli_json(["small-molecule:design", "run", "--idempotency-key", key, "--input", json.dumps(inp),
              "--root-dir", str(RUNROOT), "--name", key, "--poll-interval-seconds", "10"], timeout=7200)
    rows = read_index(key)
    state["jobs"][key] = {"status": "done" if rows else "ran_no_metrics", "est": est, "n": len(rows), **meta}
    if rows:
        state["spent_est"] = round(state["spent_est"] + est, 4)
    save_state(state); print(f"  {key}: ${est} designs={len(rows)} | spent~${state['spent_est']}")


# ---------- metrics ----------
def auroc(labels, scores):
    pos = [s for s, l in zip(scores, labels) if l == 1 and s is not None]
    neg = [s for s, l in zip(scores, labels) if l == 0 and s is not None]
    if not pos or not neg:
        return None
    n = c = 0
    for p in pos:
        for q in neg:
            n += 1; c += 1 if p > q else (0.5 if p == q else 0)
    return round(c / n, 4)


def spearman(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i]); r = [0]*len(v)
        for rk, i in enumerate(s):
            r[i] = rk
        return r
    rx, ry = rank([p[0] for p in pairs]), rank([p[1] for p in pairs])
    n = len(pairs); d2 = sum((a-b)**2 for a, b in zip(rx, ry))
    return round(1 - 6*d2/(n*(n*n-1)), 4)


# ---------- phases ----------
def phase_p1(max_spend, state):
    print("== P1 validation ==")
    for gene in PARTNERS:
        try:
            refs, actives, decoys = validation_set(gene)
        except Exception as e:
            print(f"  {gene}: set build FAIL {e}"); continue
        scored = [{**a, "_label": 1, "_pchembl": a["pchembl"]} for a in actives] + \
                 [{**d, "_label": 0, "_pchembl": d["pchembl"]} for d in decoys]
        meta = {"phase": "P1", "gene": gene, "n_act": len(actives), "n_decoy": len(decoys),
                "labels": {m["id"]: m["_label"] for m in scored}, "pchembl": {m["id"]: m["_pchembl"] for m in scored}}
        inp = screen_input(target_domain(gene), scored, refs=refs)
        run_screen(f"partner-p1-{sanitize(gene)}-{KEYVER}", inp, max_spend, state, meta)


def phase_p4(max_spend, state):
    print("== P4 selectivity ==")
    for panel_name, panel in (("lsd1", SEL_LSD1), ("hdac", SEL_HDAC)):
        cmpd_smiles = {}
        for nm in panel["compounds"]:
            s = pubchem_smiles(nm)
            if s:
                cmpd_smiles[nm] = s
        if not cmpd_smiles:
            print(f"  {panel_name}: no SMILES resolved"); continue
        for tgt_gene, acc in panel["targets"].items():
            seq = fetch_seq(acc)
            seq = seq if len(seq) <= SM_MAX else seq[:SM_MAX]
            mols = [{"smiles": s, "id": sanitize(nm)} for nm, s in cmpd_smiles.items()]
            meta = {"phase": "P4", "panel": panel_name, "target": tgt_gene,
                    "compounds": list(cmpd_smiles.keys())}
            inp = screen_input(seq, mols)
            run_screen(f"partner-p4-{panel_name}-{sanitize(tgt_gene)}-{KEYVER}", inp, max_spend, state, meta)


def p1_scorecard(state):
    """compute AUROC + potency Spearman per target from completed P1 screens."""
    card = {}
    for key, v in state["jobs"].items():
        if v.get("phase") != "P1" or v.get("status") != "done":
            continue
        rows = read_index(key)
        labels = v["labels"]; pch = v["pchembl"]
        sc = []
        for r in rows:
            eid = r.get("external_id") or r.get("id"); m = r.get("metrics", {})
            sc.append((eid, m.get("optimization_score"), m.get("binding_confidence")))
        labs = [labels.get(e) for e, o, b in sc]
        opt = [o for e, o, b in sc]
        card[v["gene"]] = {
            "auroc_opt": auroc(labs, opt),
            "auroc_bind": auroc(labs, [b for e, o, b in sc]),
            "spearman_potency": spearman([o for e, o, b in sc if labels.get(e) == 1],
                                         [pch.get(e) for e, o, b in sc if labels.get(e) == 1]),
            "n_act": v.get("n_act"), "n_decoy": v.get("n_decoy"),
        }
    return card


def phase_p2(max_spend, state):
    print("== P2 deploy (adaptive: targets that passed P1) ==")
    card = p1_scorecard(state)
    # pass = enrichment AUROC >= 0.65 (calibration-aware); rank by AUROC + max(0,spearman)
    ranked = sorted(card.items(), key=lambda kv: -((kv[1]["auroc_opt"] or 0) + max(0, kv[1]["spearman_potency"] or 0)))
    passed = [g for g, m in ranked if (m["auroc_opt"] or 0) >= 0.65][:3]
    if not passed:
        passed = [g for g, _ in ranked[:2]]   # fallback: best 2 regardless
    print("  P2 targets:", passed)
    state["p2_targets"] = passed; save_state(state)
    cns = cns_repurposing_library()
    for gene in passed:
        run_design(f"partner-p2-design-{sanitize(gene)}-{KEYVER}", target_domain(gene), N_DESIGN, max_spend, state,
                   {"phase": "P2", "kind": "design", "gene": gene})
        meta = {"phase": "P2", "kind": "repurpose", "gene": gene,
                "names": {m["id"]: m["name"] for m in cns}}
        inp = screen_input(target_domain(gene), cns)
        run_screen(f"partner-p2-repurpose-{sanitize(gene)}-{KEYVER}", inp, max_spend, state, meta)


def estimate_all():
    state = {"jobs": {}, "spent_est": 0.0}; total = 0.0; per = defaultdict(float)
    print("== estimating P1 ==")
    for gene in PARTNERS:
        refs, actives, decoys = validation_set(gene)
        scored = actives + decoys
        e, err = estimate_one(screen_input(target_domain(gene), scored, refs=refs))
        print(f"  P1 {gene:6s} act{len(actives)}+dec{len(decoys)} -> ${e} {err if e is None else ''}")
        if e:
            total += e; per["P1"] += e
    print("== estimating P4 ==")
    for panel_name, panel in (("lsd1", SEL_LSD1), ("hdac", SEL_HDAC)):
        cs = [{"smiles": pubchem_smiles(n), "id": sanitize(n)} for n in panel["compounds"]]
        cs = [c for c in cs if c["smiles"]]
        for tgt_gene, acc in panel["targets"].items():
            seq = fetch_seq(acc)[:SM_MAX]
            e, _ = estimate_one(screen_input(seq, cs))
            if e:
                total += e; per["P4"] += e
    print(f"  P4 total ~${per['P4']:.3f}")
    print("== estimating P2 (assume 3 targets) ==")
    cns = cns_repurposing_library()
    g = list(PARTNERS)[0]
    e_rep, _ = estimate_one(screen_input(target_domain(g), cns))
    di = {"num_molecules": N_DESIGN, "target": {"entities": [{"type": "protein", "chain_ids": ["A"], "value": target_domain(g)}]},
          "chemical_space": "enamine_real"}
    d, _ = cli_json(["small-molecule:design", "estimate-cost", "--input", json.dumps(di)])
    e_des = float(d["estimated_cost_usd"]) if d and d.get("estimated_cost_usd") else 0
    per["P2"] = 3 * ((e_rep or 0) + (e_des or 0)); total += per["P2"]
    print(f"  P2 ~3x(design ${e_des}+repurpose ${e_rep}) = ${per['P2']:.3f}")
    print(f"\n  per-phase: { {k: round(v,3) for k,v in per.items()} }")
    print(f"=== GRAND TOTAL (P1+P4+P2): ${total:.4f} ===")


LOCK = REPO / "results" / "boltz_partner.lock"


def acquire_lock():
    """Single-instance guard: refuse to start a paid run if another instance is alive."""
    if LOCK.is_file():
        try:
            old = int(LOCK.read_text().strip())
            os.kill(old, 0)            # raises if pid dead
            print(f"another partner runner alive (pid {old}); exiting to avoid a race."); sys.exit(0)
        except (ProcessLookupError, ValueError):
            pass                       # stale lock
        except PermissionError:
            print(f"pid in lock alive; exiting."); sys.exit(0)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(str(os.getpid()))


if __name__ == "__main__":
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "estimate"
    ms = float(sys.argv[sys.argv.index("--max-spend") + 1]) if "--max-spend" in sys.argv else MAX_SPEND_DEFAULT
    print(f"partner run mode={mode} max_spend=${ms}\n")
    if mode == "estimate":
        estimate_all()
    else:
        acquire_lock()
        st = load_state()
        if mode in ("p1", "all"):
            phase_p1(ms, st)
        if mode in ("p4", "all"):
            phase_p4(ms, st)
        if mode in ("p2", "all"):
            phase_p2(ms, st)
        print(f"\n=== pass done. spent_est ~${st['spent_est']} ===")
