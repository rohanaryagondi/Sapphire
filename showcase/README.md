# Sapphire — UI Showcase

Download this folder and open **`showcase/index.html`** in a browser to show the Sapphire UI without running anything.

## What's here
- **`index.html`** — landing page linking everything below.
- **`app-snapshots/`** — the two flagship React apps, captured as real *populated* UI (a TSC2 rescue run):
  - `web-linear-vercel.{png,mhtml}` — the build target (`http://localhost:3000`).
  - `web-perplexity.{png,mhtml}` — the citation-forward alternate (`http://localhost:3001`).
  - `.png` opens in anything; `.mhtml` opens the full rendered page in **Chrome/Edge** (Safari/Firefox don't open MHTML natively).
- **`concepts/`** — the four design-direction mockups (fully interactive static HTML, open in any browser): `linear-vercel.html`, `claude-editorial.html`, `perplexity-citation.html`, `chatgpt-minimal.html` (and `index.html`, a 1–4 switcher).

---

## Run the live, interactive apps — exact commands

The snapshots above are static. To run the real apps, use the commands below **exactly**.
Paths assume the repo is at `/Users/rohanaryagondi/Desktop/Projects/Quiver/sapphire-capability-map` — if you cloned elsewhere, change it once:

```bash
export SAPPHIRE=/Users/rohanaryagondi/Desktop/Projects/Quiver/sapphire-capability-map
```

Prereqs: **Node 18+** (`node --version`) and **Python 3.10+** (`python3 --version`).

### Terminal 1 — backend engine API (port 8201)
```bash
cd "$SAPPHIRE/sapphire-orchestrator"
python3 frontend2/server.py --port 8201
```

### Terminal 2 — Linear / Vercel app → http://localhost:3000
```bash
cd "$SAPPHIRE/web"
npm install
npm run build
SAPPHIRE_API=http://127.0.0.1:8201 npx next start -p 3000
```

### Terminal 3 (optional) — Perplexity app → http://localhost:3001
```bash
cd "$SAPPHIRE/web-perplexity"
npm install
npm run build
SAPPHIRE_API=http://127.0.0.1:8201 npx next start -p 3001
```

### Check it's working
```bash
curl -s -o /dev/null -w "api %{http_code}\n"  http://127.0.0.1:8201/
curl -s -o /dev/null -w "web %{http_code}\n"  http://localhost:3000/
```
Both should print `200`. Then open **http://localhost:3000** and pick a suggested query.

### Notes
- **`Demo` profile works out of the box** (instant, clearly-labeled mock data).
- **`Simulate` / `Live`** need real backends: the moat DB at `RohanOnly/moat/moat.sqlite` (gitignored — built from the CNS_DFP parquet via `python3 _build/build_moat_db.py`) and, for live literature, a one-time BenchSci login: `cd "$SAPPHIRE/sapphire-orchestrator" && python3 -m emet.login`.
- If `npm run build` complains about the Node version, use Node 18 or 20.
- Stop a server with `Ctrl-C` in its terminal.
