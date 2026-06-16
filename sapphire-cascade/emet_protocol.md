# EMET Driving Protocol

Every agent that needs external evidence drives **EMET** (BenchSci) through the **shared Playwright
browser**. This is the single source of all external evidence in Sapphire Cascade. Follow it
exactly; it is written so any agent (or the standalone port) reproduces the same interaction.

App: `https://app.summit-prod.benchsci.com/` — signed in as the user (manual login at
`id.benchsci.com`). If a tab lands on the login page, **stop and ask the user to re-authenticate**;
never attempt to log in.

---

## Invariants (do not violate)

1. **Public identifiers only.** Gene symbols (SCN10A, TSC2), protein names (Nav1.8), SMILES,
   disease terms, trial IDs. **Never** enter Quiver proprietary EP/CRISPR/functional data, internal
   scores, candidate IDs (e.g. `QS00…`), or the synthetic moat list.
2. **Always leave base tab 0 open.** Each agent opens its **own** tab, works, and **closes only its
   own tab**. The browser must never be left with zero tabs (it would close the session).
3. **Mode = Thorough** for every substantive evidence query (multi-stage research). Use Balanced/Quick
   only for trivial confirmations, and only if explicitly noted.
4. **One agent drives at a time.** The browser is shared; the cascade runs agents sequentially.
5. **Cite everything.** Capture the EMET answer *and* the Sources panel. Evidence with no source is dropped.

---

## Step-by-step

### 0. Open a working tab
- `browser_tabs(action="new", url="https://app.summit-prod.benchsci.com/")`
- Confirm via `browser_tabs(action="list")` that base tab 0 is still present. Note your new tab index.
- If the page shows the EMET chat (`New Chat`, the "Ask anything or @mention" input), proceed.
  If it shows a login screen → **pause and ask the user to re-sign-in.**

### 1. Set mode to Thorough
- Click the mode button — a `button` whose accessible name is the *current* mode (`Balanced`,
  `Quick`, or `Thorough`). If it already reads **Thorough**, skip.
- In the menu, click the menuitem **"Thorough — Multi-stage research"**.
- The button should now read **Thorough**.
- **Note:** once a **Workflow** is attached (Step 2), the mode toggle is **disabled** — the workflow
  governs its own (already multi-stage) depth. So set Thorough *before* attaching a workflow, or skip
  it for workflow-driven queries. A fresh chat always defaults to **Balanced**, so set this each time.

### 2. (Optional) Select a Workflow
- Click the **"+"** button at the left of the input (icon-only `button`, opens a menu with
  `Upload File`, `Workflows`, `Experts`, `Prompt Templates`, `Output → Dashboard`).
- Hover/click **`Workflows`** to open the submenu. Available workflows:
  `Database Q&A`, `Drug Repurposing`, `Lead Discovery`, `Pathway Analysis`, `Drug Safety`,
  `Quantitative Evidence`, `Safety Assessment`, `Target Modulation`, `Target Validation`.
- Click the workflow matching the agent's need (see `ARCHITECTURE.md` §3).
- If a workflow runs a guided/multi-question flow, answer each step with public identifiers only.
- *Workflow selection is optional* — a well-formed Thorough chat query often suffices. Prefer the
  matching workflow when it exists; fall back to a plain typed query otherwise.

### 3. Submit the query
- Click the input ("Ask anything or @mention"), type the agent's evidence query (public identifiers only).
- Submit (click the send icon to the right of the input, or press Enter).

### 4. Wait for the multi-stage answer
- Thorough mode is multi-stage and slow. Poll with `browser_snapshot` / `browser_wait_for` until
  the streamed answer is complete (the stop/▍ indicator clears and a final answer + `Sources` panel
  render). Budget generously; do not read a half-streamed answer as final.

### 5. Read and extract
- Capture the **answer body** and the **Sources** panel (right side: "References will appear here"
  becomes a citation list). Capture the **Interactive Knowledge Graph** panel if relevant.
- Extract: the claim(s) the agent needs, each with its citation (author/title/venue/year/ID/URL),
  plus any explicit disagreement or uncertainty EMET flags.

### 6. Close the tab
- `browser_tabs(action="close", index=<your tab>)`.
- Verify base tab 0 remains via `browser_tabs(action="list")`.

### 7. Return structured evidence
Return to the orchestrator a compact JSON-like block, e.g.:

```json
{
  "agent": "L2-context-gate",
  "candidate": "GENE_SYMBOL",
  "emet_workflow": "Drug Safety",
  "verdict": "no_go | flag | pass",
  "evidence": [
    {"claim": "...", "source": "Author/Title, Venue Year", "id_or_url": "..."}
  ],
  "notes": "any contradiction / thin-evidence flags"
}
```

---

## Failure handling

| Symptom | Action |
|---|---|
| Login page appears | **Pause, ask the user to re-authenticate.** Do not attempt login. |
| Answer never completes / very long | Re-poll a few times; if still incomplete, capture partial + flag `evidence_incomplete`, move on. |
| Only one tab left (yours) | Do **not** close it; open a fresh tab first, then close the old one, so a tab always remains. |
| Workflow demands non-public input | Decline; answer only with public identifiers, or fall back to a plain typed query. |
| EMET returns nothing relevant | Record `no_evidence`; this feeds the uncertainty/abstention gate (thin evidence). |
