"""Tests for forge_inject MCP tool."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from mcp_server import forge_inject


def test_forge_inject_writes_files_and_inject_json(tmp_path: Path) -> None:
    staging = tmp_path / "staging" / "20260430_120000"
    (staging / "Content" / "Items").mkdir(parents=True)
    (staging / "Content" / "Items" / "Foo.cs").write_text("// generated")
    (staging / "Localization").mkdir(parents=True)
    (staging / "Localization" / "en-US.hjson").write_text("Mods: {}")

    item_sprite = tmp_path / "item.png"
    item_sprite.write_bytes(b"\x89PNG\r\n\x1a\n")
    proj_sprite = tmp_path / "proj.png"
    proj_sprite.write_bytes(b"\x89PNG\r\n\x1a\n")

    mod_sources = tmp_path / "ModSources"
    mod_dest = mod_sources / "ForgeGeneratedMod"
    mod_dest.mkdir(parents=True)

    with patch("mcp_server.STAGING_ROOT", tmp_path / "staging"), \
         patch("mcp_server._mod_sources_root", return_value=mod_sources):
        result = forge_inject(
            item_name="Foo",
            cs_code="// generated",
            manifest={"item_name": "Foo", "display_name": "Foo", "tooltip": ""},
            item_sprite_path=str(item_sprite),
            projectile_sprite_path=str(proj_sprite),
            generation_id="20260430_120000",
        )

    assert result["status"] == "success"
    assert result["reload_required"] is True
    assert (mod_dest / "Content" / "Items" / "Foo.cs").exists()
    inject_payload = json.loads((mod_sources / "forge_inject.json").read_text())
    assert inject_payload["item_name"] == "Foo"


def test_forge_inject_rejects_unknown_generation_id(tmp_path: Path) -> None:
    with patch("mcp_server.STAGING_ROOT", tmp_path / "staging"), \
         patch("mcp_server._mod_sources_root", return_value=tmp_path / "ModSources"):
        result = forge_inject(
            item_name="Foo",
            cs_code="// x",
            manifest={"item_name": "Foo", "display_name": "Foo", "tooltip": ""},
            item_sprite_path="/nonexistent.png",
            projectile_sprite_path="/nonexistent.png",
            generation_id="does_not_exist",
        )
    assert result["status"] == "error"
    assert "staging" in result["error_message"].lower()
