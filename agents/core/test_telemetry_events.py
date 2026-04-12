"""Tests for agents/core/telemetry_events.py."""

from __future__ import annotations

from core.telemetry_events import LabTelemetryEvent


def test_lab_telemetry_event_validates_minimal_event() -> None:
    event = LabTelemetryEvent.model_validate(
        {
            "candidate_id": "candidate-001",
            "run_id": "run-201",
            "package_key": "storm_brand",
            "event_type": "candidate_started",
            "timestamp_ms": 123456789,
        }
    )

    assert event.candidate_id == "candidate-001"
    assert event.run_id == "run-201"
    assert event.package_key == "storm_brand"
    assert event.event_type == "candidate_started"
    assert event.timestamp_ms == 123456789


def test_lab_telemetry_event_accepts_loop_family_when_present() -> None:
    event = LabTelemetryEvent.model_validate(
        {
            "candidate_id": "candidate-001",
            "run_id": "run-202",
            "package_key": "storm_brand",
            "event_type": "loop_triggered",
            "timestamp_ms": 123456789,
            "loop_family": "mark_cashout",
        }
    )

    assert event.loop_family == "mark_cashout"
