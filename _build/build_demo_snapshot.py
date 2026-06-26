#!/usr/bin/env python3
"""Bake a console's static page + a captured run into ONE self-contained HTML.

The output embeds the CSS, the JS, and the captured SSE events inline (no <link>, no
<script src>, no fetch, no server) so it opens with a double-click via file:// with zero
dependencies. The page's own app.js replay hook (window.SAPPHIRE_REPLAY) renders the run
through the exact same handlers the live UI uses — faithful, not a re-mock.

Usage:
  python3 _build/build_demo_snapshot.py \
      --static orchestrator_ui/static \
      --events docs/demo/8101_tsc2_run.events.json \
      --out    docs/demo/8101_tsc2_run.html \
      --title  "Sapphire Orchestrator — saved TSC2 run"
"""
import argparse
import json
import re
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--static", required=True, help="dir holding index.html + app.css + app.js")
ap.add_argument("--events", required=True, help="captured run JSON {query,events,status}")
ap.add_argument("--out", required=True)
ap.add_argument("--title", default="Sapphire — saved run")
ap.add_argument("--banner", default="Saved run — static snapshot (no server, no live model). "
                                     "This is a real captured run, replayed read-only.")
args = ap.parse_args()

static = Path(args.static)
html = (static / "index.html").read_text(encoding="utf-8")
css = (static / "app.css").read_text(encoding="utf-8")
js = (static / "app.js").read_text(encoding="utf-8")
run = json.loads(Path(args.events).read_text(encoding="utf-8"))

# --- sanity: the run must carry events (no silent empty snapshot) ---
events = run.get("events") or []
if not events:
    sys.exit(f"ERROR: {args.events} has no events — refusing to build an empty snapshot")
has_result = any(e.get("event") == "result" for e in events)
if not has_result:
    sys.stderr.write(f"WARNING: {args.events} has no 'result' frame — table/synthesis may be empty\n")

# --- guard: app.css must be self-contained (offline-openable) ---
for bad in re.findall(r"@import|url\(\s*['\"]?https?:", css):
    sys.exit(f"ERROR: app.css references an external asset ({bad!r}) — not offline-safe")

# NOTE: use FUNCTION replacements (lambda) everywhere — a string replacement would have
# re interpret backslash escapes inside the JS/CSS (e.g. `\d`, `\2022`) and crash.

# --- inline the stylesheet (replace the <link>), keep the data: favicon ---
style = f"<style>\n{css}\n</style>"
html, n_css = re.subn(r'<link[^>]+href="/static/app\.css"[^>]*>', lambda m: style, html)
if n_css != 1:
    sys.exit(f"ERROR: expected exactly 1 app.css <link>, found {n_css}")

# --- inline the script: embed the captured run, then the page's own JS (replay hook fires) ---
embed = ("<script>window.SAPPHIRE_REPLAY = "
         + json.dumps(run, ensure_ascii=False)
         + ";</script>\n<script>\n" + js + "\n</script>")
html, n_js = re.subn(r'<script[^>]+src="/static/app\.js"[^>]*></script>', lambda m: embed, html)
if n_js != 1:
    sys.exit(f"ERROR: expected exactly 1 app.js <script src>, found {n_js}")

# --- title + a small "saved snapshot" ribbon so a viewer knows it's frozen ---
title_tag = f"<title>{args.title}</title>"
html = re.sub(r"<title>.*?</title>", lambda m: title_tag, html, count=1)
ribbon = (
    '<div style="position:fixed;left:50%;transform:translateX(-50%);top:6px;z-index:9999;'
    'background:rgba(124,108,255,.12);color:#7c6cff;border:1px solid rgba(124,108,255,.35);'
    'border-radius:999px;padding:3px 12px;font:600 11px/1.4 -apple-system,system-ui,sans-serif;'
    'pointer-events:none;white-space:nowrap">📸 ' + args.banner + "</div>")
html = html.replace("<body>", "<body>\n" + ribbon, 1)

# --- guard: no /static/ refs survive (would 404 / break offline) ---
leftover = re.findall(r'(?:href|src)="/static/[^"]*"', html)
if leftover:
    sys.exit(f"ERROR: un-inlined /static/ refs remain: {leftover}")

out = Path(args.out)
out.write_text(html, encoding="utf-8")
kb = len(html.encode("utf-8")) / 1024
n_trace = sum(1 for e in events if e.get("event") == "trace")
print(f"wrote {out}  ({kb:.0f} KB, self-contained; {len(events)} events / {n_trace} trace, "
      f"result={'yes' if has_result else 'NO'})")
