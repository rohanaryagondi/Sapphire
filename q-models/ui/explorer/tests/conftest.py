"""Pytest fixtures for the Quiver Capability Explorer smoke tests.

These tests run the backend in **stub mode** — no AWS, no GPU, no model weights.
We guarantee stub mode by clearing ``EXPLORER_AWS_ENDPOINT`` and we isolate the
run history by pointing ``EXPLORER_HISTORY`` at a per-test temp file BEFORE the
app module is imported (``backend/inference.py`` and ``backend/history.py`` read
those env vars at import time).

The fixture yields a Starlette/FastAPI ``TestClient`` bound to
``ui.explorer.backend.app:app``. We import the app lazily inside the fixture (after
the env is set) so module-import-time env reads see the test values.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

# Repo root = .../mammal-models-wt (this file is ui/explorer/tests/conftest.py).
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ``ui`` is a regular package; for ``import ui.explorer.backend.app`` to resolve,
# ``ui/explorer`` and ``ui/explorer/backend`` must be packages too. The backend
# agent owns ``backend/__init__.py`` and ``ui/explorer/__init__.py`` is unassigned,
# so create any missing markers defensively (idempotent, empty files) — this keeps
# the test harness runnable regardless of build order.
for _pkg in (REPO_ROOT / "ui" / "explorer", REPO_ROOT / "ui" / "explorer" / "backend"):
    _init = _pkg / "__init__.py"
    if _pkg.is_dir() and not _init.exists():
        _init.write_text("")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A fresh TestClient in stub mode with an isolated, empty history file.

    Each test gets its own temp history path and a freshly (re)imported app so the
    history/inference modules pick up this test's env. Stub mode is enforced by
    removing ``EXPLORER_AWS_ENDPOINT``.
    """
    history_path = tmp_path / "ex_hist.jsonl"
    monkeypatch.setenv("EXPLORER_HISTORY", str(history_path))
    monkeypatch.delenv("EXPLORER_AWS_ENDPOINT", raising=False)

    # Reimport the backend modules so import-time env reads use this test's values.
    for mod in list(sys.modules):
        if mod == "ui.explorer.backend" or mod.startswith("ui.explorer.backend."):
            sys.modules.pop(mod, None)

    app_mod = importlib.import_module("ui.explorer.backend.app")

    from fastapi.testclient import TestClient

    with TestClient(app_mod.app) as c:
        c.history_path = history_path  # expose for assertions, if a test wants it
        yield c
