import json
import os
import unittest
from types import SimpleNamespace
from harness.contracts import Contract
from harness import dispatch as D

def fake_runner(stdout, returncode=0, stderr=""):
    return lambda cmd: SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)


def capturing_runner(captured, stdout):
    """A runner that records the argv it was handed, then returns a canned envelope."""
    def _run(cmd):
        captured.append(list(cmd))
        return SimpleNamespace(stdout=stdout, returncode=0, stderr="")
    return _run


class TestDispatch(unittest.TestCase):
    def test_build_prompt_includes_inputs(self):
        c = Contract(id="x", role="", kind="claude-subagent", spec=None)
        p = D.build_prompt(c, {"gene": "SCN11A"})
        self.assertIn("SCN11A", p)
        self.assertIn("structured object", p.lower())

    def test_dispatch_claude_parses_structured_output(self):
        c = Contract(id="x", role="", kind="claude-subagent", output_schema={"type": "object"})
        env = json.dumps({"structured_output": {"facts": [], "ok": True}})
        out = D.dispatch_claude(c, {"q": 1}, runner=fake_runner(env))
        self.assertEqual(out, {"facts": [], "ok": True})

    def test_dispatch_claude_falls_back_to_result(self):
        c = Contract(id="x", role="", kind="claude-subagent")
        env = json.dumps({"result": json.dumps({"v": 2})})
        out = D.dispatch_claude(c, {}, runner=fake_runner(env))
        self.assertEqual(out, {"v": 2})

    def test_dispatch_claude_nonzero_raises(self):
        c = Contract(id="x", role="", kind="claude-subagent")
        with self.assertRaises(RuntimeError):
            D.dispatch_claude(c, {}, runner=fake_runner("", returncode=1, stderr="boom"))

    def test_dispatch_qmodels_delegates(self):
        c = Contract(id="q-models-runner", role="", kind="qmodels-delegate")
        # Client returns raw {tool_id, out} shape (no "facts" key) — adapter wraps into findings.
        client = SimpleNamespace(call=lambda tool, inp: {"tool_id": tool, "out": "p=0.5"})
        out = D.dispatch_qmodels(c, {"tool_id": "bbbp", "candidate": "CCO", "inputs": {"smiles": "CCO"}}, client=client)
        self.assertIn("facts", out)
        self.assertTrue(len(out["facts"]) >= 1)
        self.assertEqual(out["facts"][0]["source"], "Q-Models")

    def test_dispatch_qmodels_passthrough_if_findings(self):
        c = Contract(id="q-models-runner", role="", kind="qmodels-delegate")
        # Client already returns findings shape — adapter passes through unchanged.
        findings = {"candidate": "X", "facts": [{"value": "v", "source": "Q-Models", "tier": "T2"}]}
        client = SimpleNamespace(call=lambda tool, inp: findings)
        out = D.dispatch_qmodels(c, {"tool_id": "bbbp"}, client=client)
        self.assertEqual(out, findings)

    def test_dispatch_python_calls_fn(self):
        c = Contract(id="step", role="", kind="python")
        out = D.dispatch_python(c, {"n": 2}, fn=lambda i: {"doubled": i["n"] * 2})
        self.assertEqual(out["doubled"], 4)

    def test_dispatch_routes_by_kind(self):
        c = Contract(id="step", role="", kind="python")
        out = D.dispatch(c, {"n": 3}, ctx={"python_fns": {"step": lambda i: {"v": i["n"]}}})
        self.assertEqual(out["v"], 3)

    # ── Opt-2 — batch-per-bucket dispatch ────────────────────────────────────
    def test_batch_empty_items(self):
        self.assertEqual(D.dispatch_claude_batch([]), {})

    def test_batch_prompt_and_schema(self):
        a = Contract(id="patent-ip", role="", kind="claude-subagent",
                     output_schema={"type": "object", "properties": {"facts": {"type": "array"}}})
        b = Contract(id="payer", role="", kind="claude-subagent", output_schema={"type": "object"})
        items = [(a, {"candidate": "TSC2"}), (b, {"candidate": "TSC2"})]
        prompt = D.build_batch_prompt(items)
        self.assertTrue(prompt.startswith(D.SHARED_PREAMBLE))
        self.assertIn("### AGENT: patent-ip", prompt)
        self.assertIn("### AGENT: payer", prompt)
        schema = D._batch_schema(items)
        self.assertEqual(set(schema["required"]), {"patent-ip", "payer"})
        self.assertIn("patent-ip", schema["properties"])

    def test_batch_returns_per_agent_outputs(self):
        a = Contract(id="patent-ip", role="", kind="claude-subagent", output_schema={"type": "object"})
        b = Contract(id="payer", role="", kind="claude-subagent", output_schema={"type": "object"})
        body = {"patent-ip": {"facts": [{"value": "x"}]}, "payer": {"facts": []}}
        env = json.dumps({"structured_output": body})
        out = D.dispatch_claude_batch([(a, {}), (b, {})], runner=fake_runner(env))
        self.assertEqual(out["patent-ip"], {"facts": [{"value": "x"}]})
        self.assertEqual(out["payer"], {"facts": []})

    def test_batch_missing_agent_raises(self):
        a = Contract(id="patent-ip", role="", kind="claude-subagent", output_schema={"type": "object"})
        b = Contract(id="payer", role="", kind="claude-subagent", output_schema={"type": "object"})
        env = json.dumps({"structured_output": {"patent-ip": {"facts": []}}})  # payer missing
        with self.assertRaises(RuntimeError):
            D.dispatch_claude_batch([(a, {}), (b, {})], runner=fake_runner(env))

    def test_batch_nonzero_raises(self):
        a = Contract(id="patent-ip", role="", kind="claude-subagent", output_schema={"type": "object"})
        with self.assertRaises(RuntimeError):
            D.dispatch_claude_batch([(a, {})], runner=fake_runner("", returncode=1, stderr="boom"))

    def test_batch_forwards_union_of_allowed_tools(self):
        # Batched agents must NOT run tool-blind: their --allowedTools is forwarded (union).
        a = Contract(id="patent-ip", role="", kind="claude-subagent",
                     output_schema={"type": "object"}, tools_allowed=["WebSearch", "WebFetch"])
        b = Contract(id="payer", role="", kind="claude-subagent",
                     output_schema={"type": "object"}, tools_allowed=["WebSearch"])
        captured = []
        env = json.dumps({"structured_output": {"patent-ip": {}, "payer": {}}})
        D.dispatch_claude_batch([(a, {}), (b, {})], runner=capturing_runner(captured, env))
        argv = captured[0]
        self.assertIn("--allowedTools", argv)
        tools = argv[argv.index("--allowedTools") + 1].split(",")
        self.assertIn("WebSearch", tools)
        self.assertIn("WebFetch", tools)   # union across both agents

    def test_batch_no_tools_flag_when_none_allowed(self):
        a = Contract(id="x", role="", kind="claude-subagent", output_schema={"type": "object"})
        captured = []
        env = json.dumps({"structured_output": {"x": {}}})
        D.dispatch_claude_batch([(a, {})], runner=capturing_runner(captured, env))
        self.assertNotIn("--allowedTools", captured[0])

    def test_batch_includes_context_flags(self):
        # The batch call must also carry the Opt-1 cache flags (regression guard).
        a = Contract(id="patent-ip", role="", kind="claude-subagent", output_schema={"type": "object"})
        captured = []
        env = json.dumps({"structured_output": {"patent-ip": {"facts": []}}})
        prev = os.environ.pop("SAPPHIRE_DISPATCH_FULL_CONTEXT", None)
        try:
            D.dispatch_claude_batch([(a, {})], runner=capturing_runner(captured, env))
        finally:
            if prev is not None:
                os.environ["SAPPHIRE_DISPATCH_FULL_CONTEXT"] = prev
        self.assertIn("--setting-sources", captured[0])
        self.assertIn("--exclude-dynamic-system-prompt-sections", captured[0])

    def test_dispatch_emet_without_handler_errors(self):
        c = Contract(id="emet-runner", role="", kind="emet-playwright")
        with self.assertRaises(RuntimeError):
            D.dispatch(c, {"candidate": "SCN11A"}, ctx={})

    # ── W2(a) — CLAUDE_MODEL → --model pass-through ──────────────────────────
    def test_dispatch_claude_adds_model_when_env_set(self):
        c = Contract(id="x", role="", kind="claude-subagent", output_schema={"type": "object"})
        env = json.dumps({"structured_output": {"ok": True}})
        captured = []
        prev = os.environ.get("CLAUDE_MODEL")
        os.environ["CLAUDE_MODEL"] = "claude-haiku-4-5"
        try:
            D.dispatch_claude(c, {"q": 1}, runner=capturing_runner(captured, env))
        finally:
            if prev is None:
                os.environ.pop("CLAUDE_MODEL", None)
            else:
                os.environ["CLAUDE_MODEL"] = prev
        argv = captured[0]
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-haiku-4-5")

    def test_dispatch_claude_falls_back_to_sapphire_model(self):
        # serve.py pins via SAPPHIRE_MODEL; dispatch must honor it too so both levers work.
        c = Contract(id="x", role="", kind="claude-subagent", output_schema={"type": "object"})
        env = json.dumps({"structured_output": {"ok": True}})
        captured = []
        prev_c = os.environ.pop("CLAUDE_MODEL", None)
        prev_s = os.environ.get("SAPPHIRE_MODEL")
        os.environ["SAPPHIRE_MODEL"] = "claude-haiku-4-5"
        try:
            D.dispatch_claude(c, {"q": 1}, runner=capturing_runner(captured, env))
        finally:
            if prev_c is not None:
                os.environ["CLAUDE_MODEL"] = prev_c
            if prev_s is None:
                os.environ.pop("SAPPHIRE_MODEL", None)
            else:
                os.environ["SAPPHIRE_MODEL"] = prev_s
        argv = captured[0]
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-haiku-4-5")

    # ── Opt-1 — cache-friendly context flags + shared preamble ───────────────
    def test_build_prompt_starts_with_shared_preamble(self):
        c = Contract(id="x", role="", kind="claude-subagent", spec=None)
        p = D.build_prompt(c, {"gene": "SCN11A"})
        self.assertTrue(p.startswith(D.SHARED_PREAMBLE))   # identical + FIRST → cache reuse
        self.assertIn("SCN11A", p)                         # inputs still present

    def test_context_flags_on_by_default(self):
        prev = os.environ.pop("SAPPHIRE_DISPATCH_FULL_CONTEXT", None)
        try:
            flags = D._context_flags()
        finally:
            if prev is not None:
                os.environ["SAPPHIRE_DISPATCH_FULL_CONTEXT"] = prev
        self.assertIn("--setting-sources", flags)
        self.assertIn("user", flags)
        self.assertIn("--exclude-dynamic-system-prompt-sections", flags)

    def test_context_flags_opt_out(self):
        prev = os.environ.get("SAPPHIRE_DISPATCH_FULL_CONTEXT")
        os.environ["SAPPHIRE_DISPATCH_FULL_CONTEXT"] = "1"
        try:
            self.assertEqual(D._context_flags(), [])
        finally:
            if prev is None:
                os.environ.pop("SAPPHIRE_DISPATCH_FULL_CONTEXT", None)
            else:
                os.environ["SAPPHIRE_DISPATCH_FULL_CONTEXT"] = prev

    def test_dispatch_claude_includes_context_flags(self):
        c = Contract(id="x", role="", kind="claude-subagent", output_schema={"type": "object"})
        env = json.dumps({"structured_output": {"ok": True}})
        captured = []
        prev = os.environ.pop("SAPPHIRE_DISPATCH_FULL_CONTEXT", None)
        try:
            D.dispatch_claude(c, {"q": 1}, runner=capturing_runner(captured, env))
        finally:
            if prev is not None:
                os.environ["SAPPHIRE_DISPATCH_FULL_CONTEXT"] = prev
        self.assertIn("--setting-sources", captured[0])
        self.assertIn("--exclude-dynamic-system-prompt-sections", captured[0])

    def test_dispatch_claude_no_model_when_env_unset(self):
        c = Contract(id="x", role="", kind="claude-subagent", output_schema={"type": "object"})
        env = json.dumps({"structured_output": {"ok": True}})
        captured = []
        prev_c = os.environ.pop("CLAUDE_MODEL", None)
        prev_s = os.environ.pop("SAPPHIRE_MODEL", None)
        try:
            D.dispatch_claude(c, {"q": 1}, runner=capturing_runner(captured, env))
        finally:
            if prev_c is not None:
                os.environ["CLAUDE_MODEL"] = prev_c
            if prev_s is not None:
                os.environ["SAPPHIRE_MODEL"] = prev_s
        self.assertNotIn("--model", captured[0])

if __name__ == "__main__":
    unittest.main()
