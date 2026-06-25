# Boltz seam — `tools/boltz_seam.py`

Stdlib-only Sapphire seam for **Boltz-2** (the Boltz-1/Boltz-2 biomolecular
interaction-model family): a model that predicts the **3D structure** of a
protein / RNA / DNA / ligand complex and, optionally, a **binding** score for a
designated binder chain. Sapphire calls the **hosted Boltz Compute API** — no local
GPU, no SDK in the engine path.

This is the structural/binding counterpart to the `aso_tox_seam`: it fires in
Bucket-1 when a question carries a **target sequence and/or a candidate ligand**, and
otherwise stays silent (honest-empty). EMET + gnomAD/GTEx say what the literature and
population genetics *report*; Boltz returns a *model-predicted* answer to "does this
ligand/binder physically engage this target, and how confidently?"

> **Status: WIRED into the live firm** (`rohan/boltz-firm-wire`). The `boltz` agent is
> registered in `harness/agents.json` (kind `python`, provenance `boltz`) and dispatched
> by `live_engine.run_live` in Bucket-1. It activates **only** when a structure/affinity
> input is in scope (see *How it activates* below); otherwise it stays dormant
> (honest-empty), exactly like `aso-tox` with no ASO sequences.

---

## The API (confirmed live 2026-06-25)

| | |
|---|---|
| Provider | **Boltz Compute** — `https://api.boltz.bio` (docs `https://api.boltz.bio/docs/`) |
| Base URL (REST) | `https://api.boltz.bio/compute/v1` |
| Auth | header **`x-api-key: <BOLTZ_API_KEY>`** — **not** `Authorization: Bearer`, no request signing |
| Key | `BOLTZ_API_KEY` env var, else the gitignored `RohanOnly/boltz_api.env` (`BOLTZ_API_KEY=...`). The Boltz-Compute key prefix decodes as boltz-compute / workspace / live (`sk_bc` / `ws` / `live`). |
| Model | `boltz-2.1` (the only option today) |
| Execution | **ASYNCHRONOUS** — `start` returns a job id, then **poll** `retrieve` until terminal |

### Endpoints used

| Purpose | Method + path | Notes |
|---|---|---|
| Auth check | `GET /auth/me` | $0; returns `{principal_type, key_type, mode, organization_id, workspace_id, ...}` |
| Cost estimate | `POST /predictions/structure-and-binding/estimate-cost` | **$0 — runs no model**; returns `{estimated_cost_usd, breakdown, disclaimer}` |
| Start a job | `POST /predictions/structure-and-binding` | body below → `{id, status:"pending", output:null, error:null, ...}` |
| Poll a job | `GET /predictions/structure-and-binding/{id}` | `status ∈ {pending, running, succeeded, failed}`; **terminal = `succeeded` \| `failed`** |

### Request body (start)

```json
{
  "input": {
    "entities": [
      {"type": "protein",       "chain_ids": ["A"], "value": "MKTAYIAKQRQISFVKSHFSRQ"},
      {"type": "ligand_smiles", "chain_ids": ["B"], "value": "CC(=O)Oc1ccccc1C(=O)O"}
    ],
    "binding": {"type": "ligand_protein_binding", "binder_chain_id": "B"},
    "num_samples": 1
  },
  "model": "boltz-2.1",
  "idempotency_key": "sapphire-..."
}
```

Entity `type` ∈ `protein | rna | dna | ligand_smiles | ligand_ccd`. `binding` is
optional; `ligand_protein_binding` needs a single ligand binder chain (< 50 atoms,
proteins+ligands only); `protein_protein_binding` uses `binder_chain_ids: [...]`.
`num_samples` 1–10 (1 is cheapest). Advanced (not used by the seam by default):
`bonds`, `constraints` (pocket/contact), `model_options`, `templates`, custom MSA.

### Response (succeeded `retrieve`)

