"""Quiver Capability Explorer — FastAPI backend.

One tab per Quiver track, each routed to the best model we found, with that
model's empirical operating envelope (the "verdict") on every result.

This app is FRONTEND-COMPLETE + BACKEND-WIRED-EXCEPT-THE-AWS-CALL: it imports
and serves with NO AWS, NO GPU, NO model weights. The only stub is
`inference.run_inference` (see inference.py). Run from the repo root:

    EXPLORER_HISTORY=/tmp/ex_hist.jsonl \\
      /opt/anaconda3/envs/mammal/bin/uvicorn ui.explorer.backend.app:app --reload

then open http://localhost:8000/ (Swagger at /docs).
"""

from __future__ import annotations

import os

# transformers auto-imports TensorFlow which deadlocks on macOS; keep imports
# light so `import ui.explorer.backend.app` is fast and AWS-free. (Ported from
# ui/backend/app.py.)
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import re
from html import escape as _html_escape
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response

from . import history
from . import inference
from . import registry
from .schemas import (
    BatchRequest,
    BatchResponse,
    PredictResponse,
)

# Repo root: ui/explorer/backend/app.py -> parents[3].
REPO = Path(__file__).resolve().parents[3]
FRONTEND = Path(__file__).resolve().parents[1] / "frontend"

# Docs we serve read-only so every verdict's `source:` citation is clickable.
_DOC_ROOTS = [(REPO / "results").resolve(), (REPO / "docs").resolve()]

app = FastAPI(
    title="Quiver Capability Explorer",
    description=(
        "One tab per Quiver capability track, each routed to the best model we "
        "found, with that model's empirical operating envelope on every result. "
        "Stub mode runs with no AWS/GPU/weights; set EXPLORER_AWS_ENDPOINT to go live."
    ),
    version="0.1.0",
)


# ----------------------------- helpers -----------------------------

def _track_or_404(track_id: str) -> dict:
    if not registry.has_track(track_id):
        raise HTTPException(404, f"unknown track '{track_id}'")
    return registry.get_track(track_id)


def _build_verdict(track: dict) -> dict:
    """Resolve a track's `badge` id + `verdict` block into the response shape."""
    badge_id = track.get("badge")
    info = registry.resolve_badge(badge_id)
    v = track.get("verdict", {})
    return {
        "badge": badge_id,
        "badge_label": info.get("label"),
        "badge_emoji": info.get("emoji"),
        "headline": v.get("headline"),
        "why": v.get("why"),
        "recommended_use": v.get("recommended_use"),
        "source": v.get("source"),
    }


def _track_public(track: dict, *, with_stub: bool = False) -> dict:
    """A track dict for list/detail responses (drops the heavy stub_prediction
    unless explicitly requested)."""
    out = {k: val for k, val in track.items() if k != "stub_prediction"}
    out["verdict_resolved"] = _build_verdict(track)
    out["batchable"] = "batch" in track
    if with_stub:
        out["stub_prediction"] = track.get("stub_prediction")
    return out


def _primary_score(prediction: dict | None) -> float | None:
    """The primary numeric score used to rank a batch row (higher = better).

    Batch-enabled tracks are bbbp (probability) and toxicity (panel of
    endpoints). For probability we rank by `value`; for a panel we rank by the
    max endpoint risk so the riskiest compounds float to the top of a tox
    triage. Falls back to any obvious numeric field (value/affinity/confidence).
    """
    if not prediction:
        return None
    if prediction.get("value") is not None:
        try:
            return float(prediction["value"])
        except (TypeError, ValueError):
            pass
    endpoints = prediction.get("endpoints")
    if isinstance(endpoints, list) and endpoints:
        vals = [e.get("value") for e in endpoints if isinstance(e.get("value"), (int, float))]
        if vals:
            return float(max(vals))
    for key in ("affinity", "confidence", "rank_percentile"):
        if isinstance(prediction.get(key), (int, float)):
            return float(prediction[key])
    return None


