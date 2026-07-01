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


class TestPerAgentModelSelection(unittest.TestCase):
    """Per-agent model selection (WO-9): Bucket-2 → haiku, Bucket-1/control → sonnet."""

    def _no_env(self):
        """Context manager that removes CLAUDE_MODEL and SAPPHIRE_MODEL from env."""
        import contextlib

        @contextlib.contextmanager
        def _cm():
            prev_c = os.environ.pop("CLAUDE_MODEL", None)
            prev_s = os.environ.pop("SAPPHIRE_MODEL", None)
            try:
                yield
            finally:
                if prev_c is not None:
                    os.environ["CLAUDE_MODEL"] = prev_c
                if prev_s is not None:
                    os.environ["SAPPHIRE_MODEL"] = prev_s

        return _cm()

    def _canned_env(self, stdout=None):
        if stdout is None:
            stdout = json.dumps({"structured_output": {"ok": True}})
        return stdout

    def _dispatch(self, contract):
        """Run dispatch_claude with a capturing runner; return the argv list."""
        captured = []
        stdout = self._canned_env()
        D.dispatch_claude(contract, {}, runner=capturing_runner(captured, stdout))
        return captured[0]

    # ── _resolve_model unit tests ─────────────────────────────────────────────

    def test_resolve_model_contract_haiku(self):
        """contract.model='claude-haiku-4-5' → haiku when env unset."""
        c = Contract(id="company-partner", role="", kind="claude-subagent",
                     model="claude-haiku-4-5")
        with self._no_env():
            self.assertEqual(D._resolve_model(c), "claude-haiku-4-5")

    def test_resolve_model_contract_sonnet(self):
        """contract.model='claude-sonnet-4-6' → sonnet when env unset."""
        c = Contract(id="fda-institutional-memory", role="", kind="claude-subagent",
                     model="claude-sonnet-4-6")
        with self._no_env():
            self.assertEqual(D._resolve_model(c), "claude-sonnet-4-6")

    def test_resolve_model_no_model_field(self):
        """contract.model=None → empty string (no --model flag)."""
        c = Contract(id="x", role="", kind="claude-subagent")
        with self._no_env():
            self.assertEqual(D._resolve_model(c), "")

    def test_resolve_model_env_overrides_contract(self):
        """CLAUDE_MODEL env wins over contract.model (tier 1 > tier 2)."""
        c = Contract(id="company-partner", role="", kind="claude-subagent",
                     model="claude-haiku-4-5")
        prev = os.environ.pop("CLAUDE_MODEL", None)
        os.environ["CLAUDE_MODEL"] = "claude-sonnet-4-6"
        try:
            result = D._resolve_model(c)
        finally:
            os.environ.pop("CLAUDE_MODEL", None)
            if prev is not None:
                os.environ["CLAUDE_MODEL"] = prev
        self.assertEqual(result, "claude-sonnet-4-6")

    def test_resolve_model_sapphire_model_env_overrides_contract(self):
        """SAPPHIRE_MODEL env also overrides contract.model."""
        c = Contract(id="company-partner", role="", kind="claude-subagent",
                     model="claude-haiku-4-5")
        prev_c = os.environ.pop("CLAUDE_MODEL", None)
        prev_s = os.environ.pop("SAPPHIRE_MODEL", None)
        os.environ["SAPPHIRE_MODEL"] = "claude-opus-4-5"
        try:
            result = D._resolve_model(c)
        finally:
            os.environ.pop("SAPPHIRE_MODEL", None)
            if prev_c is not None:
                os.environ["CLAUDE_MODEL"] = prev_c
            if prev_s is not None:
                os.environ["SAPPHIRE_MODEL"] = prev_s
        self.assertEqual(result, "claude-opus-4-5")

    def test_resolve_model_none_contract(self):
        """_resolve_model(None) → empty string (safe for batch with no items)."""
        with self._no_env():
            self.assertEqual(D._resolve_model(None), "")

    # ── dispatch_claude integration: --model flag in argv ────────────────────

    def test_bucket2_partner_dispatches_haiku(self):
        """Bucket-2 company-partner contract → --model claude-haiku-4-5 in argv."""
        c = Contract(id="company-partner", role="", kind="claude-subagent",
                     model="claude-haiku-4-5",
                     output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}})
        with self._no_env():
            argv = self._dispatch(c)
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-haiku-4-5")

    def test_bucket2_ex_fda_regulator_dispatches_haiku(self):
        """ex-fda-regulator → haiku."""
        c = Contract(id="ex-fda-regulator", role="", kind="claude-subagent",
                     model="claude-haiku-4-5",
                     output_schema={"type": "object"})
        with self._no_env():
            argv = self._dispatch(c)
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-haiku-4-5")

    def test_bucket1_fact_agent_dispatches_sonnet(self):
        """Bucket-1 fact agent (fda-institutional-memory) → sonnet."""
        c = Contract(id="fda-institutional-memory", role="", kind="claude-subagent",
                     model="claude-sonnet-4-6",
                     output_schema={"type": "object"})
        with self._no_env():
            argv = self._dispatch(c)
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-sonnet-4-6")

    def test_rescue_mechanism_dispatches_sonnet(self):
        """rescue-mechanism (Bucket-1 scientific) → sonnet."""
        c = Contract(id="rescue-mechanism", role="", kind="claude-subagent",
                     model="claude-sonnet-4-6",
                     output_schema={"type": "object"})
        with self._no_env():
            argv = self._dispatch(c)
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-sonnet-4-6")

    def test_env_override_beats_per_agent_model(self):
        """CLAUDE_MODEL env wins even when contract.model says haiku."""
        c = Contract(id="company-partner", role="", kind="claude-subagent",
                     model="claude-haiku-4-5",
                     output_schema={"type": "object"})
        prev_c = os.environ.pop("CLAUDE_MODEL", None)
        prev_s = os.environ.pop("SAPPHIRE_MODEL", None)
        os.environ["CLAUDE_MODEL"] = "claude-sonnet-4-6"
        try:
            captured = []
            stdout = self._canned_env()
            D.dispatch_claude(c, {}, runner=capturing_runner(captured, stdout))
            argv = captured[0]
        finally:
            os.environ.pop("CLAUDE_MODEL", None)
            if prev_c is not None:
                os.environ["CLAUDE_MODEL"] = prev_c
            if prev_s is not None:
                os.environ["SAPPHIRE_MODEL"] = prev_s
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-sonnet-4-6")

    # ── Registry-level: verify agents.json encodes the right models ──────────

    def test_registry_bucket2_agents_have_haiku(self):
        """All Bucket-2 verdict agents in agents.json declare model=claude-haiku-4-5."""
        from harness.contracts import load_registry, resolve
        reg = load_registry()
        b2_ids = {"company-partner", "ex-fda-regulator", "adversarial-red-team",
                  "payer-partner", "kol-partner"}
        for entry in reg["agents"]:
            if entry["id"] in b2_ids:
                self.assertEqual(
                    entry.get("model"), "claude-haiku-4-5",
                    f"{entry['id']} should be claude-haiku-4-5",
                )

    def test_registry_bucket1_claude_subagent_fact_agents_have_sonnet(self):
        """Bucket-1 semantic + rescue-mechanism agents in agents.json declare sonnet."""
        from harness.contracts import load_registry
        reg = load_registry()
        b1_ids = {
            "fda-institutional-memory", "patent-ip", "global-regulatory-divergence",
            "dea-scheduling", "clinical-trial-registry", "post-market-safety",
            "financial", "payer", "manufacturing-cmc", "patient-advocacy",
            "kol-social", "policy-legislative", "reputational", "rescue-mechanism",
        }
        for entry in reg["agents"]:
            if entry["id"] in b1_ids:
                self.assertEqual(
                    entry.get("model"), "claude-sonnet-4-6",
                    f"{entry['id']} should be claude-sonnet-4-6",
                )

    def test_registry_resolve_loads_model_field(self):
        """contracts.resolve() populates Contract.model from agents.json."""
        from harness.contracts import resolve
        c = resolve("company-partner")
        self.assertEqual(c.model, "claude-haiku-4-5")
        c2 = resolve("fda-institutional-memory")
        self.assertEqual(c2.model, "claude-sonnet-4-6")