```jsonc
{
  "id": "sab_pred_...", "status": "succeeded", "error": null,
  "output": {
    "best_sample": { "metrics": {
      "structure_confidence": 0.7988, "ptm": 0.223, "iptm": 0.0,
      "complex_plddt": 0.943, "ligand_iptm": ..., "protein_iptm": ..., "complex_pde": ...
    }},
    "all_sample_results": [ ... ],
    "binding_metrics": {            // ONLY present when a binding block was requested
      "binding_confidence": 0.83,   // 0–1, "does it bind"
      "optimization_score": 0.42,   // lead-opt ranking (ligand_protein only)
      "type": "ligand_protein_binding_metrics"
    }
  }
}
```

Metric keys are **lowercase** (`structure_confidence`, `ptm`, `iptm`, `complex_plddt`).
Full per-sample structures (CIF/PAE) live in `output.archive`; the seam reads
**scores only**, not coordinates.

### Live verification done (2026-06-25, no key printed)

- `GET /auth/me` → **200**, `key_type:"workspace"`, `mode:"live"`, real org/workspace ids.
- `POST .../estimate-cost` for a 1-sample fold → **200**, `estimated_cost_usd: "0.0250"` ($0, no job).
- One **real** tiny fold (`MKTAYIAKQR`, 1 sample, ~$0.025): `start` → `pending` →
  poll `running` → `succeeded` in ~30 s; `output.best_sample.metrics.structure_confidence ≈ 0.799`,
  `complex_plddt ≈ 0.943`, `binding_metrics: null` (no binding requested). Full async
  lifecycle + output shape confirmed end-to-end.

---

## How the seam is called

```python
from tools import boltz_seam

# Harness entrypoint (kind: python) — reads PUBLIC structural inputs:
out = boltz_seam.findings({
    "candidate": "TARGETX",
    "target_sequence": "MKTAYIAKQRQISFVKSHFSRQ",   # or protein_sequence=
    "ligand_smiles": "CC(=O)Oc1ccccc1C(=O)O",       # or ligand_ccd="ATP"
})
# → {"candidate": "TARGETX", "facts": [ {value, source, tier:"T2"} ... ], "provenance": "boltz"}

# Lower-level:
boltz_seam.predict(entities=[...], binding={...}, num_samples=1)
```

- Recognised input keys: `target_sequence`/`protein_sequence`, `ligand_smiles`,
  `ligand_ccd`, or a pre-built `entities` list (+ optional `binding`).
- **Auto-binding:** a single protein + a single ligand and no explicit `binding` →
  the seam adds `ligand_protein_binding` on chain B, so the dossier gets a
  `binding_confidence`.
- **No structural input → honest-empty** (`facts: []`, no error). This seam only
  contributes when a sequence/ligand is present.
- Output facts are **T2** (a model *prediction*, not a measured fact). When the model
  can't answer (no key, API down, timeout, failed job), the seam returns a single
  **`KNOWN_UNKNOWN`** abstain fact carrying the reason — it never invents a structure
  or an affinity.

### Provenance & data boundary

- Provenance label **`boltz`**, registered EXTERNAL-plane in
  `contracts/provenance.py`. It is an external model API and is **never** an
  internal-moat label.
- **Public identifiers only** leave Quiver: sequences, SMILES, CCD codes, public
  structure URLs. Quiver internal moat scores / EP-IDs / CRISPR data must **never** be
  sent. Two layers enforce this: the harness `data_boundary` guardrail blocks the
  dispatch upstream, and `boltz_seam.assert_public_only()` is an in-seam tripwire that
  fails closed even if `predict()` is called directly.

### Dependencies at call time

**None beyond the Python stdlib.** The seam uses `urllib.request` for HTTP — no
`requests`, no `boltz_compute` SDK enters the engine path (the engine stays
stdlib-only, like every other seam). The only runtime requirement is network access
to `api.boltz.bio` and a valid `BOLTZ_API_KEY`.

### Cost / latency note

