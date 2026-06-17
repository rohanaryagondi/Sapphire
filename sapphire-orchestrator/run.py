#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI for the Sapphire Orchestrator — the bucket-facing layer, observable.

    python run.py                      # list shipped scenarios
    python run.py nav1_8               # full end-to-end run (plan -> dossier -> roundtable -> synthesis)
    python run.py tsc2
    python run.py "rank Nav1.8 pain targets for a systemic program"   # free-text -> routed
    python run.py --json nav1_8        # raw canonical run object (what the site Console consumes)

Runs fully offline at $0. The control flow / dossier / roundtable / synthesis logic is real;
facts + persona verdicts come from the captured scenario evidence (live EMET + Q-Models + persona
runs). See orchestrator.py for the live-agent seams.
"""
from __future__ import annotations

import json
import sys

from orchestrator import ENGINE, SCENARIOS

# ---- tiny ANSI helpers (no deps) ----
def _supports_color() -> bool:
    return sys.stdout.isatty()

C = {"b": "\033[1m", "dim": "\033[2m", "cy": "\033[36m", "ye": "\033[33m",
     "gr": "\033[32m", "rd": "\033[31m", "mg": "\033[35m", "x": "\033[0m"} if _supports_color() \
    else {k: "" for k in ("b", "dim", "cy", "ye", "gr", "rd", "mg", "x")}


def rule(label=""):
    line = "=" * 78
    return f"{C['dim']}{line}{C['x']}" + (f"\n{C['b']}{label}{C['x']}" if label else "")


def conv_dots(n):
    return C["ye"] + "●" * n + C["dim"] + "○" * (5 - n) + C["x"]


def print_run(run: dict):
    # plan-only result?
    if "plan" in run and "discover" not in run:
        print(rule("ENGAGEMENT PLAN (planner only — no shipped scenario matched)"))
        _print_plan(run["plan"])
        print(f"\n{C['ye']}note:{C['x']} {run['note']}")
        return

    print(rule(f"SAPPHIRE ORCHESTRATOR · {run['title']}"))
    print(f"{C['cy']}QUERY{C['x']}  {run['query']}")
    print(f"{C['mg']}↳{C['x']} {run['headline']}\n")

    # 0. PLAN
    print(rule("0 · ENGAGEMENT PLAN  (Engagement Lead)"))
    _print_plan(run["plan"])

    # 1. DISCOVER / Bucket 1 dossier
    d = run["discover"]
    print("\n" + rule("1 · DISCOVER → FACT DOSSIER  (Bucket 1 · Research Manager)"))
    print(f"{C['dim']}source:{C['x']} {d['source']}")
    print(f"{d['summary']}\n{C['b']}→ {d['result']}{C['x']}\n")
    print(f"{C['dim']}dossier (field · tier · source):{C['x']}")
    for f in d["dossier"]:
        flag = f.get("flag", "")
        ftag = {"VETO": C["rd"] + " ⛔VETO" + C["x"], "DIVERGENCE": C["mg"] + " ⚡DIVERGENCE" + C["x"],
                "KNOWN_UNKNOWN": C["ye"] + " ?UNKNOWN" + C["x"]}.get(flag, "")
        print(f"  {C['b']}{f['field']}{C['x']} [{f.get('tier','-')}]{ftag}\n      {f['value']}  {C['dim']}({f.get('source','-')}){C['x']}")
    fl = d["flags"]
    print(f"\n{C['dim']}STATUS:{C['x']} {d['status']}")
    if fl["VETO"]:
        print(f"{C['rd']}⛔ VETO gates:{C['x']} " + " | ".join(fl["VETO"]))
    if fl["DIVERGENCE"]:
        print(f"{C['mg']}⚡ DIVERGENCE (surfaced, not reconciled):{C['x']} " + " | ".join(fl["DIVERGENCE"]))
    if fl["KNOWN_UNKNOWNS"]:
        print(f"{C['ye']}? KNOWN UNKNOWNS:{C['x']} " + " | ".join(fl["KNOWN_UNKNOWNS"]))

    # 2. VALIDATE
    v = run["validate"]
    print("\n" + rule("2 · VALIDATE  (Q-Models — " + ("MOCK" if v.get("mock") else "live") + ")"))
    for r in v["runs"]:
        print(f"  {C['cy']}{r['model']:<28}{C['x']} {r['out']}")
    print(f"{C['b']}→ {v['result']}{C['x']}")

    # 3. CONSULT / Bucket 2
    c = run["consult"]
    print("\n" + rule("3 · CONSULT → ROUNDTABLE  (Bucket 2 · Moderator)"))
    print(f"{C['dim']}Round 1 — independent verdicts:{C['x']}")
    for p in c["round1"]:
        print(f"  {conv_dots(p['conviction'])} {C['b']}{p['persona']}{C['x']} {C['dim']}({p['lens']}·{p['stance']}){C['x']}")
        print(f"      “{p['headline']}”")
        print(f"      {C['dim']}risk:{C['x']} {p['top_risk']}")
        print(f"      {C['dim']}ask:{C['x']}  {p['ask']}")
    if c["round2"]:
        print(f"\n{C['dim']}Round 2 — moderated rebuttal:{C['x']}")
        for r in c["round2"]:
            moved = (C["ye"] + "↻ revised" + C["x"]) if r.get("revised") else (C["dim"] + "held" + C["x"])
            print(f"  {conv_dots(r['conviction'])} {C['b']}{r['persona'].split(',')[0]}{C['x']} [{moved}] {r['shift']}")
    s = c["spread"]
    print(f"\n{C['dim']}SPREAD:{C['x']} conviction {s['conviction_range']} · stances {s['stance_mix']}")
    print(f"  {C['b']}convergent gate:{C['x']} {s['convergent_gate']}")
    print(f"  {C['dim']}consensus:{C['x']} {s['consensus']}")
    print(f"  {C['dim']}dissent:{C['x']} {s['dissent']}")

    # 4. SYNTHESIZE
    sy = run["synthesize"]
    print("\n" + rule("4 · SYNTHESIZE  (Engagement Lead)"))
    print(f"{C['b']}{C['gr']}RECOMMENDATION:{C['x']} {sy['recommendation']}")
    print(f"{C['dim']}confidence:{C['x']} {sy['confidence']}")
    print(f"{C['dim']}proposed experiment:{C['x']} {sy['proposed_experiment']}")
    print(rule())


def _print_plan(p: dict):
    print(f"  {C['dim']}deliverable:{C['x']} {p['deliverable']}   {C['dim']}type:{C['x']} {p['type']}")
    print(f"  {C['dim']}disease:{C['x']} {p['disease']}   {C['dim']}modality:{C['x']} {p['modality']}")
    print(f"  {C['dim']}dossier required:{C['x']} {', '.join(p['required_fields'])}")
    print(f"  {C['dim']}dossier skipped:{C['x']}  {', '.join(p['skip_fields']) or '—'}")
    print(f"  {C['dim']}agents activated:{C['x']}")
    for a in p["agents"]:
        print(f"      • {C['b']}{a['name']}{C['x']} — {a['why']}")
    print(f"  {C['dim']}panel seated:{C['x']}")
    for s in p["panel"]:
        wh = "" if s["why"] in s["persona"] else f" {C['dim']}({s['why']}){C['x']}"
        print(f"      • [{s['lens']}] {s['persona']}{wh}")


def main(argv) -> int:
    as_json = False
    args = [a for a in argv if a != "--json"]
    if "--json" in argv:
        as_json = True

    if not args:
        print("Shipped scenarios:")
        for sid in SCENARIOS:
            print(f"  {sid}")
        print('\nUsage: python run.py <scenario|"free text query"> [--json]')
        return 0

    arg = " ".join(args)
    run = ENGINE.run(arg) if arg in SCENARIOS else ENGINE.run_query(arg)

    if as_json:
        print(json.dumps(run, ensure_ascii=False, indent=2))
    else:
        print_run(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
