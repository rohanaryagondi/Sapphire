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

# boto3 is a LAUNCH-ONLY dep (used lazily in launcher._presign) — not a guaranteed test-env dep,
# and every other suite is stdlib-only. So the presign tests SKIP (not error) where it's absent.
try:
    import boto3  # noqa: F401
    _HAS_BOTO3 = True
except ImportError:
    _HAS_BOTO3 = False


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


class TestUserdataRender(unittest.TestCase):
    """Gap 1 — the recipe-driven GPU userdata renders to the proven S3-staged pattern (no git clone)."""

    _JOB = {"job_id": "sapphire-qmodels-tool-abc", "tool_id": "boltz2",
            "inputs": {"target_seq": "MKVLA", "smiles": "CCO", "name": "tsc2_x"}}

    def test_build_inputs_is_valid_complexes(self):
        cx = json.loads(L._build_inputs(self._JOB))
        self.assertEqual(cx[0]["protein_seq"], "MKVLA")
        self.assertEqual(cx[0]["smiles"], "CCO")

    def test_userdata_stages_via_presigned_get_not_git_clone(self):
        ud = L._render_tool_userdata(self._JOB, L._placeholder_urls(L._gpu_recipe("boltz2")))
        self.assertNotIn("git clone", ud)                      # the Gate-1 root cause is gone
        self.assertIn("boltz_runner.py", ud)                   # code staged
        self.assertIn("complexes.json", ud)                    # inputs staged
        self.assertIn("geturl get:boltz_runner.py", ud)        # via presigned GET
        self.assertIn("pip install", ud)
        self.assertIn("boltz", ud)                             # the dep
        self.assertIn("python boltz_runner.py complexes.json", ud)  # the run
        self.assertIn("export BOLTZ_OUT=", ud)                 # out env
        self.assertIn("put:results.json", ud)                  # result uploaded (presigned PUT)
        self.assertIn("shutdown -h now", ud)                   # parachute + final
        self.assertIn("sleep 3600", ud)                        # 60-min hard cap

    def test_unwired_tool_userdata_is_a_clear_stub(self):
        eng = tempfile.mkdtemp()
        prev = (L._RUN_DIR, L._JOBS_DIR, L._LEDGER)
        L._RUN_DIR, L._JOBS_DIR, L._LEDGER = (
            __import__("pathlib").Path(eng), __import__("pathlib").Path(eng) / "jobs",
            __import__("pathlib").Path(eng) / "ledger.jsonl")
        try:
            job = L.submit_job({"id": "esm2"}, {"x": 1}, mode="dry-run")  # esm2 has no recipe yet
            self.assertIn("no GPU recipe", job["userdata"])   # clear stub, not a crash
            self.assertNotIn("python boltz_runner", job["userdata"])
        finally:
            L._RUN_DIR, L._JOBS_DIR, L._LEDGER = prev

    def test_dry_run_boltz_renders_real_recipe_userdata(self):
        eng = tempfile.mkdtemp()
        prev = (L._RUN_DIR, L._JOBS_DIR, L._LEDGER)
        from pathlib import Path
        L._RUN_DIR, L._JOBS_DIR, L._LEDGER = Path(eng), Path(eng) / "jobs", Path(eng) / "ledger.jsonl"
        try:
            job = L.submit_job({"id": "boltz2"}, {"target_seq": "MKVLA", "smiles": "CCO"}, mode="dry-run")
            self.assertEqual(job["status"], "dry-run-validated")
            self.assertIn("python boltz_runner.py complexes.json", job["userdata"])
            self.assertNotIn("git clone", job["userdata"])
        finally:
            L._RUN_DIR, L._JOBS_DIR, L._LEDGER = prev


