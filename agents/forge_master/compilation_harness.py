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

_REQUIRED_DLLS = ["Terraria.dll", "FNA.dll"]


def find_tmod_path() -> Path | None:
    """Return a directory that contains the required tModLoader DLLs, or None."""
    # 1. Explicit env override
    env = os.environ.get("TMODLOADER_PATH")
    if env:
        candidate = Path(env)
        if _has_dlls(candidate):
            return candidate
        return None  # env was set but path doesn't have the DLLs — don't fall through to Steam

    # 2. Common Steam paths
    for base in _STEAM_PATHS:
        if _has_dlls(base):
            return base
        # DLLs may live one level deeper (macOS app bundle, etc.)
        if base.is_dir():
            for sub in base.glob("*/"):
                if _has_dlls(sub):
                    return sub

    return None


def _has_dlls(path: Path) -> bool:
    return path.is_dir() and all((path / dll).exists() for dll in _REQUIRED_DLLS)
