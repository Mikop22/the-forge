"""Shared ModSources path resolution for orchestrator, Gatekeeper, and tests."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path


def config_toml_path() -> Path:
    return Path.home() / ".config" / "theforge" / "config.toml"


def _trim_inline_comment(val: str) -> str:
    """Strip TOML inline comments outside quotes."""
    in_quote = 0
    escaped = False
    for i, ch in enumerate(val):
        if escaped:
            escaped = False
            continue
        if in_quote:
            if ch == "\\":
                escaped = True
                continue
            if ch in ('"', "'") and ch == chr(in_quote):
                in_quote = 0
            continue
        if ch in ('"', "'"):
            in_quote = ord(ch)
            continue
        if ch == "#" and (i == 0 or val[i - 1] in " \t"):
            return val[:i].strip()
    return val.strip()


def read_mod_sources_dir_from_config() -> str:
    """Read the root-level ``mod_sources_dir`` from config.toml."""
    cfg_path = config_toml_path()
    try:
        data = cfg_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            break
        eq_idx = line.find("=")
        if eq_idx < 0:
            continue
        key = line[:eq_idx].strip()
        if key != "mod_sources_dir":
            continue
        val = line[eq_idx + 1 :].strip()
        val = _trim_inline_comment(val)
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        val = val.strip()
        return val
    return ""


def mod_sources_root() -> Path:
    """Resolve the tModLoader ModSources directory."""
    override = os.environ.get("FORGE_MOD_SOURCES_DIR", "").strip()
    if override:
        return Path(override).expanduser()

    cfg = read_mod_sources_dir_from_config().strip()
    if cfg:
        return Path(cfg).expanduser()

    home = Path.home()
    system = platform.system().lower()
    if system == "windows":
        user_profile = Path(os.environ.get("USERPROFILE") or home)
        return (
            user_profile
            / "Documents"
            / "My Games"
            / "Terraria"
            / "tModLoader"
            / "ModSources"
        )
    if system == "linux":
        return home / ".local" / "share" / "Terraria" / "tModLoader" / "ModSources"
    return (
        home
        / "Library"
        / "Application Support"
        / "Terraria"
        / "tModLoader"
        / "ModSources"
    )
