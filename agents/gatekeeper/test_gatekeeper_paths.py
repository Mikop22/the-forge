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


def test_build_and_verify_rejects_spectacle_critique_before_staging(tmp_path) -> None:
    """Gatekeeper is the final boundary before bad bespoke code reaches ModSources."""
    from gatekeeper.gatekeeper import Integrator

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"
    integ._max_retries = 0
    integ._coder = None

    bad_cs = """
public class LimitlessVioletStaff : ModItem { }
public class LimitlessVioletStaffProjectile : ModProjectile
{
    public override void SetDefaults() { Projectile.width = 6; Projectile.height = 16; }
    public override void SetStaticDefaults() { ProjectileID.Sets.TrailCacheLength[Type] = 22; }
    public override void AI() { Projectile.localAI[0]++; }
    public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone) { AddStormBrandMark(target); }
    private void AddStormBrandMark(NPC target) { TriggerStarfallBurst(target); }
    private void TriggerStarfallBurst(NPC target) { }
    private void Collapse() { }
    public override bool PreDraw(ref Color lightColor)
    {
        Main.EntitySpriteDraw(null, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0f);
        Main.EntitySpriteDraw(null, Projectile.oldPos[0], null, Color.White, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0f);
        return false;
    }
}
"""
    manifest = {
        "item_name": "LimitlessVioletStaff",
        "projectile_visuals": {"hitbox_size": [6, 16]},
        "spectacle_plan": {
            "fantasy": "hollow purple singularity",
            "must_not_include": ["starfall", "mark/cashout"],
        },
    }

    with mock.patch.object(integ, "_stage_files") as stage_files:
        with mock.patch.object(integ, "_run_tmod_build") as run_build:
            with mock.patch.object(integ, "_write_status"):
                out = integ.build_and_verify(
                    {
                        "status": "success",
                        "cs_code": bad_cs,
                        "hjson_code": "",
                    },
                    manifest=manifest,
                )

    assert out["status"] == "error"
    assert "spectacle_plan forbids" in out["error_message"]
    stage_files.assert_not_called()
    run_build.assert_not_called()


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


def test_stage_files_copies_projectile_sprite_to_projectile_texture_path(tmp_path) -> None:
    """Projectile art is staged where tModLoader autoloads ModProjectile textures."""
    from gatekeeper.gatekeeper import Integrator

    source_item = tmp_path / "NyanCatStaff.png"
    source_projectile = tmp_path / "NyanCatStaffProjectile.png"
    source_item.write_bytes(b"item")
    source_projectile.write_bytes(b"projectile")

    mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"
    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_root

    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class NyanCatStaff : Terraria.ModLoader.ModItem { }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class NyanCatStaffProjectile : Terraria.ModLoader.ModProjectile { }
}
"""

    integ._stage_files(
        cs_code=cs_code,
        hjson_code="",
        item_name="NyanCatStaff",
        sprite_path=str(source_item),
        projectile_sprite_path=str(source_projectile),
    )

    assert (mod_root / "Content" / "Items" / "NyanCatStaff.png").read_bytes() == b"item"
    assert (
        mod_root / "Content" / "Projectiles" / "NyanCatStaffProjectile.png"
    ).read_bytes() == b"projectile"
    assert not (mod_root / "Content" / "Items" / "NyanCatStaffProjectile.png").exists()


def test_stage_files_rejects_projectile_sprite_name_mismatch(tmp_path) -> None:
    """Codegen and asset-gen must agree on the projectile class/asset name."""
    import pytest

    from gatekeeper.gatekeeper import Integrator

    source_item = tmp_path / "NyanCatStaff.png"
    source_projectile = tmp_path / "nyan_cat_projectile.png"
    source_item.write_bytes(b"item")
    source_projectile.write_bytes(b"projectile")

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"

    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class NyanCatStaff : Terraria.ModLoader.ModItem { }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class NyanCatStaffProjectile : Terraria.ModLoader.ModProjectile { }
}
"""

    with pytest.raises(ValueError, match="projectile sprite name mismatch"):
        integ._stage_files(
            cs_code=cs_code,
            hjson_code="",
            item_name="NyanCatStaff",
            sprite_path=str(source_item),
            projectile_sprite_path=str(source_projectile),
        )