# ----------------------------- meta / catalog endpoints -----------------------------

@app.get("/api/meta")
def api_meta() -> dict:
    m = registry.meta()
    return {
        "title": m.get("title"),
        "subtitle": m.get("subtitle"),
        "banner": m.get("banner"),
        "badges": m.get("badges", {}),
        "generated_from": m.get("generated_from"),
        "stubbed": inference.is_stubbed(),
        # Tracks served by a live LOCAL model (CPU fine-tunes, no AWS) — lets the UI show
        # "N tracks live" instead of a blanket DEMO banner when some tracks are live.
        "live_tracks": _live_tracks(),
    }


def _live_tracks() -> list:
    try:
        from . import local_models
        return local_models.live_tracks()
    except Exception:
        return []


@app.get("/api/tracks")
def api_tracks() -> dict:
    return {"tracks": [_track_public(t) for t in registry.all_tracks()]}


@app.get("/api/track/{track_id}")
def api_track(track_id: str) -> dict:
    track = _track_or_404(track_id)
    return _track_public(track, with_stub=True)


@app.get("/api/report")
def api_report() -> dict:
    """Report-page rows: which model per track + how it performs."""
    rows = []
    for t in registry.all_tracks():
        info = registry.resolve_badge(t.get("badge"))
        rows.append({
            "n": t.get("n"),
            "id": t.get("id"),
            "label": t.get("label"),
            "emoji": t.get("emoji"),
            "best_model": t.get("best_model"),
            "license": t.get("license"),
            "est_runtime": t.get("est_runtime"),
            "performance": {"headline": t.get("performance", {}).get("headline")},
            "badge": t.get("badge"),
            "badge_label": info.get("label"),
            "badge_emoji": info.get("emoji"),
            "verdict": {"headline": t.get("verdict", {}).get("headline")},
            "source": t.get("verdict", {}).get("source"),
        })
    return {"tracks": rows, "badges": registry.badges()}


@app.get("/api/examples/{track_id}")
def api_examples(track_id: str) -> dict:
    track = _track_or_404(track_id)
    return {
        "example": track.get("example", {}),
        "example_note": track.get("example_note"),
    }


# ----------------------------- prediction core -----------------------------

def _predict(track: dict, payload: dict) -> PredictResponse:
    track_id = track["id"]
    inputs_echo = {k: v for k, v in (payload or {}).items() if v is not None}
    prediction = inference.run_inference(track_id, payload)
    # A live LOCAL prediction (_local, e.g. the per-target DTI fine-tunes) is NOT stubbed even
    # when no AWS endpoint is configured; only an explicit _stub or the global stub (with no
    # local result) counts as stubbed.
    is_local = bool(prediction.get("_local"))
    stubbed = bool(prediction.pop("_stub", False)) or (inference.is_stubbed() and not is_local)
    verdict = _build_verdict(track)
    history.append(
        track_id,
        inputs_echo,
        prediction,
        track.get("badge"),
        track.get("best_model"),
        stubbed,
        label=track.get("label"),
    )
    return PredictResponse(
        track=track_id,
        label=track.get("label"),
        model=track.get("best_model"),
        license=track.get("license"),
        stubbed=stubbed,
        prediction=prediction,
        verdict=verdict,
        performance=track.get("performance", {}),
        inputs_echo=inputs_echo,
    )


@app.post("/api/predict/{track_id}", response_model=PredictResponse)
def api_predict(track_id: str, body: dict = Body(default_factory=dict)) -> PredictResponse:
    """Run one prediction. Inputs validated loosely (no 422 on a missing
    optional); the track's verdict + performance are attached and the run is
    logged to history."""
    track = _track_or_404(track_id)
    payload = dict(body or {})
    return _predict(track, payload)


# ----------------------------- batch triage -----------------------------

