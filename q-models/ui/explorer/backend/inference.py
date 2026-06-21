"""inference.py — the ONE place that talks to a model. Everything else is done.

This is the single stub boundary for the whole Explorer. In stub mode (no
`EXPLORER_AWS_ENDPOINT` configured) `run_inference` returns the per-track
`stub_prediction` from tracks.json, flagged `_stub: True`, so the entire app —
routes, schemas, history, verdicts, batch parsing, report page — runs locally
with NO AWS, NO GPU, NO model weights.

The final "go live" step the user performs is setting one env var. When
`EXPLORER_AWS_ENDPOINT` is set, the clearly-marked AWS block below POSTs the
track id + the track's `aws_model_key` + the raw inputs to that endpoint and
returns its JSON. Nothing else in the codebase changes.

Informational tracks (e.g. crossmodal, `informational: true`) never call a
model, in stub mode OR live mode — they just echo their build-plan prediction.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .registry import get_track

# --- configuration (all read at call time so a running process can be flipped
#     live without a reimport; tests stay stubbed by leaving the endpoint unset) ---
_ENDPOINT_ENV = "EXPLORER_AWS_ENDPOINT"   # the model-inference URL; unset => stub mode
_API_KEY_ENV = "EXPLORER_AWS_API_KEY"     # optional; sent as `x-api-key` if present
_TIMEOUT_ENV = "EXPLORER_AWS_TIMEOUT"     # seconds; default 600 (Boltz-2 co-fold is minutes)
_DEFAULT_TIMEOUT = 600.0


def _endpoint() -> str | None:
    ep = os.environ.get(_ENDPOINT_ENV)
    return ep.strip() if ep else None


def _timeout() -> float:
    try:
        return float(os.environ.get(_TIMEOUT_ENV, "") or _DEFAULT_TIMEOUT)
    except ValueError:
        return _DEFAULT_TIMEOUT


def is_stubbed() -> bool:
    """True until an AWS endpoint is configured (the app is in DEMO mode)."""
    return not _endpoint()


def _post(url: str, body: dict) -> dict:
    """POST JSON to the inference endpoint and return the decoded JSON object.

    Raises RuntimeError with a clear, user-facing message on any transport or
    decode failure so the UI shows *why* a live call failed (endpoint down,
    wrong URL, model error) instead of a bare 500.
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = os.environ.get(_API_KEY_ENV)
    if api_key:
        headers["x-api-key"] = api_key.strip()
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_timeout()) as r:  # noqa: S310 (operator-set URL)
            raw = r.read()
    except urllib.error.HTTPError as e:  # endpoint reachable but returned an error status
        detail = e.read().decode("utf-8", "replace")[:500] if hasattr(e, "read") else ""
        raise RuntimeError(f"inference endpoint returned HTTP {e.code}: {detail or e.reason}") from e
    except urllib.error.URLError as e:  # DNS/connection/timeout — endpoint unreachable
        raise RuntimeError(
            f"could not reach inference endpoint ({e.reason}). Is EXPLORER_AWS_ENDPOINT correct "
            f"and the GPU endpoint running? See ui/explorer/SETUP.md §5."
        ) from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"inference endpoint returned non-JSON: {raw[:200]!r}") from e


def run_inference(track_id: str, payload: dict) -> dict:
    """Return a prediction dict for `track_id` given the user's `payload`.

    Stub mode → the track's `stub_prediction` (flagged `_stub: True`).
    Live mode → POST to the AWS endpoint and return its JSON.
    Informational tracks → never call a model.
    """
    track = get_track(track_id)

    # Informational tracks (build-don't-buy, e.g. crossmodal) never hit a model.
    if track.get("informational"):
        return {**track["stub_prediction"]}

    # LIVE LOCAL MODELS (gated by EXPLORER_LOCAL_MODELS=1; off by default so tests stay stubbed):
    # the per-target CNS binder fine-tunes are CPU/FP joblibs that run in-process (no AWS). For
    # the DTI track on a data-rich CNS target, return a real binder probability; otherwise fall
    # through to stub/AWS. See backend/local_models.py.
    _LOCAL = {"dti": "predict_dti", "bbbp": "predict_bbbp", "toxicity": "predict_toxicity"}
    if track_id in _LOCAL:
        try:
            from . import local_models
            local = getattr(local_models, _LOCAL[track_id])(payload)
        except Exception:
            local = None
        if local is not None:
            return local

    if is_stubbed():
        pred = dict(track["stub_prediction"])
        pred["_stub"] = True
        return pred

    # --- AWS WIRING (the final step the user will do) ----------------------
    # Set EXPLORER_AWS_ENDPOINT to your inference endpoint (e.g. the FastAPI
    # server in aws/explorer_inference_server.py, fronted by an instance URL or
    # API Gateway). This is the ONLY code path that requires AWS. The server
    # dispatches on `model` (the track's aws_model_key) and returns the
    # prediction body matching the track's score_kind — see SETUP.md §5.
    pred = _post(_endpoint(), {
        "track": track_id,
        "model": track.get("aws_model_key"),
        "inputs": payload,
    })
    if not isinstance(pred, dict) or "score_kind" not in pred:
        raise RuntimeError(
            f"inference endpoint response for '{track_id}' is missing required 'score_kind' "
            f"(got keys: {list(pred)[:8] if isinstance(pred, dict) else type(pred).__name__})."
        )
    return pred
    # -----------------------------------------------------------------------
