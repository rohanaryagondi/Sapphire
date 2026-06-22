"""
_build/loop_and_trace_demo.py — Sapphire self-improvement loop end-to-end demo.

Exercises:
  1. Harnessed-trace: run_live("Is TSC2 a viable target in tuberous sclerosis?")
     with offline mock backends ($0) — writes real trace to RohanOnly/engagements/<eid>/trace.jsonl
     and renders to docs/sample-trace.txt.
  2. Loop accumulation: three run_engagement() calls (nav1_8, tsc2, lrrk2_pd).
  3. Recall demo: recall by gene (LRRK2) and disease (Parkinson's disease).
  4. Active-learning: record_outcome on a refuted proposal → opens moat_blindspot;
     record_outcome on a confirmed proposal.
  5. Metrics: write_report() → selfimprove/REPORT.md.
  6. Summary print.

Run from repo root:
    cd sapphire-orchestrator && PYTHONPATH=. python3 ../_build/loop_and_trace_demo.py
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

# ── resolve the sapphire-orchestrator package root ────────────────────────────
_SCRIPT = Path(__file__).resolve()
_REPO_ROOT = _SCRIPT.parents[1]
_ORCH = _REPO_ROOT / "sapphire-orchestrator"
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))

# ── imports ───────────────────────────────────────────────────────────────────
from live_engine import run_live
from engagement import run_engagement
from trace_view import render
from memory import recall, record_outcome, read_all
from selfimprove.metrics import write_report


# ── offline mock ctx (mirrors test_live_engine._build_ctx exactly) ────────────

def _fake_claude_runner(cmd):
    schema_str = ""
    for i, tok in enumerate(cmd):
        if tok == "--json-schema" and i + 1 < len(cmd):
            schema_str = cmd[i + 1]
            break
    if '"stance"' in schema_str:
        obj = {
            "persona": "Mock Persona",
            "stance": "conditional",
            "conviction": 3,
            "rationale": "TSC2 loss hyperactivates mTORC1; rapalogues validate the pathway.",
            "fact_claims": [{"claim": "TSC2 loss activates mTOR", "cite": "PMID:11573973"}],
            "provenance": "semantic-web",
        }
    else:
        obj = {
            "candidate": "TSC2",
            "facts": [
                {"value": "TSC2 mutations cause tuberous sclerosis via mTOR hyper-activation",
                 "source": "PMID:11573973", "tier": "T2"},
                {"value": "Everolimus (mTOR inhibitor) approved for TSC-associated tumours",
                 "source": "PMID:24094718", "tier": "T1"},
            ],
            "provenance": "semantic-web",
        }
    stdout = json.dumps({"structured_output": obj})
    return types.SimpleNamespace(stdout=stdout, returncode=0, stderr="")


def _fake_emet_handler(contract, inputs):
    return {
        "candidate": inputs.get("candidate", "TSC2"),
        "facts": [
            {"value": "EMET mock: TSC2 high essentiality in tuberous sclerosis cell lines",
             "source": "PMID:29790870", "tier": "T2"}
        ],
        "provenance": "emet-live",
    }


def _fake_qmodels_client():
    def _call(tool, inp):
        return {"model": tool, "out": "mock ADMET pass", "provenance": "stub"}
    return types.SimpleNamespace(call=_call)


def _build_ctx():
    return {
        "runner": _fake_claude_runner,
        "emet_handler": _fake_emet_handler,
        "qmodels_client": _fake_qmodels_client(),
        # NOTE: do NOT pre-populate python_fns["internal-science-lead"] so that
        # run_live wires the REAL moat backend by default (matches test pattern).
    }


# ── docs output dir ──────────────────────────────────────────────────────────

def _docs_dir() -> Path:
    d = _ORCH / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _selfimprove_report_path() -> Path:
    return _ORCH / "selfimprove" / "REPORT.md"


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Sapphire loop+trace demo — $0 / offline")
    print("=" * 70)

    # ── Step 1: harnessed-trace via run_live ─────────────────────────────────
    print("\n[1/5] run_live (TSC2 query, offline mock backends) …")
    tsc2_query = "Is TSC2 a viable target in tuberous sclerosis?"
    result = run_live(tsc2_query, ctx=_build_ctx())
    eid = result["engagement_id"]
    print(f"      engagement_id = {eid}")
    print(f"      discover agents: {len(result['discover']['agents'])}")
    print(f"      consult round1:  {len(result['consult']['round1'])}")
    print(f"      reflection written: {result['reflection']['written']}")

    # render and save timeline
    rendered = render(eid, full=False)
    trace_out = _docs_dir() / "sample-trace.txt"
    trace_out.write_text(rendered, encoding="utf-8")
    print(f"      → docs/sample-trace.txt written ({len(rendered.splitlines())} lines)")

    # ── Step 2: loop accumulation ─────────────────────────────────────────────
    print("\n[2/5] run_engagement × 3 (nav1_8, tsc2, lrrk2_pd) …")
    for sid in ("nav1_8", "tsc2", "lrrk2_pd"):
        r = run_engagement(sid)
        refl = r.get("reflection") or {}
        print(f"      {sid}: reflection.written={refl.get('written', 0)}")

    # ── Step 3: recall demo ───────────────────────────────────────────────────
    print("\n[3/5] recall demo …")
    lrrk2_priors  = recall({"genes": ["LRRK2"]})
    pd_priors      = recall({"diseases": ["Parkinson's disease"]})
    print(f"      recall(LRRK2):               {len(lrrk2_priors)} record(s), "
          f"types={[r['type'] for r in lrrk2_priors[:3]]}")
    print(f"      recall(Parkinson's disease): {len(pd_priors)} record(s), "
          f"types={[r['type'] for r in pd_priors[:3]]}")

    # ── Step 4: active-learning — find an experiment_proposal ─────────────────
    print("\n[4/5] active-learning (record_outcome) …")
    all_recs = read_all()
    proposals = [r for r in all_recs if r["type"] == "experiment_proposal"]
    print(f"      found {len(proposals)} experiment_proposal record(s)")

    blindspot_opened = False
    if len(proposals) >= 1:
        refuted_proposal = proposals[0]
        print(f"      refuting proposal id={refuted_proposal['id']}")
        record_outcome(
            refuted_proposal["id"],
            {
                "result": "refuted",
                "data": "moat under-detected the lung lysosomal window",
                "source": "wetlab-demo",
            },
        )
        blindspot_opened = True
        print("      → moat_blindspot written ✓")

    if len(proposals) >= 2:
        confirmed_proposal = proposals[1]
        print(f"      confirming proposal id={confirmed_proposal['id']}")
        record_outcome(
            confirmed_proposal["id"],
            {
                "result": "confirmed",
                "data": "mTOR inhibition validated in TSC2-null spheroids",
                "source": "wetlab-demo",
            },
        )
        print("      → experiment_outcome (confirmed) written ✓")

    # ── Step 5: metrics report ─────────────────────────────────────────────────
    print("\n[5/5] write_report() …")
    report_path = _selfimprove_report_path()
    metrics = write_report(path=str(report_path))
    print(f"      → selfimprove/REPORT.md written")
    print(f"      records={metrics['records']}  by_type={dict(sorted(metrics['by_type'].items()))}")
    print(f"      prediction_accuracy={metrics['prediction_accuracy']}  blindspots={metrics['blindspots']}")

    # ── Summary ───────────────────────────────────────────────────────────────
    all_recs_final = read_all()
    by_type: dict = {}
    for r in all_recs_final:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    acc_str = "n/a" if metrics["prediction_accuracy"] is None else f"{metrics['prediction_accuracy']:.0%}"

    print("\n" + "=" * 70)
    print("DEMO SUMMARY")
    print("=" * 70)
    print(f"  Harnessed-trace eid : {eid}")
    print(f"  Memory records total: {metrics['records']}")
    print(f"  Records by type     : {dict(sorted(by_type.items()))}")
    print(f"  recall(LRRK2) hits  : {len(lrrk2_priors)}")
    print(f"  recall(PD) hits     : {len(pd_priors)}")
    print(f"  Blindspot opened    : {'yes' if blindspot_opened else 'no'}")
    print(f"  Prediction accuracy : {acc_str}")
    print(f"  Moat blindspots     : {metrics['blindspots']}")
    print(f"  Sample trace        : {trace_out}")
    print(f"  Metrics report      : {report_path}")
    print("=" * 70)

    return {
        "eid": eid,
        "by_type": by_type,
        "lrrk2_recall": len(lrrk2_priors),
        "pd_recall": len(pd_priors),
        "blindspot_opened": blindspot_opened,
        "metrics": metrics,
    }


if __name__ == "__main__":
    main()
