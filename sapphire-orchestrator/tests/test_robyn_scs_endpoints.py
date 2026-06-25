"""
tests/test_robyn_scs_endpoints.py — wiring lock for tools/robyn_scs/endpoints.py.

Verifies the endpoint wiring WITHOUT running the full pipeline (which needs MATLAB-split imaging
CSVs we don't have here). Two layers:
  * always (stdlib-only): the module imports; all 10 endpoints exist, are callable, have docstrings;
    discover_fov_quartets works (pure stdlib); each endpoint's own signature is stable; and the module
    is import-safe with every heavy dep blocked (subprocess + sys.meta_path) — proving the engine path
    stays stdlib-only.
  * when numpy/scipy/pandas/matplotlib are present (tool deps): the vendored targets actually resolve
    from the VENDORED package and their signatures contain the parameters the endpoints pass (the real
    "endpoints wire to the right functions" check), plus one cheap synthetic detect_events run.

Run from sapphire-orchestrator/:  python -m unittest tests.test_robyn_scs_endpoints -v
"""
from __future__ import annotations

import importlib
import inspect
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_TOOL = os.path.join(_ROOT, "tools", "robyn_scs")
if _TOOL not in sys.path:
    sys.path.insert(0, _TOOL)

import endpoints as ep  # noqa: E402  (stdlib-only at import time; heavy deps are lazy inside the endpoints)


def _have(mods):
    for m in mods:
        try:
            importlib.import_module(m)
        except ImportError:
            return False
    return True


_HEAVY = _have(["numpy", "scipy", "pandas", "matplotlib"])

_ENDPOINTS = [
    "detect_events", "run_scs", "run_sta", "load_stim_metadata", "stim_mask_from_sidecar",
    "merge_and_classify", "visualize", "discover_fov_quartets", "run_fov", "run_batch",
]


def _params(fn):
    return set(inspect.signature(fn).parameters)


class TestModuleSurface(unittest.TestCase):
    """The endpoint surface is present and self-describing — no heavy deps needed."""

    def test_all_list_matches_endpoints(self):
        self.assertEqual(sorted(ep.__all__), sorted(_ENDPOINTS))

    def test_endpoints_exist_callable_documented(self):
        for name in _ENDPOINTS:
            self.assertTrue(hasattr(ep, name), f"missing endpoint {name}")
            fn = getattr(ep, name)
            self.assertTrue(callable(fn), f"{name} not callable")
            self.assertTrue((fn.__doc__ or "").strip(), f"{name} has no docstring")

    def test_endpoint_signatures_stable(self):
        self.assertLessEqual({"raw", "fs", "snr_gate"}, _params(ep.detect_events))
        self.assertLessEqual({"spont_p1_csv", "spont_p2_csv", "score_thresh", "min_ap"}, _params(ep.run_scs))
        self.assertLessEqual({"stim_p1_csv", "stim_p2_csv", "stim_meta", "in_stim_mask_override"}, _params(ep.run_sta))
        self.assertLessEqual({"scs_df", "sta_df", "fov_label", "in_stim_mask"}, _params(ep.merge_and_classify))
        self.assertLessEqual({"mat_path", "meta"}, _params(ep.stim_mask_from_sidecar))
        self.assertIn("quartet", _params(ep.run_fov))
        self.assertLessEqual({"input_dir", "output_dir"}, _params(ep.run_batch))

    def test_import_safe_with_heavy_deps_blocked(self):
        # Proves endpoints.py imports with numpy/scipy/pandas/matplotlib/seaborn ALL blocked,
        # i.e. nothing third-party is imported at module load (engine stays stdlib-only).
        code = (
            "import sys\n"
            "class _Block:\n"
            "    _b = {'numpy', 'scipy', 'pandas', 'matplotlib', 'seaborn', 'sklearn'}\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name.split('.')[0] in self._b:\n"
            "            raise ImportError('blocked: ' + name)\n"
            "        return None\n"
            "sys.meta_path.insert(0, _Block())\n"
            f"sys.path.insert(0, r'{_TOOL}')\n"
            "import endpoints\n"
            "print('IMPORT_OK', len(endpoints.__all__))\n"
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("IMPORT_OK 10", proc.stdout)


class TestDiscovery(unittest.TestCase):
    """discover_fov_quartets is pure stdlib — runs without any heavy dep."""

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ep.discover_fov_quartets(d), [])

    def test_quartet_assembly(self):
        with tempfile.TemporaryDirectory() as d:
            stem = "FOV_0007_plateA"
            for suff in ("_spont_part1.csv", "_spont_part2.csv", "_stim_part1.csv",
                         "_stim_part2.csv", "_stim_meta.json"):
                open(os.path.join(d, stem + suff), "w").close()
            quartets = ep.discover_fov_quartets(d)
            self.assertEqual(len(quartets), 1)
            q = quartets[0]
            self.assertEqual(q["fov"], "FOV_0007")
            self.assertTrue(q["has_spont"] and q["has_stim"])
            self.assertTrue(q["spont_p1"].endswith("_spont_part1.csv"))
            self.assertTrue(q["stim_p2"].endswith("_stim_part2.csv"))

    def test_spont_only_quartet(self):
        with tempfile.TemporaryDirectory() as d:
            stem = "FOV_0011_x"
            for suff in ("_spont_part1.csv", "_spont_part2.csv", "_stim_meta.json"):
                open(os.path.join(d, stem + suff), "w").close()
            q = ep.discover_fov_quartets(d)[0]
            self.assertTrue(q["has_spont"])
            self.assertFalse(q["has_stim"])
            self.assertIsNone(q["stim_p1"])


