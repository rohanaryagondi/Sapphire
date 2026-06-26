#!/usr/bin/env python3
"""Capture a real :8101 orchestrator run's SSE stream into a JSON the static snapshot replays.

Usage: python3 _build/capture_8101_run.py <out.json> [port] ["query"]

POSTs the query to the running orchestrator_ui server (/api/run), parses every SSE frame
into {"event", "data"}, and writes {"query","events","status"} — the exact shape the replay
hook in static/app.js consumes. No fabrication: these are the frames the live UI would render.
"""
import json
import sys
import urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else "_build/8101_run.json"
PORT = sys.argv[2] if len(sys.argv) > 2 else "8110"
QUERY = sys.argv[3] if len(sys.argv) > 3 else (
    "Rank these genes by how strongly knocking each one down reverses the "
    "TSC2-KO / mTORC1-hyperactivation phenotype. For each gene weigh the evidence "
    "FOR vs AGAINST (mechanism, pathway, toxicity, expression, essentiality, genetics). "
    "Genes: BCL2, VPS54, KMT2D, DPM2, RPS3, FZD7, SSU72, DIDO1, ACTR3, CDK9, NCOA6, "
    "SMARCE1, SAP18, MTOR, PSMD13"
)

url = f"http://127.0.0.1:{PORT}/api/run"
req = urllib.request.Request(
    url, data=json.dumps({"query": QUERY}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

events = []
buf = ""
with urllib.request.urlopen(req, timeout=1800) as r:
    while True:
        chunk = r.read(2048)
        if not chunk:
            break
        buf += chunk.decode("utf-8", "replace")
        while "\n\n" in buf:
            frame, buf = buf.split("\n\n", 1)
            ev, data_lines = None, []
            for line in frame.split("\n"):
                if line.startswith("event: "):
                    ev = line[7:].strip()
                elif line.startswith("data: "):
                    data_lines.append(line[6:])
            if not ev or not data_lines:
                continue
            try:
                data = json.loads("\n".join(data_lines))
            except Exception:
                continue
            events.append({"event": ev, "data": data})
            tag = data.get("type") if isinstance(data, dict) else ""
            sys.stderr.write(f"[{len(events):>3}] {ev:7} {tag}\n")
            sys.stderr.flush()

json.dump({"query": QUERY, "events": events, "status": "done"},
          open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
n_trace = sum(1 for e in events if e["event"] == "trace")
n_result = sum(1 for e in events if e["event"] == "result")
sys.stderr.write(f"\ncaptured {len(events)} events ({n_trace} trace, {n_result} result) -> {OUT}\n")
