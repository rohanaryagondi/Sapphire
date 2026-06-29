# Sapphire — UI Showcase

Download this folder and open **`showcase/index.html`** in a browser to show the Sapphire UI without running any servers.

## What's here
- **`index.html`** — landing page linking everything below.
- **`app-snapshots/`** — the two flagship React apps, captured as real *populated* UI (a TSC2 rescue run):
  - `web-linear-vercel.{png,mhtml}` — the build target (`http://localhost:3000`).
  - `web-perplexity.{png,mhtml}` — the citation-forward alternate (`http://localhost:3001`).
  - `.png` opens in anything; `.mhtml` opens the full rendered page in **Chrome/Edge** (Safari/Firefox don't open MHTML natively).
- **`concepts/`** — the four design-direction mockups (fully interactive static HTML, open in any browser): `linear-vercel.html`, `claude-editorial.html`, `perplexity-citation.html`, `chatgpt-minimal.html` (and `index.html`, a 1–4 switcher).

## These are snapshots, not the live app
The snapshots show the real UI but are static (buttons don't call the backend). To run the **live, interactive** apps:

```bash
# 1) backend (engine API)
cd sapphire-orchestrator && python frontend2/server.py --port 8201
# 2) the Linear/Vercel app  → http://localhost:3000
cd web && SAPPHIRE_API=http://127.0.0.1:8201 npm install && npm run build && npx next start -p 3000
# (or the Perplexity app: cd web-perplexity && … next start -p 3001)
```

Live `Demo` profile is instant (mock, clearly labeled); `Simulate` uses real moat/EMET/Q-Models data.