def test_stage_files_rejects_item_sprite_name_mismatch(tmp_path) -> None:
    """The manifest item_name contract applies to the item sprite filename too."""
    import pytest

    from gatekeeper.gatekeeper import Integrator

    source_item = tmp_path / "nyan_cat_staff.png"
    source_item.write_bytes(b"item")

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"

    with pytest.raises(ValueError, match="item sprite name mismatch"):
        integ._stage_files(
            cs_code="public class NyanCatStaff : Terraria.ModLoader.ModItem { }",
            hjson_code="",
            item_name="NyanCatStaff",
            sprite_path=str(source_item),
            projectile_sprite_path=None,
        )


def test_stage_files_validates_before_writing_code(tmp_path) -> None:
    """A failed handoff must not leave fresh code staged without matching art."""
    import pytest

    from gatekeeper.gatekeeper import Integrator

    source_item = tmp_path / "nyan_cat_staff.png"
    source_item.write_bytes(b"item")

    mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"
    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_root

    with pytest.raises(ValueError, match="item sprite name mismatch"):
        integ._stage_files(
            cs_code="public class NyanCatStaff : Terraria.ModLoader.ModItem { }",
            hjson_code="",
            item_name="NyanCatStaff",
            sprite_path=str(source_item),
            projectile_sprite_path=None,
        )

    assert not (mod_root / "Content" / "Items" / "NyanCatStaff.cs").exists()


def test_stage_files_removes_stale_generated_content_after_validation(tmp_path) -> None:
    """A new live forge should not compile stale generated weapons from older runs."""
    from gatekeeper.gatekeeper import Integrator

    source_item = tmp_path / "NyanCatStaff.png"
    source_projectile = tmp_path / "NyanCatStaffProjectile.png"
    source_item.write_bytes(b"item")
    source_projectile.write_bytes(b"projectile")

    mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"
    old_item = mod_root / "Content" / "Items" / "OldBadStaff.cs"
    old_projectile = mod_root / "Content" / "Projectiles" / "OldBadStaffProjectile.png"
    old_hjson = mod_root / "Localization" / "en-US.hjson"
    old_item.parent.mkdir(parents=True)
    old_projectile.parent.mkdir(parents=True)
    old_hjson.parent.mkdir(parents=True)
    old_item.write_text("public class OldBadStaff : ModItem { }", encoding="utf-8")
    old_projectile.write_bytes(b"old projectile")
    old_hjson.write_text("malformed stale hjson }", encoding="utf-8")

    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_root

    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class NyanCatStaff : Terraria.ModLoader.ModItem { }
    public class NyanCatStaffProjectile : Terraria.ModLoader.ModProjectile { }
}
"""

    integ._stage_files(
        cs_code=cs_code,
        hjson_code="",
        item_name="NyanCatStaff",
        sprite_path=str(source_item),
        projectile_sprite_path=str(source_projectile),
    )

    assert not old_item.exists()
    assert not old_projectile.exists()
    assert not old_hjson.exists()
    assert (mod_root / "Content" / "Items" / "NyanCatStaff.cs").exists()


def test_stage_files_rejects_missing_asset_path(tmp_path) -> None:
    """A provided pixelsmith output path must exist; otherwise the handoff failed."""
    import pytest

    from gatekeeper.gatekeeper import Integrator

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"

    with pytest.raises(FileNotFoundError, match="item sprite path does not exist"):
        integ._stage_files(
            cs_code="public class NyanCatStaff : Terraria.ModLoader.ModItem { }",
            hjson_code="",
            item_name="NyanCatStaff",
            sprite_path=str(tmp_path / "NyanCatStaff.png"),
            projectile_sprite_path=None,
        )


def test_stage_files_rejects_empty_item_asset_path_when_texture_autoloads(tmp_path) -> None:
    """Generated ModItems without a vanilla Texture override need a staged PNG."""
    import pytest

    from gatekeeper.gatekeeper import Integrator

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"

    with pytest.raises(ValueError, match="item sprite path is required"):
        integ._stage_files(
            cs_code="public class NyanCatStaff : Terraria.ModLoader.ModItem { }",
            hjson_code="",
            item_name="NyanCatStaff",
            sprite_path=None,
            projectile_sprite_path=None,
        )


def test_stage_files_allows_empty_asset_path_for_vanilla_texture_override(tmp_path) -> None:
    """Tier-3 procedural prototypes can use vanilla Terraria textures without PNG assets."""
    from gatekeeper.gatekeeper import Integrator

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"

    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class BlackLightningVfxTester : Terraria.ModLoader.ModItem
    {
        public override string Texture => "Terraria/Images/Item_" + Terraria.ID.ItemID.WarAxeoftheNight;
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class BlackLightningVfxTesterProjectile : Terraria.ModLoader.ModProjectile
    {
        public override string Texture => "Terraria/Images/Projectile_" + Terraria.ID.ProjectileID.MagicMissile;
    }
}
"""

    integ._stage_files(
        cs_code=cs_code,
        hjson_code="",
        item_name="BlackLightningVfxTester",
        sprite_path=None,
        projectile_sprite_path=None,
    )

    assert (
        integ._mod_root / "Content" / "Items" / "BlackLightningVfxTester.cs"
    ).exists()


