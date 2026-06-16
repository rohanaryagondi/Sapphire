# Sapphire site — "How It Works"

A self-contained, interactive walkthrough of the Sapphire capability map: the methodology flow,
the system (gate→boost) flow with an animated query, the 3-layer data map, and the 16-capability
dashboard. No build step, no dependencies.

## Run it

```bash
# from this folder
python -m http.server 8077
# then open http://localhost:8077
```

Or open `index.html` directly in a browser — it works from `file://` too (data is embedded in `data.js`).

## What's here

| File | Role |
|---|---|
| `index.html` | Structure + Google Fonts (Instrument Serif / IBM Plex Sans + Mono). |
| `styles.css` | The dark "electrophysiology instrument" theme. |
| `app.js` | All interactions — renders from `data.js`, animates the cascade, filters, drawer. |
| `console.js` | The **Console** section — animates the orchestrator (Discover → Validate → Consult → Synthesize) with the live persona panel. |
| `data.js` | Auto-generated from `../capability_map.xlsx`. **Do not hand-edit.** |
| `orchestrator_data.js` | Auto-generated from `../sapphire-orchestrator/`. **Do not hand-edit.** |

## Regenerate the data

The site reads `data.js`, which is generated from the spreadsheet so the two never drift:

```bash
python ../_build/build_site_data.py     # capability dashboard  ← capability_map.xlsx
python ../_build/build_orch_data.py      # Console               ← sapphire-orchestrator/scenarios/*.json
```

Re-run after editing the spreadsheet or the orchestrator scenarios, then refresh the page.

## Notes

- The query animation auto-plays once when the System-flow section scrolls into view, and replays
  on the **Run query** button.
- Capability **status** badges and **verdicts** are carried verbatim from the spreadsheet — `Gap`
  (CAP-04, CAP-15) and `Untested` mean exactly that.
- Static rendering of trusted local data only; no user input, no network calls.
