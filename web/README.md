# Sapphire — flagship web front end

The product-grade Sapphire console in the **Linear / Vercel** design language: a custom
**Next.js (App Router) + TypeScript (strict) + Tailwind v4 + Geist + shadcn-style** app.

This is the flagship surface. The stdlib `frontend2/` console stays as the offline fallback;
this app is a thin, beautiful front end that **proxies to the same Python firm server** — it
never reimplements the engine.

## Run

```bash
# 1) start the Python firm server (the backend) on :8201
cd sapphire-orchestrator   # or repo root
python frontend2/server.py --port 8201

# 2) start the web app (separate terminal)
cd web
npm install        # first time only
npm run dev        # → http://localhost:3000
```

`next.config.ts` proxies every `/api/*` call to `http://127.0.0.1:8201` (override with the
`SAPPHIRE_API` env var, e.g. `SAPPHIRE_API=http://127.0.0.1:8100 npm run dev`). Same-origin →
no CORS, and the SSE stream flows straight through.

`npm run build` compiles clean (TypeScript strict).

## Layout (the dual-panel console)

- **Left — History rail:** new-chat, conversation list (preview / star / rename / delete),
  search. Wired to the persistence API (`/api/conversations` CRUD). Degrades gracefully when
  those endpoints aren't merged yet (empty history, no crash).
- **Center — Chat thread:** the query, then the firm's streamed answer — the **synthesis**
  recommendation up top, honest run banners, the **two-plane dossier** (🔒 internal moat vs
  🌐 external evidence), and the **roundtable spread** (no forced consensus).
- **Right — Inspector** (`⌘/` to toggle): two capabilities.
  - **Monitor** — the live trace: plan → each fact agent (status · provenance · timing) →
    flags → persona verdicts → synthesis, streaming as it runs.
  - **Investigate** — click any agent / fact / verdict / step to inspect its detailed output,
    sources, and provenance.
- **Top bar:** model selector (Default / Sonnet / Haiku) + profile selector
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
| `src/app/` | layout (Geist fonts) · `globals.css` (Linear/Vercel theme tokens) · `page.tsx` (3-zone shell) |
| `src/lib/` | `types.ts` (run_live types) · `api.ts` (SSE consumer + persistence) · `store.ts` (Zustand) · `utils.ts` (provenance / labels) |
| `src/components/` | `topbar` · `history-rail` · `chat-thread` · `composer` · `empty-state` · `command-palette` |
| `src/components/run/` | `synthesis` · `flags` · `dossier` (two planes) · `spread` |
| `src/components/inspector/` | `index` (tabs) · `monitor` (live trace) · `investigate` (component detail) · `trace-model` |
| `src/components/ui/` | shadcn-style primitives themed to the language: `button` · `select` · `tooltip` · `chips` |
