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

import asyncio
import sys
from pathlib import Path

import chainlit as cl

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bridge          # noqa: E402  in-process run_live seam
import render          # noqa: E402  pure run_live dict → specs
import elements        # noqa: E402  specs → chainlit messages (imports chainlit+pandas)
import progress        # noqa: E402  pure progress-event → step-label formatting
from starters import STARTERS  # noqa: E402

DEMO_PROFILE = "Demo (mock backends)"
LIVE_PROFILE = "Live (real firm)"
CHEAP_PROFILE = "Live (cheap · haiku)"
SIMULATE_PROFILE = "Live (demo · simulated models)"
REPLAY_PROFILE = "Replay (captured TSC2 · $0)"
REPLAY_SCENARIO = "tsc2_live_run"

# 🧪 simulated-models banner — shown on every simulated run so the labeling is unmistakable.
SIMULATE_BANNER = (
    "🧪 **Simulated-models run.** Real **moat**, **EMET PMIDs**, **seams** and **Q-Models** — but the "
    "**roundtable verdicts + any claude fact-agent reasoning are SIMULATED** (labeled `🧪 simulated`, "
    "provenance `simulated`), not real model output. For a fast demo while real reasoning is wired in."
)

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
            name=SIMULATE_PROFILE,
            markdown_description=("**Fast demo — real facts, 🧪 simulated reasoning.** Real moat · "
                                  "real EMET PMIDs (logged-in) · real seams/Q-Models, but the "
                                  "**roundtable verdicts + claude fact-agents are SIMULATED** "
                                  "(clearly labeled `🧪 simulated`) so the run is fast while real "
                                  "`claude -p` reasoning is wired in. Honest: simulated ≠ real verdict."),
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
    if profile == SIMULATE_PROFILE:
        # Real backends (moat/EMET/seams), but claude-subagent reasoning is 🧪 simulated (fast).
        return {"mock": False, "model": CHEAP_MODEL, "simulate": True}
    return {"mock": True, "model": None}


class _StepTree:
    """Builds the live step tree from streamed run_live progress events. Top-level steps for
    plan/flags/synthesis; parent groups for bucket1/roundtable, with a child step per agent/
    persona that flips pending→done in place. Honest labels via progress.py (abstain ⇒ ⚠)."""

    def __init__(self):
        self._parents = {}   # stage -> cl.Step
        self._children = {}  # (stage, agent_id) -> cl.Step
        self._top = {}       # stage -> cl.Step (plan/flags/synthesis)

    async def _parent(self, stage):
        if stage not in self._parents:
            p = cl.Step(name=progress.parent_name(stage), type="tool")
            await p.send()
            self._parents[stage] = p
        return self._parents[stage]

    async def handle(self, ev):
        stage = ev.get("stage")
        done = progress.is_done(ev)
        if stage in ("plan", "flags", "synthesis"):
            st = self._top.get(stage)
            if st is None:
                st = cl.Step(name=progress.step_name(ev), type="tool")
                await st.send()
                self._top[stage] = st
            if done:
                st.output = progress.step_output(ev)
                await st.update()
            return
        # bucket1 / roundtable → child step under a parent group
        parent = await self._parent(stage)
        key = (stage, ev.get("agent_id"))
        st = self._children.get(key)
        if st is None:
            st = cl.Step(name=progress.step_name(ev), type="tool", parent_id=parent.id)
            await st.send()
            self._children[key] = st
        if done:
            st.output = progress.step_output(ev)
            await st.update()


async def _run_with_live_steps(query: str, kwargs: dict) -> dict:
    """Sync→async bridge: run `bridge.run` (which calls the synchronous `run_live`) in a worker
    thread; its `on_progress` callback marshals each event back to THIS event loop via a
    thread-safe queue, which we drain to update `cl.Step`s LIVE — steps appear DURING the run,
    not after. Returns the final result dict (sentinel-terminated)."""
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def _on_progress(ev):                      # called on the worker thread
        loop.call_soon_threadsafe(q.put_nowait, {"__event__": ev})

    async def _runner():
        res = await asyncio.to_thread(bridge.run, query, on_progress=_on_progress, **kwargs)
        loop.call_soon_threadsafe(q.put_nowait, {"__result__": res})
        return res

    task = asyncio.create_task(_runner())
    tree = _StepTree()
    result = None
    while True:
        item = await q.get()
        if "__result__" in item:
            result = item["__result__"]
            break
        await tree.handle(item["__event__"])
    await task                                 # propagate any (already-defensively-handled) state
    return result


async def _render_final(result: dict) -> None:
    """The rich final view (dossier/planes/roundtable/synthesis) — unchanged from before."""
    for msg in elements.to_messages(render.render_run(result)):
        await cl.Message(content=msg["content"], elements=msg["elements"]).send()


@cl.on_message
async def on_message(message: cl.Message):
    profile = cl.user_session.get("chat_profile") or DEMO_PROFILE
    query = (message.content or "").strip()
    if not query:
        await cl.Message(content="_Please enter a question._").send()
        return

    if profile == REPLAY_PROFILE:
        # $0 deterministic replay of a frozen REAL capture — no model, no network, no live steps.
        async with cl.Step(name="Replaying captured TSC2 run…", type="run") as step:
            result = await cl.make_async(bridge.replay)(REPLAY_SCENARIO)
            step.output = f"via=replay · captured {result.get('_captured_at', '')} · $0 (frozen real run)"
        await _render_final(result)
        return

    # Live / Cheap / Demo / Simulated: stream the firm convening as a live step tree, then the
    # rich final view. A simulated run shows the 🧪 banner up-front so the labeling is unmistakable.
    if profile == SIMULATE_PROFILE:
        await cl.Message(content=SIMULATE_BANNER).send()
    result = await _run_with_live_steps(query, _profile_run_kwargs(profile))
    await _render_final(result)
