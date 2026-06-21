import os
import tempfile

# Point history at a throwaway file BEFORE the app (and history module) import,
# so tests never touch the real ui/backend/_history.jsonl.
os.environ.setdefault(
    "MAMMAL_UI_HISTORY", os.path.join(tempfile.gettempdir(), "mammal_ui_test_history.jsonl")
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: loads MAMMAL checkpoints (~1.8 GB each); run with `pytest` (omit `-m 'not slow'`)"
    )