def test_stage_files_allows_block_bodied_vanilla_texture_override(tmp_path) -> None:
    """Codegen may emit either expression-bodied or block-bodied Texture overrides."""
    from gatekeeper.gatekeeper import Integrator

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"

    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class BlockTextureTester : Terraria.ModLoader.ModItem
    {
        public override string Texture
        {
            get { return "Terraria/Images/Item_" + Terraria.ID.ItemID.WarAxeoftheNight; }
        }
    }
}
"""

    integ._stage_files(
        cs_code=cs_code,
        hjson_code="",
        item_name="BlockTextureTester",
        sprite_path=None,
        projectile_sprite_path=None,
    )

    assert (integ._mod_root / "Content" / "Items" / "BlockTextureTester.cs").exists()


def test_stage_files_rejects_empty_projectile_asset_path_when_texture_autoloads(
    tmp_path,
) -> None:
    """Generated ModProjectiles without a vanilla Texture override need their PNG."""
    import pytest

    from gatekeeper.gatekeeper import Integrator

    item_sprite = tmp_path / "NyanCatStaff.png"
    item_sprite.write_bytes(b"item")

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"

    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class NyanCatStaff : Terraria.ModLoader.ModItem { }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class NyanCatStaffProjectile : Terraria.ModLoader.ModProjectile { }
}
"""

    with pytest.raises(ValueError, match="projectile sprite path is required"):
        integ._stage_files(
            cs_code=cs_code,
            hjson_code="",
            item_name="NyanCatStaff",
            sprite_path=str(item_sprite),
            projectile_sprite_path=None,
        )


def test_build_and_verify_stages_assets_to_tmodloader_texture_paths(tmp_path) -> None:
    """The public gatekeeper path stages item/projectile assets without manual copy."""
    from gatekeeper.gatekeeper import CompileResult, Integrator

    source_item = tmp_path / "NyanCatStaff.png"
    source_projectile = tmp_path / "NyanCatStaffProjectile.png"
    source_item.write_bytes(b"item")
    source_projectile.write_bytes(b"projectile")

    mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"
    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_root
    integ._max_retries = 0
    integ._coder = None

    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class NyanCatStaff : Terraria.ModLoader.ModItem { }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class NyanCatStaffProjectile : Terraria.ModLoader.ModProjectile { }
}
"""

    with mock.patch.object(
        integ, "_run_tmod_build", return_value=CompileResult(True, "ok")
    ):
        with mock.patch.object(integ, "_write_status"):
            with mock.patch.object(integ, "_ensure_mod_enabled"):
                out = integ.build_and_verify(
                    {
                        "status": "success",
                        "cs_code": cs_code,
                        "hjson_code": "",
                    },
                    sprite_path=str(source_item),
                    projectile_sprite_path=str(source_projectile),
                )

    assert out["status"] == "success"
    assert (mod_root / "Content" / "Items" / "NyanCatStaff.png").read_bytes() == b"item"
    assert (
        mod_root / "Content" / "Projectiles" / "NyanCatStaffProjectile.png"
    ).read_bytes() == b"projectile"


def test_build_and_verify_reuses_asset_paths_after_code_repair(tmp_path) -> None:
    """Repair restaging must keep the original assets so retry builds can run."""
    from gatekeeper.gatekeeper import CompileResult, Integrator

    source_item = tmp_path / "NyanCatStaff.png"
    source_projectile = tmp_path / "NyanCatStaffProjectile.png"
    source_item.write_bytes(b"item")
    source_projectile.write_bytes(b"projectile")

    mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"
    coder = mock.Mock()
    coder.fix_code.return_value = {
        "status": "success",
        "cs_code": """
