"""Pydantic models for JSON files exchanged via ModSources.

These mirror the shapes written by ``orchestrator.py``, ``main.go`` (TUI), and
consumed by tests. Use ``model_validate`` on parsed JSON; unknown keys are
ignored on input where noted so the contract can evolve without breaking older
clients.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UserRequest(BaseModel):
    """``user_request.json`` — TUI → orchestrator."""

    model_config = ConfigDict(extra="ignore")

    prompt: str = ""
    tier: str = "Tier1_Starter"
    crafting_station: str | None = None
    content_type: str = "Weapon"
    sub_type: str = "Sword"
    mode: Literal["compile", "instant"] = "compile"
    existing_manifest: dict[str, Any] | None = None
    art_feedback: str | None = None


class GenerationStatus(BaseModel):
    """``generation_status.json`` — orchestrator → TUI.

    The Bubble Tea client maps a subset into ``internal/ipc.PipelineStatus``
    (e.g. ``batch_list[0]`` → item name; ``message`` maps to ``ErrMsg`` for
    errors and for ready/building copy). Fields
    like ``inject_mode`` and ``error_code`` are part of the wire format but
    are not always surfaced in the Go struct; keep them here for validation
    and forward compatibility.
    """

    model_config = ConfigDict(extra="allow")

    status: Literal["building", "ready", "error"]
    stage_label: str | None = None
    stage_pct: int | None = None
    batch_list: list[str] | None = None
    message: str | None = None
    manifest: dict[str, Any] | None = None
    sprite_path: str | None = None
    projectile_sprite_path: str | None = None
    inject_mode: bool | None = None
    error_code: str | None = None


class OrchestratorHeartbeat(BaseModel):
    """``orchestrator_alive.json`` — liveness from Python daemon."""

    model_config = ConfigDict(extra="allow")

    status: str = "listening"
    pid: int = Field(..., ge=0)
    timestamp: float = 0.0
    mod_sources_root: str = ""
