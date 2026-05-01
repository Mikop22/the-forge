"""Persistence helpers for Forge Director workshop sessions.

Layout under ``root``:

- ``<session_id>.json`` — full session payload (bench, shelf, ``session_shell``, …).
- ``active_session.txt`` — legacy pointer to the active session id (optional); when present
  but stale, ``active_session_id()`` prefers the newest ``*.json`` by mtime.

``save()`` does not write ``active_session.txt``; newest JSON wins for ``active_session_id()``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.atomic_io import atomic_write_text
from contracts.session_shell import SessionShellState


class WorkshopSessionStore:
    """Read/write per-session JSON next to an optional legacy active-session pointer."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._active_path = self._root / "active_session.txt"

    def _session_path(self, session_id: str) -> Path:
        cleaned = session_id.strip()
        if not cleaned:
            raise ValueError("session_id is required")
        return self._root / f"{cleaned}.json"

    def save(self, payload: dict[str, Any]) -> None:
        session_id = str(payload.get("session_id", "")).strip()
        path = self._session_path(session_id)
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        atomic_write_text(path, text)

    def _session_json_paths(self) -> list[Path]:
        if not self._root.exists():
            return []
        paths = [
            path
            for path in self._root.glob("*.json")
            if path.name != self._active_path.name
        ]
        paths.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
        return paths

    def _most_recent_session_id(self) -> str | None:
        paths = self._session_json_paths()
        if not paths:
            return None
        return paths[-1].stem

    def load(self, session_id: str) -> dict[str, Any]:
        """Load session JSON. Missing file → ``{}``; corrupt JSON → ``{}``."""
        path = self._session_path(session_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def save_session_shell(self, session_id: str, shell: SessionShellState) -> None:
        session = self.load(session_id)
        if not session:
            session = {"session_id": session_id}
        session["session_shell"] = shell.model_dump(mode="json", exclude_none=True)
        self.save(session)

    def load_session_shell(self, session_id: str) -> SessionShellState | None:
        session = self.load(session_id)
        if not session:
            return None
        raw_shell = session.get("session_shell")
        if raw_shell is None:
            return None
        return SessionShellState.model_validate(raw_shell)

    def active_session_id(self) -> str | None:
        """Newest ``*.json`` session id, else legacy ``active_session.txt`` if still valid."""
        session_id = self._most_recent_session_id()
        if session_id is not None:
            return session_id
        try:
            legacy_session_id = self._active_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not legacy_session_id:
            return None
        session_path = self._session_path(legacy_session_id)
        if session_path.exists():
            return legacy_session_id
        return None

    def load_active(self) -> dict[str, Any]:
        session_id = self.active_session_id()
        if not session_id:
            return {}
        return self.load(session_id)
