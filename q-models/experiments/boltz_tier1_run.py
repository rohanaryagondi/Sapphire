#!/usr/bin/env python3
"""Boltz-API Tier-1 runner — Q1/Q2/Q3 structure-and-binding, via the hosted boltz-api CLI.

Q1  Nav1.8 binder-vs-decoy  : 11 cpds x Nav1.8 -> binding_confidence AUROC (vs our fine-tune 0.987 / BALM)
Q2  Suzetrigine selectivity : suzetrigine x 9 Nav paralogs -> is Nav1.8 ranked #1, with separation?
Q3  TSC2 deconvolution      : 9 Ben hits x {PKM2, PPARD} -> does binding_confidence deconvolve (where ligand-QSAR failed)?

Modes:
  --mode estimate : estimate-cost every job (FREE, no GPU), print per-job + grand total. Run this FIRST.
  --mode run      : start each job (stable idempotency key), poll, download, parse binding_confidence,
                    compute metrics -> results/boltz_tier1_result.json.

Uses the `boltz-api` CLI (must be on PATH; BOLTZ_API_KEY set). model = boltz-2.1.
"""
import json, os, re, shutil, subprocess, sys, time, concurrent.futures as cf
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOLTZ = os.environ.get("BOLTZ_BIN", "boltz-api")
MODEL = "boltz-2.1"
RUNROOT = REPO / "results" / "boltz_tier1_runs"
SB = ["predictions:structure-and-binding"]


def sanitize(s): return re.sub(r"[^A-Za-z0-9_.-]", "-", str(s))[:48]


def read_seq(path: Path) -> str:
    lines = [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.startswith(">")]
    return "".join(lines)


def sb_input(prot_seq, smiles):
    return json.dumps({
        "entities": [
            {"type": "protein", "chain_ids": ["A"], "value": prot_seq},
            {"type": "ligand_smiles", "chain_ids": ["B"], "value": smiles},
        ],
        "binding": {"type": "ligand_protein_binding", "binder_chain_id": "B"},
        "num_samples": 1,
    })


def build_jobs():
    jobs = []
    cm = json.loads((REPO / "aws/crossmodal_panels.json").read_text())["nav18"]
    nav_seq = cm["protein_seq"]
    for c in cm["compounds"]:
        d = c.get("drug") or c.get("name")
        jobs.append({"q": "Q1", "name": f"q1-nav18-{sanitize(d)}", "label": c["label"],
                     "prot": nav_seq, "smiles": c["smiles"], "drug": d, "target": "Nav1.8"})
    sel = json.loads((REPO / "docs/boltz_handoff/data/04_suzetrigine_selectivity.json").read_text())
    for e in sel:
        tgt = e.get("target")
        jobs.append({"q": "Q2", "name": f"q2-sel-{sanitize(tgt)}", "label": e.get("label"),
                     "prot": e["protein_seq"], "smiles": e["smiles"], "drug": "suzetrigine", "target": tgt})
    tsc = json.loads((REPO / "aws/tsc2_deconv_panel.json").read_text())
    seqs = {"PKM2": read_seq(REPO / "results/aws_eval/boltz_pkm2_ppard/scripts/seq_P14618.txt"),
            "PPARD": read_seq(REPO / "results/aws_eval/boltz_pkm2_ppard/scripts/seq_Q03181.txt")}
    for c in tsc["compounds"]:
        for tgt in ("PKM2", "PPARD"):
            jobs.append({"q": "Q3", "name": f"q3-tsc2-{sanitize(c['qs_id'])}-{tgt}",
                         "prot": seqs[tgt], "smiles": c["smiles"], "drug": c.get("name") or c["qs_id"],
                         "target": tgt, "true_bind": c.get(f"binds_{tgt}")})
    return jobs


def cli_json(args, timeout=120):
    p = subprocess.run([BOLTZ] + args + ["--format", "json"], capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or "").strip()
    try:
        return json.loads(out), p.returncode, (p.stderr or "")[-400:]
    except Exception:
        return None, p.returncode, ((p.stderr or "") + out)[-400:]


def estimate(jobs):
    total = 0.0; rows = []
    for j in jobs:
        d, rc, err = cli_json(SB + ["estimate-cost", "--model", MODEL,
                                    "--idempotency-key", f"tier1-{j['name']}", "--input", sb_input(j["prot"], j["smiles"])])
        cost = float(d["estimated_cost_usd"]) if d and d.get("estimated_cost_usd") is not None else None
        if cost is not None: total += cost
        rows.append((j["name"], cost, err if cost is None else ""))
        print(f"  {j['name']:34s} ${cost if cost is not None else '??'}  {rows[-1][2]}")
    print(f"\n=== Q-counts: Q1={sum(1 for j in jobs if j['q']=='Q1')} Q2={sum(1 for j in jobs if j['q']=='Q2')} Q3={sum(1 for j in jobs if j['q']=='Q3')} ; {len(jobs)} jobs ===")
    print(f"=== ESTIMATED TOTAL: ${total:.4f} ===")
    return total


