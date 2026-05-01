"""Tests for agents/paths.py (ModSources resolution)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from core import paths


def test_read_mod_sources_dir_from_config_root_keys_only(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        'mod_sources_dir = "/foo/bar" # inline\n[cloud]\nkey = "x"\n',
        encoding="utf-8",
    )
    with mock.patch.object(paths, "config_toml_path", return_value=cfg):
        assert paths.read_mod_sources_dir_from_config() == "/foo/bar"


def test_mod_sources_root_prefers_env_over_config(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('mod_sources_dir = "/from/config"\n', encoding="utf-8")
    env_ms = tmp_path / "from_env" / "ModSources"
    with mock.patch.object(paths, "config_toml_path", return_value=cfg):
        with mock.patch.dict(os.environ, {"FORGE_MOD_SOURCES_DIR": str(env_ms)}):
            assert paths.mod_sources_root() == env_ms


def test_mod_sources_root_uses_config_when_env_unset(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    want = tmp_path / "configured" / "ModSources"
    cfg.write_text(f'mod_sources_dir = "{want.as_posix()}"\n', encoding="utf-8")
    with mock.patch.object(paths, "config_toml_path", return_value=cfg):
        with mock.patch.dict(os.environ, {"FORGE_MOD_SOURCES_DIR": ""}):
            assert paths.mod_sources_root() == want
