"""Shared test setup.

Puts ``src/`` and ``data/`` on the import path, and makes sure the synthetic
database exists before the tool tests run. None of these tests need an API key.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data"))


@pytest.fixture(scope="session", autouse=True)
def ensure_database() -> None:
    """Build the synthetic database once if it isn't already present."""
    import build_db  # from data/

    if not build_db.DB_PATH.exists():
        build_db.build()
