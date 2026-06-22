"""Shared test fixtures and path setup."""

import sys
from pathlib import Path

# Add project root and scripts/ to sys.path so imports like
# `from scripts.bootstrap_library import main` and `from bootstrap.stats import ...` work.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"

for _p in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