namespace ForgeGeneratedMod.Content.Items
{
    public class NyanCatStaff : Terraria.ModLoader.ModItem { }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class NyanCatStaffProjectile : Terraria.ModLoader.ModProjectile { }
}
""",
    }

    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_root
    integ._max_retries = 1
    integ._coder = coder

    failing_build = CompileResult(
        False,
        "/tmp/NyanCatStaff.cs(1,1): error CS0103: missing name",
    )
    passing_build = CompileResult(True, "ok")

    with mock.patch.object(
        integ, "_run_tmod_build", side_effect=[failing_build, passing_build]
    ) as run_build:
        with mock.patch.object(integ, "_write_status"):
            with mock.patch.object(integ, "_ensure_mod_enabled"):
                out = integ.build_and_verify(
                    {
                        "status": "success",
                        "cs_code": coder.fix_code.return_value["cs_code"],
                        "hjson_code": "",
                    },
                    sprite_path=str(source_item),
                    projectile_sprite_path=str(source_projectile),
                )

    assert out["status"] == "success"
    assert run_build.call_count == 2
    assert (mod_root / "Content" / "Items" / "NyanCatStaff.png").read_bytes() == b"item"
    assert (
        mod_root / "Content" / "Projectiles" / "NyanCatStaffProjectile.png"
    ).read_bytes() == b"projectile"


def test_build_and_verify_passes_manifest_to_code_repair(tmp_path) -> None:
    """Gatekeeper repair must preserve deterministic manifest contracts."""
    from gatekeeper.gatekeeper import CompileResult, Integrator

    source_item = tmp_path / "NyanCatStaff.png"
    source_projectile = tmp_path / "NyanCatStaffProjectile.png"
    source_item.write_bytes(b"item")
    source_projectile.write_bytes(b"projectile")

    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class NyanCatStaff : Terraria.ModLoader.ModItem { }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class NyanCatStaffProjectile : Terraria.ModLoader.ModProjectile { }
}
"""
    manifest = {"projectile_visuals": {"hitbox_size": [16, 20]}}
    coder = mock.Mock()
    coder.fix_code.return_value = {"status": "error"}

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"
    integ._max_retries = 1
    integ._coder = coder

    failing_build = CompileResult(
        False,
        "/tmp/NyanCatStaff.cs(1,1): error CS0103: missing name",
    )

    with mock.patch.object(integ, "_run_tmod_build", return_value=failing_build):
        with mock.patch.object(integ, "_write_status"):
            integ.build_and_verify(
                {
                    "status": "success",
                    "cs_code": cs_code,
                    "hjson_code": "",
                },
                sprite_path=str(source_item),
                projectile_sprite_path=str(source_projectile),
                manifest=manifest,
            )

    coder.fix_code.assert_called_once()
    assert coder.fix_code.call_args.kwargs["manifest"] == manifest


def test_inject_mod_projectile_texture_inserts_when_class_has_no_texture() -> None:
    from gatekeeper.gatekeeper import Integrator

    cs = """
public class SomeGun : ModItem { }
public class MyProj : ModProjectile
{
    public override void SetDefaults() { }
}
"""
    out = Integrator._inject_mod_projectile_texture(
        cs, "MyProj", "ForgeGeneratedMod", use_mod_projectile_png=True
    )
    assert "ForgeGeneratedMod/Content/Projectiles/MyProj" in out
    assert "public override string Texture" in out


def test_inject_mod_projectile_texture_skips_vanilla_terraria_images() -> None:
    from gatekeeper.gatekeeper import Integrator

    cs = """
public class MyProj : ModProjectile
{
    public override string Texture => "Terraria/Images/Projectile_3" + "x";
}
"""
    out = Integrator._inject_mod_projectile_texture(
        cs, "MyProj", "ForgeGeneratedMod", use_mod_projectile_png=True
    )
    assert out == cs


