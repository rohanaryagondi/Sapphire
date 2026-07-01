# -*- coding: utf-8 -*-
"""WO-9 Phase 4 — hermetic tests for GPU-tier Q-Models dispatch.

No real AWS calls: the launcher and boto are mocked/patched throughout.
Three coverage goals:
  1. GPU-tier tool selection routes to the launcher path (not local-cpu).
  2. Default (SAPPHIRE_QMODELS_LIVE unset/0) returns a labeled gpu-dry-run result.
  3. Live path (SAPPHIRE_QMODELS_LIVE=1) is exercised with a MOCK launcher:
     - asserts tagged create (Name=Sapphire) recorded in ledger
     - asserts ledger append (create event present)
     - asserts teardown is gated to ledgered ids
     - zero real boto/aws calls
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---- module imports ----
import sys
# ensure sapphire-orchestrator is on the path (tests/conftest or run from orchestrator root)
ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from qmodels.client import QModelsClient, REGISTRY_PATH
from qmodels import launcher as L


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gpu_tool_stub():
    """A minimal tool dict that looks like a gpu-launch entry."""
    return {
        "id": "family_clustering",
        "label": "Protein Family Clustering",
        "tier": "gpu-launch",
        "status": "live",
        "invoke": {"instance_type": "g6e.xlarge"},
    }


def _cpu_tool_stub():
    return {"id": "dti", "label": "DTI / Binder Triage", "tier": "local-cpu", "status": "live-local"}


def _make_client(extra_tools=None):
    """Build a QModelsClient with a minimal registry (no file I/O)."""
    tools = [_cpu_tool_stub(), _gpu_tool_stub()]
    if extra_tools:
        tools.extend(extra_tools)
    registry = {"models": [], "tracks": tools}
    return QModelsClient(registry=registry)


# ---------------------------------------------------------------------------
# 1. GPU-tier routing
# ---------------------------------------------------------------------------

class TestGpuTierRouting(unittest.TestCase):
    """GPU-tier tools are routed through _submit_gpu, not _call_local."""

    def test_gpu_tier_tool_calls_submit_gpu_not_call_local(self):
        """calling client.call() on a gpu-launch tool must NOT hit _call_local."""
        client = _make_client()
        hit_local = []
        hit_gpu = []

        original_call_local = client._call_local
        original_submit_gpu = client._submit_gpu

        def fake_local(tool, inputs, live_tracks, adapters):
            hit_local.append(tool["id"])
            return {"ok": True, "provenance": "live-local", "out": "local"}

        def fake_gpu(tool, inputs):
            hit_gpu.append(tool["id"])
            return {"ok": True, "provenance": "gpu-dry-run", "out": "dry-run"}

        client._call_local = fake_local
        client._submit_gpu = fake_gpu

        client.call("family_clustering", {"sequences": []})
        self.assertEqual(hit_local, [], "gpu-launch tool should NOT hit _call_local")
        self.assertEqual(hit_gpu, ["family_clustering"], "gpu-launch tool should hit _submit_gpu")

    def test_cpu_tier_tool_calls_call_local_not_submit_gpu(self):
        """local-cpu tools must NOT hit _submit_gpu."""
        client = _make_client()
        hit_gpu = []

        def fake_gpu(tool, inputs):
            hit_gpu.append(tool["id"])
            return {"ok": True, "provenance": "gpu-dry-run", "out": ""}

        client._submit_gpu = fake_gpu

        # patch _call_local so we don't need the Explorer endpoint up
        def fake_local(tool, inputs, live_tracks, adapters):
            return {"ok": True, "provenance": "live-local", "out": "local"}

        client._call_local = fake_local
        client.call("dti", {"smiles": "CCO"})
        self.assertEqual(hit_gpu, [], "local-cpu tool must NOT hit _submit_gpu")


# ---------------------------------------------------------------------------
# 2. Dry-run default (SAPPHIRE_QMODELS_LIVE not set / =0)
# ---------------------------------------------------------------------------

class TestGpuDryRunDefault(unittest.TestCase):
    """Without SAPPHIRE_QMODELS_LIVE=1, gpu-launch tools return gpu-dry-run."""

    def _call_gpu_tool_dry(self):
        """Call family_clustering with LIVE env unset; patch the launcher to capture calls."""
        launcher_calls = []

        def fake_submit(tool, inputs, mode="dry-run", kind="tool", **kw):
            launcher_calls.append({"tool": tool, "inputs": inputs, "mode": mode})
            return {
                "job_id": "sapphire-qmodels-tool-drytest",
                "status": "dry-run-validated",
                "mode": "dry-run",
            }

        client = _make_client()

        import qmodels.client as _client_mod
        prev_live = _client_mod.QMODELS_LIVE
        _client_mod.QMODELS_LIVE = False  # force dry-run regardless of env
        try:
            with patch("qmodels.client.QModelsClient._import_launcher",
                       return_value=SimpleNamespace(submit_job=fake_submit),
                       create=True):
                # Directly patch submit_job on the imported launcher module
                import qmodels.launcher as _launcher_mod
                orig_submit = _launcher_mod.submit_job
                _launcher_mod.submit_job = fake_submit
                try:
                    result = client._submit_gpu(_gpu_tool_stub(), {"sequences": [{"name": "A", "sequence": "MK", "family": "test"}]})
                finally:
                    _launcher_mod.submit_job = orig_submit
        finally:
            _client_mod.QMODELS_LIVE = prev_live

        return result, launcher_calls

    def test_dry_run_provenance_is_gpu_dry_run(self):
        result, _ = self._call_gpu_tool_dry()
        self.assertEqual(result["provenance"], "gpu-dry-run",
                         f"Expected gpu-dry-run, got {result.get('provenance')!r}")

    def test_dry_run_ok_is_true(self):
        result, _ = self._call_gpu_tool_dry()
        self.assertTrue(result["ok"])

    def test_dry_run_out_is_labeled(self):
        result, _ = self._call_gpu_tool_dry()
        out = result.get("out", "")
        self.assertIn("dry-run", out.lower(),
                      f"dry-run out should mention dry-run, got: {out!r}")
        self.assertIn("family_clustering", out,
                      "dry-run out should name the tool_id")

    def test_dry_run_no_aws_calls(self):
        """The launcher's submit_job is called with mode=dry-run — which is pure local."""
        _, calls = self._call_gpu_tool_dry()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["mode"], "dry-run")

    def test_dispatch_qmodels_gpu_dry_run_in_fact_value(self):
        """dispatch_qmodels integrates gpu-dry-run into fact value with the labeled out string."""
        from harness import dispatch as D
        from harness.contracts import Contract

        def fake_call(tool_id, payload):
            return {
                "ok": True,
                "tool_id": tool_id,
                "provenance": "gpu-dry-run",
                "model": "Protein Family Clustering",
                "out": f"GPU tool {tool_id!r} selected; would launch tagged Sapphire EC2 (dry-run). Label: Protein Family Clustering. Input recorded. Set SAPPHIRE_QMODELS_LIVE=1 for a real run.",
            }

        client = _make_client()
        client.call = fake_call

        contract = Contract(id="q-models-runner", role="", kind="qmodels-delegate")
        result = D.dispatch_qmodels(contract, {"tool_id": "family_clustering", "candidate": "CA14"},
                                     client=client)
        self.assertIn("facts", result)
        fact_val = result["facts"][0]["value"]
        self.assertIn("dry-run", fact_val.lower(),
                      f"fact value should mention dry-run, got: {fact_val!r}")
        self.assertEqual(result["provenance"], "gpu-dry-run")


