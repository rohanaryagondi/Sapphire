# Report — site: console visual redesign (design polish pass)

**Branch:** `gavin/site-console-redesign` · **Built-By:** gavin · **Date:** 2026-06-25
**Type:** Front-end design / CSS polish. **No engine, JS, or data change.**
**Scope:** `site/styles.css`, `site/index.html`, `site/explainer.html` only.

## What this PR does
Elevates the visual design of the static **Console** (`site/index.html`) — the front-facing demo surface — and, because the stylesheet is shared, carries the same polish through to `explainer.html`. The goal was "make it look awesome" **within the existing design language** (the dark "EP-instrument" theme: sapphire-blue + teal `--signal`, Instrument Serif display, IBM Plex Sans/Mono). This is an elevation, **not a redesign/pivot** — every existing class, JS hook, and data binding is preserved.

## Why (the problems addressed)
The original console was competent but read flat and cramped: thin single-tone card fills with no depth, a weak hero (no entrance, low contrast title), a plain-dot brand mark, a flat solid button, and dense inspector headers. The bones were strong; it needed depth, hierarchy, ambiance, and micro-interaction polish.

## Changes (all in `site/styles.css` unless noted)
1. **Design tokens — new elevation system** (`:root`): added `--surface`/`--surface-2` (layered gradient fills), `--edge-hi` (inset top highlight), `--shadow-sm/md/lg`, `--glow`. Deepened `--bg` and brightened `--ink`/`--muted`/`--faint` slightly for contrast. These are additive primitives reused across surfaces.
2. **Ambient background**: richer multi-radial glow (added a bottom sapphire bloom + a soft vignette) and `background-attachment:fixed` so the atmosphere stays put while content scrolls.
3. **Brand mark**: plain pulsing dot → a faceted **sapphire gem** (conic-gradient + `clip-path` pentagon + a screen-blend specular highlight, slow rotation). Brand wordmark now a subtle ink→blue gradient.
4. **Console hero** (`.console-head`): animated entrance (`rise`) on title + sub; eyebrow gets a leading accent rule; title enlarged (`clamp(2.4→4rem)`) with a teal→blue gradient + glow on the *Sapphire* emphasis; sub link gets an underline-on-hover affordance.
5. **Surfaces get depth**: `.chat-pane` and `.insp-card` now use the gradient surface + `--edge-hi` + soft shadow (real elevation vs. the old flat fill). `.chat-shell` fades/rises in on load.
6. **Inspector headers** (`.insp-h`): added a glowing signal dot + a divider rule, so each card ("Systems", "Models", "Active run") reads as a titled panel.
7. **Send button** (`.run-btn`, shared): solid → teal gradient with depth shadow + edge highlight and a press state. **Presets** (`.preset-chip`) now fill teal on hover with a lift. **Input** (`#chatInput`) gets a focus glow ring.
8. **Nav**: "Full flow →" became a bordered pill CTA with hover wash; status pill got a faint fill.
9. **Favicon** (`index.html`, `explainer.html`): added an inline-SVG sapphire-gem favicon (data URI). Also removes the `favicon.ico` 404 seen on the static server.

## Verification
- **Rendered in Playwright (Chromium @ 1440×900)** in three states, all confirmed visually:
  - Console idle (hero + empty chat + inspector)
  - Console populated (clicked the **TSC2** preset → user bubble, serif run-card with EMET-tagged citations, populated "Active run" inspector — chat JS works, nothing broke)
  - `explainer.html` full page (shared tokens carry over cohesively; hero/pipeline/tiers/capabilities/real-vs-mock all intact)
- **Console errors:** only the pre-existing `/api/health` + `/api/tools` 404s (those endpoints are served by `serve.py`, the subscription bridge — not the static `http.server`; the page falls back to canned data by design). The `favicon.ico` 404 is now gone.
- **Suite:** `bash dev/run-tests.sh` → **540 green** (no regression; this PR touches no Python).

## Risk / review notes
- **Pure presentation.** No `.js`, no Python, no data files touched. All original CSS class names and the `id` hooks (`#chatInput`, `#chatSend`, `#inspSystems`, etc.) used by `console.js`/`app.js` are unchanged.
- The stylesheet is shared by `index.html` and `explainer.html`; I verified both. The shared-token changes (button/nav/brand/background) are intended to keep the two pages cohesive.
- No external assets added (favicon is an inline data URI; fonts unchanged). CSP-safe.

## How to preview
```
cd site && python -m http.server 8077
# open http://localhost:8077/index.html  (and /explainer.html)
```

## Anti-overreach
This stays in `site/` (the static Console). It does **not** touch the newer `frontend/` Chainlit app — that's a separate surface (and separate future task if design polish is wanted there too).
