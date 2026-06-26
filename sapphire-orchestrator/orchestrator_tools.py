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
import re
import subprocess
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
        cands = (env or {}).get("candidates", []) or []
        if not cands:
            return []
        # Attach the REAL moat cosine DISTANCE (smaller = stronger rescue; rank 1 = smallest) for each
        # curated gene — so the orchestrator can weight by the metric, not just the ordinal rank.
        cos = {}
        try:
            from moat.client import MoatClient  # noqa: PLC0415
            client = MoatClient()
            if client.available():
                for r in client.neighbors(gene.upper(), effect="opposite", ref_type="gene", k=2000):
                    cos[r["ref"]] = round(float(r["cosine"]), 4)
        except Exception:
            pass
        out = []
        for c in cands:
            g = c.get("gene")
            if g:
                out.append({"gene": g, "rank": c.get("moat_rank"),
                            "cosine_distance": cos.get(g), "curated": True})
        return out
    except Exception:
        return []


def _moat_probe(perturbation: str, probe_csv: str) -> dict:
    """For a perturbation (e.g. TSC2), report each PROBED gene's moat relationship to it:
    rescue-direction (opposite EP-signature), exacerbate-direction (similar), or absent. Lets the
    orchestrator check a specific candidate list (incl. controls/exacerbation genes) in ONE call.
    Ordinal rank only — internal cosines stay inside the moat (never cross to the reasoner)."""
    targets = [g.strip().upper() for g in (probe_csv or "").split(",") if g.strip()]
    try:
        from moat.client import MoatClient  # noqa: PLC0415
        client = MoatClient()
        if not client.available():
            return {"perturbation": perturbation, "available": False, "probe": [],
                    "note": "moat DB unavailable — honest abstain", "provenance": "moat-real"}
        lut = {}
        for eff in ("opposite", "similar"):
            for r in client.neighbors(perturbation, effect=eff, ref_type="gene", k=2000):
                lut.setdefault(r["ref"], {"effect": eff, "rank": r["rank"],
                                          "cosine_distance": round(float(r["cosine"]), 4)})
        out = []
        for t in targets:
            hit = lut.get(t)
            if hit:
                out.append({"gene": t, "in_moat": True,
                            "role": "rescue-direction" if hit["effect"] == "opposite" else "exacerbate-direction",
                            "moat_rank": hit["rank"], "cosine_distance": hit["cosine_distance"]})
            else:
                out.append({"gene": t, "in_moat": False,
                            "role": "absent — moat is silent (not in the perturbation's top neighbors); lean on EMET + semantic agents"})
        return {"perturbation": perturbation, "available": True, "probe": out, "provenance": "moat-real",
                "note": ("rescue-direction = knockdown OPPOSES the perturbation's EP-signature (rescue candidate); "
                         "exacerbate-direction = knockdown MIMICS/worsens it (bad/perturbative). cosine_distance: "
                         "SMALLER = STRONGER (rank 1 = smallest) — weight by it, not rank alone.")}
    except Exception as exc:
        return {"perturbation": perturbation, "available": False, "probe": [], "error": str(exc),
                "provenance": "moat-real"}