def test_inject_mod_projectile_texture_rewrites_content_items_path() -> None:
    from gatekeeper.gatekeeper import Integrator

    cs = """
public class MyProj : ModProjectile
{
    public override string Texture => "ForgeGeneratedMod/Content/Items/MyProj";
}
"""
    out = Integrator._inject_mod_projectile_texture(
        cs, "MyProj", "ForgeGeneratedMod", use_mod_projectile_png=True
    )
    assert "Content/Projectiles/MyProj" in out
    assert "Content/Items/MyProj" not in out


def test_resolve_staging_hjson_uses_manifest_over_llm_hjson() -> None:
    from gatekeeper.gatekeeper import Integrator

    bad = "this is not valid hjson {}}} raw tooltip"
    got = Integrator._resolve_staging_hjson(
        bad,
        {
            "display_name": "Voidline Pistol",
            "tooltip": "Line one.\nShots have [c/ff0000:color].",
        },
        "VoidlinePistol",
        "ForgeGeneratedMod",
    )
    assert "Voidline Pistol" in got
    assert "Line one" in got
    assert "[c/ff0000:color]" in got
    assert "Mods:" in got and "VoidlinePistol" in got


def test_build_and_verify_stages_manifest_hjson_on_success(tmp_path) -> None:
    from gatekeeper.gatekeeper import CompileResult, Integrator

    item_png = tmp_path / "TestItem.png"
    item_png.write_bytes(b"png")
    mod_root = tmp_path / "ModSources" / "ForgeGeneratedMod"
    integ = Integrator.__new__(Integrator)
    integ._mod_root = mod_root
    integ._max_retries = 0
    integ._coder = None

    cs = "public class TestItem : ModItem { }"
    hjson_bogus = "not valid"

    with mock.patch.object(
        integ, "_run_tmod_build", return_value=CompileResult(True, "ok")
    ):
        with mock.patch.object(integ, "_write_status"):
            with mock.patch.object(integ, "_ensure_mod_enabled"):
                integ.build_and_verify(
                    {
                        "status": "success",
                        "cs_code": cs,
                        "hjson_code": hjson_bogus,
                    },
                    sprite_path=str(item_png),
                    manifest={
                        "display_name": "Hello",
                        "tooltip": "World",
                    },
                )

    path = mod_root / "Localization" / "en-US.hjson"
    text = path.read_text(encoding="utf-8")
    assert "Hello" in text
    assert "World" in text


def test_run_tmod_build_removes_empty_install_shadow_source(tmp_path) -> None:
    from gatekeeper.gatekeeper import Integrator

    shadow = tmp_path / "ForgeGeneratedMod"
    shadow.mkdir()

    Integrator._remove_empty_tmodloader_shadow_source(shadow)

    assert not shadow.exists()


def test_run_tmod_build_preserves_non_empty_install_shadow_source(tmp_path) -> None:
    from gatekeeper.gatekeeper import Integrator

    shadow = tmp_path / "ForgeGeneratedMod"
    shadow.mkdir()
    (shadow / "keep.txt").write_text("do not remove", encoding="utf-8")

    Integrator._remove_empty_tmodloader_shadow_source(shadow)

    assert shadow.exists()
    assert (shadow / "keep.txt").is_file()


def test_run_tmod_build_passes_absolute_mod_source_path(tmp_path) -> None:
    from gatekeeper.gatekeeper import Integrator

    integ = Integrator.__new__(Integrator)
    integ._mod_root = tmp_path / "save" / "ModSources" / "ForgeGeneratedMod"
    integ._tmod_dll = tmp_path / "tModLoader" / "tModLoader.dll"
    integ._mod_root.mkdir(parents=True)
    integ._tmod_dll.parent.mkdir(parents=True)

    captured = {}

    def fake_run(cmd, capture_output, text):
        captured["cmd"] = cmd

        class Proc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Proc()

    with mock.patch("gatekeeper.gatekeeper.subprocess.run", side_effect=fake_run):
        result = integ._run_tmod_build()

    assert result.success is True
    assert captured["cmd"][3] == str(integ._mod_root)
