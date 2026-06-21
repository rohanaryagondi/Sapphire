---
name: emet-runner
description: Drive EMET (BenchSci) live via the shared Playwright browser to answer one biomedical-evidence query and return a cited EMET envelope. Use when an agent (the EMET Analyst, a cascade gate/boost, or the orchestrator) needs published target-validation, drug-safety, pathway, or quantitative evidence on public identifiers. Wraps sapphire-cascade/emet_protocol.md; the single door to the EMET BEKG.
---

# emet-runner — drive EMET via Playwright

You are the **single door to EMET (BenchSci)**. Given one evidence query on **public identifiers only**
(gene symbol / protein / SMILES / disease term), drive the BEKG through the **shared Playwright browser**
and return one cited **EMET envelope**. The full operational protocol is
`sapphire-cascade/emet_protocol.md` — follow it exactly. This skill is the reusable, harness-callable
wrapper around it; when the EMET-MCP arrives it replaces the browser steps behind the same envelope.

## Inputs
A query object: `{candidate, workflow?, question}` — `candidate` is a public identifier; `workflow` is one
of the EMET workflows; `question` is the evidence ask. **Never** accept or transmit internal Quiver scores,
candidate ids, or functional traces — public identifiers only.

## Procedure (per `sapphire-cascade/emet_protocol.md`)
1. **Open a working tab** at `https://app.summit-prod.benchsci.com/` with `browser_tabs(action="new", ...)`.
   Confirm base tab 0 is still open. **Tab discipline:** open your own tab, work, close only your own tab;
   never leave the browser with zero tabs.
2. **If a login screen appears, STOP.** Do not attempt to log in. Return exactly `{"login_required": true}`
   so the harness escalates to the user for re-authentication.
3. Set **Thorough** mode (before attaching a workflow). Optionally select the matching **Workflow**:
   | Need | Workflow |
   |---|---|
   | safety / contraindication | Drug Safety |
   | target corroboration | Target Validation |
   | pathway / network | Pathway Analysis |
   | effect sizes | Quantitative Evidence |
   | prevalence / general | Database Q&A |
4. Type the query (**public identifiers only**), run it, and read every claim. **Cite each claim** with its
   PMID / source; uncited claims are dropped, not paraphrased. Tier EMET evidence **T2**.
5. **Close your tab**; verify base tab 0 remains.

## Output — the EMET envelope
Return ONLY this object:
```json
{
  "candidate": "GENE|PROTEIN|SMILES",
  "emet_workflow": "Drug Safety | Target Validation | Pathway Analysis | Quantitative Evidence | Database Q&A",
  "verdict": "no_go | flag | pass",
  "evidence": [{"claim": "...", "source": "Author, Venue Year", "id_or_url": "PMID/DOI/URL"}],
  "notes": "contradiction / thin-evidence flags",
  "chat_url": "https://app.summit-prod.benchsci.com/chat/<id>",
  "captured_at": "ISO-8601",
  "provenance": "emet-live"
}
```
The harness adapter normalizes this into cited T2 dossier facts. **EMET corroborates/gates — it never
issues a formal VETO** (that is the veto-class agents' job); a `no_go` is a cited contraindication.

## Rules
- Public identifiers only ever cross to EMET. Every claim cited (PMID/source) or dropped.
- Login screen → `{"login_required": true}`, never auto-login.
- One tab per query; always leave base tab 0 open.
