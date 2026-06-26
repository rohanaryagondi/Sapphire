#!/usr/bin/env python3
"""Capture a frontend2 (:8099) REPLAY run's SSE into the static-snapshot JSON shape.

profile=replay → bridge.replay(scenario): a frozen REAL capture, $0, no model/network.
Usage: python3 _build/capture_replay.py <out.json> [port] [scenario] ["query"]
"""
import json
import sys
import urllib.request

OUT = sys.argv[1]
PORT = sys.argv[2] if len(sys.argv) > 2 else "8098"
SCENARIO = sys.argv[3] if len(sys.argv) > 3 else "tsc2_emet_session"
QUERY = sys.argv[4] if len(sys.argv) > 4 else "Is TSC2 a viable target in tuberous sclerosis?"

url = f"http://127.0.0.1:{PORT}/api/run"
body = {"query": QUERY, "profile": "replay", "scenario": SCENARIO}
req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                            headers={"Content-Type": "application/json"})
events, buf = [], ""
with urllib.request.urlopen(req, timeout=300) as r:
    while True:
        chunk = r.read(2048)
        if not chunk:
            break
        buf += chunk.decode("utf-8", "replace")
        while "\n\n" in buf:
            frame, buf = buf.split("\n\n", 1)
            ev, dl = None, []
            for line in frame.split("\n"):
                if line.startswith("event: "):
                    ev = line[7:].strip()
                elif line.startswith("data: "):
                    dl.append(line[6:])
            if not ev or not dl:
                continue
            try:
                data = json.loads("\n".join(dl))
            except Exception:
                continue
            events.append({"event": ev, "data": data})
            tag = (f"{data.get('stage','')} {data.get('phase','')}"
                   if isinstance(data, dict) else "")
            sys.stderr.write(f"[{len(events):>3}] {ev:9} {tag}\n")

json.dump({"query": QUERY, "events": events, "status": "done"},
          open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
n_res = sum(1 for e in events if e["event"] == "result")
sys.stderr.write(f"captured {len(events)} events ({n_res} result) -> {OUT}\n")
