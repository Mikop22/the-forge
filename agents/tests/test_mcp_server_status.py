"""Tests for forge_status MCP tool."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from mcp_server import forge_status


def test_forge_status_returns_offline_when_no_files(tmp_path: Path) -> None:
    with patch("mcp_server._mod_sources_root", return_value=tmp_path):
        result = forge_status()
    assert result["forge_connector_alive"] is False
    assert result["tmodloader_running"] is False


def test_forge_status_reports_alive_when_heartbeat_recent(tmp_path: Path) -> None:
    alive_path = tmp_path / "forge_connector_alive.json"
    alive_path.write_text(json.dumps({"timestamp_unix": __import__("time").time()}))
    with patch("mcp_server._mod_sources_root", return_value=tmp_path):
        result = forge_status()
    assert result["forge_connector_alive"] is True
