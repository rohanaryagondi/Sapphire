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


if __name__ == "__main__":
    unittest.main()