@app.post("/api/predict/{track_id}/batch", response_model=BatchResponse)
def api_predict_batch(track_id: str, req: BatchRequest) -> BatchResponse:
    """Run a batch (one row per compound) for a batch-enabled track and rank
    results best-first by the prediction's primary numeric score. Errored rows
    sort last. One compact history entry is logged per batch."""
    track = _track_or_404(track_id)
    if not registry.is_batchable(track_id):
        raise HTTPException(404, f"track '{track_id}' is not batchable")

    verdict = _build_verdict(track)
    requested = len(req.rows)

    scored: list[dict] = []
    errored: list[dict] = []
    for i, row in enumerate(req.rows):
        row = dict(row or {})
        try:
            prediction = inference.run_inference(track_id, row)
            prediction.pop("_stub", None)
            scored.append({"index": i, "inputs": row, "prediction": prediction})
        except Exception as e:  # noqa: BLE001 — one bad row must not fail the batch
            errored.append({"index": i, "inputs": row, "error": f"{type(e).__name__}: {e}"})

    # Rank successful rows best-first by primary score; ties keep input order.
    scored.sort(
        key=lambda s: (
            _primary_score(s["prediction"]) is not None,
            _primary_score(s["prediction"]) if _primary_score(s["prediction"]) is not None else 0.0,
        ),
        reverse=True,
    )

    rows_out: list[dict] = []
    for rank, s in enumerate(scored, start=1):
        rows_out.append({
            "index": s["index"], "rank": rank, "inputs": s["inputs"],
            "prediction": s["prediction"], "error": None,
        })
    for e in sorted(errored, key=lambda x: x["index"]):
        rows_out.append({
            "index": e["index"], "rank": None, "inputs": e["inputs"],
            "prediction": None, "error": e["error"],
        })

    stubbed = inference.is_stubbed()
    if scored:
        top = scored[0]
        history.append(
            track_id,
            {"_batch": f"{len(scored)} scored / {requested} submitted"},
            top["prediction"],
            track.get("badge"),
            track.get("best_model"),
            stubbed,
            label=f"{track.get('label')} (batch · {len(scored)} rows)",
        )

    return BatchResponse(
        track=track_id,
        label=track.get("label"),
        model=track.get("best_model"),
        license=track.get("license"),
        stubbed=stubbed,
        requested=requested,
        processed=len(scored) + len(errored),
        rows=rows_out,
        verdict=verdict,
        performance=track.get("performance", {}),
    )


# ----------------------------- history -----------------------------

@app.get("/api/history")
def api_history(limit: int = 100, track: str | None = None) -> dict:
    return {"count": history.count(), "records": history.recent(limit=limit, track=track)}


@app.delete("/api/history")
def api_history_clear() -> dict:
    history.clear()
    return {"status": "cleared"}


# ----------------------------- evidence docs (read-only) -----------------------------
# Make each verdict's `source:` citation clickable: serve the actual writeups,
# read-only, but ONLY from results/ and docs/ (path-traversal-safe). Ported from
# ui/backend/app.py.

def _resolve_doc(path: str) -> Path:
    """Resolve a /doc path to a real file under results/ or docs/, or raise.

    Path-traversal-safe: the resolved target must be (or live under) one of the
    allowed roots, so encoded `..` escapes are rejected before any read.
    """
    target = (REPO / path).resolve()
    if not any(target == root or root in target.parents for root in _DOC_ROOTS):
        raise HTTPException(403, "only results/ and docs/ are served")
    if not target.is_file():
        raise HTTPException(404, f"no such doc: {path}")
    return target


# A Track heading we want to give a STABLE `id="track-N"` so the report page can
# deep-link to it (`/doc/docs/models_tracks_scorecard.md#track-4`). Matches the
# rendered <h2>/<h3> whose visible text starts with "Track <N>" (case-insensitive),
# tolerating any markdown-injected `id="…"` the toc extension already added.
_TRACK_HEADING_RE = re.compile(
    r'(<h[23])\b([^>]*?)>\s*Track\s+(\d+)\b',
    re.IGNORECASE,
)
_ID_ATTR_RE = re.compile(r'\s+id="[^"]*"')


