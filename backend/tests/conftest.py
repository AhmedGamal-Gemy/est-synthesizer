"""Shared test fixtures and path setup."""

import sys
from pathlib import Path

import structlog

# Add project root and scripts/ to sys.path so imports like
# `from scripts.bootstrap_library import main` and `from bootstrap.stats import ...` work.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"

for _p in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── Structlog: use stdlib logger factory for testability ──────
# Default _LoggerFactory bypasses stdlib logging (writes to sys.stdout directly),
# which means caplog/capsys cannot capture log output.  Switching to
# stdlib.LoggerFactory here routes structlog through standard logging so
# pytest fixtures (caplog, capsys, capfd) see all log records.
structlog.configure(
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
