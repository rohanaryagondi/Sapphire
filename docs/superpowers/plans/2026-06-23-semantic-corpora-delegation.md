# Task Brief — Bucket-1 semantic agent knowledge corpora (the 12, dual-source)

**Owners: `hayes` (6) · `gavin` (6).** Tier: Feature epic (one PR per agent). Assigned 2026-06-23.
This is a replication task: the method is **proven and locked** on FDA Institutional Memory. You follow it
per agent. Build autonomously per `dev/CONTRIBUTOR_RULES.md`; open one PR per agent; Rohan's Claude
adversarially reviews + merges each.

## The goal
Each assigned Bucket-1 *semantic* agent gets a pre-ingested, queryable, dual-source knowledge corpus so a
runtime check hits the local corpus for the stable ~70% and only searches the novel ~30%. Grounded, cheaper,
faster — and every claim cited, dated, tiered.

## The authority — read these first, they ARE the spec
- **`sapphire-orchestrator/corpus/fda-institutional-memory/METHOD.md`** — the locked 6-step recipe. Follow it
  exactly; it tells you how to derive a per-agent lens, run both ingestion passes, organize, and self-check.
- **`sapphire-orchestrator/corpus/fda-institutional-memory/`** — the worked example (index.jsonl, notes/,
  manifest.md, QUERIES.md). Your output mirrors this shape.
- **`dev/validate-corpus.sh`** — the mandatory mechanical gate. Your corpus PR is not ready until it prints
  `✓ corpus validation CLEAN`.
- The agent's current spec: `architecture/bucket1/semantic/<agent>.md` (derive its lens + check types from it).

## Step 0 — ONE-TIME setup: browser + EMET sign-in (do this before your first corpus)
Both ingestion passes need a working browser, and Pass B needs an **authenticated** EMET session. Do this once
per machine, at the very start:
1. **Install the Playwright browser MCP** so you have `browser_navigate` / `browser_evaluate` etc.:
   ```
   claude mcp add playwright npx '@playwright/mcp@latest'      # registers the Playwright MCP server
   npx playwright install chromium                              # installs the actual browser binary
   ```
   (If `browser_navigate` is already available in your session, the MCP is installed — skip to step 2.)
   Verify by navigating to any page; if the browser tools aren't present after this, post in `dev/HELP.md`.
2. **Open EMET in the browser:** `browser_navigate` to **`https://emet.benchsci.com/`**.
3. **Ask your human operator to sign in.** You will land on the BenchSci login (`id.summit.benchsci.com`).
   **Do NOT attempt to log in yourself** (no credential handling by the agent). Tell your operator, verbatim:
   > "I've opened the BenchSci/EMET login in the Playwright browser. Please **sign in** — or **sign up with
   >  your `.edu` email** if you don't have an account — then tell me when you're done."
   Then **wait**. When they confirm, `browser_navigate` to `https://emet.benchsci.com/` again and verify the
   page title is **"Chat · EMET"** (not the sign-in page). If it still shows the login wall, the session didn't
   take — ask them to retry; do not proceed to Pass B until it lands on the app.
4. The session persists for the browser's lifetime — you only re-do this if EMET later bounces you to the login
   wall mid-build (if so, stop that EMET query, ask your operator to re-sign-in, and continue).

Pass A (browser primary + web) works without any login; only Pass B (EMET) needs the sign-in above.

## Per-agent procedure (one branch `<handle>/corpus-<agent>`, one PR)
1. **Derive the lens** from the agent's spec (METHOD Step 1) — each agent's claim-card fields differ:
   - `patent-ip`: patent_no · assignee · claims_scope · priority/expiry · target/molecule · status (granted/litigated/IPR)
   - `clinical-trial-registry`: nct_id · phase · status · indication · endpoints · sponsor · result/why-stopped
   - `post-market-safety`: drug · adverse_event · signal · action (label/REMS/withdrawal) · date  ← **EMET-central**
   - `payer-market-access`: payer/body · drug · decision (cover/restrict/reject) · ICER/$ · rationale · date
   - `manufacturing-cmc`: issue type · 483/warning-letter/CRL-CMC · facility/modality · date · resolution
   - `dea-scheduling`: substance · schedule · action · date · rationale
   - `global-regulatory-divergence`: agency (EMA/PMDA/MHRA/NMPA) · drug · decision vs FDA · date · reason
   - `financial-investor`: program/company · event (raise/M&A/milestone/writeoff) · figure · date · source
   - `kol-social-signal`: KOL/venue · position · target/drug · date  (public posts/talks only)
   - `patient-advocacy`: group · position/ask · indication · date
   - `policy-legislative`: bill/rule · status · effect on CNS dev/pricing · date
   - `reputational-institutional`: actor · event · reputational signal · date