class TestSimulateModels(unittest.TestCase):
    """SAPPHIRE_SIMULATE_MODELS=1 → labeled, schema-valid simulated output, NO claude call."""

    _VERDICT = Contract(
        id="company-partner", role="", kind="claude-subagent", provenance_label="persona-judgment",
        output_schema={"type": "object", "additionalProperties": False,
                       "required": ["persona", "stance", "conviction", "rationale", "fact_claims"],
                       "properties": {
                           "persona": {"type": "string"},
                           "stance": {"type": "string", "enum": ["pass", "conditional", "hold", "no_go"]},
                           "conviction": {"type": "integer"},
                           "rationale": {"type": "string"},
                           "fact_claims": {"type": "array", "items": {"type": "object"}},
                           "provenance": {"type": "string"}}})
    _FACTS = Contract(
        id="some-fact-agent", role="", kind="claude-subagent", provenance_label="semantic-web",
        output_schema={"type": "object", "additionalProperties": False,
                       "required": ["candidate", "facts"],
                       "properties": {
                           "candidate": {"type": "string"},
                           "facts": {"type": "array", "items": {"type": "object",
                                     "properties": {"value": {"type": "string"}, "source": {"type": "string"},
                                                    "tier": {"type": "string"}, "provenance": {"type": "string"}}}},
                           "provenance": {"type": "string"}}})

    def setUp(self):
        self._prev = os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)
        if self._prev is not None:
            os.environ["SAPPHIRE_SIMULATE_MODELS"] = self._prev

    def _boom_runner(self, cmd):
        raise AssertionError("claude must NOT be called when simulate-models is on")

    def test_off_by_default(self):
        self.assertFalse(D._simulate_models_on())

    def test_persona_verdict_simulated_and_labeled(self):
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        out = D.dispatch_claude(self._VERDICT, {"persona": "Denali CSO"}, runner=self._boom_runner)
        self.assertEqual(out["provenance"], "simulated")
        self.assertIn(D.SIMULATE_MARKER, out["rationale"])     # 🧪 marker survives + is unmistakable
        self.assertIn(out["stance"], ["pass", "conditional", "hold", "no_go"])  # schema-valid enum
        self.assertEqual(out["persona"], "Denali CSO")          # echoes the input persona

    def test_fact_agent_simulated_and_labeled(self):
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        out = D.dispatch_claude(self._FACTS, {"candidate": "TSC2"}, runner=self._boom_runner)
        self.assertEqual(out["candidate"], "TSC2")
        self.assertTrue(out["facts"])
        self.assertEqual(out["facts"][0]["provenance"], "simulated")
        self.assertIn("simulated", out["facts"][0]["value"].lower())

    def test_only_schema_keys_emitted(self):
        # additionalProperties:false → simulated output must contain ONLY declared keys.
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        out = D.dispatch_claude(self._VERDICT, {}, runner=self._boom_runner)
        allowed = set(self._VERDICT.output_schema["properties"])
        self.assertTrue(set(out).issubset(allowed), f"unexpected keys: {set(out) - allowed}")

    def test_batch_also_simulates(self):
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        out = D.dispatch_claude_batch([(self._FACTS, {"candidate": "TSC2"})], runner=self._boom_runner)
        self.assertIn("some-fact-agent", out)
        self.assertEqual(out["some-fact-agent"]["provenance"], "simulated")


