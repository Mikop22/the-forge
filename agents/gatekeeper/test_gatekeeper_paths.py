"""Regression tests for ModSources path resolution in gatekeeper."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock


def test_default_mod_sources_dir_matches_linux_layout() -> None:
    from gatekeeper.gatekeeper import default_mod_sources_dir

    fake_home = Path("/home/testuser")
    with mock.patch("core.paths.Path.home", return_value=fake_home):
        with mock.patch("core.paths.platform.system", return_value="Linux"):
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
    with mock.patch.dict(
        os.environ, {"FORGE_MOD_SOURCES_DIR": str(custom)}, clear=True
    ):
        integ = Integrator(coder=None)
    assert integ._mod_root == custom / "ForgeGeneratedMod"


def test_integrator_normalizes_standalone_mod_source_path_to_mod_sources_layout() -> (
    None
):
    from gatekeeper.gatekeeper import Integrator

    standalone = Path("/opt/terraria/CustomCombatPack")
    with mock.patch.dict(os.environ, {"MOD_SOURCE_PATH": str(standalone)}, clear=True):
        integ = Integrator(coder=None)
    assert integ._mod_root == standalone.parent / "ModSources" / standalone.name


def test_enabled_json_follows_mod_sources_parent() -> None:
    from gatekeeper.gatekeeper import default_mod_sources_dir, tmod_enabled_json_path

    fake_home = Path("/home/testuser")
    with mock.patch("core.paths.Path.home", return_value=fake_home):
        with mock.patch("core.paths.platform.system", return_value="Linux"):
            with mock.patch.dict(os.environ, {}, clear=True):
                ms = default_mod_sources_dir()
                got = tmod_enabled_json_path()
    assert got == ms.parent / "Mods" / "enabled.json"


def test_integrator_root_status_mapping_finishing() -> None:
    from gatekeeper.gatekeeper import Integrator

    got = Integrator._status_for_mod_sources_root(
        {"status": "finishing", "message": "Almost done"}
    )
    assert got["status"] == "building"
    assert got["stage_pct"] == 95
    assert "Almost done" in got["stage_label"]


def test_write_status_mirrors_to_active_custom_mod_sources_root(tmp_path) -> None:
    from gatekeeper.gatekeeper import Integrator

    mod_sources_root = tmp_path / "custom-save" / "ModSources"
    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_sources_root / "CustomCombatPack"

    integ._write_status({"status": "finishing", "message": "Almost done"})

    mirrored = mod_sources_root / "generation_status.json"
    assert mirrored.exists()
    assert json.loads(mirrored.read_text()) == {
        "status": "building",
        "stage_label": "Almost done",
        "stage_pct": 95,
    }


def test_ensure_mod_enabled_writes_under_active_custom_savedir(tmp_path) -> None:
    from gatekeeper.gatekeeper import Integrator

    savedir = tmp_path / "custom-save"
    integ = Integrator.__new__(Integrator)
    integ._mod_root = savedir / "ModSources" / "CustomCombatPack"

    integ._ensure_mod_enabled("CustomCombatPack")

    enabled = savedir / "Mods" / "enabled.json"
    assert enabled.exists()
    assert json.loads(enabled.read_text()) == ["CustomCombatPack"]


def test_build_and_verify_enables_active_mod_folder_name_on_success() -> None:
    from gatekeeper.gatekeeper import CompileResult, Integrator

    integ = Integrator.__new__(Integrator)
    integ._mod_root = Path("/tmp/CustomCombatPack")
    integ._max_retries = 0
    integ._coder = None

    with mock.patch.object(
        integ, "_run_tmod_build", return_value=CompileResult(True, "ok")
    ):
        with mock.patch.object(integ, "_stage_files"):
            with mock.patch.object(integ, "_write_status"):
                with mock.patch.object(integ, "_ensure_mod_enabled") as ensure_enabled:
                    out = integ.build_and_verify(
                        {
                            "status": "success",
                            "cs_code": "public class DemoSword : ModItem { }",
                            "hjson_code": "",
                        },
                    )

    assert out["status"] == "success"
    ensure_enabled.assert_called_once_with("CustomCombatPack")


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


def test_parse_errors_tmod_lock_without_tml_line() -> None:
    """IOException on .tmod still classifies as packaging failure when no TML### line."""
    from gatekeeper.gatekeeper import Integrator

    log = """\
Compilation finished with 0 errors and 0 warnings
Packaging: ForgeGeneratedMod
System.IO.IOException: The process cannot access the file '/Mods/ForgeGeneratedMod.tmod' because it is being used by another process.
"""
    errors = Integrator._parse_errors(log)
    assert any(e.code == "TML_LOCK" for e in errors)
    assert Integrator._is_packaging_only_failure(errors)


def test_tml003_fails_fast_without_coder_repair() -> None:
    """Packaging locks must not trigger CoderAgent.fix_code (LLM cannot fix a locked file)."""
    from gatekeeper.gatekeeper import Integrator, CompileResult

    tml_log = """\
Compiling ForgeGeneratedMod.dll
Compilation finished with 0 errors and 0 warnings
tModLoader: Mod Build error TML003: Please close tModLoader or disable the mod in-game to build mods directly.
"""
    coder = mock.Mock()
    integ = Integrator(coder=coder)
    with mock.patch.object(
        integ, "_run_tmod_build", return_value=CompileResult(False, tml_log)
    ):
        with mock.patch.object(integ, "_stage_files"):
            with mock.patch.object(integ, "_write_status"):
                out = integ.build_and_verify(
                    {
                        "status": "success",
                        "cs_code": "public class DemoSword : ModItem { }",
                        "hjson_code": "",
                    },
                )
    assert out["status"] == "error"
    assert out["errors"][0]["code"] == "TML003"
    em = out["error_message"].lower()
    assert "reload" in em and "close tmodloader" in em
    coder.fix_code.assert_not_called()


def test_cs_error_not_treated_as_packaging_only() -> None:
    """Roslyn failures must keep the repair path — never classify as packaging-only."""
    from gatekeeper.gatekeeper import Integrator, RoslynError

    errors = [
        RoslynError(code="CS0103", message="missing name", line=1, file="Item.cs"),
        RoslynError(
            code="TML003", message="ignored for this check", line=None, file=None
        ),
    ]
    assert not Integrator._is_packaging_only_failure(errors)


def test_ensure_mod_entry_class_writes_when_absent(tmp_path) -> None:
    """Entry class file is created when it does not exist."""
    from gatekeeper.gatekeeper import Integrator

    mod_root = tmp_path / "MyMod"
    mod_root.mkdir()
    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_root

    integ._ensure_mod_entry_class()

    entry = mod_root / "MyMod.cs"
    assert entry.exists()
    content = entry.read_text()
    assert "namespace MyMod" in content
    assert "class MyMod : Mod" in content


def test_ensure_mod_entry_class_does_not_overwrite(tmp_path) -> None:
    """Entry class file is left untouched when it already exists."""
    from gatekeeper.gatekeeper import Integrator

    mod_root = tmp_path / "MyMod"
    mod_root.mkdir()
    entry = mod_root / "MyMod.cs"
    original = "// existing file"
    entry.write_text(original)

    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_root
    integ._ensure_mod_entry_class()

    assert entry.read_text() == original