def run_one(j):
    rundir = RUNROOT / j["name"]
    mpath = rundir / "outputs/files/prediction/metrics.json"
    rc, err, metrics = 1, "", {}
    for attempt in range(3):  # transient 402 / cold billing-check on first POST -> retry
        shutil.rmtree(rundir, ignore_errors=True)  # clear stale dir; idempotency key reuses the server job (no re-fold/re-bill)
        d, rc, err = cli_json(SB + ["run", "--model", MODEL, "--idempotency-key", f"tier1-{j['name']}",
                                    "--input", sb_input(j["prot"], j["smiles"]),
                                    "--root-dir", str(RUNROOT), "--name", j["name"],
                                    "--poll-interval-seconds", "10"], timeout=5400)
        if mpath.is_file():
            try: metrics = json.loads(mpath.read_text())
            except Exception: metrics = {}
            if metrics: break
        if attempt < 2:
            time.sleep(10 + attempt * 10)   # back off, then retry (idempotency key dedupes successes)
    return {**j, "rc": rc, "metrics": metrics, "err": "" if metrics else err}


def auroc(labels, scores):
    pos = [s for s, l in zip(scores, labels) if l == 1 and s is not None]
    neg = [s for s, l in zip(scores, labels) if l == 0 and s is not None]
    if not pos or not neg: return None
    n = c = 0
    for p in pos:
        for q in neg:
            n += 1; c += 1 if p > q else (0.5 if p == q else 0)
    return round(c / n, 4)


def run(jobs):
    RUNROOT.mkdir(parents=True, exist_ok=True)
    results = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(run_one, jobs):
            bc = r["metrics"].get("binding_metrics",{}).get("binding_confidence")
            print(f"  {r['name']:34s} rc={r['rc']} binding_confidence={bc} {r['err'][:80]}")
            results.append(r)
    def bc(r): return r["metrics"].get("binding_metrics",{}).get("binding_confidence")
    out = {"model": MODEL, "n_jobs": len(results), "results": [
        {k: r[k] for k in ("q", "name", "drug", "target", "label", "true_bind") if k in r} | {"binding_confidence": bc(r), "metrics": r["metrics"]}
        for r in results]}
    q1 = [r for r in results if r["q"] == "Q1"]
    out["Q1_nav18_binder_auroc"] = auroc([r["label"] for r in q1], [bc(r) for r in q1])
    q2 = sorted([r for r in results if r["q"] == "Q2" and bc(r) is not None], key=lambda r: -bc(r))
    out["Q2_selectivity_ranking"] = [(r["target"], bc(r)) for r in q2]
    out["Q2_nav18_rank"] = next((i + 1 for i, r in enumerate(q2) if "1.8" in str(r["target"]) or r["target"] == "Nav1.8"), None)
    q3 = {}
    for r in (r for r in results if r["q"] == "Q3"):
        q3.setdefault(r["drug"], {})[r["target"]] = bc(r)
    out["Q3_tsc2_deconvolution"] = q3
    (REPO / "results/boltz_tier1_result.json").write_text(json.dumps(out, indent=2))
    print("\n=== Q1 Nav1.8 binder AUROC:", out["Q1_nav18_binder_auroc"], "(vs fine-tune 0.987 / BALM ~0.86)")
    print("=== Q2 Nav1.8 selectivity rank:", out["Q2_nav18_rank"], "of 9 |", out["Q2_selectivity_ranking"][:3], "...")
    print("=== Q3 TSC2 deconvolution (drug -> {PKM2,PPARD} binding_confidence):")
    for drug, tt in out["Q3_tsc2_deconvolution"].items(): print("   ", drug, tt)
    print("=== wrote results/boltz_tier1_result.json ===")


if __name__ == "__main__":
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "estimate"
    jobs = build_jobs()
    if "--qs" in sys.argv:
        keep = set(sys.argv[sys.argv.index("--qs") + 1].split(","))
        jobs = [j for j in jobs if j["q"] in keep]
    print(f"built {len(jobs)} jobs ; mode={mode}\n")
    (estimate if mode == "estimate" else run)(jobs)
