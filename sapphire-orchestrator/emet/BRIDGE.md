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
{
  "id":    "<uuid>",
  "query": "<comprehensive multi-source prompt>",
  "gene":  "<str|null>",
  "genes": ["<gene1>", "<gene2>", ...],
  "ts":    "<iso8601>"
}
```

- `id`    — a fresh UUID the handler generates per request; the join key.
- `query` — a **COMPREHENSIVE MULTI-SOURCE PROMPT** (see §Comprehensive prompts below).
- `gene`  — the primary public candidate identifier (gene symbol / target term), or `null`.
- `genes` — ALL gene symbols in scope for this request (one-element for single-gene queries;
             the full set for multi-gene batched requests — see §Batching below).
- `ts`    — ISO-8601 UTC timestamp.

### `responses.jsonl` — the EMET (Claude-in-Chrome) session APPENDS one JSON per line

```json
{
  "id":        "<uuid>",
  "status":    "ok|empty|error",
  "evidence":  "<markdown str>",
  "citations": ["<str>", ...],
  "ts":        "<iso8601>"
}
```

- `id`        — **must equal** the request's `id`. A request is answered once its `id` appears here.
- `status`    — `ok` (evidence found), `empty` (no evidence), or `error` (EMET failed).
- `evidence`  — markdown summary of the cited evidence (only on `ok`). Passed through UNTRUNCATED.
- `citations` — list of public source strings (PMIDs / DOIs / URLs).
- `ts`        — ISO-8601 UTC timestamp.

---

## Comprehensive multi-source prompts

Every request's `query` field is built by `bridge_handler.build_emet_query()` — NOT a bare gene
symbol or BenchSci-only question. It instructs the EMET (Claude-in-Chrome) worker to use **ANY
source it judges useful**, including but not limited to:

| Source | What to look for |
|---|---|
| BenchSci LITERATURE | Assay/study evidence from the scientific literature (the primary EMET channel) |
| **GTEx** (expression atlas) | Tissue-level mRNA expression; CNS selectivity |
| **Human Protein Atlas (HPA)** | Protein/RNA expression; subcellular localization |
| **gnomAD** | pLI, LOEUF, missense Z — constraint metrics for druggability / safety |
| **ClinVar** | Pathogenic variants; clinical significance; variant frequency |
| **Reactome / STRING / KEGG** | Pathway membership; protein–protein interactions |
| **ClinicalTrials.gov** | Active/completed clinical trials; phase; indication |
| **MGI / IMPC** | Mouse knockout phenotypes; model-organism evidence |
| Any other public DB | Worker's discretion — any source relevant to the biological question |

The prompt asks for:
1. **Evidence FOR** — supporting biology (mechanism, expression, variant burden, preclinical / clinical)
2. **Evidence AGAINST** — negative data, safety signals, known liabilities
3. **Mechanistic context** — pathway membership, key interactors, disease-relevant phenotype
4. **Source attribution per claim** — PMID / DOI / URL / DB accession (never omit citations)

**Data boundary:** only public identifiers appear in the prompt — gene symbols, disease terms, SMILES.
Quiver internal EP/CRISPR data never enters the bridge queue.

---

## Multi-gene batching

When an engagement covers multiple gene symbols (e.g. a ranking / comparison query),
**the orchestrator sends ONE batched request covering all genes** — not one request per gene.

The `genes` field on the request carries the full gene list. `build_emet_query` produces a
single comprehensive prompt that tells the worker to survey all genes in one pass. This is
enforced mechanically: `emet-runner` is a single agent in `_BUCKET1_AGENTS` called once per
engagement; its inputs include `genes: [G1, G2, …]` from `live_engine.bucket1_inputs["genes"]`.

**EMET worker instruction in a multi-gene request:** *"This is a MULTI-GENE request covering N
targets (G1, G2, …). Survey all of them in a single pass — do NOT limit to one gene only."*

---

## Timeout + scaling

**Default base timeout: 900 s (15 min)** — generous for a real multi-source EMET sweep across
literature, expression atlases, constraint DBs, and clinical trials. Set
`$SAPPHIRE_EMET_BRIDGE_TIMEOUT_S` to override.

When multiple requests are pending in the queue (earlier requests are unanswered), the effective
timeout **scales up** to give the EMET worker time to finish them before the new one ages out:

```
effective_timeout = min(base + per_pending × (unanswered_count − 1), cap)
```

| Parameter | Value | Meaning |
|---|---|---|
| `base` | `$SAPPHIRE_EMET_BRIDGE_TIMEOUT_S` (default 900 s) | Per-request base |
| `per_pending` | 120 s | Added per additional unanswered request |
| `unanswered_count` | requests without a matching response line | Measured at request time |
| `cap` | 3600 s (1 h) | Hard ceiling — never blocks the firm indefinitely |

**Examples:**
- 1 pending request: `min(900 + 120×0, 3600)` = **900 s**
- 2 pending requests: `min(900 + 120×1, 3600)` = **1020 s**
- 25 pending requests: `min(900 + 120×24, 3600)` = 3780 → capped at **3600 s**

Implemented in `bridge_handler._scaled_timeout_s(requests_path, responses_path)`.

---

## Handler behaviour (`emet/bridge_handler.py::make_emet_bridge_handler`)

Returns a 2-arg `(contract, inputs)` callable — the same seam `emet.make_emet_handler` produces, so
it drops into `ctx["emet_handler"]` unchanged. On an EMET query it:

1. `mkdir -p` the bridge dir; build a **comprehensive multi-source prompt** via `build_emet_query`;
   append a request line with a fresh `id`, `gene`, `genes[]`, `query`, `ts`.
2. Count unanswered requests and compute the **scaled timeout** (formula above).
3. **Poll** `responses.jsonl` for the matching `id` (interval `~2s`, override
   `$SAPPHIRE_EMET_BRIDGE_POLL_S`) until it lands or the timeout elapses.
4. On a matching `status:"ok"` with a non-empty `evidence` body → return **cited T2 facts**
   (the evidence markdown passes through UNTRUNCATED + one fact per citation), provenance
   **`emet-live-bridge`** — honesty-guarded, only what the response holds.
5. On **timeout / `error` / `empty` / blank evidence** → **honest abstain**: a schema-valid findings
   envelope with an **empty** `facts` list and provenance `emet-live-bridge`. No fabricated facts.
6. **Never raises** — any I/O or filesystem failure degrades to the same honest abstain.

---

## How the EMET session answers a request (operator loop)

1. Tail `RohanOnly/emet_bridge/requests.jsonl` for a new line.
2. Read `query` (the comprehensive multi-source prompt) + `gene`/`genes`. In your
   **already-authenticated BenchSci tab and any other public DB tab**, run the requested
   survey across all named sources.
3. Append one line to `responses.jsonl` with the **same `id`**:
   - real cited evidence → `status:"ok"`, `evidence` markdown (comprehensive, untruncated),
     `citations` (public PMIDs / DOIs / URLs — as many as found; include non-literature sources);
   - genuinely nothing found → `status:"empty"`;
   - the workflow failed → `status:"error"`.
4. **Never fabricate.** Public identifiers only in both directions (data-boundary rule).
5. For **multi-gene requests**: cover ALL genes named in `genes[]` in a single response.

---

## Wiring / env flags

Wired in `live_engine.py::_wire_emet_handler` (setdefault semantics preserved):

| Env flag | Default | Effect |
|---|---|---|
| `SAPPHIRE_EMET_BRIDGE` | *(off)* | `1`/`true`/`yes` → install the **file-bridge** handler in `run_live`. Default OFF keeps the existing Playwright-runner path unchanged. A caller-supplied `ctx["emet_handler"]` always wins. |
| `SAPPHIRE_EMET_BRIDGE_DIR` | `RohanOnly/emet_bridge/` | Shared queue directory. |
| `SAPPHIRE_EMET_BRIDGE_TIMEOUT_S` | `900` | Base poll timeout in seconds (floor `5`; bad value → default). Scales up per §Timeout above. |
| `SAPPHIRE_EMET_BRIDGE_POLL_S` | `2` | Poll interval in seconds (floor `0.05`). |

---

## Honesty / data boundary

- **Public identifiers only** cross to EMET — the `query`/`gene`/`genes` are built from the run's public
  inputs (gene symbols, target/disease terms, SMILES). Quiver internal EP/CRISPR data never enters the queue.
- Facts are **cited T2** and carry provenance `emet-live-bridge` (external plane) so a bridge fact is
  always distinguishable in the trace from a Playwright-driven `emet-live` fact.
- Timeout / empty / error → **honest abstain** (zero facts), never a fabricated fact or citation.
- The full evidence body passes through **UNTRUNCATED** — no summary or truncation in the pipeline.
- Honest abstain ONLY on real timeout or a genuinely empty / error response — never on partial evidence.
