"""Tests for forge_compile MCP tool."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mcp_server import forge_compile


def test_forge_compile_creates_staging_dir_with_generation_id(tmp_path: Path) -> None:
    cs_code = "namespace ForgeGeneratedMod.Content.Items { class Foo {} }"
    manifest = {
        "item_name": "Foo",
        "display_name": "Foo Item",
        "tooltip": "A simple foo",
    }

    with patch("mcp_server.STAGING_ROOT", tmp_path), \
         patch("mcp_server._invoke_tmodloader_build") as mock_build:
        mock_build.return_value = MagicMock(returncode=0, stdout="Build success", stderr="")
        result = forge_compile(cs_code, manifest, "20260430_120000")

    assert result["status"] == "success"
    staged = tmp_path / "20260430_120000"
    assert staged.exists()
    assert (staged / "Content" / "Items" / "Foo.cs").exists()
    assert (staged / "Localization" / "en-US.hjson").exists()


def test_forge_compile_returns_errors_on_build_failure(tmp_path: Path) -> None:
    cs_code = "broken c# code"
    manifest = {"item_name": "Bad", "display_name": "Bad", "tooltip": ""}

    with patch("mcp_server.STAGING_ROOT", tmp_path), \
         patch("mcp_server._invoke_tmodloader_build") as mock_build:
        mock_build.return_value = MagicMock(
            returncode=1,
            stdout="error CS1002: ; expected",
            stderr="",
        )
        result = forge_compile(cs_code, manifest, "20260430_120001")

    assert result["status"] == "error"
    assert any("CS1002" in err for err in result["errors"])
