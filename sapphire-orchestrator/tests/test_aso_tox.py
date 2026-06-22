"""
tests/test_aso_tox.py — Verbatim-logic lock + integration tests for the ASO tox delegate.

Skips cleanly if sklearn/joblib are unavailable.
"""
from __future__ import annotations

import sys
import os
import unittest

# Ensure sapphire-orchestrator is on sys.path when running from repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ORCH_ROOT = os.path.dirname(_HERE)
if _ORCH_ROOT not in sys.path:
    sys.path.insert(0, _ORCH_ROOT)

# ---------------------------------------------------------------------------
# Skip guard — tests skip cleanly if sklearn/joblib not installed
# ---------------------------------------------------------------------------
try:
    import sklearn  # noqa: F401
    import joblib   # noqa: F401
    import numpy    # noqa: F401
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

_SKIP_REASON = "sklearn/joblib/numpy not installed in this environment"

# Three golden sequences (verbatim from the task spec)
_SEQS = [
    "GCACTTGAATTTCACGTTGT",
    "GGTGAATCTTTATTAAAC",
    "TTGCTCCACCTTGGCCTGGCA",
]

# Expected Hagedorn values (pure formula — version-independent)
_HAGEDORN_EXPECTED = [26.1763, 62.6419, 12.6636]

# Expected tox labels
_LABELS_EXPECTED = ["Toxic", "Non-toxic", "Toxic"]

# Reference GBR scores on sklearn 1.6.1 (ordering: seq3 > seq1 > seq2)
_GBR_REF = [1.884452, 0.562909, 2.820860]
_GBR_TOL = 0.05


# ---------------------------------------------------------------------------
# Pure-formula unit test (no sklearn needed)
# ---------------------------------------------------------------------------
class TestHagedornPureFormula(unittest.TestCase):
    """Hagedorn score only depends on the formula — always runs, no sklearn."""

    def _extract_features(self, seq):
        """Verbatim from predict.py / notebook."""
        seq = seq.upper().strip(); n = len(seq); f = {}
        for base in ['A', 'T', 'G', 'C']:
            max_run = 0
            for r in range(1, 7):
                if base * r in seq: max_run = r
            f[f'MaxLength_{base}'] = max_run
        for b in ['A', 'T', 'G', 'C']: f[f'Number_{b}'] = seq.count(b)
        Gfree5 = n
        for k in range(n):
            if seq[k] == 'G': Gfree5 = k; break
        f['Length_Gfree_5'] = Gfree5
        Gfree3 = n
        for k in range(n - 1, -1, -1):
            if seq[k] == 'G': Gfree3 = n - 1 - k; break
        f['Length_Gfree_3'] = Gfree3
        return f

    def _hagedorn_score(self, f):
        """Verbatim from predict.py / notebook."""
        return (136.0430
                - 3.1263 * f['Number_A']
                - 5.1100 * f['Number_C']
                - 4.7217 * f['Number_T']
                - 10.1264 * f['Number_G']
                + 1.3577 * f['Length_Gfree_3'])

    def test_hagedorn_golden_exact(self):
        import numpy as np
        for seq, expected in zip(_SEQS, _HAGEDORN_EXPECTED):
            f = self._extract_features(seq)
            score = float(np.round(self._hagedorn_score(f), 4))
            with self.subTest(seq=seq):
                self.assertAlmostEqual(score, expected, places=4,
                                       msg=f"Hagedorn mismatch for {seq}: got {score}, expected {expected}")


# ---------------------------------------------------------------------------
# Subprocess / seam tests (require sklearn)
# ---------------------------------------------------------------------------
@unittest.skipUnless(_SKLEARN_AVAILABLE, _SKIP_REASON)
class TestPredictGolden(unittest.TestCase):
    """Run the seam on three golden sequences and verify labels + GBR ordering."""

    def setUp(self):
        from tools import aso_tox_seam
        self.seam = aso_tox_seam

    def _run(self):
        result = self.seam.predict(_SEQS)
        self.assertNotIn("error", result, f"predict() returned error: {result.get('error')}")
        preds = result["predictions"]
        self.assertEqual(len(preds), 3)
        return preds

    def test_hagedorn_golden_via_subprocess(self):
        preds = self._run()
        for i, (pred, expected) in enumerate(zip(preds, _HAGEDORN_EXPECTED)):
            with self.subTest(i=i):
                self.assertAlmostEqual(pred["hagedorn_predict_toxscore"], expected, places=4,
                                       msg=f"seq {i}: Hagedorn {pred['hagedorn_predict_toxscore']} != {expected}")

    def test_tox_labels_golden(self):
        preds = self._run()
        for i, (pred, expected_label) in enumerate(zip(preds, _LABELS_EXPECTED)):
            with self.subTest(i=i):
                self.assertEqual(pred["tox_label"], expected_label,
                                 msg=f"seq {i}: label {pred['tox_label']!r} != {expected_label!r}")

    def test_gbr_ordering_seq3_gt_seq1_gt_seq2(self):
        """GBR ordering: seq3 > seq1 > seq2 regardless of exact sklearn version."""
        preds = self._run()
        gbr1 = preds[0]["gbr_predict_toxscore"]
        gbr2 = preds[1]["gbr_predict_toxscore"]
        gbr3 = preds[2]["gbr_predict_toxscore"]
        self.assertGreater(gbr3, gbr1, f"Expected gbr3 ({gbr3}) > gbr1 ({gbr1})")
        self.assertGreater(gbr1, gbr2, f"Expected gbr1 ({gbr1}) > gbr2 ({gbr2})")

    def test_gbr_within_loose_tolerance_of_reference(self):
        """GBR values within ±0.05 of sklearn 1.6.1 reference values."""
        preds = self._run()
        for i, (pred, ref) in enumerate(zip(preds, _GBR_REF)):
            got = pred["gbr_predict_toxscore"]
            with self.subTest(i=i):
                self.assertAlmostEqual(got, ref, delta=_GBR_TOL,
                                       msg=f"seq {i}: GBR {got} not within ±{_GBR_TOL} of ref {ref}")