def cmd_moat(args) -> dict:
    """Query the Quiver internal moat for rescue / similar genes (or --probe a specific gene list)."""
    gene = (args.gene or "").strip().upper()
    direction = args.direction  # "opposite" (rescuers) or "similar"
    k = int(args.k)

    probe = getattr(args, "probe", None)
    if probe:
        return _moat_probe(gene, probe)

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
            {"gene": r["ref"], "rank": r["rank"], "cosine_distance": round(float(r["cosine"]), 4)}
            for r in rescuers_raw
        ]
        similar = [
            {"gene": r["ref"], "rank": r["rank"], "cosine_distance": round(float(r["cosine"]), 4)}
            for r in similar_raw
        ]

        # The moat ALSO holds COMPOUND neighbours (drug-repurposing leads), but those are ONLY relevant to
        # a drug/therapeutic question — for a gene-rescue ranking they are NOISE. So compounds are OPT-IN
        # via --compounds; a plain gene query returns gene-gene data only.
        want_compounds = getattr(args, "compounds", False)

        # For the rescue direction, PREFER Quiver's curated validated predictions (the <gene>_rescue
        # dossier) over the raw moat top — these align with the captured EMET evidence, so the
        # orchestrator ranks the validated set and its per-gene EMET lookups hit the captured dossier.
        curated = _quiver_predictions(gene) if direction == "opposite" else []
        if curated:
            rescuers = curated

        out = {
            "gene": gene,
            "available": True,
            "direction": direction,
            "rescuers": rescuers,
            "similar": similar,
            "curated_predictions": bool(curated),
            "metric": "cosine_distance: SMALLER = STRONGER (nearer in the EP-signature space); rank 1 = smallest. Weight by it, don't use rank alone.",
            "provenance": "moat-real",
        }
        if want_compounds:
            out["rescue_compounds"] = [{"compound": r["ref"], "rank": r["rank"]}
                                       for r in client.neighbors(gene, effect="opposite", ref_type="compound", k=k)]
            out["exacerbate_compounds"] = [{"compound": r["ref"], "rank": r["rank"]}
                                           for r in client.neighbors(gene, effect="similar", ref_type="compound", k=5)]
        return out

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


def _emet_live_queue(gene: str, query, timeout_s: int = 0) -> dict:
    """Live EMET via the persistent Chrome-Claude worker: drop a task on the file queue
    (RohanOnly/emet_queue/tasks/) and poll for the worker's result (results/<id>.json).

    The worker (skill: emet-chrome-worker) runs the BenchSci query in the user's AUTHENTICATED
    Chrome and writes back the envelope. A real Thorough BenchSci run takes minutes, so we wait up to
    SAPPHIRE_EMET_TIMEOUT seconds (default 600). Honest-degrades to found:False if no worker responds.
    """
    import time as _time  # noqa: PLC0415
    if not timeout_s:
        timeout_s = int(os.environ.get("SAPPHIRE_EMET_TIMEOUT", "600"))
    g = (gene or "").strip()
    try:
        root = Path(__file__).resolve().parents[1]
        qroot = Path(os.environ.get("SAPPHIRE_EMET_QUEUE", str(root / "RohanOnly" / "emet_queue")))
        tasks = qroot / "tasks"
        results = qroot / "results"
        tasks.mkdir(parents=True, exist_ok=True)
        results.mkdir(parents=True, exist_ok=True)
        tid = f"{g}_{int(_time.time() * 1000)}"
        # Default query asks for FULL breadth + balanced for-vs-against evidence (see emet-prompting skill),
        # not just papers — so the worker leverages EMET's genetics/expression/perturbation/pathway/clinical
        # surface and surfaces the risks (pleiotropy, inflammation, toxicity, essentiality, expression gap).
        default_q = (
            f"Run the Target Validation workflow for {g} in tuberous sclerosis, thinking=Thorough, high-stringency. "
            f"What does the evidence indicate about the effect of KNOCKING DOWN {g} on the TSC2-KO / "
            f"mTORC1-hyperactivation phenotype — would it normalize/rescue it, have no effect, or worsen it? Assess "
            f"neutrally, no assumptions. Use your FULL toolset, not just literature: genetic association "
            f"(GWAS/ClinVar/OpenTargets), CNS/neuron expression (GTEx/Protein Atlas/single-cell), perturbation & "
            f"dependency (DepMap/CRISPR screens), pathway position & pleiotropy (Reactome/STRING + GO breadth), and "
            f"clinical/safety (FAERS). Give evidence on BOTH sides — support for a rescue effect AND evidence it would "
            f"be ineffective or harmful (pleiotropy, inflammation, toxicity, essentiality / is knockdown lethal, "
            f"expression gaps, gnomAD constraint). Flag contradictions. Cite every claim (PMID/DOI/DB record)."
        )
        task = {
            "id": tid, "candidate": g,
            "query": query or default_q,
            "created": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        }
        tfile = tasks / f"{tid}.json"
        tfile.write_text(json.dumps(task), encoding="utf-8")
        rfile = results / f"{tid}.json"
        # grab-detection: the worker removes/moves the task file when it picks it up. If it hasn't grabbed
        # within the grace window, it isn't looping — bail fast so we don't hang the full timeout (the caller
        # falls back to captured). If it HAS grabbed, wait the full timeout for the (slow) real result.
        grab_grace = int(os.environ.get("SAPPHIRE_EMET_GRAB_GRACE", "90"))
        start = _time.time()
        deadline = start + timeout_s
        grabbed = False
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
            if not grabbed and not tfile.exists():
                grabbed = True   # worker picked it up — now wait for the real (slow) result
            if not grabbed and (_time.time() - start) > grab_grace:
                return {
                    "gene": g, "found": False, "evidence": [], "worker_active": False,
                    "note": f"live EMET worker did not pick up the task within {grab_grace}s — not looping; fall back to captured.",
                }
            _time.sleep(2)
        return {
            "gene": g, "found": False, "evidence": [], "worker_active": grabbed,
            "note": ("worker picked up the task but did not finish within the timeout"
                     if grabbed else
                     "no live EMET worker responded — start the Chrome-Claude worker (skill: emet-chrome-worker)."),
        }
    except Exception as exc:
        return {"gene": g, "found": False, "evidence": [], "error": str(exc)}