@unittest.skipUnless(_HEAVY, "needs numpy/scipy/pandas/matplotlib (tool deps) — wiring check skips cleanly without them")
class TestVendoredWiring(unittest.TestCase):
    """The endpoints resolve to the right VENDORED functions, whose signatures accept the params we pass."""

    def test_utils_loads_from_vendor(self):
        du, scs, sta, cons = ep._utils()
        for mod in (du, scs, sta, cons):
            self.assertIn("vendor", mod.__file__.replace("\\", "/"), mod.__file__)
            self.assertIn("robyn_scs", mod.__file__.replace("\\", "/"))

    def test_data_utils_signatures(self):
        du, _, _, _ = ep._utils()
        self.assertLessEqual({"raw", "segs", "fs"}, _params(du.preprocess))
        self.assertLessEqual({"trace", "segs", "raw", "snr_gate", "pbr_thresh", "fs"}, _params(du.detect_aps))
        for fn in ("detect_segments", "load_stim_meta", "load_ensemble_mask_sidecar", "stim_mask_from_mat"):
            self.assertTrue(callable(getattr(du, fn)), f"data_utils.{fn} missing")

    def test_scs_sta_signatures(self):
        _, scs, sta, _ = ep._utils()
        self.assertLessEqual(
            {"csv_path", "score_thresh", "output_dir", "exclude_neurons", "regress_global"},
            _params(scs.run_scs_pipeline))
        self.assertLessEqual({"res1", "res2", "score_thresh", "val_score_thresh", "min_ap"},
                             _params(scs.validate_scs_in_part2))
        self.assertLessEqual(
            {"csv_p1", "csv_p2", "stim_meta", "in_stim_mask_override", "min_ap_stim", "onset_ms", "regress_global"},
            _params(sta.run_sta_pipeline_interleaved))
        self.assertLessEqual({"res", "score_thresh"}, _params(sta.validate_sta_interleaved))

    def test_consensus_signatures(self):
        _, _, _, cons = ep._utils()
        self.assertLessEqual({"scs_df", "sta_df", "fov_label"}, _params(cons.merge_connections))
        self.assertLessEqual({"scs_neuron_type", "sta_neuron_type", "all_traces", "in_stim_mask"},
                             _params(cons.classify_neurons))
        self.assertTrue(callable(getattr(cons, "neuron_types_from_merged")))

    def test_visualization_signatures(self):
        viz = ep._viz()
        self.assertLessEqual({"merged_df", "all_traces", "output_path", "title"}, _params(viz.plot_consensus_heatmap))
        self.assertLessEqual({"neuron_tier_df", "output_path"}, _params(viz.plot_neuron_tier_bar))

    def test_run_scs_forwards_clean_kwargs(self):
        # A bogus forwarded kwarg raises TypeError AT THE CALL (before the body runs); a clean forward
        # reaches the vendored CSV read and fails on the missing file instead. So: never TypeError here.
        try:
            ep.run_scs("/no/such_p1.csv", "/no/such_p2.csv")
        except TypeError as exc:
            self.fail(f"run_scs forwarded a bad kwarg to run_scs_pipeline: {exc}")
        except Exception:
            pass  # expected: the vendored code fails on the missing CSV — kwargs bound cleanly

    def test_run_sta_forwards_clean_kwargs(self):
        try:
            ep.run_sta("/no/such_p1.csv", "/no/such_p2.csv")
        except TypeError as exc:
            self.fail(f"run_sta forwarded a bad kwarg to run_sta_pipeline_interleaved: {exc}")
        except Exception:
            pass  # expected: vendored code fails on the missing CSV — kwargs bound cleanly


@unittest.skipUnless(_have(["numpy", "scipy"]), "needs numpy/scipy for the synthetic detect run")
class TestSyntheticDetect(unittest.TestCase):
    """One cheap offline run through detect_segments -> preprocess -> detect_aps (no CSV / MATLAB)."""

    def test_detect_events_runs(self):
        import numpy as np
        trace = np.zeros(2000, dtype=float)
        for i in (300, 800, 1500):  # toy sharp deflections
            trace[i:i + 3] += 5.0
        out = ep.detect_events(trace, fs=500)
        self.assertEqual(set(out), {"segments", "trace", "aps"})
        self.assertEqual(len(out["trace"]), 2000)
        self.assertIsInstance(out["segments"], list)
        self.assertIsInstance(out["aps"], np.ndarray)


if __name__ == "__main__":
    unittest.main()