class TestLifecycle(unittest.TestCase):
    """Gap 3 — staging + S3 result retrieval + wait_for, all offline (injected aws/presign)."""

    def setUp(self):
        from pathlib import Path
        self._tmp = tempfile.mkdtemp()
        self._prev = (L._RUN_DIR, L._JOBS_DIR, L._LEDGER)
        L._RUN_DIR, L._JOBS_DIR, L._LEDGER = (
            Path(self._tmp), Path(self._tmp) / "jobs", Path(self._tmp) / "ledger.jsonl")

    def tearDown(self):
        L._RUN_DIR, L._JOBS_DIR, L._LEDGER = self._prev

    def test_stage_and_presign_builds_full_url_set(self):
        calls = []
        aws = lambda *a, **k: calls.append(a) or {}
        presign = lambda b, key, method="get_object", **k: f"https://{b}/{key}?sig=X&m={method}"
        job = {"job_id": "sapphire-qmodels-tool-1", "tool_id": "boltz2",
               "inputs": {"target_seq": "MK", "smiles": "CCO"}}
        urls = L._stage_and_presign(job, "buck", aws=aws, presign=presign)
        self.assertEqual(set(urls), {"get:boltz_runner.py", "get:complexes.json",
                                     "put:results.json", "put:progress.log"})
        cps = [a for a in calls if a[:2] == ("s3", "cp")]
        self.assertGreaterEqual(len(cps), 2)              # code + inputs uploaded
        self.assertIn("put_object", urls["put:results.json"])

    def test_job_status_downloads_result_when_terminated(self):
        from pathlib import Path
        Path(L._JOBS_DIR).mkdir(parents=True, exist_ok=True)
        L._write_job({"job_id": "j1", "status": "launched", "instance_id": "i-abc"})
        result_json = json.dumps({"prob_binder": 0.81, "log_ic50": -6.2})

        def aws(*a, **k):
            if a[:2] == ("ec2", "describe-instances"):
                return ["terminated"]
            if a[:2] == ("s3", "cp"):
                return result_json                        # parse=False path returns the body
            return {}
        job = L.job_status("j1", aws=aws)
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"]["prob_binder"], 0.81)

    def test_job_status_done_no_result_when_missing(self):
        from pathlib import Path
        Path(L._JOBS_DIR).mkdir(parents=True, exist_ok=True)
        L._write_job({"job_id": "j2", "status": "launched", "instance_id": "i-xyz"})

        def aws(*a, **k):
            if a[:2] == ("ec2", "describe-instances"):
                return ["terminated"]
            if a[:2] == ("s3", "cp"):
                raise RuntimeError("NoSuchKey")
            return {}
        job = L.job_status("j2", aws=aws)
        self.assertEqual(job["status"], "done-no-result")   # honest: no fabricated prediction

    def test_wait_for_returns_when_done(self):
        from pathlib import Path
        Path(L._JOBS_DIR).mkdir(parents=True, exist_ok=True)
        L._write_job({"job_id": "j3", "status": "launched", "instance_id": "i-1"})

        def aws(*a, **k):
            if a[:2] == ("ec2", "describe-instances"):
                return ["terminated"]
            if a[:2] == ("s3", "cp"):
                return json.dumps({"prob_binder": 0.5})
            return {}
        job = L.wait_for("j3", timeout=120, poll=1, aws=aws, sleep=lambda _s: None)
        self.assertEqual(job["status"], "done")


@unittest.skipUnless(_HAS_BOTO3, "boto3 not installed (launch-only dep) — presign tests skipped")
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


class TestAmiSelection(unittest.TestCase):
    """A GPU (tool) job must boot the Ubuntu Deep-Learning GPU AMI; smoke uses the CPU al2023 AMI."""

    def test_tool_job_uses_gpu_ubuntu_ami(self):
        ssm = L._ami_ssm_for({"kind": "tool", "tool_id": "boltz2"})
        self.assertEqual(ssm, L.GPU_AMI_SSM)
        self.assertIn("gpu-ubuntu-22.04", ssm)          # NVIDIA driver + apt-based, as the userdata needs

    def test_smoke_job_uses_cpu_ami(self):
        self.assertEqual(L._ami_ssm_for({"kind": "smoke"}), L.PUBLIC_AMI_SSM)


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
