"""Sapphire ↔ Q-Models integration: registry + client + launcher + adapters.

The orchestrator calls any Q-Models tool through `QModelsClient` (see client.py), which routes by the
tool's tier in registry.json: local-cpu tools run synchronously against the vendored Explorer backend;
gpu-launch tools run asynchronously via the unified launcher (see launcher.py). Every result carries a
provenance tag so nothing fabricated is shown as real.
"""
from .client import QModelsClient, load_registry  # noqa: F401
