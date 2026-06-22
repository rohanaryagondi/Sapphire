import json
import unittest
from types import SimpleNamespace
from harness.contracts import Contract
from harness import dispatch as D

def fake_runner(stdout, returncode=0, stderr=""):
    return lambda cmd: SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)

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

    def test_dispatch_emet_without_handler_errors(self):
        c = Contract(id="emet-runner", role="", kind="emet-playwright")
        with self.assertRaises(RuntimeError):
            D.dispatch(c, {"candidate": "SCN11A"}, ctx={})

if __name__ == "__main__":
    unittest.main()
