"""Tests for forge_generate_sprite MCP tool."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

from mcp_server import forge_generate_sprite


def test_forge_generate_sprite_returns_three_candidates(tmp_path: Path) -> None:
    fake_paths = [tmp_path / f"cand_{i}.png" for i in range(3)]
    for p in fake_paths:
        p.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch("mcp_server._run_pixelsmith_audition") as mock_run:
        mock_run.return_value = [str(p) for p in fake_paths]
        result = forge_generate_sprite(
            description="silver wand with crescent",
            size=[40, 40],
            animation_frames=1,
            kind="item",
            reference_path=None,
            generation_id="20260430_120000",
        )

    assert result["status"] == "success"
    assert len(result["candidate_paths"]) == 3


def test_forge_generate_sprite_passes_reference_when_supplied(tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake_paths = [tmp_path / f"cand_{i}.png" for i in range(3)]
    for p in fake_paths:
        p.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch("mcp_server._run_pixelsmith_audition") as mock_run:
        mock_run.return_value = [str(p) for p in fake_paths]
        forge_generate_sprite(
            description="moon beam projectile",
            size=[18, 18],
            animation_frames=3,
            kind="projectile",
            reference_path=str(ref),
            generation_id="20260430_120001",
        )

    mock_run.assert_called_once()
    _args, kwargs = mock_run.call_args
    assert kwargs["reference_path"] == str(ref)