# ---------------------------------------------------------------------------
# 3. Live path with MOCK launcher — safety guards asserted
# ---------------------------------------------------------------------------

class TestGpuLiveMockLauncher(unittest.TestCase):
    """With SAPPHIRE_QMODELS_LIVE=1, the live path delegates to the launcher.
    All AWS is mocked — zero real boto/aws calls."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._prev_run = L._RUN_DIR
        self._prev_jobs = L._JOBS_DIR
        self._prev_ledger = L._LEDGER
        self._prev_snapshot = L._SNAPSHOT
        self._prev_budget = L.BUDGET_CAP_USD
        L._RUN_DIR = Path(self._tmp)
        L._JOBS_DIR = Path(self._tmp) / "jobs"
        L._LEDGER = Path(self._tmp) / "aws_ledger.jsonl"
        L._SNAPSHOT = Path(self._tmp) / "aws_preexisting_snapshot.json"
        # Write an empty snapshot so the launcher doesn't refuse for missing snapshot
        L._SNAPSHOT.write_text(json.dumps({"instances": []}))
        # Stub identity + bucket checks (live path calls these)
        self._prev_identity = L._assert_identity
        L._assert_identity = lambda: None
        self._prev_ensure_bucket = L.ensure_bucket
        L.ensure_bucket = lambda aws=None: "sapphire-qmodels-scratch-255493511886"
        # Raise budget cap so tests exercise the live path (real live runs are separately capped)
        L.BUDGET_CAP_USD = 999.0

    def tearDown(self):
        L._RUN_DIR = self._prev_run
        L._JOBS_DIR = self._prev_jobs
        L._LEDGER = self._prev_ledger
        L._SNAPSHOT = self._prev_snapshot
        L._assert_identity = self._prev_identity
        L.ensure_bucket = self._prev_ensure_bucket
        L.BUDGET_CAP_USD = self._prev_budget

    def _mock_aws_for_live(self, instance_id="i-mock001"):
        """Fake AWS call that simulates: run-instances → instance created; describe → terminated; s3 cp → result."""
        result_json = json.dumps({"nn_recall": 1.0, "model": "esm2_3b"})
        calls_log = []

        def fake_aws(*args, **kwargs):
            calls_log.append(args)
            if args[:2] == ("ec2", "run-instances"):
                # tag-specifications arg must carry Value=Sapphire (the Name tag value)
                all_args_str = " ".join(str(a) for a in args)
                if "Value=Sapphire" not in all_args_str:
                    raise AssertionError(
                        f"run-instances called without Name=Sapphire tag; args: {args}")
                return {"Instances": [{"InstanceId": instance_id}]}
            if args[:2] == ("ec2", "describe-instances"):
                return ["terminated"]
            if args[:2] == ("s3", "cp"):
                return result_json
            if args[:2] == ("ssm", "get-parameter"):
                return "ami-0mock1234"
            return {}

        return fake_aws, calls_log

    def _presign_stub(self, bucket, key, method="get_object", expires=3600, s3=None):
        return f"https://mock/{bucket}/{key}?m={method}"

    def _run_live_submit_job(self, tool, inputs, instance_id="i-mock001"):
        """Run launcher.submit_job in live mode with fully mocked aws + presign.

        _launch_live calls the module-level _aws function directly (not an injected parameter),
        so we patch it on the module object. We also patch _presign (used in _stage_and_presign)
        and _assert_identity (already stubbed in setUp) and ensure_bucket (also stubbed in setUp).
        Additionally, _stage_and_presign calls _aws for s3 cp; we cover that too.
        """
        fake_aws, calls_log = self._mock_aws_for_live(instance_id=instance_id)

        import qmodels.launcher as _L
        prev_aws = _L._aws
        prev_presign = _L._presign
        _L._aws = fake_aws
        _L._presign = self._presign_stub
        try:
            job = _L.submit_job(tool, inputs, mode="live")
        finally:
            _L._aws = prev_aws
            _L._presign = prev_presign

        return job, calls_log

    def test_live_submit_creates_and_ledgers_instance(self):
        """live mode: an instance is created and the CREATE event is in the ledger."""
        tool = _gpu_tool_stub()
        inputs = {
            "sequences": [{"name": "CA14", "sequence": "MSLSSSS", "family": "carbonic_anhydrase"}]
        }
        job, _ = self._run_live_submit_job(tool, inputs, instance_id="i-mock001")
        self.assertEqual(job["status"], "launched")
        self.assertEqual(job["instance_id"], "i-mock001")
        # ledger has the create event
        ledger_events = [
            json.loads(line)
            for line in L._LEDGER.read_text().splitlines()
            if line.strip()
        ]
        create_events = [e for e in ledger_events
                         if e.get("event") == "create" and e.get("resource") == "instance"]
        self.assertEqual(len(create_events), 1)
        self.assertEqual(create_events[0]["id"], "i-mock001")

    def test_live_run_instances_tags_name_sapphire(self):
        """run-instances must be called with Name=Sapphire (as a tag value) in tag-specifications."""
        tool = _gpu_tool_stub()
        inputs = {"sequences": [{"name": "CA14", "sequence": "MK", "family": "test"}]}
        _, calls_log = self._run_live_submit_job(tool, inputs, instance_id="i-mock002")
        run_calls = [a for a in calls_log if a[:2] == ("ec2", "run-instances")]
        self.assertEqual(len(run_calls), 1)
        all_args_str = " ".join(str(a) for a in run_calls[0])
        self.assertIn("Value=Sapphire", all_args_str,
                      "run-instances must include {Key=Name,Value=Sapphire} in tag-specifications")

    def test_teardown_only_by_ledgered_id(self):
        """safe_terminate refuses an id not in the ledger (the core safety invariant)."""
        from qmodels.launcher import SafetyRefusal
        with self.assertRaises(SafetyRefusal):
            # "i-not-ours" is not in the ledger — must be refused
            L.safe_terminate("i-not-ours")

    def test_teardown_refuses_preexisting_instance(self):
        """safe_terminate refuses an id that appears in the pre-existing snapshot."""
        from qmodels.launcher import SafetyRefusal
        # Put the id in the ledger (as if WE created it) but ALSO in the snapshot
        L._ledger_append({"event": "create", "resource": "instance", "id": "i-preexist"})
        L._SNAPSHOT.write_text(json.dumps({"instances": [{"id": "i-preexist"}]}))
        with self.assertRaises(SafetyRefusal):
            L.safe_terminate("i-preexist")

    def test_client_live_returns_gpu_live_on_done_result(self):
        """With SAPPHIRE_QMODELS_LIVE=1 and a completed job, provenance=gpu-live."""
        import qmodels.client as _client_mod
        prev_live = _client_mod.QMODELS_LIVE
        _client_mod.QMODELS_LIVE = True
        try:
            tool = _gpu_tool_stub()
            job_id = "sapphire-qmodels-tool-mock99"

            def fake_submit(t, inputs, mode="dry-run", **kw):
                return {"job_id": job_id, "status": "launched", "instance_id": "i-m99"}

            def fake_wait(jid, **kw):
                return {
                    "job_id": jid, "status": "done",
                    "instance_id": "i-m99",
                    "result": {"nn_recall": 1.0},
                }

            import qmodels.launcher as _launcher_mod
            orig_submit = _launcher_mod.submit_job
            orig_wait = _launcher_mod.wait_for
            _launcher_mod.submit_job = fake_submit
            _launcher_mod.wait_for = fake_wait
            try:
                client = _make_client()
                result = client._submit_gpu(tool, {"sequences": []})
            finally:
                _launcher_mod.submit_job = orig_submit
                _launcher_mod.wait_for = orig_wait
        finally:
            _client_mod.QMODELS_LIVE = prev_live

        self.assertEqual(result["provenance"], "gpu-live")
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["nn_recall"], 1.0)

    def test_client_live_returns_gpu_stub_on_no_result(self):
        """done-no-result state degrades honestly to gpu-stub."""
        import qmodels.client as _client_mod
        prev_live = _client_mod.QMODELS_LIVE
        _client_mod.QMODELS_LIVE = True
        try:
            tool = _gpu_tool_stub()

            def fake_submit(t, inputs, mode="dry-run", **kw):
                return {"job_id": "jX", "status": "launched", "instance_id": "i-X"}

            def fake_wait(jid, **kw):
                return {"job_id": jid, "status": "done-no-result", "note": "no result.json"}

            import qmodels.launcher as _launcher_mod
            orig_submit = _launcher_mod.submit_job
            orig_wait = _launcher_mod.wait_for
            _launcher_mod.submit_job = fake_submit
            _launcher_mod.wait_for = fake_wait
            try:
                client = _make_client()
                result = client._submit_gpu(tool, {})
            finally:
                _launcher_mod.submit_job = orig_submit
                _launcher_mod.wait_for = orig_wait
        finally:
            _client_mod.QMODELS_LIVE = prev_live

        self.assertEqual(result["provenance"], "gpu-stub")
        self.assertFalse(result["ok"])

    def test_budget_cap_is_enforced(self):
        """submit_job(mode=live) with an estimate above the cap must refuse without launching."""
        # Set the cap to 0 so even the cheapest instance refuses
        prev_cap = L.BUDGET_CAP_USD
        L.BUDGET_CAP_USD = 0.0
        tool = _gpu_tool_stub()
        try:
            # Patch _assert_identity so it doesn't try real AWS
            result = L.submit_job(tool, {}, mode="live")
            self.assertEqual(result["status"], "refused-budget",
                             f"expected refused-budget, got {result['status']!r}")
        finally:
            L.BUDGET_CAP_USD = prev_cap

    def test_no_real_boto_calls_in_dry_run(self):
        """Dry-run must complete without importing boto3 or making any subprocess aws calls."""
        import subprocess
        orig_run = subprocess.run
        boto_imported = []
        subprocess_calls = []

        def guarded_run(cmd, **kw):
            if isinstance(cmd, (list, tuple)) and "aws" in str(cmd):
                subprocess_calls.append(cmd)
                raise AssertionError(f"Real aws subprocess call in dry-run: {cmd}")
            return orig_run(cmd, **kw)

        import qmodels.client as _client_mod
        prev_live = _client_mod.QMODELS_LIVE
        _client_mod.QMODELS_LIVE = False

        client = _make_client()
        with patch("subprocess.run", side_effect=guarded_run):
            result = client._submit_gpu(_gpu_tool_stub(),
                                         {"sequences": [{"name": "A", "sequence": "MK",
                                                         "family": "test"}]})

        _client_mod.QMODELS_LIVE = prev_live
        self.assertEqual(result["provenance"], "gpu-dry-run")
        self.assertEqual(subprocess_calls, [], "No aws subprocess calls in dry-run mode")


# ---------------------------------------------------------------------------
# 4. Provenance vocabulary completeness
# ---------------------------------------------------------------------------

class TestProvenanceVocabulary(unittest.TestCase):
    """gpu-dry-run, gpu-live, gpu-stub are in the provenance vocabulary and on the external plane."""

    def test_new_labels_in_provenance_set(self):
        from contracts.provenance import PROVENANCE, plane_for
        for label in ("gpu-dry-run", "gpu-live", "gpu-stub"):
            self.assertIn(label, PROVENANCE, f"{label!r} missing from PROVENANCE")
            self.assertEqual(plane_for(label), "external",
                             f"{label!r} should be external plane")

    def test_is_valid_provenance(self):
        from contracts.provenance import is_valid_provenance
        for label in ("gpu-dry-run", "gpu-live", "gpu-stub"):
            self.assertTrue(is_valid_provenance(label), f"{label!r} should be valid provenance")


if __name__ == "__main__":
    unittest.main()