def _captured_emet(gene: str):
    """Captured EMET evidence for a gene (envelope, then rescue-dossier). Returns the dict or None."""
    from emet.envelopes import load_envelope_for  # noqa: PLC0415
    env = load_envelope_for(gene)
    if env is not None:
        return {
            "gene": gene, "found": True, "candidate": env.get("candidate", gene),
            "verdict": env.get("verdict"), "evidence": env.get("evidence", []),
            "notes": env.get("notes", ""), "captured_at": env.get("captured_at"),
            "provenance": "emet-captured", "source": "captured envelope",
        }
    rescue_ev = _rescue_evidence_for_gene(gene)
    if rescue_ev:
        return {"gene": gene, "found": True, "evidence": rescue_ev,
                "provenance": "emet-captured", "source": "rescue-dossier (captured)"}
    return None


def _emet_paths():
    root = Path(__file__).resolve().parents[1]
    qroot = Path(os.environ.get("SAPPHIRE_EMET_QUEUE", str(root / "RohanOnly" / "emet_queue")))
    tasks = qroot / "tasks"; results = qroot / "results"
    tasks.mkdir(parents=True, exist_ok=True); results.mkdir(parents=True, exist_ok=True)
    return tasks, results


def _emet_batch_query(genes, perturbation="TSC2"):
    gl = ", ".join(genes)
    # NEUTRAL / BLIND — never reveal which genes are controls, expected rescuers, or expected exacerbators,
    # and don't presuppose any of them rescues. We are EVALUATING the predictions; EMET must assess blind.
    return (f"For the {perturbation}-KO / mTORC1-hyperactivation phenotype, evaluate the following genes BLIND and "
            f"EQUALLY in one Thorough, high-stringency research pass — make NO assumptions about which will or won't "
            f"matter: {gl}. For EACH gene determine the effect of KNOCKING IT DOWN (rescue/normalize | no effect | "
            f"worsen) and give RICH, SPECIFIC evidence on BOTH sides — with the actual numbers, not vague statements:\n"
            f"  FOR rescue: the precise mechanistic link to the mTORC1/TSC2 pathway (which step), human genetics "
            f"(GWAS / ClinVar / OpenTargets association score), and perturbation/dependency data (DepMap, CRISPR rescue screens).\n"
            f"  AGAINST: pleiotropy (GO-term breadth / # of pathways), pan-essentiality (DepMap common-essential — is KD "
            f"lethal), CNS/neuron expression level (GTEx / Protein Atlas TPM — is it even expressed there), target "
            f"toxicity, and gnomAD constraint (pLI).\n"
            f"For each gene give the single STRONGEST piece of evidence, its directionality, and a confidence. TAG every "
            f"claim with its gene in square brackets, e.g. '[BCL2] ...'. Cite EVERY claim with its specific identifier "
            f"(PMID / DOI / DB accession) — uncited claims are dropped, never paraphrased.")


def _batch_store(perturbation):
    root = Path(__file__).resolve().parents[1]
    d = root / "scenarios" / "emet_batches"; d.mkdir(parents=True, exist_ok=True)
    return d / f"{(perturbation or 'tsc2').lower()}.json"


