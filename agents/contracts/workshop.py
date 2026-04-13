"""Pydantic models for the Forge Director workshop loop.

The transcript/memory shell state lives in ``contracts.session_shell`` so the
workshop bench/shelf transport stays small and stable.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class BenchState(BaseModel):
    """Active item snapshot shown on the workshop bench."""

    model_config = ConfigDict(extra="ignore")

    item_id: str = ""
    label: str = ""
    manifest: dict[str, Any] | None = None
    sprite_path: str | None = None
    projectile_sprite_path: str | None = None


class ShelfVariant(BaseModel):
    """A materialized alternative the director can place on the bench."""

    model_config = ConfigDict(extra="ignore")

    variant_id: str = ""
    label: str = ""
    rationale: str | None = None
    change_summary: str | None = None
    manifest: dict[str, Any] | None = None
    sprite_path: str | None = None
    projectile_sprite_path: str | None = None


class WorkshopRequest(BaseModel):
    """``workshop_request.json`` — TUI → orchestrator."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["variants", "bench", "try", "restore"] = "variants"
    session_id: str = ""
    snapshot_id: int = 0
    bench_item_id: str | None = None
    variant_id: str | None = None
    directive: str | None = None
    bench: BenchState | None = None
    restore_target: Literal["baseline", "last_live"] | None = None


class WorkshopStatus(BaseModel):
    """``workshop_status.json`` — orchestrator → TUI."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = ""
    snapshot_id: int = 0
    bench: BenchState = BenchState()
    shelf: list[ShelfVariant] = []
    last_action: str | None = None
    error: str | None = None


class RuntimeSummary(BaseModel):
    """``forge_runtime_summary.json`` — ForgeConnector → TUI."""

    model_config = ConfigDict(extra="ignore")

    bridge_alive: bool = False
    world_loaded: bool = False
    live_item_name: str | None = None
    last_inject_status: str | None = None
    last_runtime_note: str | None = None
    updated_at: str | None = None
