"""End-to-end smoke test of the MCP server (Tier 1 weapon)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from mcp_server import forge_compile, forge_generate_sprite, forge_inject, forge_status


def test_full_pipeline_tier1(tmp_path: Path) -> None:
    generation_id = "20260430_120000"
    manifest = {
        "item_name": "TestStarterBow",
        "display_name": "Test Starter Bow",
        "tooltip": "A simple bow",
        "stats": {"damage": 10, "knockback": 2, "use_time": 28, "rarity": "ItemRarityID.Blue"},
        "mechanics": {
            "custom_projectile": False,
            "shoot_projectile": "ProjectileID.WoodenArrowFriendly",
            "crafting_material": "ItemID.Wood",
            "crafting_cost": 10,
            "crafting_tile": "TileID.WorkBenches",
        },
    }
    cs_code = (
        "using Terraria; using Terraria.ID; using Terraria.ModLoader;\n"
        "namespace ForgeGeneratedMod.Content.Items {\n"
        "  public class TestStarterBow : ModItem {\n"
        "    public override void SetDefaults() { Item.damage = 10; }\n"
        "  }\n"
        "}\n"
    )

    item_sprite = tmp_path / "item.png"
    item_sprite.write_bytes(b"\x89PNG\r\n\x1a\n")
    proj_sprite = tmp_path / "proj.png"
    proj_sprite.write_bytes(b"\x89PNG\r\n\x1a\n")

    mod_sources = tmp_path / "ModSources"
    (mod_sources / "ForgeGeneratedMod").mkdir(parents=True)

    with patch("mcp_server.STAGING_ROOT", tmp_path / "staging"), \
         patch("mcp_server._mod_sources_root", return_value=mod_sources), \
         patch("mcp_server._invoke_tmodloader_build") as mock_build, \
         patch("mcp_server._run_pixelsmith_audition") as mock_sprite:
        mock_build.return_value = MagicMock(returncode=0, stdout="Build success", stderr="")
        mock_sprite.return_value = [str(item_sprite), str(item_sprite), str(item_sprite)]

        compile_result = forge_compile(cs_code, manifest, generation_id)
        assert compile_result["status"] == "success"

        sprite_result = forge_generate_sprite(
            description="simple wooden bow",
            size=[40, 40],
            animation_frames=1,
            kind="item",
            reference_path=None,
            generation_id=generation_id,
        )
        assert sprite_result["status"] == "success"
        assert len(sprite_result["candidate_paths"]) == 3

        status_result = forge_status()
        assert status_result["forge_connector_alive"] is False  # no heartbeat in test fixture

        inject_result = forge_inject(
            item_name="TestStarterBow",
            cs_code=cs_code,
            manifest=manifest,
            item_sprite_path=str(item_sprite),
            projectile_sprite_path=str(proj_sprite),
            generation_id=generation_id,
        )
        assert inject_result["status"] == "success"
        assert inject_result["reload_required"] is True

    assert (mod_sources / "ForgeGeneratedMod" / "Content" / "Items" / "TestStarterBow.cs").exists()
    inject_payload = json.loads((mod_sources / "forge_inject.json").read_text())
    assert inject_payload["item_name"] == "TestStarterBow"