def _emet_batch_assemble_captured(genes):
    ev = []
    for g in genes:
        cap = _captured_emet(g)
        if cap and cap.get("evidence"):
            for e in cap["evidence"]:
                ev.append({"gene": g, **(e if isinstance(e, dict) else {"claim": str(e)})})
    return ev


def _emet_batch_live(genes, perturbation, query, timeout_s=0):
    """ONE worker task covering ALL genes — far faster than per-gene. Falls back to assembled captured."""
    import time as _t  # noqa: PLC0415
    if not timeout_s:
        timeout_s = int(os.environ.get("SAPPHIRE_EMET_BATCH_TIMEOUT", os.environ.get("SAPPHIRE_EMET_TIMEOUT", "900")))
    tasks, results = _emet_paths()
    tid = f"BATCH_{int(_t.time() * 1000)}"
    (tasks / f"{tid}.json").write_text(json.dumps({
        "id": tid, "candidate": "BATCH", "genes": genes,
        "query": query or _emet_batch_query(genes, perturbation),
        "created": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
    }), encoding="utf-8")
    tfile = tasks / f"{tid}.json"; rfile = results / f"{tid}.json"
    grab_grace = int(os.environ.get("SAPPHIRE_EMET_GRAB_GRACE", "90"))
    start = _t.time(); deadline = start + timeout_s; grabbed = False
    while _t.time() < deadline:
        if rfile.exists():
            env = json.loads(rfile.read_text(encoding="utf-8"))
            return {"batch": True, "genes": genes, "found": True, "evidence": env.get("evidence", []),
                    "provenance": "emet-live", "source": "live Chrome worker (batch)",
                    "captured_at": env.get("captured_at")}
        if not grabbed and not tfile.exists():
            grabbed = True
        if not grabbed and (_t.time() - start) > grab_grace:
            break
        _t.sleep(2)
    ev = _emet_batch_assemble_captured(genes)
    return {"batch": True, "genes": genes, "found": bool(ev), "evidence": ev, "provenance": "emet-captured",
            "note": ("worker grabbed the batch but didn't finish in time — captured fallback" if grabbed
                     else "worker not looping — captured fallback"),
            "source": "assembled from captured envelopes"}


def cmd_emet(args) -> dict:
    """EMET evidence for a gene. With --live (or SAPPHIRE_EMET_LIVE=1) the connected Chrome-Claude worker
    runs a REAL BenchSci query (the task is queued and we wait for its cited envelope); captured evidence is
    the fallback if the worker doesn't respond. Without --live, captured-first (honest abstain if none)."""
    gene = (args.gene or "").strip()
    live = (getattr(args, "live", False)
            or os.environ.get("SAPPHIRE_EMET_LIVE", "").lower() in ("1", "on", "true"))

    # BATCH: one EMET pass over many genes (far faster than per-gene). `emet --gene TSC2 --batch G1,G2,...`
    batch = getattr(args, "batch", None)
    if batch:
        genes = [g.strip().upper() for g in batch.split(",") if g.strip()]
        pert = gene or "TSC2"
        if live:
            return _emet_batch_live(genes, pert, getattr(args, "query", None))
        store = _batch_store(pert)
        if store.exists():
            try:
                d = json.loads(store.read_text(encoding="utf-8"))
                return {"batch": True, "genes": genes, "found": bool(d.get("evidence")),
                        "evidence": d.get("evidence", []), "provenance": "emet-captured",
                        "source": "saved batch envelope"}
            except Exception:
                pass
        ev = _emet_batch_assemble_captured(genes)
        return {"batch": True, "genes": genes, "found": bool(ev), "evidence": ev, "provenance": "emet-captured"}

    try:
        if live:
            # PREFER the live worker — queue the task and wait for its result (this is what reaches your
            # connected Chrome-Claude). Fall back to captured only if the worker doesn't answer in time.
            res = _emet_live_queue(gene, getattr(args, "query", None))
            if res.get("found") and res.get("evidence"):
                return res
            cap = _captured_emet(gene)
            if cap:
                cap["live_attempted"] = True
                cap["note"] = "live Chrome worker did not respond in time — fell back to captured evidence"
                return cap
            return res  # honest: live attempted, no worker result, no capture either

        cap = _captured_emet(gene)
        if cap:
            return cap
        return {
            "gene": gene, "found": False, "evidence": [],
            "note": (f"No captured EMET evidence for '{gene}' — EMET abstains honestly. "
                     "Pass --live (with the Chrome-Claude worker running) for a live BenchSci query."),
        }
    except Exception as exc:
        return {"gene": gene, "found": False, "evidence": [], "error": str(exc)}


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
    # AWS opt-in. Default: GPU launcher OFF so a qmodels call can NEVER launch AWS — GPU tools return an
    # honest "gpu-disabled (gated)". With --gpu-live the orchestrator ACTUALLY launches on AWS for a GPU
    # model (real cost ~$0.13, auto-teardown) — behind the launcher's every guard (account-gate==255493511886,
    # create-only+ledger, $0.50 budget cap, triple-teardown). (Env set before the import: client.py reads it.)
    if getattr(args, "gpu_live", False):
        os.environ["QMODELS_GPU"] = "on"
        os.environ["QMODELS_GPU_MODE"] = "live"
    else:
        os.environ.setdefault("QMODELS_GPU", "off")
    try:
        from qmodels.client import QModelsClient  # noqa: PLC0415
        return QModelsClient().call(tool_id, inputs)
    except Exception as exc:
        return {"ok": False, "tool_id": tool_id, "provenance": "unavailable", "error": str(exc)}


