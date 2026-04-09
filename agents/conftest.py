"""Pytest: ensure `agents/` is importable as top-level (orchestrator-style imports)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_AGENTS = Path(__file__).resolve().parent
if str(_AGENTS) not in sys.path:
    sys.path.insert(0, str(_AGENTS))


@pytest.fixture(autouse=True)
def _reset_event_loop():
    """Ensure a fresh event loop exists before each test.

    unittest.IsolatedAsyncioTestCase (used in test_polished_architect) leaves
    the loop closed and unset on Python 3.9 after its tests run.  Without this
    fixture, any subsequent test that calls asyncio.Lock() or
    asyncio.new_event_loop() will raise 'There is no current event loop'.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield
    try:
        loop.close()
    except Exception:
        pass