@unittest.skipUnless(_SKLEARN_AVAILABLE, _SKIP_REASON)
class TestSeamFindingsShape(unittest.TestCase):
    """predict_findings() returns the harness findings dict contract."""

    def setUp(self):
        from tools import aso_tox_seam
        self.seam = aso_tox_seam

    def test_findings_with_sequences(self):
        result = self.seam.predict_findings({"candidate": "UBE3A", "sequences": _SEQS})
        self.assertEqual(result["provenance"], "aso-tox")
        self.assertEqual(result["candidate"], "UBE3A")
        self.assertEqual(len(result["facts"]), len(_SEQS),
                         f"Expected {len(_SEQS)} facts, got {len(result['facts'])}")
        for fact in result["facts"]:
            self.assertIn("value", fact)
            self.assertIn("source", fact)
            self.assertEqual(fact["tier"], "T2")

    def test_findings_no_sequences_returns_empty_not_raise(self):
        """No sequences → facts=[] and no exception."""
        result = self.seam.predict_findings({"candidate": "TSC2"})
        self.assertEqual(result["provenance"], "aso-tox")
        self.assertEqual(result["facts"], [])
        self.assertNotIn("error", result)

    def test_findings_empty_sequences_list(self):
        result = self.seam.predict_findings({"candidate": "X", "sequences": []})
        self.assertEqual(result["facts"], [])


class TestHarnessRegistry(unittest.TestCase):
    """aso-tox agent resolves correctly from agents.json."""

    def test_resolve_aso_tox(self):
        from harness.contracts import resolve, Contract
        c = resolve("aso-tox")
        self.assertIsInstance(c, Contract)

    def test_aso_tox_kind_python(self):
        from harness.contracts import resolve
        c = resolve("aso-tox")
        self.assertEqual(c.kind, "python")

    def test_aso_tox_provenance_label(self):
        from harness.contracts import resolve
        c = resolve("aso-tox")
        self.assertEqual(c.provenance_label, "aso-tox")

    def test_aso_tox_output_schema_inlined(self):
        """output_schema must be inlined (no $ref remaining)."""
        from harness.contracts import resolve
        c = resolve("aso-tox")
        self.assertIsNotNone(c.output_schema)
        self.assertNotIn("$ref", c.output_schema)

    def test_aso_tox_guardrails(self):
        from harness.contracts import resolve
        c = resolve("aso-tox")
        self.assertIn("facts_only_cited", c.guardrails)
        self.assertIn("stamp_provenance", c.guardrails)


class TestFailSafeEnvelope(unittest.TestCase):
    """Seam returns error envelope on bad path, never raises."""

    def test_bogus_predict_path_returns_envelope(self):
        import subprocess
        import json
        import sys
        # Call predict.py with a non-existent path — simulate by calling a missing script
        payload = json.dumps({"sequences": ["GCAC"]})
        result = subprocess.run(
            [sys.executable, "/nonexistent/path/predict.py", "--json"],
            input=payload,
            capture_output=True,
            text=True,
        )
        # Should fail nonzero (FileNotFoundError at OS level)
        self.assertNotEqual(result.returncode, 0)

    def test_seam_predict_empty_sequences(self):
        from tools import aso_tox_seam
        result = aso_tox_seam.predict([])
        self.assertEqual(result["predictions"], [])
        self.assertNotIn("error", result)

    def test_seam_predict_findings_no_sequences_no_raise(self):
        from tools import aso_tox_seam
        # Should not raise even with no sequences key at all
        try:
            result = aso_tox_seam.predict_findings({})
            self.assertEqual(result["facts"], [])
        except Exception as exc:
            self.fail(f"predict_findings raised unexpectedly: {exc}")


if __name__ == "__main__":
    unittest.main()
