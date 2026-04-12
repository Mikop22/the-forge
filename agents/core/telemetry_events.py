"""Telemetry events emitted by the hidden weapon lab flow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.combat_packages import CombatPackageLiteral
from core.runtime_capabilities import LoopFamilyLiteral

LabTelemetryEventType = Literal[
    "candidate_started",
    "candidate_completed",
    "loop_triggered",
    "fx_emitted",
    "audio_emitted",
    "seed_triggered",
    "escalate_triggered",
    "cashout_triggered",
    "fx_marker",
    "audio_marker",
]


class LabTelemetryEvent(BaseModel):
    """Single telemetry record for a lab candidate or loop event."""

    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    package_key: CombatPackageLiteral
    event_type: LabTelemetryEventType
    timestamp_ms: int = Field(..., ge=0)
    loop_family: LoopFamilyLiteral | None = None
    cast_id: int | None = Field(default=None, ge=1)
    target_id: str | None = None
    stack_count: int | None = Field(default=None, ge=0)
    fx_marker: str | None = None
    audio_marker: str | None = None
