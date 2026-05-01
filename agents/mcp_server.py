"""The Forge MCP server — exposes 4 execution tools to Claude Code."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from core.paths import mod_sources_root as _mod_sources_root_default

mcp = FastMCP("forge")


def _mod_sources_root() -> Path:
    return _mod_sources_root_default()


def _read_json_or_none(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@mcp.tool()
def forge_status() -> dict[str, Any]:
    """Return current Forge pipeline state.

    Returns:
        {
            pipeline_stage: str,
            forge_connector_alive: bool,
            tmodloader_running: bool,
        }
    """
    root = _mod_sources_root()

    alive_payload = _read_json_or_none(root / "forge_connector_alive.json")
    forge_connector_alive = False
    if alive_payload:
        ts = alive_payload.get("timestamp_unix", 0)
        forge_connector_alive = (time.time() - ts) < 30  # heartbeat within 30s

    status_payload = _read_json_or_none(root / "generation_status.json")
    pipeline_stage = (status_payload or {}).get("status", "idle")

    return {
        "pipeline_stage": pipeline_stage,
        "forge_connector_alive": forge_connector_alive,
        "tmodloader_running": forge_connector_alive,
    }


if __name__ == "__main__":
    mcp.run()
