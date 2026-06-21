"""On-instance Boltz-2 affinity runner (A10G 24GB g5.xlarge).

V3 hardening (vs v1/v2 which failed silently for various reasons):
  - Per-call wall-clock TIMEOUTS (preflight 30min, subsequent 15min).
  - Distinguishes Boltz-fail (rc!=0) from parse-fail (rc=0 but no affinity JSON)
    in the preflight gate — no more "we got an unrecognized output filename, abort the whole run".
  - Atomic write of results.json (tmp + os.replace + fsync) so termination
    mid-write doesn't lose state.
  - nvidia-smi probe + which(boltz) probe BEFORE the loop — fail fast on infra
    issues, not on Boltz "errors" that are really PATH problems.
  - Records boltz version + flag list in metadata for reproducibility.
  - Better OOM detection (includes SIGKILL rc=-9, CUBLAS/cuDNN alloc failures).
  - Logs `boltz --help | head` on first run so when CLI flags change, we have
    evidence right next to the failure.
  - YAML emitted via yaml.safe_dump if PyYAML is present (escapes SMILES with
    quotes safely); falls back to the old %-format if not.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CACHE = os.environ.get("BOLTZ_CACHE", "/mnt/rohan/boltz_cache")
OUT = Path(os.environ.get("BOLTZ_OUT", "/mnt/rohan/boltz_out"))
OUT.mkdir(parents=True, exist_ok=True)

# 60 min preflight — covers cold weight download (~10 GB) + ColabFold MSA queue
# (which can be 10-20 min when busy) + first-time kernel JIT. v4/v5 used 30 min
# which was too short on a truly fresh volume.
PREFLIGHT_TIMEOUT_S = int(os.environ.get("BOLTZ_PREFLIGHT_TIMEOUT_S", "3600"))
PAIR_TIMEOUT_S      = int(os.environ.get("BOLTZ_PAIR_TIMEOUT_S",      "900"))   # 15 min subsequent

if len(sys.argv) < 2:
    sys.exit("USAGE: boltz_runner.py <complexes.json>")
try:
    with open(sys.argv[1]) as _f:
        complexes = json.load(_f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    sys.exit(f"INPUT_FAIL: {type(e).__name__}: {e}")
_required = ("name", "protein_seq", "smiles")
for _i, _c in enumerate(complexes):
    _missing = [k for k in _required if k not in _c]
    if _missing:
        sys.exit(f"INPUT_FAIL: complex {_i} missing keys: {_missing}")


def _atomic_write_json(path: Path, payload) -> None:
    """fsync + os.replace so termination doesn't truncate results.json."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_yaml(seq: str, smi: str, path: Path, n_chains: int = 1) -> None:
    """Boltz YAML for a homo-oligomeric receptor (n_chains identical protein chains)
    + one ligand + affinity readout. n_chains>1 lets the affinity ligand bind at a
    subunit INTERFACE pocket (e.g. the PKM2 activator site, absent from a monomer).
    Prefer yaml.safe_dump so SMILES with single quotes don't break parsing."""
    import string
    ids = list(string.ascii_uppercase)
    chains = [{"protein": {"id": ids[i], "sequence": seq}} for i in range(n_chains)]
    lig_id = ids[n_chains]
    chains.append({"ligand": {"id": lig_id, "smiles": smi}})
    try:
        import yaml  # type: ignore
        yaml.safe_dump({
            "version": 1,
            "sequences": chains,
            "properties": [{"affinity": {"binder": lig_id}}],
        }, open(path, "w"), sort_keys=False)
    except ImportError:
        lines = ["version: 1", "sequences:"]
        for i in range(n_chains):
            lines += ["  - protein:", "      id: %s" % ids[i], "      sequence: %s" % seq]
        lines += ["  - ligand:", "      id: %s" % lig_id, "      smiles: '%s'" % smi]
        lines += ["properties:", "  - affinity:", "      binder: %s" % lig_id, ""]
        path.write_text("\n".join(lines))


def read_affinity(d: Path):
    """Find Boltz's affinity output. Try a few path patterns since the layout
    has changed across Boltz releases."""
    import glob
    patterns = [
        "**/affinity_*.json",
        "**/predictions/**/affinity_*.json",
        "**/*affinity*.json",
        "**/affinity/*.json",
    ]
    for pat in patterns:
        hits = sorted(glob.glob(str(d / pat), recursive=True),
                      key=lambda p: (-p.count(os.sep), p))
        if hits:
            try:
                j = json.load(open(hits[0]))
                return {"prob_binder": j.get("affinity_probability_binary"),
                        "log_ic50":    j.get("affinity_pred_value"),
                        "raw_path":    hits[0]}
            except Exception as e:  # noqa: BLE001
                return {"prob_binder": None, "log_ic50": None,
                        "parse_error": f"{type(e).__name__}: {e}",
                        "raw_path": hits[0]}
    return None


