"""Shared atomic file writes for orchestrator and gatekeeper."""

from __future__ import annotations

import contextlib
import errno
import logging
import os
import tempfile
import time
from pathlib import Path

log = logging.getLogger(__name__)


def _retryable_atomic_error(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    if isinstance(exc, OSError):
        return exc.errno in (errno.ENOENT, errno.ENOTDIR)
    return False


def atomic_write_text(path: Path | str, text: str) -> None:
    """Write UTF-8 text via unique temp file in *path*'s directory, fsync, then replace.

    Retries on transient ENOENT/ENOTDIR (e.g. ModSources briefly missing, sync tools, AV).
    Re-mkdirs the parent immediately before :func:`os.replace` so the destination path exists.
    """
    path = Path(path).expanduser()
    parent = path.parent
    prefix = f"{path.stem}."
    dst = os.fspath(path)
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                prefix=prefix,
                suffix=".tmp",
                dir=os.fspath(parent),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(text)
                    f.flush()
                    os.fsync(f.fileno())
                # Directory may vanish between mkstemp and replace (game, sync, manual delete).
                parent.mkdir(parents=True, exist_ok=True)
                os.replace(os.fspath(tmp_path), dst)
                return
            except Exception:
                with contextlib.suppress(Exception):
                    os.unlink(tmp_path)
                raise
        except Exception as exc:
            if attempt < max_attempts - 1 and _retryable_atomic_error(exc):
                log.warning(
                    "Atomic write retry %s/%s for %s — %s",
                    attempt + 1,
                    max_attempts,
                    path.name,
                    exc,
                )
                time.sleep(0.05 * (2 ** min(attempt, 5)))
                continue
            raise
