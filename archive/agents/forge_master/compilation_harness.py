"""tModLoader DLL discovery for the Forge pipeline."""

from __future__ import annotations

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# DLL discovery
# ---------------------------------------------------------------------------

_STEAM_PATHS = [
    # macOS
    Path.home() / "Library/Application Support/Steam/steamapps/common/tModLoader",
    # Windows
    Path("C:/Program Files (x86)/Steam/steamapps/common/tModLoader"),
    Path("C:/Program Files/Steam/steamapps/common/tModLoader"),
    # Linux
    Path.home() / ".steam/steam/steamapps/common/tModLoader",
    Path.home() / ".local/share/Steam/steamapps/common/tModLoader",
]

_TMOD_DLL = "tModLoader.dll"


def find_tmod_path() -> Path | None:
    """Return the tModLoader install root, or None."""
    # 1. Explicit env override
    env = os.environ.get("TMODLOADER_PATH")
    if env:
        candidate = Path(env)
        if _has_tmod_dll(candidate):
            return candidate
        return None  # env was set but path doesn't have the DLLs — don't fall through to Steam

    # 2. Common Steam paths
    for base in _STEAM_PATHS:
        if _has_tmod_dll(base):
            return base
        # The install root may live one level deeper (macOS app bundle, etc.)
        if base.is_dir():
            for sub in base.glob("*/"):
                if _has_tmod_dll(sub):
                    return sub

    return None


def _has_tmod_dll(path: Path) -> bool:
    # Current macOS installs place FNA under Libraries/FNA/... and may not ship a
    # top-level Terraria.dll, so the build wrapper should key off the real entrypoint.
    return path.is_dir() and (path / _TMOD_DLL).exists()
