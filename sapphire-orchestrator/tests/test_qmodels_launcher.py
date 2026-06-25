"""Offline tests for qmodels/launcher.py scratch-bucket lifecycle (Task 2, Gap 4a).

No AWS: a fake `aws` callable is injected; the ledger is redirected to a temp dir so the real
RohanOnly ledger is untouched. Asserts the create-only / teardown-by-ledger safety invariants.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from qmodels import launcher as L
from qmodels.launcher import SafetyRefusal


class _FakeAws:
    """Records aws calls; head-bucket raises (absent) unless `existing` lists the bucket."""
    def __init__(self, existing=()):
        self.calls = []
        self.existing = set(existing)

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        if args[:2] == ("s3api", "head-bucket"):
            name = args[args.index("--bucket") + 1]
            if name not in self.existing:
                raise RuntimeError("head-bucket: 404 (absent)")
        return {}


class TestScratchBucket(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._prev = {"RUN": L._RUN_DIR, "LEDGER": L._LEDGER}
        L._RUN_DIR = Path(self._tmp)
        L._LEDGER = Path(self._tmp) / "aws_ledger.jsonl"
        # _assert_identity would hit AWS — stub it (the create path calls it).
        self._prev_assert = L._assert_identity
        L._assert_identity = lambda: None

    def tearDown(self):
        L._RUN_DIR = self._prev["RUN"]
        L._LEDGER = self._prev["LEDGER"]
        L._assert_identity = self._prev_assert

    def test_bucket_name_is_account_scoped(self):
        self.assertEqual(L._bucket_name(), f"{L.NAME_PREFIX}-scratch-{L.EXPECTED_ACCOUNT}")

    def test_ensure_bucket_creates_and_ledgers_when_absent(self):
        aws = _FakeAws(existing=())
        name = L.ensure_bucket(aws=aws)
        self.assertEqual(name, L._bucket_name())
        verbs = [a[:2] for a in aws.calls]
        self.assertIn(("s3api", "head-bucket"), verbs)
        self.assertIn(("s3api", "create-bucket"), verbs)
        self.assertIn(name, L._ledger_created_buckets())   # ledgered

    def test_ensure_bucket_is_idempotent_when_present(self):
        aws = _FakeAws(existing=(L._bucket_name(),))
        L.ensure_bucket(aws=aws)
        verbs = [a[:2] for a in aws.calls]
        self.assertNotIn(("s3api", "create-bucket"), verbs)   # no-op
        self.assertEqual(L._ledger_created_buckets(), set())  # nothing ledgered

    def test_safe_delete_refuses_non_ledgered_bucket(self):
        with self.assertRaises(SafetyRefusal):
            L.safe_delete_bucket(L._bucket_name(), aws=_FakeAws())

    def test_safe_delete_refuses_non_scratch_name(self):
        # Even if (somehow) ledgered, a non-scratch name is refused by the name guard.
        L._ledger_append({"event": "create", "resource": "bucket", "id": "some-prod-bucket"})
        with self.assertRaises(SafetyRefusal):
            L.safe_delete_bucket("some-prod-bucket", aws=_FakeAws())

    def test_safe_delete_deletes_ledgered_scratch_bucket(self):
        name = L.ensure_bucket(aws=_FakeAws(existing=()))    # creates + ledgers
        aws = _FakeAws(existing=(name,))
        out = L.safe_delete_bucket(name, aws=aws)
        self.assertTrue(out["deleted"])
        verbs = [a[:2] for a in aws.calls]
        self.assertIn(("s3", "rm"), verbs)                   # emptied first
        self.assertIn(("s3api", "delete-bucket"), verbs)
        # teardown ledgered
        events = [json.loads(l) for l in L._LEDGER.read_text().splitlines() if l.strip()]
        self.assertTrue(any(e["event"] == "delete" and e["id"] == name for e in events))


class TestPresign(unittest.TestCase):
    """Presigned URL generation (Gap 4b) — boto3 signs locally (no network), offline-safe."""

    def _client(self):
        import boto3  # available; presigning is pure local signing (no creds round-trip)
        from botocore.config import Config
        return boto3.client("s3", region_name=L.REGION, config=Config(signature_version="s3v4"),
                            aws_access_key_id="testkey", aws_secret_access_key="testsecret")

    def test_presigned_put_is_a_put_url_for_the_key(self):
        url = L._presign("sapphire-qmodels-scratch-x", "job-1/result.json",
                         method="put_object", s3=self._client())
        self.assertIn("sapphire-qmodels-scratch-x", url)
        self.assertIn("job-1/result.json", url)
        self.assertIn("X-Amz-Signature", url)        # SigV4 presigned

    def test_presigned_get_for_input_staging(self):
        url = L._presign("sapphire-qmodels-scratch-x", "job-1/inputs.json",
                         method="get_object", s3=self._client())
        self.assertIn("inputs.json", url)
        self.assertIn("X-Amz-Signature", url)


class TestGpuRecipes(unittest.TestCase):
    """Per-tool GPU recipes (Gap 2) — Boltz-2 input mapping + unwired-tool refusal."""

    def test_boltz_complexes_maps_registry_inputs(self):
        cx = L._boltz_complexes({"target_seq": "MKVLA", "smiles": "CCO", "name": "tsc2_x"})
        self.assertEqual(len(cx), 1)
        self.assertEqual(cx[0]["protein_seq"], "MKVLA")     # boltz_runner reads protein_seq
        self.assertEqual(cx[0]["smiles"], "CCO")
        self.assertEqual(cx[0]["name"], "tsc2_x")

    def test_boltz_complexes_requires_seq_and_smiles(self):
        with self.assertRaises(ValueError):
            L._boltz_complexes({"target_seq": "MKVLA"})     # no smiles
        with self.assertRaises(ValueError):
            L._boltz_complexes({"smiles": "CCO"})           # no seq

    def test_boltz_recipe_shape(self):
        r = L._gpu_recipe("boltz2")
        self.assertEqual(r["deps"], ["boltz"])
        self.assertIn("boltz_runner.py", r["code"])
        self.assertEqual(r["result"], "results.json")
        self.assertTrue(callable(r["inputs_fn"]))

    def test_unwired_tool_refused(self):
        with self.assertRaises(L.SafetyRefusal):
            L._gpu_recipe("not-a-real-tool")


if __name__ == "__main__":
    unittest.main()
