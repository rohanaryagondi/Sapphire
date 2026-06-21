# EMET Driving Protocol

Every agent that needs external evidence drives **EMET** (BenchSci) through the **shared Playwright
browser**. This is the single source of all external evidence in Sapphire Cascade. Follow it
exactly; it is written so any agent (or the standalone port) reproduces the same interaction.

App: **`https://emet.benchsci.com/`** — signed in as the user (manual login via `id.summit.benchsci.com`;
SSO). A new chat gets its own URL **`https://emet.benchsci.com/chat/<uuid>`** (that is the `chat_url` to
capture). If a tab lands on the login page, **stop and ask the user to re-authenticate**; never attempt
to log in. *(Verified live 2026-06-21. The old `app.summit-prod.benchsci.com` host is retired.)*

The full live tool surface — **22 capabilities, 9 workflows, ~70 data sources, visualizations** — is
catalogued in [`emet_capabilities.md`](emet_capabilities.md). EMET capabilities are invoked by natural
language (no toggles); workflows by the `+` menu or by phrasing ("Run the Target Validation workflow for
SCN11A"). Interpretation stringency is set by phrasing ("Standard" / "High-Stringency" / "Exploratory").

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
- `browser_tabs(action="new", url="https://emet.benchsci.com/")`
- Confirm via `browser_tabs(action="list")` that base tab 0 is still present. Note your new tab index.
- If the page shows the EMET chat (`New Chat`, the "Ask anything or @mention" input), proceed.
  If it shows a login screen → **pause and ask the user to re-sign-in.**

### 1. Set the thinking level to Thorough
- The chat has a thinking-level control (a `button` whose label is the *current* level). A new chat
  defaults to **Balanced**. The three levels: **Quick** (single-step lookups) · **Balanced** (standard
  execution) · **Thorough** (multi-stage research).
- Click it and choose the menuitem **"Thorough — Multi-stage research"**. The button should read **Thorough**.
- In Thorough mode EMET runs an **agentic Research Plan**: it decomposes the question into steps, loads
  named **Skills** (e.g. *Gene Resolver (MyGene.info), ClinVar Variants, GWAS Associations, Open Targets
  Associations, PubMed Literature*), and queries multiple databases in parallel — so it is slow but
  thoroughly cited.
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
- The input is a **TipTap/ProseMirror** rich editor (`.tiptap > p`). Click it and type the agent's
  evidence query (public identifiers only).
- **Enter does NOT submit** (it inserts a newline). **Submit by clicking the send button** — the up-arrow
  icon to the right of the input (`button` containing `.lucide-arrow-up`). On submit the URL becomes
  `https://emet.benchsci.com/chat/<uuid>` — record it as `chat_url`.
- (If the `+` / Workflows menu is open, press `Escape` first; an open menu can swallow the send click.)

### 4. Wait for the multi-stage answer
- Thorough mode is multi-stage and slow. Poll with `browser_snapshot` / `browser_wait_for` until
  the streamed answer is complete (the stop/▍ indicator clears and a final answer + `Sources` panel
  render). Budget generously; do not read a half-streamed answer as final.

### 5. Read and extract
- The answer renders as **structured markdown** with **inline citations** like `[PMID 24013067]`, often
  in numbered sections (e.g. "Key Findings", "Caveats and Limitations"). The right rail has, as separate
  panels: **Sources** (the reference list — "References will appear here" fills in), **Interactive
  Knowledge Graph**, **Dashboard**, **Report**, and **Slides (SVG editor)**.
- Extract: the claim(s) the agent needs, each with its citation (PMID / author / title / venue / year /
  URL), plus any explicit disagreement or uncertainty EMET flags. (A finished answer's accessibility tree
  is large — prefer saving a snapshot to a file and grepping it, or a screenshot, over inlining the tree.)

### 6. Close the tab
- `browser_tabs(action="close", index=<your tab>)`.
- Verify base tab 0 remains via `browser_tabs(action="list")`.

### 7. Return structured evidence
Return to the orchestrator a compact JSON-like block, e.g.:

```json
{
  "candidate": "GENE_SYMBOL | PROTEIN | SMILES",
  "emet_workflow": "Drug Safety | Target Validation | Pathway Analysis | Quantitative Evidence | Database Q&A",
  "verdict": "no_go | flag | pass",
  "evidence": [
    {"claim": "...", "source": "Author/Title, Venue Year", "id_or_url": "PMID/DOI/URL"}
  ],
  "notes": "any contradiction / thin-evidence flags",
  "chat_url": "https://emet.benchsci.com/chat/<uuid>",
  "captured_at": "ISO-8601",
  "provenance": "emet-live"
}
```
This is exactly the envelope `contracts/schemas.py::EMET_ENVELOPE_SCHEMA` validates and the
`emet/adapter.py::normalize_emet` turns into cited **T2** dossier facts. (EMET corroborates/gates —
a `no_go` becomes a cited contraindication, **not** a formal `VETO`; veto is the veto-class agents' T1 job.)

---

## Failure handling

| Symptom | Action |
|---|---|
| Login page appears (`id.summit.benchsci.com`) | **Pause, ask the user to re-authenticate.** Do not attempt login. |
| Typed query won't send on Enter | Expected — Enter inserts a newline. Click the **up-arrow send button** (`.lucide-arrow-up`). |
| `+` / Workflows menu stuck open over the input | Press `Escape`, then click send. |
| Answer never completes / very long | Re-poll a few times; if still incomplete, capture partial + flag `evidence_incomplete`, move on. |
| Only one tab left (yours) | Do **not** close it; open a fresh tab first, then close the old one, so a tab always remains. |
| Workflow demands non-public input | Decline; answer only with public identifiers, or fall back to a plain typed query. |
| EMET returns nothing relevant | Record `no_evidence`; this feeds the uncertainty/abstention gate (thin evidence). |
