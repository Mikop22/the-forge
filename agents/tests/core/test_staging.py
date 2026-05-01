"""Tests for staging directory lifecycle."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from core.staging import (
    STAGING_ROOT,
    create_staging_dir,
    cleanup_stale_staging,
    staging_path_for,
)


def test_create_staging_dir_creates_directory(tmp_path: Path) -> None:
    with patch("core.staging.STAGING_ROOT", tmp_path):
        path = create_staging_dir("20260430_120000")
    assert path.exists()
    assert path.name == "20260430_120000"


def test_staging_path_for_returns_expected_path(tmp_path: Path) -> None:
    with patch("core.staging.STAGING_ROOT", tmp_path):
        path = staging_path_for("20260430_120000")
    assert path == tmp_path / "20260430_120000"


def test_cleanup_stale_staging_removes_old_dirs(tmp_path: Path) -> None:
    old = tmp_path / "old"
    old.mkdir()
    (old / "marker").write_text("")
    fresh = tmp_path / "fresh"
    fresh.mkdir()

    old_time = time.time() - (25 * 3600)
    import os
    os.utime(old, (old_time, old_time))

    with patch("core.staging.STAGING_ROOT", tmp_path):
        cleanup_stale_staging(max_age_hours=24)

    assert not old.exists()
    assert fresh.exists()
