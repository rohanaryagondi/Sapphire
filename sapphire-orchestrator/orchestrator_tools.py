#!/usr/bin/env python3
"""
orchestrator_tools.py — CLI data tools for the Sapphire LLM-orchestrator agent.

Each subcommand prints JSON to stdout and NEVER raises — returns an honest error
JSON envelope instead.  Public identifiers only ever leave to external APIs.

Usage:
    python orchestrator_tools.py moat  --gene TSC2 [--direction opposite|similar] [--k N]
    python orchestrator_tools.py emet  --gene TSC2
    python orchestrator_tools.py boltz --protein <SEQ> --ligand <SMILES>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ── path setup ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# ── subcommand: moat ─────────────────────────────────────────────────────────

def cmd_moat(args) -> dict:
    """Query the Quiver internal moat for rescue / similar genes."""
    gene = (args.gene or "").strip().upper()
    direction = args.direction  # "opposite" (rescuers) or "similar"
    k = int(args.k)

    try:
        from moat.client import MoatClient  # noqa: PLC0415

        client = MoatClient()   # honours SAPPHIRE_MOAT_DB or default path
        avail = client.available()

        if not avail:
            return {
                "gene": gene,
                "available": False,
                "rescuers": [],
                "similar": [],
                "note": "moat DB unavailable — honest abstain; SAPPHIRE_MOAT_DB not set or file absent",
                "provenance": "moat-real",
            }

        # Rescuers = genes whose KD opposes the perturbation's EP-signature
        rescuers_raw = client.neighbors(gene, effect=direction, ref_type="gene", k=k)

        # Also fetch similar genes for context (always, regardless of direction flag)
        similar_raw = client.neighbors(gene, effect="similar", ref_type="gene", k=5)

        rescuers = [
            {
                "gene": r["ref"],
                "rank": r["rank"],
                "cosine": round(float(r["cosine"]), 4),
            }
            for r in rescuers_raw
        ]
        similar = [
            {
                "gene": r["ref"],
                "rank": r["rank"],
                "cosine": round(float(r["cosine"]), 4),
            }
            for r in similar_raw
        ]

        return {
            "gene": gene,
            "available": True,
            "direction": direction,
            "rescuers": rescuers,
            "similar": similar,
            "provenance": "moat-real",
        }

    except Exception as exc:
        return {
            "gene": gene,
            "available": False,
            "rescuers": [],
            "similar": [],
            "error": str(exc),
            "provenance": "moat-real",
        }


# ── subcommand: emet ─────────────────────────────────────────────────────────

def _rescue_evidence_for_gene(gene: str) -> list:
    """A gene's curated evidence inside any captured <target>_rescue dossier.

    The rescue dossiers (e.g. TSC2_rescue) carry `candidates` [{gene, moat_rank}] + `evidence`
    [{claim, id_or_url}] where each claim begins with the gene name. Returns the matching
    [{claim, source, id_or_url}] for `gene`, or []. Never raises.
    """
    g = (gene or "").strip().upper()
    if not g:
        return []
    try:
        from emet.envelopes import load_envelopes  # noqa: PLC0415
        out = []
        for cand, env in (load_envelopes() or {}).items():
            if not str(cand).endswith("_rescue"):
                continue
            cgenes = {str(c.get("gene", "")).upper() for c in env.get("candidates", []) or []}
            if g not in cgenes:
                continue
            for e in env.get("evidence", []) or []:
                claim = str(e.get("claim", ""))
                if claim.upper().startswith(g):
                    out.append({
                        "claim": claim,
                        "source": e.get("id_or_url") or e.get("source", ""),
                        "id_or_url": e.get("id_or_url", ""),
                    })
        return out
    except Exception:
        return []


def _emet_live_queue(gene: str, query, timeout_s: int = 150) -> dict:
    """Live EMET via the persistent Chrome-Claude worker: drop a task on the file queue
    (RohanOnly/emet_queue/tasks/) and poll for the worker's result (results/<id>.json).

    The worker (skill: emet-chrome-worker) runs the BenchSci query in the user's AUTHENTICATED
    Chrome and writes back the envelope. Honest-degrades to found:False if no worker responds.
    """
    import time as _time  # noqa: PLC0415
    g = (gene or "").strip()
    try:
        root = Path(__file__).resolve().parents[1]
        qroot = Path(os.environ.get("SAPPHIRE_EMET_QUEUE", str(root / "RohanOnly" / "emet_queue")))
        tasks = qroot / "tasks"
        results = qroot / "results"
        tasks.mkdir(parents=True, exist_ok=True)
        results.mkdir(parents=True, exist_ok=True)
        tid = f"{g}_{int(_time.time() * 1000)}"
        task = {
            "id": tid, "candidate": g,
            "query": query or f"Evidence that {g} reverses/rescues the TSC2-KO (mTORC1-hyperactivation) phenotype — cite PMIDs.",
            "created": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        }
        (tasks / f"{tid}.json").write_text(json.dumps(task), encoding="utf-8")
        rfile = results / f"{tid}.json"
        deadline = _time.time() + timeout_s
        while _time.time() < deadline:
            if rfile.exists():
                env = json.loads(rfile.read_text(encoding="utf-8"))
                return {
                    "gene": g, "found": True,
                    "evidence": env.get("evidence", []),
                    "provenance": "emet-live",
                    "source": "live Chrome-Claude worker",
                    "captured_at": env.get("captured_at"),
                }
            _time.sleep(2)
        return {
            "gene": g, "found": False, "evidence": [],
            "note": "no live EMET worker responded within timeout — start the Chrome-Claude worker (skill: emet-chrome-worker).",
        }
    except Exception as exc:
        return {"gene": g, "found": False, "evidence": [], "error": str(exc)}


def cmd_emet(args) -> dict:
    """Load the pre-captured EMET envelope for a gene (public PMIDs)."""
    gene = (args.gene or "").strip()

    try:
        from emet.envelopes import load_envelope_for  # noqa: PLC0415

        env = load_envelope_for(gene)
        if env is not None:
            return {
                "gene": gene,
                "found": True,
                "candidate": env.get("candidate", gene),
                "verdict": env.get("verdict"),
                "evidence": env.get("evidence", []),   # each has claim + id_or_url
                "notes": env.get("notes", ""),
                "captured_at": env.get("captured_at"),
                "provenance": env.get("provenance", "emet-live"),
            }

        # Gene-specific evidence captured INSIDE a <target>_rescue dossier (the curated rescue-gene
        # literature): so `emet --gene DCTN6` surfaces DCTN6's evidence from the TSC2_rescue envelope
        # instead of abstaining (and the orchestrator no longer needs to fall back to live PubMed).
        rescue_ev = _rescue_evidence_for_gene(gene)
        if rescue_ev:
            return {
                "gene": gene,
                "found": True,
                "evidence": rescue_ev,
                "provenance": "emet-live",
                "source": "rescue-dossier (captured)",
            }

        # Live EMET via the persistent Chrome-Claude worker (opt-in: --live). Drops a task on the
        # file queue and waits for the worker to run the BenchSci query in the authenticated browser.
        if getattr(args, "live", False):
            return _emet_live_queue(gene, getattr(args, "query", None))

        return {
            "gene": gene,
            "found": False,
            "evidence": [],
            "note": (
                f"No captured EMET evidence for '{gene}' — EMET abstains honestly. "
                "Pass --live (with the Chrome-Claude worker running) for a live BenchSci query."
            ),
        }

    except Exception as exc:
        return {
            "gene": gene,
            "found": False,
            "evidence": [],
            "error": str(exc),
        }


# ── subcommand: boltz ────────────────────────────────────────────────────────

def cmd_boltz(args) -> dict:
    """Run a Boltz structure+binding prediction. ~$0.02, ~80 s. REAL — opt-in only."""
    if not os.environ.get("BOLTZ_API_KEY"):
        return {
            "status": "not_run",
            "reason": (
                "BOLTZ_API_KEY not set — Boltz enrichment skipped. "
                "Set $BOLTZ_API_KEY to opt in (~$0.02, ~80 s)."
            ),
            "binding_confidence": None,
            "provenance": "boltz",
        }

    try:
        from tools.boltz_seam import findings  # noqa: PLC0415

        result = findings(protein=args.protein, ligand=args.ligand)
        return result

    except ImportError:
        return {
            "status": "not_run",
            "reason": "boltz_seam not importable in this environment — honest abstain.",
            "binding_confidence": None,
            "provenance": "boltz",
        }
    except Exception as exc:
        return {
            "status": "error",
            "reason": str(exc),
            "binding_confidence": None,
            "provenance": "boltz",
        }


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Sapphire orchestrator data tools — each prints JSON to stdout."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("moat", help="Query the Quiver internal moat DB")
    m.add_argument("--gene", required=True, help="Gene symbol to query (e.g. TSC2)")
    m.add_argument(
        "--direction",
        default="opposite",
        choices=["opposite", "similar"],
        help="'opposite' = rescue direction (default); 'similar' = EP-signature mimics",
    )
    m.add_argument("--k", type=int, default=10, help="Max rows to return (default 10)")

    e = sub.add_parser("emet", help="Load captured EMET evidence (envelope or rescue-dossier); --live queues a Chrome-worker task")
    e.add_argument("--gene", required=True, help="Gene symbol to look up (e.g. TSC2)")
    e.add_argument("--live", action="store_true",
                   help="If no captured evidence, queue a live EMET task for the Chrome-Claude worker")
    e.add_argument("--query", default=None, help="EMET query text (for --live)")

    b = sub.add_parser(
        "boltz", help="Run Boltz structure/binding (REAL, ~$0.02, ~80 s)"
    )
    b.add_argument("--protein", required=True, help="Protein sequence (public identifier)")
    b.add_argument("--ligand", required=True, help="Ligand SMILES (public identifier)")

    args = ap.parse_args()
    dispatch = {"moat": cmd_moat, "emet": cmd_emet, "boltz": cmd_boltz}
    result = dispatch[args.cmd](args)
    print(json.dumps(result, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