class TestAgentTimeoutCap(unittest.TestCase):
    """$SAPPHIRE_AGENT_TIMEOUT_S caps the per-agent subprocess timeout (min with the contract)."""

    def setUp(self):
        self._prev = os.environ.pop("SAPPHIRE_AGENT_TIMEOUT_S", None)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_AGENT_TIMEOUT_S", None)
        if self._prev is not None:
            os.environ["SAPPHIRE_AGENT_TIMEOUT_S"] = self._prev

    def test_unset_uses_contract(self):
        self.assertEqual(D._agent_timeout(600), 600)

    def test_cap_lowers_a_high_contract_timeout(self):
        os.environ["SAPPHIRE_AGENT_TIMEOUT_S"] = "120"
        self.assertEqual(D._agent_timeout(600), 120)      # min(600, 120)

    def test_cap_does_not_raise_a_low_contract_timeout(self):
        os.environ["SAPPHIRE_AGENT_TIMEOUT_S"] = "600"
        self.assertEqual(D._agent_timeout(120), 120)      # min(120, 600)

    def test_floor_and_bad_value(self):
        os.environ["SAPPHIRE_AGENT_TIMEOUT_S"] = "5"
        self.assertEqual(D._agent_timeout(600), 30)       # floored at 30
        os.environ["SAPPHIRE_AGENT_TIMEOUT_S"] = "nonsense"
        self.assertEqual(D._agent_timeout(300), 300)      # bad → contract value


if __name__ == "__main__":
    unittest.main()
