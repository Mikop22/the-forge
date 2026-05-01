"""Staging directory management for the Forge MCP pipeline."""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

STAGING_ROOT = Path(__file__).resolve().parents[1] / ".forge_staging"


def new_generation_id() -> str:
    """Return a fresh timestamp slug usable as a staging directory name."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def staging_path_for(generation_id: str) -> Path:
    """Resolve the staging directory path for the given generation ID."""
    return STAGING_ROOT / generation_id


def create_staging_dir(generation_id: str) -> Path:
    """Create the staging directory and return its path."""
    path = staging_path_for(generation_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_stale_staging(max_age_hours: int = 24) -> None:
    """Delete staging directories older than ``max_age_hours``."""
    if not STAGING_ROOT.exists():
        return
    cutoff = time.time() - (max_age_hours * 3600)
    for entry in STAGING_ROOT.iterdir():
        if not entry.is_dir():
            continue
        if entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