def _stabilize_track_anchors(html: str) -> str:
    """Override the toc-generated slug on every Track heading with a stable
    `id="track-N"` so the report's `#track-{n}` deep-links land exactly.

    Idempotent w.r.t. the toc extension: we strip any existing `id="…"` the
    extension injected on that same tag and replace it with `track-N`.
    """

    def _repl(m: re.Match) -> str:
        tag, attrs, n = m.group(1), m.group(2), m.group(3)
        attrs = _ID_ATTR_RE.sub("", attrs)  # drop the toc slug on this heading
        return f'{tag} id="track-{n}"{attrs}>Track {n}'

    return _TRACK_HEADING_RE.sub(_repl, html)


def _flatten_toc(tokens: list) -> list:
    """Flatten the markdown toc tree into [(level, id, name), …] in doc order."""
    out: list = []

    def _walk(nodes):
        for node in nodes or []:
            out.append((node.get("level"), node.get("id"), node.get("name") or ""))
            _walk(node.get("children"))

    _walk(tokens)
    return out


def _build_doc_toc(toc_tokens: list) -> str:
    """Build the left-sidebar TOC nav HTML from the doc's heading tree.

    - An "Overview / top" link first (jumps to #top on the H1).
    - For Track headings ("Track N — Label") → a tidy "N · Label" link to the
      STABLE `#track-N` anchor (matches `_stabilize_track_anchors`).
    - For every other H2/H3 → a link to its toc slug. H3s are indented.
    A document with no headings yields just the "top" link.
    """
    links: list[str] = ['<a class="toc-top" href="#top">Overview / top</a>']
    track_re = re.compile(r"^\s*Track\s+(\d+)\s*[—\-:]\s*(.*)$", re.IGNORECASE)

    for level, slug, name in _flatten_toc(toc_tokens):
        if level == 1:
            continue  # the H1 is the "top" link
        if level not in (2, 3):
            continue
        m = track_re.match(name)
        if m:
            n, label = m.group(1), m.group(2).strip()
            href = f"#track-{n}"
            text = f"{n} · {label}" if label else f"Track {n}"
            cls = "toc-track"
        else:
            href = f"#{slug}"
            text = name.strip()
            cls = "toc-h2" if level == 2 else "toc-h3"
        links.append(f'<a class="{cls}" href="{href}">{_html_escape(text)}</a>')

    return "\n".join(links)


def _render_doc_html(md_text: str, path: str) -> str:
    """Render markdown to a styled, dark-theme HTML page consistent with the
    Explorer. Two-column docs layout: a sticky left TOC sidebar + a wide content
    column. Reuses /styles.css design tokens; falls back to a <pre> block if the
    `markdown` package isn't installed."""
    toc_html = ""
    try:
        import markdown as _md

        # `extra` gives tables + attr_list + fenced_code; `toc` auto-adds heading
        # `id`s and exposes the heading tree on `md.toc_tokens`.
        md = _md.Markdown(
            extensions=["extra", "toc", "sane_lists"],
            output_format="html5",
        )
        body = md.convert(md_text)
        # Stable per-track anchors so the report can deep-link (overrides toc slug).
        body = _stabilize_track_anchors(body)
        toc_html = _build_doc_toc(getattr(md, "toc_tokens", []) or [])
    except Exception:
        # No markdown package (or render error) → safe, readable raw fallback.
        body = f"<pre class='doc-raw'>{_html_escape(md_text)}</pre>"
        toc_html = '<a class="toc-top" href="#top">Overview / top</a>'

    title = path.rsplit("/", 1)[-1]
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title} — Quiver Capability Explorer</title>
<link rel="icon" href="/favicon.ico" />
<link rel="stylesheet" href="/styles.css" />
<script>
  (function () {{
    try {{
      var s = localStorage.getItem("qx-theme");
      var t = s || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
      document.documentElement.setAttribute("data-theme", t);
    }} catch (e) {{}}
  }})();
