"""Sapphire endpoint wiring for the vendored robyn_scs SCS/STA connectivity pipeline.

`tools/robyn_scs/` exposes the vendored pipeline (`vendor/robyn_scs/utils/`) as clean callable
endpoints WITHOUT modifying the vendored code and WITHOUT running the full pipeline. Heavy deps
(numpy/scipy/pandas/matplotlib) are imported lazily inside `endpoints.py` (this tool's subprocess);
the Sapphire engine stays stdlib-only. See README.md for the endpoint catalogue.
"""