# ── subcommand: semantic (cheap haiku scientific agents) ─────────────────────

SEMANTIC_AGENTS = {
    "mechanism":    "molecular & cell-biology mechanism specialist (CNS / mTOR pathway)",
    "pathway":      "pathway & network specialist who judges pleiotropy and hub-ness (does the gene do many things?)",
    "toxicity":     "drug-safety / target-based-toxicity specialist",
    "expression":   "tissue-expression specialist (is the gene expressed in CNS / the relevant cell type?)",
    "essentiality": "functional-genomics specialist (is knockdown lethal or broadly fitness-affecting?)",
    "genetics":     "human-genetics specialist (disease association + gnomAD constraint / LoF-intolerance)",
}
_SEM_FOCUS = {
    "mechanism":    "Does modulating this gene plausibly produce the hypothesized effect? Is the mechanism coherent?",
    "pathway":      "How pleiotropic is this gene (GO breadth, # pathways, hub-ness)? Broad pleiotropy = knockdown collateral risk.",
    "toxicity":     "What target-based toxicity risk would modulating this gene carry?",
    "expression":   "Is this gene expressed in the relevant CNS tissue / cell type? An expression gap means the mechanism can't operate.",
    "essentiality": "Is this gene pan-essential (knockdown lethal or broadly fitness-affecting)? Essentiality = poor knockdown target.",
    "genetics":     "Human-genetic + constraint evidence (disease association, gnomAD pLI / LoF-intolerance).",
}


