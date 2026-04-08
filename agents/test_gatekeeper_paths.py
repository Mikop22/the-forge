"""Regression tests for ModSources path resolution in gatekeeper."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

_AGENTS = Path(__file__).resolve().parent
if str(_AGENTS) not in sys.path:
    sys.path.insert(0, str(_AGENTS))


def test_default_mod_sources_dir_matches_linux_layout() -> None:
    from gatekeeper.gatekeeper import default_mod_sources_dir

    fake_home = Path("/home/testuser")
    with mock.patch("paths.Path.home", return_value=fake_home):
        with mock.patch("paths.platform.system", return_value="Linux"):
            with mock.patch.dict(os.environ, {}, clear=True):
                got = default_mod_sources_dir()
    want = fake_home / ".local" / "share" / "Terraria" / "tModLoader" / "ModSources"
    assert got == want


def test_default_mod_sources_dir_respects_forge_mod_sources_dir() -> None:
    from gatekeeper.gatekeeper import default_mod_sources_dir

    custom = Path("/opt/terraria/ModSources")
    with mock.patch.dict(os.environ, {"FORGE_MOD_SOURCES_DIR": str(custom)}):
        assert default_mod_sources_dir() == custom


def test_integrator_mod_root_uses_forge_mod_sources_plus_mod_name() -> None:
    from gatekeeper.gatekeeper import Integrator

    custom = Path("/opt/terraria/ModSources")
    with mock.patch.dict(os.environ, {"FORGE_MOD_SOURCES_DIR": str(custom)}, clear=True):
        integ = Integrator(coder=None)
    assert integ._mod_root == custom / "ForgeGeneratedMod"


def test_enabled_json_follows_mod_sources_parent() -> None:
    from gatekeeper.gatekeeper import default_mod_sources_dir, tmod_enabled_json_path

    fake_home = Path("/home/testuser")
    with mock.patch("paths.Path.home", return_value=fake_home):
        with mock.patch("paths.platform.system", return_value="Linux"):
            with mock.patch.dict(os.environ, {}, clear=True):
                ms = default_mod_sources_dir()
                got = tmod_enabled_json_path()
    assert got == ms.parent / "Mods" / "enabled.json"


def test_integrator_root_status_mapping_finishing() -> None:
    from gatekeeper.gatekeeper import Integrator

    got = Integrator._status_for_mod_sources_root({"status": "finishing", "message": "Almost done"})
    assert got["status"] == "building"
    assert got["stage_pct"] == 95
    assert "Almost done" in got["stage_label"]


def test_parse_errors_extracts_tml003_packaging_lock() -> None:
    """When compile succeeds but packaging fails (game holds .tmod), surface TML003 not UNKNOWN."""
    from gatekeeper.gatekeeper import Integrator

    log = """\
Compiling ForgeGeneratedMod.dll
Compilation finished with 0 errors and 0 warnings
Packaging: ForgeGeneratedMod
tModLoader: Mod Build error TML003: Please close tModLoader or disable the mod in-game to build mods directly.
System.IO.IOException: The process cannot access the file
"""
    errors = Integrator._parse_errors(log)
    assert len(errors) >= 1
    assert errors[0].code == "TML003"
    assert "close tmodloader" in errors[0].message.lower()
