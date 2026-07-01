"""
boltz_seam.py — stdlib-only Sapphire seam for the Boltz biomolecular structure +
binding-affinity model (Boltz-2 family), hosted at the Boltz Compute API.

Bucket-1 STRUCTURAL / BINDING fact source. EMET + gnomAD/GTEx tell us what the
literature and population genetics *say* about a target; this seam returns a
*model-predicted* answer to "does this ligand/binder physically engage this target,
and how confidently?" — a structure-confidence score and (when a binding block is
requested) a binding_confidence / optimization_score. These are cited,
provenance-stamped T2 facts (model prediction, not measured) that complement the
narrative and let the Research Manager flag prediction-vs-narrative DIVERGENCE.

It fires downstream of a target/ligand-bearing question (e.g. the future ASO-Design
or small-molecule tools that emit a target sequence + a candidate ligand SMILES) —
mirroring how ``aso_tox_seam`` fires only when ASO sequences are present.

Boundary & honesty (dev/CONVENTIONS.md §2/§3):
  * Runtime is stdlib-only — this module imports only ``json`` + ``os`` + ``time`` +
    ``urllib``. No third-party deps (no ``requests``, no ``boltz_compute`` SDK) enter
    the engine path. The Boltz Python SDK is deliberately NOT used here.
  * PUBLIC IDENTIFIERS ONLY leave Quiver: protein/RNA/DNA sequences, ligand SMILES,
    CCD codes, public structure URLs. Quiver internal moat scores / EP-IDs / CRISPR
    data MUST NEVER be sent to Boltz. The seam echoes only the public entities it was
    given; the harness ``data_boundary`` guardrail additionally blocks internal ids
    before dispatch. ``assert_public_only()`` is a second, in-seam tripwire.
  * Degrade honestly, never fabricate: when the API key is missing, when the API is
    unreachable, when a job fails or times out, the seam returns a KNOWN_UNKNOWN /
    abstain-style result (facts=[] + a flagged abstain fact + ``error``). It NEVER
    invents a structure, a confidence, or an affinity. It NEVER raises into the engine.

Provenance label: ``boltz`` (EXTERNAL plane — it is an external model API run against
public identifiers only; it is NOT an internal-moat label).

API contract (confirmed live 2026-06-25 against the hosted Boltz Compute API):
  * Base URL:   https://api.boltz.bio/compute/v1
  * Auth:       header ``x-api-key: <BOLTZ_API_KEY>``  (NOT ``Authorization: Bearer``)
  * Estimate:   POST /predictions/structure-and-binding/estimate-cost   (runs no job, $0)
                → {"estimated_cost_usd": "0.0250", "breakdown": {...}, "disclaimer": ...}
  * Start:      POST /predictions/structure-and-binding
                  body {"input": {"entities": [...], "binding"?, "num_samples"?, ...},
                        "model": "boltz-2.1", "idempotency_key"?}
                → {"id": "sab_pred_...", "status": "pending", "output": null, "error": null, ...}
  * Poll:       GET  /predictions/structure-and-binding/{id}
                → status ∈ {pending, running, succeeded, failed}; terminal = succeeded|failed
  * Output:     output.best_sample.metrics.{structure_confidence, ptm, iptm, complex_plddt, ...}
                output.binding_metrics.{binding_confidence, optimization_score?}  (only if
                a ``binding`` block was requested)
The model is ASYNCHRONOUS: start → poll until terminal → read ``output``.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_BASE_URL = "https://api.boltz.bio/compute/v1"
_START_PATH = "/predictions/structure-and-binding"
_PROVENANCE = "boltz"
_MODEL = "boltz-2.1"
_SOURCE = "Boltz-2 structure/binding model (Boltz Compute API)"

# R-Sapphire shortcut: when SAPPHIRE_QMODELS_GPU_ENDPOINT is set, route boltz through
# R-Sapphire's boltz2 model via POST /predict rather than the hosted Boltz API
# (which requires BOLTZ_API_KEY). Only falls back to the hosted API when the endpoint
# env var is unset or the endpoint is unreachable.
_RSAPPHIRE_ENV = "SAPPHIRE_QMODELS_GPU_ENDPOINT"

# Network / polling budget. Kept tight: this is a fact seam inside an engine turn,
# not a batch screen. A tiny fold returns in ~30s; we cap total wait so a slow or
# stuck job degrades to an honest KNOWN_UNKNOWN rather than blocking the dossier.
_HTTP_TIMEOUT = 60          # per-request socket timeout (seconds)
_POLL_INTERVAL = 10         # seconds between status polls
_MAX_POLLS = 30             # → up to ~5 min total before honest timeout

_ENV_KEY = "BOLTZ_API_KEY"
# Gitignored env file the key lives in (read only if the env var itself is unset).
# Path is resolved relative to the repo root so it works regardless of CWD.
_THIS_FILE = os.path.abspath(__file__)
# sapphire-orchestrator/tools/boltz_seam.py → repo root is two levels up
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE)))
_KEY_ENV_FILE = os.path.join(_REPO_ROOT, "RohanOnly", "boltz_api.env")

# Confidence interpretation thresholds (Boltz convention; structure_confidence and
# binding_confidence are both 0–1). Only the well-supported "high-confidence" call is
# made; anything else is stated plainly without an interpretive claim.
_CONF_HIGH = 0.80
_CONF_LOW = 0.50

# Terminal job states.
_TERMINAL_OK = "succeeded"
_TERMINAL_FAIL = "failed"


# ---------------------------------------------------------------------------
# Public-only boundary tripwire
# ---------------------------------------------------------------------------
# Tokens that mark Quiver INTERNAL data. If any entity value (or an MSA/template URL)
# contains one of these, we refuse to transmit — a defence-in-depth backstop behind
# the harness data_boundary guardrail. This keys on the shape of internal identifiers,
# never on a provenance label (see contracts/provenance.py for why those are kept apart).
_INTERNAL_MARKERS = ("EP-", "EP_", "CRISPR_SCORE", "MOAT_", "CNS_DFP", "QUIVER_INTERNAL")


def assert_public_only(entities: list[dict]) -> None:
    """Raise ValueError if any entity value smells like Quiver internal data.

    Boltz receives PUBLIC identifiers only (sequences, SMILES, CCD codes, public
    structure URLs). This is a tripwire, not the primary enforcer (the harness
    ``data_boundary`` guardrail blocks the dispatch upstream); it exists so the seam
    fails CLOSED even if called directly, outside the harness.
    """
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        val = str(ent.get("value", ""))
        up = val.upper()
        for marker in _INTERNAL_MARKERS:
            if marker in up:
                raise ValueError(
                    "boltz_seam: refusing to transmit — entity value contains an "
                    f"internal-data marker ({marker!r}). Boltz receives public "
                    "identifiers only."
                )


# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------
def _resolve_key() -> str | None:
    """Return the Boltz API key from the env var, else from the gitignored env file.

    Never logs or returns a partial key for display. Returns None when no key is
    available (→ honest KNOWN_UNKNOWN degrade upstream)."""
    key = os.environ.get(_ENV_KEY)
    if key:
        return key.strip() or None
    # Fall back to the gitignored env file (BOLTZ_API_KEY=...).
    try:
        with open(_KEY_ENV_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == _ENV_KEY:
                    return value.strip().strip('"').strip("'") or None
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------
# Network boundary (single indirection — tests monkeypatch HERE)
# ---------------------------------------------------------------------------
def _http(method: str, path: str, api_key: str, body: dict | None = None) -> dict:
    """One HTTP indirection for the whole seam. Tests monkeypatch ``_http`` to mock
    the network — no live key is ever needed in tests.

    Sends ``x-api-key`` auth (the Boltz contract — NOT Authorization: Bearer). Returns
    the parsed JSON dict. Raises on transport/decode error; the caller catches and
    degrades to an honest envelope.
    """
    url = _BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "sapphire-boltz-seam/1.0",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _sleep(seconds: float) -> None:
    """Indirection so tests can monkeypatch out the real poll delay."""
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Job lifecycle (start → poll → terminal)
# ---------------------------------------------------------------------------
def _run_job(entities: list[dict], binding: dict | None, num_samples: int,
             api_key: str, idempotency_key: str | None) -> dict:
    """Start a structure-and-binding job and poll until terminal.

    Returns the terminal job record dict (carrying ``status`` + ``output`` + ``error``).
    Raises ``TimeoutError`` if the job never reaches a terminal state within budget,
    and propagates transport errors from ``_http`` (the caller degrades honestly).
    """
    payload: dict = {
        "input": {"entities": entities, "num_samples": num_samples},
        "model": _MODEL,
    }
    if binding:
        payload["input"]["binding"] = binding
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key

    started = _http("POST", _START_PATH, api_key, body=payload)
    job_id = started.get("id")
    status = started.get("status")
    if not job_id:
        # No id back → treat as a hard error (surfaced honestly upstream).
        raise RuntimeError(
            "boltz start returned no job id: "
            + (json.dumps(started.get("error")) if started.get("error") else "unknown")
        )

    # If the start call already returned a terminal record (idempotent replay of a
    # finished job), don't poll.
    if status in (_TERMINAL_OK, _TERMINAL_FAIL):
        return started

    for _ in range(_MAX_POLLS):
        _sleep(_POLL_INTERVAL)
        rec = _http("GET", f"{_START_PATH}/{job_id}", api_key)
        status = rec.get("status")
        if status in (_TERMINAL_OK, _TERMINAL_FAIL):
            return rec
    raise TimeoutError(
        f"boltz job {job_id} did not reach a terminal state within "
        f"{_MAX_POLLS * _POLL_INTERVAL}s"
    )


# ---------------------------------------------------------------------------
# Result normalisation
# ---------------------------------------------------------------------------
def _num(x):
    """Return x as a float if it is a real number (not bool/None/str), else None.

    The API may serialise numbers as strings (e.g. cost) or omit them; we only ever
    format genuine numbers and never fabricate one."""
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            return None
    return None


def _interpret_conf(conf: float | None, kind: str) -> str:
    """Short, conservative interpretation of a 0–1 confidence, or '' to state it plainly."""
    if conf is None:
        return ""
    if conf >= _CONF_HIGH:
        return f"high-confidence {kind}"
    if conf < _CONF_LOW:
        return f"low-confidence {kind}"
    return ""


def _abstain_fact(reason: str) -> dict:
    """A KNOWN_UNKNOWN abstain fact — the honest-degrade marker. Carries the reason
    in ``value`` so the dossier shows *why* the model could not contribute, rather
    than a fabricated structure/affinity."""
    return {
        "value": f"Boltz structure/binding prediction unavailable: {reason}",
        "source": _SOURCE,
        "tier": "T2",
        "flag": "KNOWN_UNKNOWN",
    }


def normalize(job: dict, requested_binding: bool) -> list[dict]:
    """Turn a terminal Boltz job record into a list of cited T2 fact dicts.

    Emits a structure-confidence fact, and (when binding was requested and returned)
    a binding fact. A succeeded job with no usable metrics, or a failed job, yields a
    single KNOWN_UNKNOWN abstain fact — never a fabricated number.
    """
    status = job.get("status")
    if status == _TERMINAL_FAIL:
        err = job.get("error") or {}
        msg = err.get("message") if isinstance(err, dict) else str(err)
        return [_abstain_fact(f"job failed ({msg or 'no detail'})")]

    out = job.get("output")
    if not isinstance(out, dict):
        return [_abstain_fact("job succeeded but returned no output")]

    facts: list[dict] = []

    # --- structure confidence (best sample) ---
    best = out.get("best_sample") or {}
    metrics = best.get("metrics") or {} if isinstance(best, dict) else {}
    sc = _num(metrics.get("structure_confidence"))
    ptm = _num(metrics.get("ptm"))
    iptm = _num(metrics.get("iptm"))
    plddt = _num(metrics.get("complex_plddt"))
    if sc is not None:
        parts = [f"structure_confidence {sc:.2f}"]
        if plddt is not None:
            parts.append(f"complex_pLDDT {plddt:.2f}")
        if ptm is not None:
            parts.append(f"pTM {ptm:.2f}")
        if iptm is not None:
            parts.append(f"ipTM {iptm:.2f}")
        value = "Boltz-2 predicted complex: " + ", ".join(parts)
        interp = _interpret_conf(sc, "fold")
        if interp:
            value += f" ({interp})"
        facts.append({"value": value, "source": _SOURCE, "tier": "T2"})

    # --- binding metrics (only when a binding block was requested) ---
    bm = out.get("binding_metrics")
    if requested_binding and isinstance(bm, dict):
        bc = _num(bm.get("binding_confidence"))
        opt = _num(bm.get("optimization_score"))
        if bc is not None:
            parts = [f"binding_confidence {bc:.2f}"]
            if opt is not None:
                parts.append(f"optimization_score {opt:.2f}")
            value = "Boltz-2 predicted binding: " + ", ".join(parts)
            interp = _interpret_conf(bc, "binding")
            if interp:
                value += f" ({interp})"
            facts.append({"value": value, "source": _SOURCE, "tier": "T2"})

    if not facts:
        # Succeeded but nothing usable parsed out — honest abstain, no fabrication.
        return [_abstain_fact("job succeeded but no usable metrics in output")]
    return facts


# ---------------------------------------------------------------------------
# R-Sapphire routing (preferred when endpoint is set; no API key required)
# ---------------------------------------------------------------------------
def _rsapphire_endpoint() -> str | None:
    """Return the R-Sapphire /predict URL if set, else None."""
    ep = os.environ.get(_RSAPPHIRE_ENV, "").strip()
    return ep if ep else None


def _predict_via_rsapphire(entities: list[dict], binding: dict | None) -> dict | None:
    """Attempt to run a boltz2 prediction via R-Sapphire's /predict endpoint.

    Sends {"track": "boltz2", "model": "boltz2", "inputs": {"target_seq": ..., "smiles": ...}}.
    Returns a parsed result dict on success, None on connection failure (caller falls through
    to the hosted API), or a fact-bearing error dict on HTTP/server error.
    """
    ep = _rsapphire_endpoint()
    if not ep:
        return None

    # Extract protein sequence and ligand SMILES from the Boltz entities list.
    target_seq = ""
    smiles = ""
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        if ent.get("type") == "protein":
            target_seq = ent.get("value", "")
        elif ent.get("type") in ("ligand_smiles",):
            smiles = ent.get("value", "")

    if not target_seq and not smiles:
        return None  # nothing to send; fall through

    r_inputs: dict = {}
    if target_seq:
        r_inputs["target_seq"] = target_seq
    if smiles:
        r_inputs["smiles"] = smiles

    body = json.dumps({"track": "boltz2", "model": "boltz2", "inputs": r_inputs}).encode("utf-8")
    req = urllib.request.Request(
        ep, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            pred = json.loads(resp.read())
        # Normalise the R-Sapphire response into the same fact shape as the hosted path.
        # R-Sapphire returns the raw model output dict; extract structure_confidence/binding_confidence.
        sc = pred.get("structure_confidence") or pred.get("score")
        bc = pred.get("binding_confidence")
        facts: list[dict] = []
        if sc is not None:
            val = f"Boltz-2 (R-Sapphire) predicted complex: structure_confidence {float(sc):.2f}"
            facts.append({"value": val, "source": "Boltz-2 via R-Sapphire endpoint", "tier": "T2"})
        if bc is not None:
            val = f"Boltz-2 (R-Sapphire) predicted binding: binding_confidence {float(bc):.2f}"
            facts.append({"value": val, "source": "Boltz-2 via R-Sapphire endpoint", "tier": "T2"})
        if not facts:
            # Server responded but no recognised metric keys — emit what we got.
            summary = json.dumps(pred)[:200]
            facts.append({"value": f"Boltz-2 (R-Sapphire) response: {summary}",
                          "source": "Boltz-2 via R-Sapphire endpoint", "tier": "T2"})
        return {"facts": facts, "provenance": "boltz-rsapphire", "status": "succeeded"}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200] if hasattr(e, "read") else str(e)
        return {
            "facts": [_abstain_fact(f"R-Sapphire boltz2 HTTP {e.code}: {detail}")],
            "provenance": "boltz-rsapphire",
            "status": "rsapphire-error",
            "error": f"R-Sapphire HTTP {e.code}",
        }
    except urllib.error.URLError:
        # Endpoint unreachable → fall through to the hosted API path.
        return None
    except Exception:
        # Any other unexpected error → fall through.
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def predict(entities: list[dict], binding: dict | None = None,
            num_samples: int = 1, idempotency_key: str | None = None) -> dict:
    """Run one Boltz structure/binding prediction over PUBLIC entities.

    Args:
        entities       — list of Boltz entity dicts (``{"type","value","chain_ids"}``);
                         public identifiers only (protein/RNA/DNA sequences, SMILES,
                         CCD codes). See module docstring for the entity schema.
        binding        — optional binding block, e.g.
                         ``{"type":"ligand_protein_binding","binder_chain_id":"B"}``.
        num_samples    — 1–10 structure samples (default 1, the cheapest).
        idempotency_key— optional stable string so retries de-dupe server-side.

    Returns a dict ALWAYS carrying:
        facts       — list of cited T2 fact dicts (or one KNOWN_UNKNOWN abstain fact)
        provenance  — "boltz"
        status      — terminal job status, or a degrade reason string

    Never raises. Missing key / API error / timeout → honest KNOWN_UNKNOWN.
    """
    if not entities:
        return {"facts": [], "provenance": _PROVENANCE, "status": "no_input"}

    # Boundary tripwire (fail closed even outside the harness).
    try:
        assert_public_only(entities)
    except ValueError as exc:
        return {
            "facts": [_abstain_fact(str(exc))],
            "provenance": _PROVENANCE,
            "status": "boundary_block",
            "error": str(exc),
        }

    # R-Sapphire shortcut: when SAPPHIRE_QMODELS_GPU_ENDPOINT is set, route boltz through
    # the warm R-Sapphire box (no API key required) rather than the hosted Boltz API.
    # Falls through to the hosted path only when the endpoint is unset or unreachable.
    if _rsapphire_endpoint():
        r_result = _predict_via_rsapphire(entities, binding)
        if r_result is not None:
            return r_result
        # None means endpoint unreachable → fall through to hosted API below.

    api_key = _resolve_key()
    if not api_key:
        return {
            "facts": [_abstain_fact(f"no API key ({_ENV_KEY} unset)")],
            "provenance": _PROVENANCE,
            "status": "no_key",
            "error": f"{_ENV_KEY} not set and {_KEY_ENV_FILE} unreadable",
        }

    try:
        job = _run_job(entities, binding, num_samples, api_key, idempotency_key)
    except urllib.error.URLError as exc:
        return {
            "facts": [_abstain_fact(f"API unreachable ({exc})")],
            "provenance": _PROVENANCE,
            "status": "unreachable",
            "error": str(exc),
        }
    except TimeoutError as exc:
        return {
            "facts": [_abstain_fact(str(exc))],
            "provenance": _PROVENANCE,
            "status": "timeout",
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 — degrade honestly, never raise into the engine
        return {
            "facts": [_abstain_fact(f"API error ({exc})")],
            "provenance": _PROVENANCE,
            "status": "error",
            "error": str(exc),
        }

    facts = normalize(job, requested_binding=bool(binding))
    return {"facts": facts, "provenance": _PROVENANCE, "status": job.get("status")}


def _entities_from_inputs(inputs: dict) -> tuple[list[dict], dict | None]:
    """Assemble Boltz entities + an optional binding block from harness inputs.

    Recognised public input keys (any subset):
        target_sequence / protein_sequence — one-letter AA string → protein chain A
        ligand_smiles                      — SMILES string         → ligand chain B
        ligand_ccd                         — CCD code              → ligand chain B
        entities                           — a pre-built Boltz entities list (advanced;
                                             used verbatim, still boundary-checked)
        binding                            — a pre-built binding block (advanced)

    When a protein + a ligand are both present and no explicit binding block was given,
    a ligand_protein_binding block on chain B is added automatically so the dossier
    gets a binding_confidence. Returns ([], None) when no usable public inputs exist.
    """
    # Advanced: caller supplied a ready-made entities list.
    pre = inputs.get("entities")
    if isinstance(pre, list) and pre:
        return pre, (inputs.get("binding") if isinstance(inputs.get("binding"), dict) else None)

    entities: list[dict] = []
    protein = (inputs.get("target_sequence") or inputs.get("protein_sequence") or "").strip()
    if protein:
        entities.append({"type": "protein", "chain_ids": ["A"], "value": protein})

    ligand_smiles = (inputs.get("ligand_smiles") or "").strip()
    ligand_ccd = (inputs.get("ligand_ccd") or "").strip()
    if ligand_smiles:
        entities.append({"type": "ligand_smiles", "chain_ids": ["B"], "value": ligand_smiles})
    elif ligand_ccd:
        entities.append({"type": "ligand_ccd", "chain_ids": ["B"], "value": ligand_ccd})

    binding = inputs.get("binding") if isinstance(inputs.get("binding"), dict) else None
    # Auto-request ligand-protein binding when we have exactly one protein + one ligand.
    if binding is None and protein and (ligand_smiles or ligand_ccd):
        binding = {"type": "ligand_protein_binding", "binder_chain_id": "B"}

    return entities, binding


def findings(inputs: dict) -> dict:
    """Harness-compatible findings dict for the ``boltz`` agent.

    Reads public structural inputs (see ``_entities_from_inputs``), runs one Boltz
    prediction, and returns cited T2 facts. Honest-empty (facts=[]) when no structural
    inputs are present — this seam only contributes when a target sequence and/or a
    candidate ligand are available (i.e. downstream of a Design / target-structure
    question), mirroring how ``aso_tox_seam`` fires only on ASO sequences.

    Output contract (matches the harness output_schema, additionalProperties:false):
        candidate   — echo of the candidate/target label
        facts       — list of {value, source, tier[, flag]}
        provenance  — "boltz"
        error       — present only on a hard failure (honest error envelope)

    Never raises.
    """
    candidate = (inputs.get("candidate") or inputs.get("target") or "").strip()

    entities, binding = _entities_from_inputs(inputs)
    if not entities:
        # No structural inputs → honest empty (not an error). This is the common case
        # for questions without a sequence/ligand; the seam simply stays silent.
        return {"candidate": candidate, "facts": [], "provenance": _PROVENANCE}

    # Stable idempotency key so engine retries of the same question de-dupe server-side
    # (and don't double-charge). Derived only from public inputs.
    idem = "sapphire-" + str(abs(hash((candidate, json.dumps(entities, sort_keys=True),
                                       json.dumps(binding, sort_keys=True)))))[:24]

    result = predict(entities, binding=binding, num_samples=1, idempotency_key=idem)

    out: dict = {
        "candidate": candidate,
        "facts": result.get("facts", []),
        "provenance": _PROVENANCE,
    }
    if result.get("error"):
        out["error"] = result["error"]
    return out