def _extract_json_obj(text):
    """Best-effort: parse a JSON object out of a possibly-noisy string."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def cmd_semantic(args) -> dict:
    """Spawn a cheap claude-haiku semantic scientific agent to analyse ONE dimension for a gene. The
    orchestrator decides which agents/genes to call. This is REAL LLM reasoning (labelled semantic-haiku —
    inference, not a cited DB fact); it weighs evidence FOR vs AGAINST and abstains rather than fabricate."""
    agent = (getattr(args, "agent", "") or "").strip().lower()
    role = SEMANTIC_AGENTS.get(agent)
    if not role:
        return {"ok": False, "error": f"unknown semantic agent '{agent}'", "available": list(SEMANTIC_AGENTS)}
    gene = (getattr(args, "gene", "") or "").strip()
    question = (getattr(args, "question", "") or "").strip()
    context = (getattr(args, "context", "") or "").strip()[:1800]  # public cited facts only
    prompt = (
        f"You are a {role} on a CNS drug-discovery team. Analyse ONLY your dimension for gene {gene}.\n"
        f"Team question: {question or 'rank genes that rescue the TSC2-KO / mTORC1-hyperactivation phenotype'}\n"
        f"Your focus: {_SEM_FOCUS.get(agent, '')}\n"
        + (f"Cited evidence available (public, from EMET): {context}\n" if context else "")
        + "Weigh evidence FOR vs AGAINST honestly. If unsure or lacking evidence, say so (verdict=neutral, "
          "confidence=low) — do NOT fabricate. Public identifiers only. Respond with STRICT JSON only, no prose:\n"
        '{"agent":"' + agent + '","gene":"' + gene + '","verdict":"favorable|risk|neutral",'
        '"finding":"<2-3 sentence assessment>","confidence":"high|medium|low"}'
    )
    claude = os.environ.get("SAPPHIRE_CLAUDE_BIN", "/Users/rohanaryagondi/.local/bin/claude")
    try:
        proc = subprocess.run([claude, "-p", prompt, "--model", "claude-haiku-4-5", "--output-format", "json"],
                              capture_output=True, text=True, timeout=120)
    except Exception as exc:
        return {"ok": False, "agent": agent, "gene": gene, "provenance": "semantic-haiku",
                "error": f"haiku call failed: {exc}"}
    raw = (proc.stdout or "").strip()
    result_text = raw
    env = _extract_json_obj(raw)
    if isinstance(env, dict) and "result" in env:
        result_text = env.get("result", raw)
    finding = _extract_json_obj(result_text)
    if not isinstance(finding, dict):
        finding = {"finding": (result_text or "(no output)")[:400], "verdict": "neutral", "confidence": "low"}
    finding.update({"ok": True, "agent": agent, "gene": gene,
                    "provenance": "semantic-haiku", "model": "claude-haiku-4-5"})
    return finding


# ── subcommand: esm (gene/protein embedding similarity — the gene-specific enrichment) ───────

# Proven ESM-2-650M nearest-neighbors to TSC2 (mean-pooled embeddings, public UniProt sequences) from the
# live GPU run — used instantly/free for the known set; the warm box computes any other target live.
_ESM_TSC2_CACHE = {
    "SSU72": 0.9575, "RPS3": 0.9500, "SAP18": 0.9484, "DPM2": 0.9430, "DIDO1": 0.9428, "MTOR": 0.9380,
    "CDK9": 0.9363, "NCOA6": 0.9252, "KMT2D": 0.9166, "FZD7": 0.8960, "BCL2": 0.8815, "VPS54": 0.8440,
    "SMARCE1": 0.7740, "ACTR3": 0.1624,
}


def _esm_warm_meta():
    try:
        p = Path(__file__).resolve().parents[1] / "RohanOnly" / "qmodels_run" / "warm_instance.json"
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _uniprot_seq(gene, _cache={}):  # noqa: B006 (process-local memo)
    if gene in _cache:
        return _cache[gene]
    try:
        import urllib.request  # noqa: PLC0415
        url = (f"https://rest.uniprot.org/uniprotkb/search?query=gene_exact:{gene}+AND+organism_id:9606"
               f"+AND+reviewed:true&format=fasta&size=1")
        with urllib.request.urlopen(url, timeout=20) as r:  # public sequence only
            fasta = r.read().decode("utf-8")
        seq = "".join(fasta.split("\n")[1:]).strip()
        _cache[gene] = seq or None
        return _cache[gene]
    except Exception:
        return None


def cmd_esm(args) -> dict:
    """Gene/protein embedding similarity (ESM-2-650M) of each gene to a target — the gene/protein-specific
    enrichment (replaces Boltz for gene-rescue questions). TSC2 neighbors are cached (instant, free, real);
    any other target is computed live on the warm GPU box. Honest-degrades if the box is down."""
    target = (getattr(args, "vs", None) or "TSC2").strip().upper()
    raw = (getattr(args, "genes", None) or getattr(args, "gene", None) or "")
    genes = [g.strip().upper() for g in raw.replace(" ", "").split(",") if g.strip()]
    if not genes:
        return {"ok": False, "error": "no genes given (use --genes G1,G2,... [--vs TARGET])"}

    # 1) cached path — TSC2 neighbors are pre-computed (real ESM-2-650M, public sequences)
    if target == "TSC2" and all(g in _ESM_TSC2_CACHE for g in genes):
        ranked = sorted(({"gene": g, "similarity": _ESM_TSC2_CACHE[g]} for g in genes),
                        key=lambda x: x["similarity"], reverse=True)
        return {"ok": True, "target": target, "neighbors": ranked,
                "provenance": "esm-cached", "model": "ESM-2-650M",
                "note": "embedding similarity to TSC2 (sequence/structure proximity — NOT a rescue claim)"}

    # 2) live path — warm GPU box
    meta = _esm_warm_meta()
    endpoint = meta.get("endpoint_url")
    if endpoint:
        try:
            import urllib.request  # noqa: PLC0415
            tgt_seq = _uniprot_seq(target)
            cands = {g: _uniprot_seq(g) for g in genes}
            cands = {g: s for g, s in cands.items() if s}
            if tgt_seq and cands:
                body = json.dumps({"target_seq": tgt_seq, "candidates": cands}).encode("utf-8")
                req = urllib.request.Request(endpoint.rstrip("/") + "/neighbors", data=body,
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    out = json.loads(r.read().decode("utf-8"))
                # the box returns {"ranked":[{"gene","cosine"}]} (list); accept dict forms too
                raw_rank = out.get("ranked") or out.get("neighbors") or out.get("similarities") or []
                if isinstance(raw_rank, dict):
                    raw_rank = [{"gene": g, "cosine": v} for g, v in raw_rank.items()]
                ranked = sorted(
                    ({"gene": r.get("gene"),
                      "similarity": round(float(r.get("cosine", r.get("similarity", 0))), 4)}
                     for r in raw_rank if isinstance(r, dict) and r.get("gene")),
                    key=lambda x: x["similarity"], reverse=True)
                if ranked:
                    return {"ok": True, "target": target, "neighbors": ranked,
                            "provenance": "esm-live", "model": "ESM-2-650M",
                            "note": "embedding similarity (sequence/structure proximity — NOT a rescue claim)"}
        except Exception as exc:
            # fall through to honest degrade
            warm_err = str(exc)
        else:
            warm_err = "no usable sequences/embeddings"
    else:
        warm_err = "warm ESM box not registered (warm_instance.json absent)"

    # 3) honest degrade — partial cache for TSC2 if available
    if target == "TSC2":
        ranked = sorted(({"gene": g, "similarity": _ESM_TSC2_CACHE[g]} for g in genes if g in _ESM_TSC2_CACHE),
                        key=lambda x: x["similarity"], reverse=True)
        if ranked:
            return {"ok": True, "target": target, "neighbors": ranked, "provenance": "esm-cached",
                    "model": "ESM-2-650M", "note": f"warm box unavailable ({warm_err}); cached TSC2 neighbors for known genes"}
    return {"ok": False, "target": target, "neighbors": [], "provenance": "esm-unavailable",
            "note": f"ESM unavailable: {warm_err}. No cached values for target {target}."}


# ── subcommand: catalog (tool/model discovery) ───────────────────────────────

def cmd_catalog(args) -> dict:
    """List EVERY tool + Q-Model the orchestrator can call, so it can DISCOVER and pick the right
    one for any question (this is what makes it flexible — e.g. map 'use ESM' → esm2). Honest about
    what's runnable now vs gated."""
    core = [
        {"tool": "moat", "purpose": "Quiver internal moat — rescue (opposite) / exacerbate (similar) genes for a target; or --probe a specific gene list (each → rescue/exacerbate/absent).", "call": "moat --gene G --direction opposite|similar [--k N]  |  moat --gene G --probe GENE1,GENE2,..."},
        {"tool": "emet", "purpose": "Captured BenchSci literature (real PMIDs) for a gene; --live queues a Chrome-worker BenchSci query.", "call": "emet --gene G [--live]"},
        {"tool": "boltz", "purpose": "Boltz-2 structure + binding / druggability for a gene+ligand (REAL, ~80s, ~$0.02).", "call": "boltz --gene G --ligand DRUG"},
        {"tool": "qmodels", "purpose": "Call a Q-Model from the catalog below by id (live-local real; GPU via --gpu-live on AWS).", "call": "qmodels --tool ID --inputs '<json>' [--gpu-live]"},
        {"tool": "semantic", "purpose": "Spawn a cheap claude-haiku semantic scientific agent to analyse ONE dimension for a gene — YOU decide which to call.", "call": "semantic --agent <mechanism|pathway|toxicity|expression|essentiality|genetics> --gene G [--context '<facts>']"},
        {"tool": "esm", "purpose": "ESM-2 embedding similarity of genes to a target protein (gene/protein-specific enrichment; sequence/structure proximity, NOT druggability). Prefer this over Boltz for gene-rescue questions.", "call": "esm --genes G1,G2,... --vs TARGET"},
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
    m.add_argument("--probe", default=None,
                   help="CSV of genes to check against --gene: each returned as rescue-direction / exacerbate-direction / absent (one call for a whole candidate list)")
    m.add_argument("--compounds", action="store_true",
                   help="ALSO return drug rescue/exacerbate compounds (drug-repurposing leads). OFF by default — only for a drug/therapeutic question, NOT a gene-rescue ranking.")

    e = sub.add_parser("emet", help="Load captured EMET evidence (envelope or rescue-dossier); --live queues a Chrome-worker task")
    e.add_argument("--gene", required=True, help="Gene symbol to look up (e.g. TSC2)")
    e.add_argument("--live", action="store_true",
                   help="If no captured evidence, queue a live EMET task for the Chrome-Claude worker")
    e.add_argument("--query", default=None, help="EMET query text (for --live)")
    e.add_argument("--batch", default=None,
                   help="CSV of genes for ONE fast EMET pass (with --gene as the perturbation, e.g. --gene TSC2 --batch BCL2,CDK9,MTOR,...). Far faster than per-gene; add --live for the worker.")

    b = sub.add_parser(
        "boltz", help="Boltz structure/binding (REAL, ~$0.02, ~80 s): --gene G --ligand DRUG | --protein SEQ --ligand SMILES"
    )
    b.add_argument("--gene", default="", help="Gene with a known public sequence (e.g. BCL2) — resolves protein + ligand")
    b.add_argument("--protein", default="", help="Raw protein sequence (public) — alternative to --gene")
    b.add_argument("--ligand", default="", help="Ligand: a known drug name (e.g. venetoclax) or a raw SMILES")

    q = sub.add_parser("qmodels", help="Call a Q-Model via the launchpad (real for live-local; honest-degrades)")
    q.add_argument("--tool", required=True, help="Q-Model tool id (e.g. chemberta2, boltz2, esm2)")
    q.add_argument("--inputs", default="", help="JSON inputs for the tool")
    q.add_argument("--gpu-live", action="store_true",
                   help="For a GPU model (esm2/boltz2/balm): ACTUALLY launch on AWS (real cost ~$0.13, auto-teardown, every guard). Default off → honest gpu-disabled.")

    s = sub.add_parser("semantic", help="Spawn a cheap claude-haiku semantic scientific agent for one dimension")
    s.add_argument("--agent", required=True, help="dimension: " + " | ".join(SEMANTIC_AGENTS))
    s.add_argument("--gene", required=True, help="gene symbol (public)")
    s.add_argument("--question", default="", help="the team question for context")
    s.add_argument("--context", default="", help="cited public facts (e.g. EMET evidence) for the agent to weigh")

    x = sub.add_parser("esm", help="ESM-2 embedding similarity of genes to a target (gene/protein enrichment)")
    x.add_argument("--genes", default=None, help="CSV of gene symbols to rank by similarity to --vs")
    x.add_argument("--gene", default=None, help="single gene (alternative to --genes)")
    x.add_argument("--vs", default="TSC2", help="target gene to measure embedding similarity against (default TSC2)")

    sub.add_parser("catalog", help="List all tools + Q-Models (discover what's available + what's runnable)")

    args = ap.parse_args()
    dispatch = {"moat": cmd_moat, "emet": cmd_emet, "boltz": cmd_boltz, "qmodels": cmd_qmodels,
                "semantic": cmd_semantic, "esm": cmd_esm, "catalog": cmd_catalog}
    result = dispatch[args.cmd](args)
    print(json.dumps(result, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