def _detect_failure_class(rc: int, tail: str) -> dict:
    """Categorise failures so we don't conflate OOM with CLI mismatch."""
    t = tail.lower()
    oom_markers = (
        "out of memory", "cuda out of memory", "cuda_error_out_of_memory",
        "cublas_status_alloc_failed", "cudnn_status_not_initialized",
        "outofmemoryerror", "std::bad_alloc", "resource exhausted",
        "allocator ran out of memory", "unable to allocate",
    )
    flag_markers = ("no such option", "unrecognized arguments",
                    "got unexpected", "invalid value for")
    msa_markers = ("msa server", "colabfold", "connection refused",
                   "503 service", "502 bad gateway", "504 gateway")
    return {
        "rc": rc,
        "killed_by_signal": (rc < 0),
        "timeout": (rc == 124),
        "oom": (rc != 0) and (rc == -9 or any(m in t for m in oom_markers)),
        "cuda_other": (rc != 0) and ("cuda error" in t) and not any(m in t for m in oom_markers),
        "flag_mismatch": (rc != 0) and any(m in t for m in flag_markers),
        "msa_failure": (rc != 0) and any(m in t for m in msa_markers),
    }


# Boltz CLI flags as of current install (verified from boltz_help in v4):
#   --sampling_steps INTEGER  (default 200; reduce to 100 for ~2x speed)
#   --diffusion_samples INTEGER (default 1)
# The `_affinity` suffix variants I used in v3/v4 DO NOT EXIST in current Boltz —
# v4 runner stripped them via the flag-mismatch retry path; v5 uses correct flags.
REDUCED = ["--sampling_steps", "100", "--diffusion_samples", "1"]


def run_one(yml: Path, odir: Path, reduced: bool, timeout_s: int):
    # --no_kernels forces Boltz's pure-PyTorch triangle path (the reference
    # implementation). cuequivariance CUDA kernels are only a speed/memory
    # optimization and the cu12 ops wheels are ABI-incompatible with this torch
    # (2.12+cu130); disabling them avoids the ModuleNotFoundError that broke the
    # prior AWS run on large proteins. [bouchet eval modification]
    cmd = ["boltz", "predict", str(yml), "--out_dir", str(odir),
           "--cache", CACHE, "--use_msa_server", "--no_kernels",
           "--accelerator", "gpu", "--devices", "1"] + (REDUCED if reduced else [])
    log = odir / "run.log"
    with open(log, "w") as lf:
        try:
            rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                timeout=timeout_s).returncode
        except subprocess.TimeoutExpired:
            lf.write(f"\nTIMEOUT after {timeout_s}s\n")
            rc = 124
    tail = log.read_text()[-4000:]
    return rc, tail, cmd


def _infra_probe(probe_log: Path) -> dict:
    """Sanity-check Boltz CLI + GPU BEFORE running any complex. Returns dict
    that goes into results.json metadata. Exits hard if Boltz isn't installed."""
    out = {}
    out["boltz_bin"] = shutil.which("boltz")
    if not out["boltz_bin"]:
        msg = "INFRA_FAIL: `boltz` binary not on PATH"
        probe_log.write_text(msg + "\n")
        print(msg, flush=True)
        sys.exit(2)
    # boltz --version doesn't exist in 2.x; use Python package metadata as truth source.
    try:
        import importlib.metadata as _im  # noqa: PLC0415
        out["boltz_version"] = _im.version("boltz")
        try:
            out["cuequivariance_torch_version"] = _im.version("cuequivariance-torch")
        except Exception:
            out["cuequivariance_torch_version"] = "(not installed)"
    except Exception as e:  # noqa: BLE001
        out["boltz_version"] = f"version-probe-failed: {e}"
    try:
        helptxt = subprocess.run(["boltz", "predict", "--help"], capture_output=True, text=True, timeout=30)
        out["boltz_help_head"] = (helptxt.stdout or helptxt.stderr).splitlines()[:30]
    except Exception as e:  # noqa: BLE001
        out["boltz_help_head"] = f"help-probe-failed: {e}"
    try:
        smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                              "--format=csv,noheader"], capture_output=True, text=True, timeout=30)
        out["nvidia_smi"] = smi.stdout.strip()
        if smi.returncode != 0:
            print("WARN: nvidia-smi failed; CUDA may be unavailable", flush=True)
    except Exception as e:  # noqa: BLE001
        out["nvidia_smi"] = f"nvidia-smi probe failed: {e}"
    try:
        import torch  # type: ignore
        out["torch_version"] = torch.__version__
        out["torch_cuda"]    = bool(torch.cuda.is_available())
        out["torch_cuda_name"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception as e:  # noqa: BLE001
        out["torch_version"] = f"torch import failed: {e}"

    probe_log.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2), flush=True)
    return out


