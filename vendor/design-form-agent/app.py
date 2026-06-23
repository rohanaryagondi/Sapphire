"""
app.py
Listens for PDF uploads in Slack, runs extraction, posts markdown file back.
"""

import os
import tempfile
import threading
from pathlib import Path

from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from dotenv import load_dotenv

from extract import extract, render_md

load_dotenv()

# ── Slack app ─────────────────────────────────────────────────────────
app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)

# ── Flask app (for Railway) ───────────────────────────────────────────
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

@flask_app.route("/", methods=["GET"])
def health():
    return "ok", 200


# ── Event handler ─────────────────────────────────────────────────────
@app.event("file_shared")
def handle_file_shared(event, client, say):
    file_id = event.get("file_id")
    channel_id = event.get("channel_id")

    file_info = client.files_info(file=file_id)["file"]
    filename = file_info.get("name", "")
    mimetype = file_info.get("mimetype", "")

    if not filename.lower().endswith(".pdf") and mimetype != "application/pdf":
        return

    say(channel=channel_id, text=f"Got it — extracting experiment plan from *{filename}*... :microscope:")

    def run_extraction():
        try:
            import requests
            url = file_info["url_private_download"]
            resp = requests.get(url, headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"})
            resp.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = Path(tmp.name)

            data = extract(tmp_path)
            md = render_md(data)
            tmp_path.unlink()

            out_filename = Path(filename).stem + "_extraction.md"
            client.files_upload_v2(
                channel=channel_id,
                content=md,
                filename=out_filename,
                title=out_filename,
                initial_comment=f":white_check_mark: Extraction complete for *{filename}*",
            )

        except Exception as e:
            say(channel=channel_id, text=f":x: Something went wrong during extraction:\n```{e}```")

    threading.Thread(target=run_extraction).start()


# ── Entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)