import os
import tempfile
import unittest
from harness.runtime import run
from harness.errors import HarnessEscalation

OUT_SCHEMA = {"type": "object", "additionalProperties": False,
              "required": ["candidate", "facts"],
              "properties": {"candidate": {"type": "string"},
                             "facts": {"type": "array", "items": {"type": "object"}},
                             "provenance": {"type": "string"}}}

def reg(guardrails=None, max_repair=1, on_hard_fail="abstain"):
    return {"schemas": {}, "agents": [{
        "id": "t", "role": "", "kind": "python", "output_schema": OUT_SCHEMA,
        "guardrails": guardrails or ["stamp_provenance"], "provenance_label": "synthesis",
        "retry": {"max_repair": max_repair, "on_hard_fail": on_hard_fail}}]}

class TestRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.tmp

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)

    def test_happy_path_stamps_and_traces(self):
        ctx = {"python_fns": {"t": lambda i: {"candidate": "SCN11A", "facts": []}}}
        r = run("t", {"gene": "SCN11A"}, engagement_id="eng1", ctx=ctx, registry=reg())
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.output["provenance"], "synthesis")
        self.assertEqual(r.meta["repairs"], 0)
        # trace written
        from harness import trace
        self.assertTrue(trace.trace_path("eng1").exists())

    def test_schema_violation_repairs_then_abstains(self):
        calls = {"n": 0}
        def bad(i):
            calls["n"] += 1
            return {"candidate": "SCN11A"}   # missing 'facts' → always invalid
        ctx = {"python_fns": {"t": bad}}
        r = run("t", {"g": 1}, engagement_id="eng2", ctx=ctx, registry=reg(max_repair=1))
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "abstained")
        self.assertTrue(r.output["abstained"])
        self.assertEqual(r.error, "malformed-output")
        self.assertEqual(calls["n"], 2)      # initial + 1 repair

    def test_input_guard_blocks_pre_dispatch(self):
        called = {"n": 0}
        def fn(i):
            called["n"] += 1
            return {"candidate": "x", "facts": []}
        ctx = {"python_fns": {"t": fn}}
        r = run("t", {"s_internal": 0.9}, engagement_id="eng3", ctx=ctx,
                registry=reg(guardrails=["data_boundary", "stamp_provenance"]))
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "guardrail-violation")
        self.assertEqual(called["n"], 0)     # backend never called — nothing leaked

    def test_idempotency_cache_dispatches_once(self):
        calls = {"n": 0}
        def fn(i):
            calls["n"] += 1
            return {"candidate": "x", "facts": []}
        ctx = {"python_fns": {"t": fn}}
        run("t", {"g": 1}, engagement_id="eng4", ctx=ctx, registry=reg())
        run("t", {"g": 1}, engagement_id="eng4", ctx=ctx, registry=reg())
        self.assertEqual(calls["n"], 1)      # second served from cache

    def test_unknown_agent(self):
        r = run("nope", {}, engagement_id="eng5", registry={"schemas": {}, "agents": []})
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "unknown-agent")

    def test_escalation_from_dispatch(self):
        def boom(contract, inputs, ctx):
            raise HarnessEscalation("login-required", "BenchSci login")
        r = run("t", {"g": 1}, engagement_id="eng6", ctx={}, registry=reg(), dispatch_fn=boom)
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "escalated")
        self.assertEqual(r.error, "login-required")

    def test_output_guard_failure_maps_to_guardrail_violation(self):
        calls = {"n": 0}
        def fn(i):
            calls["n"] += 1
            return {"candidate": "SCN11A", "facts": [{"value": "x", "tier": "T2"}]}  # no source
        ctx = {"python_fns": {"t": fn}}
        r = run("t", {"g": 1}, engagement_id="eng7", ctx=ctx,
                registry=reg(guardrails=["facts_only_cited", "stamp_provenance"], max_repair=1))
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "guardrail-violation")
        self.assertEqual(r.status, "abstained")
        self.assertEqual(calls["n"], 2)

if __name__ == "__main__":
    unittest.main()
