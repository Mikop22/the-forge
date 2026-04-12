"""Runtime lab result helpers for hidden audition telemetry."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.combat_packages import CombatPackageLiteral
from core.runtime_capabilities import LoopFamilyLiteral
from core.telemetry_events import LabTelemetryEvent


class RuntimeLabResult(BaseModel):
    """Normalized runtime telemetry payload for a single candidate."""

    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    package_key: CombatPackageLiteral
    loop_family: LoopFamilyLiteral
    events: list[LabTelemetryEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_identity(self) -> "RuntimeLabResult":
        for event in self.events:
            if event.candidate_id != self.candidate_id:
                raise ValueError("event candidate_id must match result candidate_id")
            if event.run_id != self.run_id:
                raise ValueError("event run_id must match result run_id")
            if event.package_key != self.package_key:
                raise ValueError("event package_key must match result package_key")
            if event.loop_family != self.loop_family:
                raise ValueError("event loop_family must match result loop_family")
        return self


def load_lab_result(payload: dict[str, Any]) -> RuntimeLabResult:
    candidate_id = str(payload.get("candidate_id") or "").strip()
    run_id = str(payload.get("run_id") or "").strip()
    package_key = payload.get("package_key")
    loop_family = payload.get("loop_family")
    raw_events = payload.get("events") or []

    normalized_events = []
    for event in raw_events:
        normalized_event = dict(event)
        normalized_event.setdefault("candidate_id", candidate_id)
        normalized_event.setdefault("run_id", run_id)
        if package_key is not None:
            normalized_event.setdefault("package_key", package_key)
        if loop_family is not None:
            normalized_event.setdefault("loop_family", loop_family)
        normalized_events.append(normalized_event)

    return RuntimeLabResult.model_validate(
        {
            **payload,
            "candidate_id": candidate_id,
            "run_id": run_id,
            "events": normalized_events,
        }
    )
