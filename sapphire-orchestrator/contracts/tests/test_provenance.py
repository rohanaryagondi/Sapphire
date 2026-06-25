import unittest
from contracts.provenance import (
    PROVENANCE, _PLANE_MAP,
    is_valid_provenance, plane_for, is_boundary_violation,
)


class TestProvenance(unittest.TestCase):
    def test_fixed_labels_present(self):
        for label in ["emet-live", "emet-mcp", "memory-recall", "persona-judgment",
                      "synthesis", "live-local", "gpu-async", "gpu-disabled",
                      "stub", "unavailable", "mock"]:
            self.assertIn(label, PROVENANCE)

    def test_fixed_label_valid(self):
        self.assertTrue(is_valid_provenance("emet-live"))

    def test_qmodels_prefixed_valid(self):
        self.assertTrue(is_valid_provenance("qmodels:boltz2"))

    def test_unknown_invalid(self):
        self.assertFalse(is_valid_provenance("made-up"))

    def test_non_string_invalid(self):
        self.assertFalse(is_valid_provenance(None))

    def test_moat_real_valid(self):
        self.assertTrue(is_valid_provenance("moat-real"))


# ---------------------------------------------------------------------------
# A1: Plane-map totality — every label in PROVENANCE maps to exactly one plane.
# ---------------------------------------------------------------------------
class TestPlaneMapTotality(unittest.TestCase):
    """Every label in PROVENANCE must appear in _PLANE_MAP with a valid plane value."""

    def test_every_provenance_label_is_mapped(self):
        """No label in PROVENANCE may be absent from _PLANE_MAP."""
        unmapped = PROVENANCE - frozenset(_PLANE_MAP.keys())
        self.assertEqual(unmapped, frozenset(),
                         f"Labels missing from _PLANE_MAP: {unmapped}")

    def test_plane_values_are_valid(self):
        """Every mapped plane must be exactly 'internal' or 'external'."""
        valid_planes = {"internal", "external"}
        invalid = {k: v for k, v in _PLANE_MAP.items() if v not in valid_planes}
        self.assertEqual(invalid, {},
                         f"Labels with invalid plane values: {invalid}")

    # The INTERNAL plane: Quiver-proprietary data sources that must NEVER leave to external
    # agents. moat-real (CNS_DFP) and robyn-scs (SCS/STA neuronal-connectivity from Quiver's own
    # imaging) are both internal IP. Adding a source here TIGHTENS the boundary (more data
    # protected), never loosens it. (Data-boundary extension — flagged for the lead in dev/HELP.md.)
    _INTERNAL_LABELS = {"moat-real", "robyn-scs"}

    def test_moat_real_is_internal(self):
        self.assertEqual(_PLANE_MAP["moat-real"], "internal")

    def test_robyn_scs_is_internal(self):
        self.assertEqual(_PLANE_MAP["robyn-scs"], "internal")

    def test_only_known_internal_labels_internal_rest_external(self):
        """Exactly the known internal labels map to 'internal'; everything else is 'external'."""
        for label in PROVENANCE:
            expected = "internal" if label in self._INTERNAL_LABELS else "external"
            self.assertEqual(_PLANE_MAP[label], expected,
                             f"{label!r} should be {expected}, got {_PLANE_MAP[label]!r}")


# ---------------------------------------------------------------------------
# A1: plane_for() function
# ---------------------------------------------------------------------------
class TestPlaneFor(unittest.TestCase):
    def test_moat_real_returns_internal(self):
        self.assertEqual(plane_for("moat-real"), "internal")

    def test_emet_live_returns_external(self):
        self.assertEqual(plane_for("emet-live"), "external")

    def test_gnomad_returns_external(self):
        self.assertEqual(plane_for("gnomad"), "external")

    def test_aso_tox_returns_external(self):
        self.assertEqual(plane_for("aso-tox"), "external")

    def test_corpus_returns_external(self):
        self.assertEqual(plane_for("corpus"), "external")

    def test_qmodels_prefix_returns_external(self):
        """qmodels:* labels are always external (public-identifier inputs only)."""
        self.assertEqual(plane_for("qmodels:boltz2"), "external")
        self.assertEqual(plane_for("qmodels:gnomad-constraint"), "external")

    def test_unknown_label_raises_key_error(self):
        with self.assertRaises(KeyError):
            plane_for("nonexistent-label")

    def test_all_provenance_labels_resolve(self):
        """plane_for must succeed for every label in PROVENANCE."""
        for label in PROVENANCE:
            result = plane_for(label)
            self.assertIn(result, {"internal", "external"},
                          f"plane_for({label!r}) returned unexpected {result!r}")


# ---------------------------------------------------------------------------
# A2: is_boundary_violation() — adversarial guard tests
# ---------------------------------------------------------------------------
class TestIsBoundaryViolation(unittest.TestCase):
    def test_internal_fact_to_external_agent_is_violation(self):
        """Routing a moat-real (internal) fact to emet-live (external) → BLOCK."""
        self.assertTrue(is_boundary_violation("emet-live", "internal"))

    def test_internal_fact_to_gnomad_agent_is_violation(self):
        self.assertTrue(is_boundary_violation("gnomad", "internal"))

    def test_internal_fact_to_aso_tox_agent_is_violation(self):
        self.assertTrue(is_boundary_violation("aso-tox", "internal"))

    def test_internal_fact_to_qmodels_agent_is_violation(self):
        self.assertTrue(is_boundary_violation("qmodels:boltz2", "internal"))

    def test_external_fact_to_external_agent_is_safe(self):
        """External fact going to an external agent is fine."""
        self.assertFalse(is_boundary_violation("emet-live", "external"))

    def test_internal_fact_to_internal_agent_is_safe(self):
        """Internal fact to the internal moat agent is fine."""
        self.assertFalse(is_boundary_violation("moat-real", "internal"))

    def test_external_fact_to_internal_agent_is_safe(self):
        """External fact flowing into moat-real is also fine (no restriction)."""
        self.assertFalse(is_boundary_violation("moat-real", "external"))

    def test_unknown_provenance_conservatively_external(self):
        """An unknown target provenance is treated as external (conservative block)."""
        self.assertTrue(is_boundary_violation("unknown-tool-xyz", "internal"))

    def test_non_string_inputs_fail_safe(self):
        """Non-string inputs must not raise. Fail-safe: a non-internal fact_plane is
        always safe (only internal facts can violate); but an internal fact bound for an
        unidentifiable (non-str) target is conservatively BLOCKED rather than waved through."""
        self.assertFalse(is_boundary_violation("emet-live", None))   # non-internal plane → safe
        self.assertFalse(is_boundary_violation(None, None))          # non-internal plane → safe
        self.assertTrue(is_boundary_violation(None, "internal"))     # internal + unknown target → block
        self.assertTrue(is_boundary_violation(123, "internal"))      # internal + non-str target → block

    def test_all_external_labels_block_internal_facts(self):
        """Every external-plane provenance must trigger a violation for internal facts."""
        external_labels = [label for label, plane in _PLANE_MAP.items()
                           if plane == "external"]
        for label in external_labels:
            self.assertTrue(
                is_boundary_violation(label, "internal"),
                f"Expected is_boundary_violation({label!r}, 'internal') to be True",
            )


if __name__ == "__main__":
    unittest.main()
