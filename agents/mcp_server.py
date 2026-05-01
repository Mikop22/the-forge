"""The Forge MCP server — exposes 4 execution tools to Claude Code."""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from core.compilation_harness import find_tmod_path
from core.hjson_gen import generate_hjson
from core.paths import mod_sources_root as _mod_sources_root_default
from core.staging import STAGING_ROOT, cleanup_stale_staging

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


_ERROR_RE = re.compile(r"(error\s+(?:CS\d+|TML\d+):\s+[^\n]+)")


def _invoke_tmodloader_build(staging_dir: Path) -> subprocess.CompletedProcess:
    """Invoke tModLoader build. Subprocess shape isolated for testability."""
    tmod_root = find_tmod_path()
    if tmod_root is None:
        raise RuntimeError("tModLoader installation not found. Set TMODLOADER_PATH.")
    return subprocess.run(
        ["dotnet", str(tmod_root / "tModLoader.dll"), "-build", str(staging_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


@mcp.tool()
def forge_compile(cs_code: str, manifest: dict, generation_id: str) -> dict:
    """Compile generated C# in an isolated staging directory.

    Args:
        cs_code: C# source for the ModItem (and any ModProjectile).
        manifest: Architect manifest. ``item_name``, ``display_name``, and
            ``tooltip`` are read for hjson generation.
        generation_id: Timestamp slug created by the main session at pipeline
            start. Used to locate the staging directory across compile/inject.

    Returns:
        {status, errors, artifact_path}
    """
    cleanup_stale_staging(max_age_hours=24)
    staging = STAGING_ROOT / generation_id
    staging.mkdir(parents=True, exist_ok=True)

    item_name = manifest["item_name"]
    items_dir = staging / "Content" / "Items"
    items_dir.mkdir(parents=True, exist_ok=True)
    (items_dir / f"{item_name}.cs").write_text(cs_code, encoding="utf-8")

    hjson = generate_hjson(
        item_name=item_name,
        display_name=manifest["display_name"],
        tooltip=manifest.get("tooltip", ""),
    )
    loc_dir = staging / "Localization"
    loc_dir.mkdir(parents=True, exist_ok=True)
    (loc_dir / "en-US.hjson").write_text(hjson, encoding="utf-8")

    proc = _invoke_tmodloader_build(staging)
    if proc.returncode == 0:
        return {
            "status": "success",
            "errors": [],
            "artifact_path": str(staging / f"{item_name}.tmod"),
        }
    errors = [m.group(1) for m in _ERROR_RE.finditer(proc.stdout + "\n" + proc.stderr)]
    if not errors:
        raw = (proc.stderr or proc.stdout).strip()
        errors = [raw.splitlines()[-1] if raw else "unknown build error"]
    return {"status": "error", "errors": errors, "artifact_path": ""}


def _run_pixelsmith_audition(
    *,
    description: str,
    size: list[int],
    animation_frames: int,
    kind: str,
    reference_path: str | None,
    generation_id: str,
) -> list[str]:
    """Bridge into the existing pixelsmith audition pipeline."""
    from pixelsmith.pixelsmith import ArtistAgent
    output_dir = STAGING_ROOT / generation_id / "sprites"
    output_dir.mkdir(parents=True, exist_ok=True)
    agent = ArtistAgent(output_dir=output_dir)
    result = agent.generate_audition_candidates(
        description=description,
        size=tuple(size),
        animation_frames=animation_frames,
        kind=kind,
        reference_path=reference_path,
    )
    return result["candidate_paths"]


@mcp.tool()
def forge_generate_sprite(
    description: str,
    size: list[int],
    animation_frames: int,
    kind: str,
    reference_path: str | None,
    generation_id: str,
) -> dict:
    """Generate sprite candidates for the Sprite-Judge subagent to choose from.

    Args:
        description: Visual description from the manifest.
        size: [width, height] in pixels.
        animation_frames: 1 for static, N for animated sheets.
        kind: "item" or "projectile".
        reference_path: Local image path for img2img mode. None for text-to-image.
        generation_id: Pipeline ID; sprites written under the staging dir.
    """
    if kind not in ("item", "projectile"):
        return {
            "status": "error",
            "candidate_paths": [],
            "error_message": f"invalid kind: {kind!r}",
        }
    try:
        candidate_paths = _run_pixelsmith_audition(
            description=description,
            size=size,
            animation_frames=animation_frames,
            kind=kind,
            reference_path=reference_path,
            generation_id=generation_id,
        )
    except Exception as exc:
        return {"status": "error", "candidate_paths": [], "error_message": str(exc)}
    return {"status": "success", "candidate_paths": candidate_paths}


if __name__ == "__main__":
    mcp.run()
