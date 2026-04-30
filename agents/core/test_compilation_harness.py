"""Tests for core.compilation_harness."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from core.compilation_harness import find_tmod_path


def test_find_tmod_path_respects_env_override(tmp_path: Path) -> None:
    fake_root = tmp_path / "tmod"
    fake_root.mkdir()
    (fake_root / "tModLoader.dll").write_text("")

    with patch.dict(os.environ, {"TMODLOADER_PATH": str(fake_root)}):
        result = find_tmod_path()

    assert result == fake_root


def test_find_tmod_path_returns_none_when_env_invalid(tmp_path: Path) -> None:
    bad_root = tmp_path / "missing"
    with patch.dict(os.environ, {"TMODLOADER_PATH": str(bad_root)}):
        result = find_tmod_path()
    assert result is None
