"""Sapphire control surface — Chainlit entrypoint (forked from LOKA src/main.py, stripped).

Forked from q-state-biosciences/drug-discovery-agent @ 8685382 (see FORKED_FROM.md). The
Bedrock agent loop is REPLACED by an in-process bridge to Sapphire's live firm; AWS data
layers / OAuth / CSV-dataframe / Bedrock model selection are STRIPPED. Chainlit's default
local (in-memory) data layer is used — no `@cl.data_layer`, no AWS.

Run from the repo root:
    chainlit run frontend/main.py            # then pick a profile:
        "Demo (mock backends)"  → $0, deterministic, no external calls (the verification path)
        "Live (real firm)"      → real backends; needs the `claude` CLI for live subagents
                                   (without it, agents abstain honestly — no crash, no fabrication)
"""
from __future__ import annotations

import sys
from pathlib import Path

import chainlit as cl

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bridge          # noqa: E402  in-process run_live seam
import render          # noqa: E402  pure run_live dict → specs
import elements        # noqa: E402  specs → chainlit messages (imports chainlit+pandas)
from starters import STARTERS  # noqa: E402

DEMO_PROFILE = "Demo (mock backends)"
LIVE_PROFILE = "Live (real firm)"
CHEAP_PROFILE = "Live (cheap · haiku)"
REPLAY_PROFILE = "Replay (captured TSC2 · $0)"
REPLAY_SCENARIO = "tsc2_live_run"

# The cheap-live model: real backends (moat/EMET/seams/corpora), but every claude agent
# (Bucket-1 fact agents + Bucket-2 personas) runs on haiku so a real run doesn't burn
# default-model tokens. Pinned via CLAUDE_MODEL through the bridge → dispatch_claude --model.
CHEAP_MODEL = "claude-haiku-4-5"


@cl.set_starters
async def set_starters():
    return [cl.Starter(label=s["label"], message=s["message"], icon=s.get("icon"))
            for s in STARTERS]


@cl.set_chat_profiles
async def chat_profiles(current_user=None):
    return [
        cl.ChatProfile(
            name=DEMO_PROFILE,
            markdown_description=("**Mock backends** — deterministic, $0, no external calls. "
                                  "Runs the real firm logic through the offline test ctx. "
                                  "Use this to inspect the full process."),
        ),
        cl.ChatProfile(
            name=LIVE_PROFILE,
            markdown_description=("**Real firm** — live backends. Needs the `claude` CLI for "
                                  "live persona/fact subagents; without it they abstain honestly. "
                                  "A real run is slow (multi-agent, no token stream)."),
        ),
        cl.ChatProfile(
            name=CHEAP_PROFILE,
            markdown_description=("**Real firm, cheap reasoning** — same live backends as Live "
                                  "(real moat · real EMET · real seams/corpora · real Q-Models), "
                                  "but every claude agent runs on **haiku** so it doesn't burn "
                                  "default-model tokens. Honest: facts are real; only the model is "
                                  "cheaper. Needs the `claude` CLI + a logged-in EMET session."),
        ),
        cl.ChatProfile(
            name=REPLAY_PROFILE,
            markdown_description=("**Captured TSC2 run — $0 instant replay.** A frozen REAL "
                                  "engagement (real Quiver moat · 8 real EMET PMIDs · the live "
                                  "persona spread · real DIVERGENCEs), captured once and replayed "
                                  "deterministically — no model, no network. Provenance/tiers/flags "
                                  "verbatim. ⚠ Contains internal moat data — internal demo only."),
        ),
    ]


@cl.on_chat_start
async def on_start():
    profile = cl.user_session.get("chat_profile") or DEMO_PROFILE
    await cl.Message(
        content=(f"**Sapphire** — transparent CNS decision firm. Profile: `{profile}`.\n\n"
                 "Ask a deliberative CNS question (a target, a go/no-go, a regulatory/payer read). "
                 "Sapphire convenes the firm: Bucket-1 cited-fact dossier → Bucket-2 persona "
                 "roundtable (the spread) → synthesis. Every fact carries its tier, provenance, and "
                 "data plane (internal vs external) verbatim.")
    ).send()


def _profile_run_kwargs(profile: str) -> dict:
    """Map the selected chat profile → bridge.run kwargs.

    Demo → mock backends ($0). Live → real backends, CLI-default model. Live (cheap) → real
    backends, haiku model (cheap reasoning). Unknown → Demo (safe default).
    """
    if profile == LIVE_PROFILE:
        return {"mock": False, "model": None}
    if profile == CHEAP_PROFILE:
        return {"mock": False, "model": CHEAP_MODEL}
    return {"mock": True, "model": None}


@cl.on_message
async def on_message(message: cl.Message):
    profile = cl.user_session.get("chat_profile") or DEMO_PROFILE
    kwargs = _profile_run_kwargs(profile)
    query = (message.content or "").strip()
    if not query:
        await cl.Message(content="_Please enter a question._").send()
        return

    async with cl.Step(name="Convening the firm…", type="run") as step:
        step.input = query
        if profile == REPLAY_PROFILE:
            # $0 deterministic replay of a frozen REAL capture — no model, no network.
            result = await cl.make_async(bridge.replay)(REPLAY_SCENARIO)
            step.output = (f"via=replay · captured {result.get('_captured_at','')} · "
                           f"$0 (frozen real run)")
        else:
            # bridge.run never raises; it runs the firm in-process (mock or live).
            result = await cl.make_async(bridge.run)(query, **kwargs)
            backend = "mock" if result.get("_mock") else "live"
            model = result.get("_model") or "default"
            step.output = (f"via={result.get('_via')} · {result.get('_elapsed_s')}s · "
                           f"{backend} backends · model={model}")

    # Map the run_live dict → render specs → chainlit messages; send each in order.
    for msg in elements.to_messages(render.render_run(result)):
        await cl.Message(content=msg["content"], elements=msg["elements"]).send()
