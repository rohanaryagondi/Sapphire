import json
import unittest
from pathlib import Path

SCN_DIR = Path(__file__).resolve().parents[1] / "scenarios"
MANIFEST = SCN_DIR / "manifest.json"
REQUIRED_KEYS = {"id", "title", "query", "headline", "discover", "validate", "panel", "rebuttal", "synthesize"}
AXES = {"go_no_go", "selectivity", "mechanism", "modality", "admet_bbb",
        "biomarker", "abstain", "divergence", "payer", "ip_veto"}

class TestScenarios(unittest.TestCase):
    def test_manifest_exists_and_has_ten(self):
        m = json.loads(MANIFEST.read_text())
        self.assertGreaterEqual(len(m["scenarios"]), 10)

    def test_manifest_covers_all_variety_axes(self):
        m = json.loads(MANIFEST.read_text())
        covered = {s["variety_axis"] for s in m["scenarios"]}
        self.assertTrue(AXES.issubset(covered), f"missing axes: {AXES - covered}")

    def test_captured_scenarios_exist_and_validate(self):
        m = json.loads(MANIFEST.read_text())
        captured = [s for s in m["scenarios"] if s["status"] == "captured"]
        self.assertGreaterEqual(len(captured), 2)   # nav1_8 + tsc2 ship today
        for s in captured:
            f = SCN_DIR / f"{s['id']}.json"
            self.assertTrue(f.exists(), f"captured scenario file missing: {f}")
            data = json.loads(f.read_text())
            self.assertTrue(REQUIRED_KEYS.issubset(data.keys()),
                            f"{s['id']} missing keys: {REQUIRED_KEYS - set(data.keys())}")

    def test_every_scenario_has_status(self):
        m = json.loads(MANIFEST.read_text())
        for s in m["scenarios"]:
            self.assertIn(s["status"], ("captured", "stub"))

if __name__ == "__main__":
    unittest.main()