</script>
<style>
  html {{ scroll-behavior: smooth; }}
  body {{ background: var(--bg); background-image: var(--bg-grad); background-attachment: fixed; }}
  /* two-column docs layout: sticky TOC sidebar + wide content column */
  .doc-layout {{
    display: grid; grid-template-columns: 256px minmax(0, 1fr); gap: 40px;
    max-width: 1320px; margin: 0 auto; padding: 24px 32px 96px; align-items: start;
  }}
  .doc-side {{ position: sticky; top: 18px; align-self: start; max-height: calc(100vh - 36px); display: flex; flex-direction: column; }}
  .doc-back {{
    display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600;
    color: var(--text-muted); background: var(--surface); border: 1px solid var(--border);
    border-radius: 999px; padding: 6px 13px; margin-bottom: 16px; transition: border-color .14s, color .14s;
    align-self: flex-start;
  }}
  .doc-back:hover {{ color: var(--text); border-color: var(--accent); text-decoration: none; }}
  .doc-toc {{
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 12px 10px; overflow-y: auto; min-height: 0;
  }}
  .doc-toc::-webkit-scrollbar {{ width: 9px; }}
  .doc-toc::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 9px; border: 2px solid var(--surface); }}
  .doc-toc .toc-label {{
    font-size: 10.5px; text-transform: uppercase; letter-spacing: .6px; color: var(--text-faint);
    font-weight: 700; padding: 4px 10px 8px;
  }}
  .doc-toc a {{
    display: block; padding: 6px 10px; border-radius: var(--radius-sm); font-size: 13px;
    color: var(--text-muted); border-left: 2px solid transparent; transition: background .14s, color .14s;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .doc-toc a:hover {{ background: var(--hover); color: var(--text); text-decoration: none; }}
  .doc-toc a.toc-top {{ color: var(--text); font-weight: 650; margin-bottom: 4px; }}
  .doc-toc a.toc-track {{ color: var(--text); }}
  .doc-toc a.toc-track::before {{ content: ""; }}
  .doc-toc a.toc-h3 {{ padding-left: 22px; font-size: 12.5px; }}

  .doc-main {{ min-width: 0; max-width: 960px; }}
  .doc-path {{
    font: 11.5px var(--mono); color: var(--text-faint); margin-bottom: 18px; word-break: break-all;
  }}
  .doc {{ color: var(--text); font-size: 15px; line-height: 1.72; }}
  .doc h1, .doc h2, .doc h3, .doc h4 {{ line-height: 1.3; letter-spacing: -.2px; margin: 1.8em 0 .6em; scroll-margin-top: 24px; }}
  .doc h1 {{ font-size: 29px; margin-top: 0; padding-bottom: .35em; border-bottom: 1px solid var(--border); }}
  .doc h2 {{ font-size: 22px; padding-bottom: .3em; border-bottom: 1px solid var(--border-soft); margin-top: 2.1em; }}
  .doc h3 {{ font-size: 17.5px; }}
  .doc h4 {{ font-size: 14.5px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .5px; }}
  .doc p {{ margin: .85em 0; }}
  .doc a {{ color: var(--accent); }}
  .doc ul, .doc ol {{ padding-left: 1.5em; margin: .7em 0; }}
  .doc li {{ margin: .32em 0; }}
  .doc code {{
    font: .88em var(--mono); background: var(--surface-3); border: 1px solid var(--border-soft);
    border-radius: 5px; padding: 1px 6px; word-break: break-word;
  }}
  .doc pre {{
    background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 14px 16px; overflow-x: auto; margin: 1em 0;
  }}
  .doc pre code {{ background: none; border: none; padding: 0; font-size: 12.5px; line-height: 1.55; }}
  .doc blockquote {{
    margin: 1em 0; padding: 4px 16px; color: var(--text-muted);
    border-left: 4px solid var(--accent); background: var(--surface-2); border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  }}
  .doc table {{ width: 100%; border-collapse: collapse; margin: 1.1em 0; font-size: 13.5px; display: block; overflow-x: auto; }}
  .doc th, .doc td {{ padding: 8px 12px; border: 1px solid var(--border); text-align: left; vertical-align: top; }}
  .doc th {{ background: var(--surface-3); color: var(--text); font-weight: 700; }}
  .doc tbody tr:nth-child(even) td {{ background: var(--surface-2); }}
  .doc hr {{ border: none; border-top: 1px solid var(--border); margin: 1.8em 0; }}
  .doc img {{ max-width: 100%; }}
  .doc-raw {{ white-space: pre-wrap; word-break: break-word; }}

  /* narrow / mobile: collapse the sidebar above the content (single column) */
  @media (max-width: 900px) {{
    .doc-layout {{ grid-template-columns: 1fr; gap: 18px; padding: 18px 18px 72px; }}
    .doc-side {{ position: static; max-height: none; }}
    .doc-toc {{ max-height: 240px; }}
    .doc-main {{ max-width: none; }}
    .doc {{ font-size: 14.5px; }}
  }}
</style>
</head>
<body>
<div class="doc-layout">
  <aside class="doc-side">
    <a class="doc-back" href="/">&larr; back to Explorer</a>
    <nav class="doc-toc" aria-label="Table of contents">
      <div class="toc-label">On this page</div>
      {toc_html}
    </nav>
  </aside>
  <main class="doc-main">
    <div class="doc-path">{path}</div>
    <article class="doc"><span id="top"></span>{body}</article>
  </main>
</div>
</body>
</html>"""


@app.get("/doc/{path:path}")
def get_doc(path: str, raw: bool = Query(False)) -> Response:
    """Serve a results/ or docs/ markdown file. By default renders it as a
    styled, dark-theme HTML page (consistent with the Explorer); `?raw=1`
    returns the original markdown text. Path-traversal-safe either way."""
    target = _resolve_doc(path)
    text = target.read_text(encoding="utf-8")
    if raw:
        return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")
    return HTMLResponse(_render_doc_html(text, path))


# ----------------------------- frontend (same-origin → no CORS) -----------------------------

def _serve_frontend(name: str, media_type: str) -> FileResponse:
    f = FRONTEND / name
    if not f.is_file():
        raise HTTPException(404, f"{name} not found (frontend not built yet)")
    return FileResponse(str(f), media_type=media_type)


@app.get("/")
def index() -> FileResponse:
    return _serve_frontend("index.html", "text/html; charset=utf-8")


@app.get("/styles.css")
def styles() -> FileResponse:
    return _serve_frontend("styles.css", "text/css; charset=utf-8")


# Quiver-branded variant: a separate re-skin that reuses the SAME /app.js and
# /api/* backend, served at /quiver with its own stylesheet (/quiver.css). The
# main version (/, /styles.css) is untouched.
@app.get("/quiver")
def quiver_index() -> FileResponse:
    return _serve_frontend("quiver.html", "text/html; charset=utf-8")


@app.get("/quiver.css")
def quiver_styles() -> FileResponse:
    return _serve_frontend("quiver.css", "text/css; charset=utf-8")


@app.get("/app.js")
def app_js() -> FileResponse:
    return _serve_frontend("app.js", "text/javascript; charset=utf-8")


# Inline SVG favicon so browsers' automatic /favicon.ico probe doesn't 404.
_FAVICON = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    "<rect width='32' height='32' rx='7' fill='#5b9dff'/>"
    "<text x='16' y='22' font-size='18' font-family='Arial,sans-serif' "
    "font-weight='800' fill='white' text-anchor='middle'>Q</text></svg>"
)


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(content=_FAVICON, media_type="image/svg+xml")
