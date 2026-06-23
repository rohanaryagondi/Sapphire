# Meeting Agent — Experiment Plan Extractor

Turns raw **Otter.ai meeting transcripts** from Quiver experiment-planning meetings
into structured **experiment design plans**. It can run two ways:

- **CLI** — point it at a transcript file and get back JSON + a readable Markdown summary.
- **Slack bot** — drop a meeting-transcript PDF into a Slack channel and the bot
  posts the extracted plan back as a Markdown file.

Under the hood it sends the transcript to Claude with a Quiver-specific prompt
(domain knowledge about optopatch, QuasAr/CheRiff, NGN2/DLX2 cultures, assay types,
etc.), gets structured JSON back, and renders it to Markdown with confidence flags.

---

## How it works

```
transcript (PDF or .txt)
        │
        ▼
  extract.py  ──►  Claude (extraction_prompt.py)  ──►  structured JSON
        │
        ▼
  render_md()  ──►  Markdown summary (with 🔶/⚠️/❌ confidence flags)
```

The Slack bot (`app.py`) wraps the same `extract()` / `render_md()` functions:
it listens for PDF uploads, downloads them, runs extraction, and uploads the
Markdown result back to the channel.

---

## File overview

| File | What it is |
|---|---|
| `extract.py` | Core engine. `extract()` calls Claude; `render_md()` formats JSON → Markdown. Also a standalone CLI. |
| `extraction_prompt.py` | **The brains.** System prompt (Quiver domain knowledge), the JSON extraction template, and `MENUS_REFERENCE` (valid values from the Excel design template). Tune extraction behavior here. |
| `app.py` | Slack + Flask server (the deployed bot). Listens for `file_shared` PDF events. |
| `schema.py` | Reference dataclass schema describing the intended output shape. **Documentation only — not imported by the code.** The live contract is the JSON template inside `extraction_prompt.py`; if you change one, update the other. |
| `requirements.txt` | Python dependencies. |
| `.env.example` | Template for the required environment variables. |
| `test_data/` | Sample meeting-transcript PDFs for testing. |
| `generation_results/` | Example extraction output (JSON + Markdown) from a real run. |
| `sample_extraction_jan6.json` / `meeting_extraction_review_jan6.md` | A hand-curated "golden" example showing the intended end product. Good onboarding reference. |

---

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in real keys
```

Environment variables (see `.env.example`):

- `ANTHROPIC_API_KEY` — required for everything.
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` — only required for the Slack bot.

---

## Running the CLI

```bash
python extract.py path/to/transcript.txt
python extract.py path/to/transcript.txt --output-dir ./out
```

Accepts a `.txt` transcript or a `.pdf` (the PDF is sent to Claude directly).
Writes `<name>_extraction.json` and `<name>_extraction.md` to the output dir
(default: current directory).

Try it against the included samples in `test_data/`.

---

## Running the Slack bot

`app.py` is a Flask server that handles Slack events.

```bash
python app.py          # listens on $PORT (default 3000) at /slack/events
```

Slack app configuration needed:

- Subscribe to the **`file_shared`** event.
- Scopes: `files:read` (download uploads) and `files:write` / `chat:write` (post results).
- Point the app's Event Subscriptions request URL at `https://<your-host>/slack/events`.

The `GET /` route returns `ok` for health checks. The app was deployed on
**Railway** (reads `PORT` from the environment); any host that can run a Flask
process works.

---

## Tuning / common changes

- **What gets extracted, or domain knowledge** → `extraction_prompt.py`.
- **How the output Markdown looks** → `render_md()` in `extract.py`.
- **Which Claude model is used** → the `model=` argument in `extract.py` (`extract()`).
- **Slack behavior** → `app.py`.
