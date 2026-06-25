"""simulate_exempt: a scientific-core reasoner (rescue-mechanism) does REAL reasoning even
under SAPPHIRE_SIMULATE_MODELS=1, while ordinary claude-subagents are stubbed. Both the
dispatch stub-skip AND the stamp_provenance honesty relabel must respect the exemption."""
import os
import unittest

from harness import dispatch
from harness.contracts import resolve
from harness.guardrails import stamp_provenance


class _Proc:
    returncode = 0
    stderr = ""
    stdout = '{"structured_output": {"target": "TSC2", "gene_mechanisms": [], "provenance": "scientific-reasoning"}}'


class TestSimulateExempt(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("SAPPHIRE_SIMULATE_MODELS")
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)
        else:
            os.environ["SAPPHIRE_SIMULATE_MODELS"] = self._prev

    def test_registry_marks_rescue_mechanism_exempt(self):
        self.assertTrue(resolve("rescue-mechanism").simulate_exempt)

    def test_ordinary_claude_agent_not_exempt(self):
        self.assertFalse(resolve("fda-institutional-memory").simulate_exempt)

    def test_exempt_agent_calls_runner_under_simulate(self):
        """The exempt agent must hit the REAL dispatch path (invoke the runner), not the stub."""
        c = resolve("rescue-mechanism")
        called = {}

        def runner(cmd):
            called["hit"] = True
            return _Proc()

        out = dispatch.dispatch_claude(c, {"target": "TSC2", "candidates": []}, runner=runner)
        self.assertTrue(called.get("hit"), "exempt agent must invoke the runner (real reasoning)")
        self.assertEqual(out.get("provenance"), "scientific-reasoning")

    def test_non_exempt_agent_returns_stub_under_simulate(self):
        """A non-exempt claude-subagent is replaced by the labeled simulated stub (no runner)."""
        c = resolve("fda-institutional-memory")
        called = {}

        def runner(cmd):
            called["hit"] = True
            return _Proc()

        out = dispatch.dispatch_claude(c, {"candidate": "TSC2"}, runner=runner)
        self.assertFalse(called.get("hit"), "non-exempt agent must NOT invoke the runner under simulate")
        self.assertEqual(out.get("provenance"), "simulated")

    def test_stamp_keeps_exempt_label_under_simulate(self):
        """HONESTY: an exempt agent's REAL output keeps its genuine provenance, never 'simulated'."""
        c = resolve("rescue-mechanism")
        out = stamp_provenance(c, {"target": "TSC2", "gene_mechanisms": [],
                                   "provenance": "scientific-reasoning"})
        self.assertEqual(out["provenance"], "scientific-reasoning")

    def test_stamp_relabels_non_exempt_under_simulate(self):
        c = resolve("fda-institutional-memory")
        out = stamp_provenance(c, {"candidate": "TSC2", "facts": []})
        self.assertEqual(out["provenance"], "simulated")


if __name__ == "__main__":
    unittest.main()
