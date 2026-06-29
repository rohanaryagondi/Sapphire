# Report — Console UI: new chat-first design (`sapphire_chat.html`)

**Branch:** `gavin/console-ui-design-refinement` · **Built-By:** gavin · **Date:** 2026-06-25
**Type:** Front-end design. No engine, Python, or data change.
**Scope:** `docs/design/console-ui/` only.

## What this PR does

Delivers a new console UI direction: **`sapphire_chat.html`** — a clean chat-first interface
modelled on Claude.ai / ChatGPT dark mode, with two independently toggleable side panels.

The design was built from a structured discovery process: ingesting Anthropic's `frontend-design`
and `artifact-design` skills, a human-vision interview with Gavin (Jobs/iPhone principles — spacious,
unintimidating, panels available but secondary), and a 5-agent design-best-practices research pass.

Also includes `sapphire_minimal.html` — an earlier serif/Jobs exploration kept as a reference.

## Design decisions

**Default view — clean chat only.**
No panels visible. Centered "Ask Sapphire" heading, suggestion chips, input bar pinned to bottom.
Identical to Claude/ChatGPT at rest. The interface disappears; the question is the only object.

**Two toggle buttons in the nav.**
- **Agents** (top-left) — slides in a 280px left panel: every agent with a status dot (done/active/queued) and a one-line finding.
- **Sources** (top-right) — slides in a 310px right panel: T1/T2 cited evidence + numbered chain-of-thought trace.
Both panels animate open/closed with `cubic-bezier(0.22,1,0.36,1)`. Active state = blue fill on the toggle button.

**Message input is functional.**
- User's actual typed text appears in their bubble (right-aligned, rounded, `#2a2a2a` background)
- Multiple sends work; each adds a new exchange to the thread
- Enter to send, Shift+Enter for newline
- Suggestion chips fill the input (and disappear once the conversation starts)
- Textarea auto-resizes up to 160px

**Token choices.**
Ground `#171717` (ChatGPT-approximate), surface `#1f1f1f`, user bubble `#2a2a2a`, panel `#111111`.
One accent: `#4d7cfe` (sapphire blue) — used only on the send button, verdict callout border, and active toggle state.
Teal `#2dd4bf` for live/active dots only. System font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI"`) — no CDN dependency.

**Content honesty preserved.**
Every fact in the demo response carries a provenance chip (✓ EMET · PMID / ◇ Claude / ◍ moat).
The verdict is a distinct callout block with a T1/T2 tag scheme in the Sources panel.

## Files

| File | Description |
|---|---|
| `docs/design/console-ui/sapphire_chat.html` | ★ New primary design direction |
| `docs/design/console-ui/sapphire_minimal.html` | Earlier serif/Jobs exploration (reference) |
| `dev/reports/gavin/console-ui-design-refinement-report.md` | This report |

## How to preview

```sh
python -m http.server 8091 --directory docs/design/console-ui
# open http://localhost:8091/sapphire_chat.html
```

Click **Agents** and **Sources** in the nav to open the side panels. Type any question and press Enter or click the send button — the input is live (multiple sends work).

## Risk / review notes

- **Design only.** No Python, no JS engine, no data files, no corpus touched.
- Self-contained HTML — no external assets beyond the system font stack.
- Does not touch `frontend/` (the runtime Chainlit app) or `site/` (the static console).
- `sapphire_loka.html` (the prior LOKA-native direction) is untouched and still present.
