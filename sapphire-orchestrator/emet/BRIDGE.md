# EMET FILE-BRIDGE (WO-9) — live EMET without Playwright / auto-login

The detached-`claude -p` EMET runner (`emet/handler.py`) drives its **own** Playwright browser, so
it cannot reach the user's authenticated BenchSci session and fights the Chrome profile lock. The
**file bridge** takes a different path: a **separate Claude-in-Chrome session** — run by the user in
their already-authenticated browser — answers EMET requests through a shared file queue. Sapphire
never touches the browser; it only reads/writes two append-only files.

## Protocol

Shared directory: **`RohanOnly/emet_bridge/`** (gitignored under `RohanOnly/`; override with
`$SAPPHIRE_EMET_BRIDGE_DIR`). Two append-only JSON-lines files:

### `requests.jsonl` — Sapphire APPENDS one JSON per line

```json
{"id": "<uuid>", "query": "<str>", "gene": "<str|null>", "ts": "<iso8601>"}
```

- `id` — a fresh UUID the handler generates per request; the join key.
- `query` — the EMET question, built from **public inputs only** (question + candidate term).
- `gene` — the public candidate identifier (gene symbol / target term), or `null`.
- `ts` — ISO-8601 UTC timestamp.

### `responses.jsonl` — the EMET (Claude-in-Chrome) session APPENDS one JSON per line

```json
{"id": "<uuid>", "status": "ok|empty|error", "evidence": "<markdown str>", "citations": ["<str>", ...], "ts": "<iso8601>"}
```

- `id` — **must equal** the request's `id`. A request is answered once its `id` appears here.
- `status` — `ok` (evidence found), `empty` (no evidence), or `error` (EMET failed).
- `evidence` — markdown summary of the cited evidence (only on `ok`).
- `citations` — list of public source strings (PMIDs / DOIs / URLs).
- `ts` — ISO-8601 UTC timestamp.

## How the EMET session answers a request (operator loop)

1. Tail `RohanOnly/emet_bridge/requests.jsonl` for a new line.
2. Read `query` + `gene`. In your **already-authenticated BenchSci tab**, run the EMET workflow
   (per `sapphire-cascade/emet_protocol.md`) for that public identifier.
3. Append one line to `responses.jsonl` with the **same `id`**:
   - real cited evidence → `status:"ok"`, `evidence` markdown, `citations` (public PMIDs/DOIs only);
   - genuinely nothing found → `status:"empty"`;
   - the workflow failed → `status:"error"`.
4. **Never fabricate.** Public identifiers only in both directions (data-boundary rule).

## Handler behaviour (`emet/bridge_handler.py::make_emet_bridge_handler`)

Returns a 2-arg `(contract, inputs)` callable — the same seam `emet.make_emet_handler` produces, so
it drops into `ctx["emet_handler"]` unchanged. On an EMET query it:

1. `mkdir -p` the bridge dir; append a request line (fresh `id`).
2. **Poll** `responses.jsonl` for the matching `id` (interval `~2s`, override
   `$SAPPHIRE_EMET_BRIDGE_POLL_S`) until it lands or the **timeout** (`180s`, override
   `$SAPPHIRE_EMET_BRIDGE_TIMEOUT_S`, floor `5s`).
3. On a matching `status:"ok"` with a non-empty `evidence` body → return **cited T2 facts**
   (the evidence markdown + one fact per citation), provenance **`emet-live-bridge`** — honesty-
   guarded, only what the response holds.
4. On **timeout / `error` / `empty` / blank evidence** → **honest abstain**: a schema-valid findings
   envelope with an **empty** `facts` list and provenance `emet-live-bridge`. No fabricated facts.
5. **Never raises** — any I/O or filesystem failure degrades to the same honest abstain.

## Wiring / env flags

Wired in `live_engine.py::_wire_emet_handler` (setdefault semantics preserved):

| Env flag | Default | Effect |
|---|---|---|
| `SAPPHIRE_EMET_BRIDGE` | *(off)* | `1`/`true`/`yes` → install the **file-bridge** handler in `run_live`. Default OFF keeps the existing Playwright-runner path unchanged. A caller-supplied `ctx["emet_handler"]` always wins. |
| `SAPPHIRE_EMET_BRIDGE_DIR` | `RohanOnly/emet_bridge/` | Shared queue directory. |
| `SAPPHIRE_EMET_BRIDGE_TIMEOUT_S` | `180` | Poll timeout in seconds (floor `5`; bad value → default). |
| `SAPPHIRE_EMET_BRIDGE_POLL_S` | `2` | Poll interval in seconds (floor `0.05`). |

## Honesty / data boundary

- **Public identifiers only** cross to EMET — the `query`/`gene` are built from the run's public
  inputs (gene symbol, target/disease term). Quiver internal EP/CRISPR data never enters the queue.
- Facts are **cited T2** and carry provenance `emet-live-bridge` (external plane) so a bridge fact is
  always distinguishable in the trace from a Playwright-driven `emet-live` fact.
- Timeout / empty / error → **honest abstain** (zero facts), never a fabricated fact or citation.