2. **Pass A — browser + web (→ T1 / T2).** Per METHOD Step 3 Pass A: drive the **shared Playwright browser**
   to load the *authoritative primary* for the domain (e.g. patents → patents.google.com/USPTO; trials →
   clinicaltrials.gov; safety → FDA FAERS/safety pages; payer → CMS/ICER; global → EMA/PMDA) and set `tier:"T1"`
   ONLY when you loaded the primary and quote a **verbatim substring**. Secondary/press = T2. A 404 = repoint;
   a blocked-but-correct primary = `"unverifiable_by_fetch": true`.
3. **Pass B — EMET (→ T2, `emet-live`).** Per METHOD Step 3 Pass B. Requires the **Step 0** authenticated EMET
   session (page title "Chat · EMET", not the login wall — if it bounces to the login, get your operator to
   re-sign-in). Run a focused set of Thorough queries on your agent's key biomedical/class mechanisms; add
   `emet-live` T2 cards citing **real PMIDs** (`pubmed.ncbi.nlm.nih.gov/<pmid>/`).
   EMET yield varies by agent: **central for post-market-safety / clinical-trial-registry**; thinner for the
   pure regulatory/financial/policy ones — run it regardless, let the yield be honest, record gaps.
4. **Organize** (METHOD Step 5): `sapphire-orchestrator/corpus/<agent>/` → themed `notes/*.md` (cited+dated) +
   `index.jsonl` (claim-cards) + `manifest.md` (coverage map + honest gaps + EMET chat_urls) + `QUERIES.md`
   (~6 real checks answered from the corpus + explicit gaps).
5. **Upgrade the skill doc** `architecture/bucket1/semantic/<agent>.md` → corpus-first → search-the-gap
   operating spec (mirror the FDA-memory skill doc: query the local corpus first; search the gap live; cite +
   tier; for veto-class agents — patent-ip — a dispositive veto needs a T1 primary).
6. **Gate + report:** `bash dev/validate-corpus.sh sapphire-orchestrator/corpus/<agent>` → CLEAN. Write
   `dev/reports/<handle>/corpus-<agent>-report.md` (T1/T2 split, EMET queries + PMIDs, coverage, gaps, frank
   thinness). Open the PR.

## Sequencing — a mini pilot-gate per contributor
Ship your **first** corpus PR and **wait for Rohan's review/merge before batching the rest** — so any
method-misread is caught once, not six times. After your first is merged, proceed through the others
(one PR each). One PR open at a time.

## Anti-fabrication (absolute — from METHOD Step 4)
Every T1 = a primary you actually loaded + verbatim quote. Every EMET claim = a real PMID EMET returned,
faithful to (not overstating) the source. Public identifiers only ever leave Quiver (the `data_boundary`
guardrail still applies). Omit-and-flag over invent. Rohan's Claude will adversarially re-check your PMIDs and
T1 quotes before merge — fabrication or a misattributed citation fails the PR.

## Assignments
**Hayes (6):** `patent-ip` (veto-class) · `post-market-safety` · `clinical-trial-registry` ·
`payer-market-access` · `manufacturing-cmc` · `dea-scheduling`.
**Gavin (6):** `global-regulatory-divergence` · `financial-investor` · `kol-social-signal` ·
`patient-advocacy` · `policy-legislative` · `reputational-institutional`.

## Out of scope
Runtime wiring (the agent querying its corpus before web/EMET at run time) — that's a separate follow-up once
the corpora exist. The 13th (FDA Institutional Memory) is done — use it as your reference.