def main() -> None:
    t_start = time.time()
    probe = _infra_probe(OUT / "_infra_probe.json")
    if not probe.get("torch_cuda"):
        print("INFRA_FAIL: torch.cuda.is_available() is False — aborting before complex 1", flush=True)
        sys.exit(3)

    results = []
    # Sticky flag — once we discover --sampling_steps/etc. don't work on this Boltz
    # version, stop trying them on every complex (saves 2x cost per complex).
    use_reduced = True
    import shutil as _shutil
    for i, c in enumerate(complexes):
        name = c["name"]
        odir = OUT / name
        # Stale-output guard: a prior partial run may have left an affinity_*.json
        # in odir; nuke it so we don't pick up old data.
        if odir.exists():
            _shutil.rmtree(odir)
        odir.mkdir(parents=True, exist_ok=True)
        yml = odir / "in.yaml"
        write_yaml(c["protein_seq"], c["smiles"], yml, c.get("n_chains", 1))

        t0 = time.time()
        timeout_s = PREFLIGHT_TIMEOUT_S if i == 0 else PAIR_TIMEOUT_S
        rc, tail, cmd = run_one(yml, odir, reduced=use_reduced, timeout_s=timeout_s)
        fc = _detect_failure_class(rc, tail)
        if rc != 0 and fc["flag_mismatch"] and use_reduced:
            print(f"  {name}: flag mismatch — disabling REDUCED for this + subsequent complexes", flush=True)
            use_reduced = False
            rc, tail, cmd = run_one(yml, odir, reduced=False, timeout_s=timeout_s)
            fc = _detect_failure_class(rc, tail)

        el = round(time.time() - t0, 1)
        aff = read_affinity(odir) if rc == 0 else None
        rec = {"name": name, "target": c.get("target"), "drug": c.get("drug"),
               "label": c.get("label"),
               "protein_seq": c["protein_seq"], "smiles": c["smiles"],
               "seq_len": len(c["protein_seq"]),
               "rc": rc, "elapsed_s": el, "failure_class": fc,
               **(aff or {"prob_binder": None, "log_ic50": None})}
        if rc != 0:
            rec["err_tail"] = tail[-800:]
        results.append(rec)
        _atomic_write_json(OUT / "results.json",
                           {"infra": probe, "complexes": results,
                            "wall_time_sec": round(time.time() - t_start, 1)})
        print(f"[{i+1}/{len(complexes)}] {name} ({rec['seq_len']}aa) rc={rc} "
              f"oom={fc['oom']} prob={rec['prob_binder']} t={el}s", flush=True)

        # Pre-flight gate: distinguish Boltz failure from parse failure.
        # SPECIAL CASE: don't abort on rc=124 (timeout) — most likely cold MSA
        # queue, subsequent complexes will reuse cached MSAs and may succeed.
        if i == 0:
            if fc.get("timeout"):
                print(f"PREFLIGHT_TIMEOUT: first complex timed out after {timeout_s}s "
                      "(likely cold MSA queue). Continuing to next complex — "
                      "subsequent complexes may have warmed caches.", flush=True)
            elif rc != 0:
                print(f"PREFLIGHT_BOLTZ_FAIL: rc={rc} on g5.xlarge/A10G "
                      f"(oom={fc['oom']}, cuda_err={fc['cuda_other']}, "
                      f"msa_failure={fc.get('msa_failure')}). Stopping.", flush=True)
                break
            elif aff is None or aff.get("prob_binder") is None:
                print("PREFLIGHT_PARSE_FAIL: Boltz rc=0 but no usable affinity JSON. "
                      "Likely output schema change. Listing odir for debugging:", flush=True)
                subprocess.run(["find", str(odir), "-maxdepth", "5", "-type", "f"],
                               check=False)
                break

    _atomic_write_json(OUT / "results.json",
                       {"infra": probe, "complexes": results,
                        "wall_time_sec": round(time.time() - t_start, 1)})
    print("RUNNER_DONE", flush=True)


if __name__ == "__main__":
    main()
