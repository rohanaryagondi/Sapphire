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

## NEXT steps — wiring into `live_engine` Bucket-1

The seam is built, contract-registered, and tested, but **not yet wired into the live
firm** (deliberately — mirrors how the ASO pieces landed incrementally). To fire it in
`live_engine.run_live`, mirror the `aso-tox` wiring exactly:

1. **Register the agent** in `harness/agents.json` (copy the `gnomad-constraint`
   entry): `id: "boltz"`, `kind: "python"`, `provenance_label: "boltz"`,
   guardrails `["facts_only_cited", "stamp_provenance", "data_boundary"]`,
   `tools_allowed: []`, and the same `output_schema` (it already matches the
   `{candidate, facts:[{value,source,tier[,flag]}], provenance, error?}` shape the
   seam emits). Set a generous `timeout_s` (the job is async; e.g. 360) and
   `retry.on_hard_fail: "abstain"`.

2. **Import + wire the fn** in `live_engine.py` (next to the other seams, ~L312):
   ```python
   from tools import boltz_seam
   ...
   if "boltz" not in ctx["python_fns"]:
       ctx["python_fns"]["boltz"] = boltz_seam.findings
   ```

3. **Thread the structural inputs** into `bucket1_inputs` (~L349): add
   `target_sequence` / `ligand_smiles` (or `ligand_ccd`) alongside the existing
   `sequences` key. These should arrive **from the upstream ASO Design / small-molecule
   tools** (the same way ASO sequences feed `aso-tox` today) — e.g. ASO Design emits a
   target sequence + candidate, which Boltz folds/scores. Until those tools feed
   structural inputs, Boltz returns honest-empty.

4. **Add `"boltz"` to `_BUCKET1_AGENTS`** so the dispatch loop runs it (it will
   honest-empty on non-structural questions, so it's safe to always include).

5. **Capture a scenario** (`_build/capture_scenario.py`) for a target+ligand question
   so the Console shows a real Boltz binding fact — never fabricated.

6. **Gating note:** because each call is paid, consider an engine flag (mirroring the
   Q-Models two-speed routing) so Boltz fires only when the question is genuinely a
   structure/binding question, or behind an explicit opt-in, to avoid surprise spend on
   every Bucket-1 pass. A `estimate-cost` pre-check ($0) before `start` is available if
   a spend guard is wanted.
