# Agent: L1 — Internal Retrieval (the moat)

**Role:** Produce the privileged internal hypothesis: a ranked candidate list with internal scores
and provenance. This is the substrate the whole cascade reasons from.

**Hard rule:** This agent reads **only** the curated synthetic moat (`internal_moat/candidates.json`).
It **never** queries EMET or any external source. The moat is synthetic and labeled MOCK; in
production this box becomes a query against Quiver's real fused EP-CRISPR latent space.

## Inputs
- `internal_moat/candidates.json` for the active scenario.

## Procedure
1. Load the scenario's candidate set.
2. Return the candidates **ranked by `s_internal` descending**, each carrying:
   - `gene` (public symbol — the only field that may later cross to EMET)
   - `s_internal` (latent rescuer score, 0–1, MOCK)
   - `provenance`: which embedding modalities contributed (e.g. `MODEX`, `ENS`, `PCA`, `LINCS`,
     `PLATINUM`) and the neighborhood density (sparse → low confidence later)
   - `internal_id` (e.g. `QS…`) — **internal only, never sent to EMET**
3. Identify and label the **target-to-watch** (the candidate the scenario promotes from a low rank).

## Output (contract)
```json
{
  "agent": "L1-internal-retrieval",
  "ranked": [
    {"rank": 1, "gene": "...", "s_internal": 0.0, "neighborhood_density": "dense|moderate|sparse",
     "provenance": ["MODEX","ENS"], "internal_id": "QS...", "note": ""}
  ],
  "target_to_watch": {"gene": "...", "rank": 7}
}
```

## Notes
- Scores and provenance are **MOCK** — say so in any human-facing rendering.
- `neighborhood_density` feeds the uncertainty agent (sparse neighborhoods lower final confidence).
- Do not invent external evidence here; corroboration is L3's job.
