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

def _quiver_predictions(gene: str) -> list:
    """Quiver's CURATED rescue predictions for <gene>, from the <gene>_rescue dossier `candidates`
    (each {gene, moat_rank}). Returns [{gene, rank, cosine, curated}] or []. These are the validated
    predictions that align with the captured EMET evidence — preferred over the raw moat top for the
    rescue direction so the orchestrator ranks the validated set. Never raises."""
    try:
        from emet.envelopes import load_envelope_for  # noqa: PLC0415
        env = load_envelope_for(f"{gene}_rescue")
        out = []
        for c in (env or {}).get("candidates", []) or []:
            g = c.get("gene")
            if g:
                out.append({"gene": g, "rank": c.get("moat_rank"), "cosine": None, "curated": True})
        return out
    except Exception:
        return []


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

        # For the rescue direction, PREFER Quiver's curated validated predictions (the <gene>_rescue
        # dossier) over the raw moat top — these align with the captured EMET evidence, so the
        # orchestrator ranks the validated set and its per-gene EMET lookups hit the captured dossier.
        curated = _quiver_predictions(gene) if direction == "opposite" else []
        if curated:
            rescuers = curated

        return {
            "gene": gene,
            "available": True,
            "direction": direction,
            "rescuers": rescuers,
            "similar": similar,
            "curated_predictions": bool(curated),
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

def _load_boltz_pairs() -> dict:
    """Known gene → (public protein sequence + ligand SMILES) pairs for the demo (real public IDs,
    captured from UniProt/PubChem). Lets the orchestrator call Boltz with just `--gene G --ligand DRUG`."""
    try:
        p = Path(__file__).resolve().parent / "scenarios" / "boltz_pairs.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def cmd_boltz(args) -> dict:
    """Boltz-2 structure + binding prediction (REAL, ~$0.02, ~80 s). Resolve `--gene G --ligand DRUG`
    to a public sequence + SMILES (scenarios/boltz_pairs.json), or take raw `--protein SEQ --ligand SMILES`.
    The API key is read from RohanOnly/boltz_api.env by the seam — no env var needed. Honest-degrades."""
    gene = (getattr(args, "gene", "") or "").strip().upper()
    ligand = (getattr(args, "ligand", "") or "").strip()
    protein = (getattr(args, "protein", "") or "").strip()
    ligand_smiles = None

    if gene and not protein:
        rec = _load_boltz_pairs().get(gene)
        if not rec:
            return {"status": "not_run", "gene": gene, "provenance": "boltz",
                    "reason": f"No embedded public sequence for {gene} — supply --protein <seq> --ligand <SMILES>."}
        protein = rec.get("target_sequence", "")
        ligands = {k.lower(): v for k, v in (rec.get("ligands") or {}).items()}
        ligand_smiles = ligands.get(ligand.lower()) or (ligand or None)  # known drug name → SMILES, else raw
    elif ligand:
        ligand_smiles = ligand  # raw SMILES alongside a raw --protein

    if not protein:
        return {"status": "not_run", "provenance": "boltz",
                "reason": "No protein sequence — supply --gene <known gene> or --protein <sequence>."}

    try:
        from tools.boltz_seam import findings  # noqa: PLC0415
        inputs = {"candidate": gene or "target", "target_sequence": protein}
        if ligand_smiles:
            inputs["ligand_smiles"] = ligand_smiles
        return findings(inputs)   # reads the key from RohanOnly/boltz_api.env; honest KNOWN_UNKNOWN on failure
    except ImportError:
        return {"status": "not_run", "provenance": "boltz", "reason": "boltz_seam not importable."}
    except Exception as exc:
        return {"status": "error", "provenance": "boltz", "reason": str(exc)}


def cmd_qmodels(args) -> dict:
    """Call a Q-Model via the launchpad client. REAL for live-local tools when the local Explorer
    endpoint is up; honest-degrades (not reachable / GPU not launched / deprecated) otherwise."""
    tool_id = (getattr(args, "tool", "") or "").strip()
    try:
        inputs = json.loads(args.inputs) if getattr(args, "inputs", None) else {}
    except Exception:
        inputs = {}
    # SAFETY: default GPU launcher OFF for the demo so a qmodels call can NEVER launch AWS — GPU
    # tools then return an honest "gpu-disabled (gated)" instead of even a dry-run job. Explicit
    # QMODELS_GPU=on still opts in. (Set before the import: client.py reads QMODELS_GPU at import.)
    os.environ.setdefault("QMODELS_GPU", "off")
    try:
        from qmodels.client import QModelsClient  # noqa: PLC0415
        return QModelsClient().call(tool_id, inputs)
    except Exception as exc:
        return {"ok": False, "tool_id": tool_id, "provenance": "unavailable", "error": str(exc)}


# ── subcommand: catalog (tool/model discovery) ───────────────────────────────

def cmd_catalog(args) -> dict:
    """List EVERY tool + Q-Model the orchestrator can call, so it can DISCOVER and pick the right
    one for any question (this is what makes it flexible — e.g. map 'use ESM' → esm2). Honest about
    what's runnable now vs gated."""
    core = [
        {"tool": "moat", "purpose": "Quiver internal moat — rescue (opposite) / similar genes for a target; curated predictions where available.", "call": "moat --gene G --direction opposite|similar [--k N]"},
        {"tool": "emet", "purpose": "Captured BenchSci literature (real PMIDs) for a gene; --live queues a Chrome-worker BenchSci query.", "call": "emet --gene G [--live]"},
        {"tool": "boltz", "purpose": "Boltz-2 structure + binding / druggability for a gene+ligand (REAL, ~80s, ~$0.02).", "call": "boltz --gene G --ligand DRUG"},
        {"tool": "qmodels", "purpose": "Call a Q-Model from the catalog below by id.", "call": "qmodels --tool ID --inputs '<json>'"},
        {"tool": "catalog", "purpose": "This list — discover available tools + models.", "call": "catalog"},
    ]
    models = []
    try:
        reg = json.loads((Path(__file__).resolve().parent / "qmodels" / "registry.json").read_text(encoding="utf-8"))
        for m in reg.get("models", []):
            st = str(m.get("status", "")); tier = str(m.get("tier", ""))
            runs_now = st in ("live-local", "live")
            note = ("runs now (local-cpu)" if st == "live-local" else
                    "runs now" if st == "live" else
                    "GPU — gated off by default (set QMODELS_GPU=on + run the launcher to enable)"
                    if (tier.startswith("gpu") or st == "gpu-unproven") else
                    f"{st} — not callable")
            models.append({"id": m.get("id"), "name": m.get("name"), "task": m.get("task"),
                           "status": st, "inputs": m.get("inputs", []), "outputs": m.get("outputs", []),
                           "runnable_now": runs_now, "note": note})
    except Exception as exc:
        models = [{"error": str(exc)}]
    return {"tools": core, "qmodels": models,
            "hint": ("For an embedding / nearest-gene question, esm2 (task=embedding, outputs embedding+nn_recall) "
                     "is the model — currently GPU-gated. live-local/live models run now; GPU models are gated for "
                     "safety. If a needed model is gated, call it anyway and report HONESTLY that it's gated — never fabricate its output.")}


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
        "boltz", help="Boltz structure/binding (REAL, ~$0.02, ~80 s): --gene G --ligand DRUG | --protein SEQ --ligand SMILES"
    )
    b.add_argument("--gene", default="", help="Gene with a known public sequence (e.g. BCL2) — resolves protein + ligand")
    b.add_argument("--protein", default="", help="Raw protein sequence (public) — alternative to --gene")
    b.add_argument("--ligand", default="", help="Ligand: a known drug name (e.g. venetoclax) or a raw SMILES")

    q = sub.add_parser("qmodels", help="Call a Q-Model via the launchpad (real for live-local; honest-degrades)")
    q.add_argument("--tool", required=True, help="Q-Model tool id (e.g. chemberta2, boltz2, esm2)")
    q.add_argument("--inputs", default="", help="JSON inputs for the tool")

    sub.add_parser("catalog", help="List all tools + Q-Models (discover what's available + what's runnable)")

    args = ap.parse_args()
    dispatch = {"moat": cmd_moat, "emet": cmd_emet, "boltz": cmd_boltz,
                "qmodels": cmd_qmodels, "catalog": cmd_catalog}
    result = dispatch[args.cmd](args)
    print(json.dumps(result, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
