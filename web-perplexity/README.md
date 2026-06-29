# Sapphire — flagship web front end (Perplexity citation-forward)

The product-grade Sapphire console in the **Perplexity citation-forward** design language: a
custom **Next.js (App Router) + TypeScript (strict) + Tailwind v4 + Geist** app. Light,
editorial, information-dense but legible — and **citations are first-class**.

This is the second flagship surface (compare against the near-black **Linear/Vercel** app in
`web/`). It reuses that app's data layer **verbatim** — the typed API client, `run_live` types,
SSE consumer, run-flow store — and **re-skins the look + rebuilds the layout** into the
Perplexity language. Both apps proxy to the **same Python firm server**; neither reimplements
the engine.

Runs on **port 3001** (the Linear app uses 3000), so both can run side by side.

## Run

```bash
# 1) start the Python firm server (the backend) on :8201
python frontend2/server.py --port 8201

# 2) start the web app (separate terminal)
cd web-perplexity
npm install        # first time only
npm run dev        # → http://localhost:3001
```

`next.config.ts` proxies every `/api/*` call to `http://127.0.0.1:8201` (override with the
`SAPPHIRE_API` env var). Same-origin → no CORS, and the SSE stream flows straight through.

`npm run build` compiles clean (TypeScript strict).

## The citation-forward design

- **Citations are first-class.** Every dossier fact is a numbered source `[n]`. The synthesis
  answer carries inline citation markers `[1][2]…` that **jump** to a prominent numbered
  **source grid** at the bottom of the answer; the fact rows and source cards share the same
  numbers, so a citation always resolves to a real cited fact with real provenance. Internal
  moat sources are marked `🔒n` (gold) vs external `n` (blue). Citations are *derived honestly*
  from the engine's dossier — nothing is fabricated (`src/lib/citations.ts`).
- **Two data planes as tabs.** The dossier is split into **🌐 External** / **🔒 Internal moat**
  tabs (not side-by-side columns).
- **Roundtable as a persona grid.** Bucket 2 renders as a card grid with verdict badges +
  conviction bars, a Round 1 / Round 2 toggle, and a **spread bar** ("no forced consensus").
- **Light, confident palette** — warm paper white, Perplexity-blue accent, gold internal /
  blue external planes. Deliberately distinct from the Linear app's near-black UI.

## Layout (3-column)

- **Left — History rail:** brand mark, new-query, conversation list (preview / star / rename /
  delete), search, profile footer. Wired to `/api/conversations` CRUD; degrades gracefully when
  those endpoints aren't merged yet (empty history, no crash).
- **Center — Chat header + answer thread + composer:** the question heading, a firm status bar
  (agent/fact/flag/verdict summary + *View trace*), the **synthesis** answer with inline
  citations, honest run banners, the flags, the two-plane **dossier**, the **roundtable spread**,
  and the numbered **source grid**.
- **Right — Trace ⇄ Inspector** (toggle in the header): **Trace** is the compact live activity
  feed (plan → each fact agent with status · provenance · timing → flags → verdicts → synthesis);
  **Inspector** shows the selected agent / fact / persona / source in full detail.
- **Header:** model selector (Default / Sonnet / Haiku) + profile selector
  (Demo / Simulate / Live / Replay) → mapped to the `/api/run` body. `⌘K` command palette.

## Honesty

Every honesty marker (● real / 🧪 simulated / ◆ captured), tier, provenance, data plane, flag,
and abstention is rendered **verbatim from the engine result** — never relabeled, never
fabricated. Unknowns are flagged, not faked.

## API contract

- `POST /api/run` (SSE): body `{ query, profile, model, conversation_id? }`; stream
  `open → progress* → result → done | error`. The `result` frame is the `run_live` dict
  (`sapphire-orchestrator/contracts/run_live_schema.py`), typed in `src/lib/types.ts`.
- `GET|POST /api/conversations`, `GET|PATCH|DELETE /api/conversations/<id>` — persistence
  (sibling backend contract); each call degrades to a safe default on 404 / network error.

## Source map

| Path | What |
|---|---|
| `src/app/` | layout (Geist fonts) · `globals.css` (**Perplexity light** theme tokens + `.cite` markers) · `page.tsx` (3-column shell) |
| `src/lib/` | `types.ts` · `api.ts` (SSE consumer + persistence) · `store.ts` (Zustand) · `utils.ts` — **reused verbatim from `web/`** · `citations.ts` (**new** — numbered-source model) |
| `src/components/` | `chat-header` · `history-rail` · `chat-thread` · `composer` · `empty-state` · `command-palette` |
| `src/components/run/` | `synthesis` (answer + inline cites) · `flags` · `dossier` (plane **tabs**) · `spread` (persona grid + spread bar + round tabs) · `sources` (**new** — numbered grid) · `section` (header) |
| `src/components/inspector/` | `index` (Trace ⇄ Inspector tabs) · `monitor` (live trace) · `investigate` (component detail) · `trace-model` |
| `src/components/ui/` | primitives themed light: `button` · `select` · `tooltip` · `chips` |
