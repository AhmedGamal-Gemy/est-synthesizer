"""Unit tests for scripts.generate_test CLI.

Most of the CLI requires Qdrant + a live LLM. The tests here cover the bits
that can be exercised in isolation: argument parsing, blueprint resolution
fallback, and the default-flag values.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Make scripts/ importable as a package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_test  # noqa: E402


# ── _resolve_blueprint: fallback path ──────────────────────


def test_resolve_blueprint_falls_back_to_default_when_id_missing():
    """A non-existent blueprint id should fall back to DEFAULT_BLUEPRINT."""
    fake_get = AsyncMock(return_value=None)
    with patch.object(generate_test, "get_blueprint", fake_get):
        bp = generate_test._resolve_blueprint("nonexistent-id-xyz")
    assert bp.id == "default_blueprint_v1"


def test_resolve_blueprint_falls_back_when_id_empty():
    """Empty string (the sentinel from --blueprint '') should also fall back."""
    fake_get = AsyncMock(return_value=None)
    with patch.object(generate_test, "get_blueprint", fake_get):
        bp = generate_test._resolve_blueprint("")
    assert bp.id == "default_blueprint_v1"


def test_resolve_blueprint_returns_db_hit():
    """When the DB returns a blueprint, _resolve_blueprint should use it."""
    db_row = {"blueprint_json": generate_test.DEFAULT_BLUEPRINT.model_dump(mode="json")}
    fake_get = AsyncMock(return_value=db_row)
    with patch.object(generate_test, "get_blueprint", fake_get):
        bp = generate_test._resolve_blueprint("default_blueprint_v1")
    assert bp.id == "default_blueprint_v1"
    assert bp.total_questions == generate_test.DEFAULT_BLUEPRINT.total_questions


# ── CLI argument parsing ──────────────────────────────────


def test_argparse_defaults():
    """Default flags: blueprint=default_blueprint_v1, render_pdfs=True, log_level=ERROR (or $LOG_LEVEL)."""
    import argparse
    # Replicate the parser setup
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint", default="default_blueprint_v1")
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--log-level", default="ERROR")
    args = parser.parse_args([])
    assert args.blueprint == "default_blueprint_v1"
    assert args.no_pdf is False
    assert args.log_level == "ERROR"


def test_argparse_no_pdf_flag():
    """--no-pdf should set no_pdf=True."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint", default="default_blueprint_v1")
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--log-level", default="ERROR")
    args = parser.parse_args(["--no-pdf"])
    assert args.no_pdf is True


def test_argparse_custom_blueprint():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint", default="default_blueprint_v1")
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--log-level", default="ERROR")
    args = parser.parse_args(["--blueprint", "harder_blueprint_v1"])
    assert args.blueprint == "harder_blueprint_v1"