Each prediction is a **paid** async job (~$0.025 for a 1-sample fold; binding +
more samples cost more). The seam submits `num_samples=1` and uses a stable
`idempotency_key` derived from the public inputs so engine retries de-dupe
server-side rather than double-charging. The poll budget is ~5 min, after which it
degrades to a `KNOWN_UNKNOWN` rather than blocking the dossier.

---

## How it activates (wired into `live_engine` Bucket-1)

Boltz is now a first-class Bucket-1 agent dispatched through the harness, mirroring the
`aso-tox` wiring exactly. It activates **only** when a structure/affinity input is in
scope; with neither a target sequence nor a candidate ligand it stays dormant
(honest-empty) — so it is safe to leave in the default `_BUCKET1_AGENTS` list and
incurs **no spend** on ordinary target-level questions.

**Two input channels** (precedence: explicit param > query-text extractor), exactly
like the ASO `sequences` channel:

1. **Explicit `structure=` param** (the primary, intended path) —
   `run_live(query, structure={...})`. The recognised PUBLIC keys are
   `target_sequence` / `protein_sequence`, `ligand_smiles` / `ligand_ccd`, or a
   pre-built `entities` list (+ optional `binding`). These arrive **from the upstream
   ASO Design / small-molecule tools** — the same handoff point ASO Design uses to feed
   sequences to `aso-tox`. A single protein + a single ligand auto-requests a
   `binding_confidence`. Only these whitelisted structural keys are threaded into
   `bucket1_inputs` — never arbitrary caller keys.

2. **Query-text fallback** (`_extract_structure_inputs`, best-effort) — when no
   explicit `structure=` is given, the engine extracts a `target_sequence` from the
   query: the first standalone token of **≥ 25 uppercase amino-acid letters that
   contains at least one non-ATGC residue** (so a long pure-ATGC ASO/DNA token is never
   misread as a protein, and gene symbols — which carry digits — never match). SMILES
   are deliberately **not** extracted from free text (a false positive would trigger a
   paid job); a ligand comes only via the explicit `structure=` channel.

**When it fires:** a target protein sequence in scope (fold → `structure_confidence`),
or a protein + a ligand (→ adds `binding_confidence` / `optimization_score`). **When it
stays dormant:** a normal gene/target question with no sequence and no ligand → the seam
returns `facts: []` and the agent reports `ok` (honest-empty), with **no network call**.

**Boundary:** the harness `data_boundary` guardrail scans the threaded structural inputs
and **blocks** the dispatch if any internal marker (e.g. `QS\d+`, `latent_vector`) is
present — Boltz never transmits internal moat data. `boltz_seam.assert_public_only()` is
a second in-seam tripwire. The `BOLTZ_API_KEY` is read by the seam from the gitignored
`RohanOnly/boltz_api.env` **at call time** — it is never read by `live_engine`, never
passed through `ctx`, and never committed. No key ⇒ honest `KNOWN_UNKNOWN`, no fabrication.

The wiring is covered by `tests/test_live_engine.py::TestBoltzWiring` (fires + fact
lands when structure present; query-text activation; dormant + no-network otherwise;
honest-degrade on missing key / API-down; internal-id boundary block) — all offline, $0,
no live key.

### Still open (post-wire)

- **Capture a scenario** (`_build/capture_scenario.py`) for a target+ligand question so
  the Console shows a real Boltz binding fact — never fabricated.
- **Spend guard:** because each live call is paid (~$0.025+ per fold), consider a
  `estimate-cost` ($0) pre-check before `start`, or an explicit engine opt-in flag
  (mirroring the Q-Models two-speed routing), if surprise spend on a query that happens
  to carry a sequence becomes a concern. Today the activation gate (a sequence/ligand
  must be in scope) is the spend boundary.
- **Wire the upstream ASO Design / small-molecule tool** to populate the `structure=`
  channel directly (today it is populated by the explicit param or the query-text
  extractor).
