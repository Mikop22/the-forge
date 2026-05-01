from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest
from pydantic import ValidationError

import orchestrator
from core.runtime_contracts import HiddenLabRequest, build_hidden_lab_request
from core.runtime_lab_contract import RuntimeLabResult, load_lab_result


def test_runtime_lab_contract_result_accepts_seed_escalate_cashout_events() -> None:
    result = load_lab_result(
        {
            "candidate_id": "cand-1",
            "run_id": "run-001",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "events": [
                {"event_type": "seed_triggered", "timestamp_ms": 100},
                {"event_type": "escalate_triggered", "timestamp_ms": 450},
                {"event_type": "cashout_triggered", "timestamp_ms": 900},
            ],
        }
    )

    assert isinstance(result, RuntimeLabResult)
    assert result.candidate_id == "cand-1"
    assert [event.event_type for event in result.events] == [
        "seed_triggered",
        "escalate_triggered",
        "cashout_triggered",
    ]
    assert all(event.package_key == "storm_brand" for event in result.events)
    assert all(event.loop_family == "mark_cashout" for event in result.events)


def test_runtime_lab_contract_result_accepts_optional_fx_and_audio_markers() -> None:
    result = load_lab_result(
        {
            "candidate_id": "cand-2",
            "run_id": "run-002",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "events": [
                {
                    "event_type": "fx_marker",
                    "timestamp_ms": 120,
                    "fx_marker": "storm_mark_flash",
                },
                {
                    "event_type": "audio_marker",
                    "timestamp_ms": 240,
                    "audio_marker": "storm_cashout_chime",
                },
            ],
        }
    )

    assert [event.event_type for event in result.events] == [
        "fx_marker",
        "audio_marker",
    ]
    assert result.events[0].fx_marker == "storm_mark_flash"
    assert result.events[1].audio_marker == "storm_cashout_chime"


def test_runtime_lab_contract_result_rejects_event_run_id_mismatch() -> None:
    with pytest.raises(ValidationError):
        load_lab_result(
            {
                "candidate_id": "cand-2",
                "run_id": "run-002",
                "package_key": "storm_brand",
                "loop_family": "mark_cashout",
                "events": [
                    {
                        "candidate_id": "cand-2",
                        "run_id": "run-other",
                        "package_key": "storm_brand",
                        "loop_family": "mark_cashout",
                        "event_type": "seed_triggered",
                        "timestamp_ms": 120,
                    },
                ],
            }
        )


def test_runtime_lab_contract_result_requires_package_key_and_loop_family() -> None:
    with pytest.raises(ValidationError):
        load_lab_result(
            {
                "candidate_id": "cand-3",
                "run_id": "run-003",
                "events": [
                    {"event_type": "seed_triggered", "timestamp_ms": 100},
                ],
            }
        )


def test_runtime_lab_contract_result_rejects_event_identity_mismatch() -> None:
    with pytest.raises(ValidationError):
        load_lab_result(
            {
                "candidate_id": "cand-4",
                "run_id": "run-004",
                "package_key": "storm_brand",
                "loop_family": "mark_cashout",
                "events": [
                    {
                        "candidate_id": "cand-other",
                        "run_id": "run-004",
                        "package_key": "storm_brand",
                        "loop_family": "mark_cashout",
                        "event_type": "seed_triggered",
                        "timestamp_ms": 100,
                    },
                ],
            }
        )


def test_build_hidden_lab_request_validates_single_runtime_payload_contract() -> None:
    request = build_hidden_lab_request(
        finalist={
            "candidate_id": "cand-9",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "behavior_contract": {
                "seed_event": "seed_triggered",
                "escalate_event": "escalate_triggered",
                "cashout_event": "cashout_triggered",
                "max_hits_to_cashout": 3,
                "max_time_to_cashout_ms": 2500,
            },
            "manifest": {"item_name": "Storm Staff"},
            "sprite_path": "/tmp/storm-staff.png",
        }
    )

    assert isinstance(request, HiddenLabRequest)
    assert request.candidate_id == "cand-9"
    assert request.run_id
    assert request.package_key == "storm_brand"
    assert request.loop_family == "mark_cashout"
    assert request.sprite_path == "/tmp/storm-staff.png"


def test_build_hidden_lab_request_rejects_hidden_lab_packages_without_runtime_telemetry_support() -> (
    None
):
    with pytest.raises(ValidationError):
        build_hidden_lab_request(
            finalist={
                "candidate_id": "cand-unsupported",
                "package_key": "orbit_furnace",
                "loop_family": "mark_cashout",
                "behavior_contract": {
                    "seed_event": "seed_triggered",
                    "escalate_event": "escalate_triggered",
                    "cashout_event": "cashout_triggered",
                    "max_hits_to_cashout": 3,
                    "max_time_to_cashout_ms": 2500,
                },
                "manifest": {"item_name": "Orbit Furnace"},
            }
        )


def test_build_hidden_lab_request_rejects_legacy_fallback_finalist() -> None:
    with pytest.raises(ValidationError):
        build_hidden_lab_request(
            finalist={
                "candidate_id": "cand-legacy",
                "manifest": {
                    "item_name": "Legacy Storm Staff",
                    "fallback_reason": "allowed legacy fallback",
                },
                "sprite_path": "/tmp/legacy-storm-staff.png",
            }
        )


def test_build_hidden_lab_request_rejects_root_fields_that_drift_from_manifest() -> (
    None
):
    with pytest.raises(ValidationError):
        build_hidden_lab_request(
            finalist={
                "candidate_id": "cand-drift",
                "package_key": "storm_brand",
                "loop_family": "mark_cashout",
                "behavior_contract": {
                    "seed_event": "seed_triggered",
                    "escalate_event": "escalate_triggered",
                    "cashout_event": "cashout_triggered",
                    "max_hits_to_cashout": 3,
                    "max_time_to_cashout_ms": 2500,
                },
                "manifest": {
                    "item_name": "Storm Staff",
                    "mechanics": {"combat_package": "frost_shatter"},
                    "resolved_combat": {
                        "package_key": "frost_shatter",
                        "loop_family": "timed_release",
                    },
                },
                "sprite_path": "/tmp/storm-staff.png",
            }
        )


def test_forge_connector_system_does_not_use_weapon_thesis_as_execution_fallback() -> (
    None
):
    source = (
        Path(__file__).resolve().parents[2]
        / "mod"
        / "ForgeConnector"
        / "ForgeConnectorSystem.cs"
    ).read_text(encoding="utf-8")

    assert (
        'GetStr(mechanics, "combat_package", GetStr(thesis, "combat_package", string.Empty))'
        not in source
    )
    assert (
        'GetStr(thesis, "loop_family", GetStr(mechanics, "loop_family", string.Empty))'
        not in source
    )


def test_storm_brand_cashout_spawns_visible_followup_attack() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "mod"
        / "ForgeConnector"
        / "ForgeProjectileGlobal.cs"
    ).read_text(encoding="utf-8")

    assert "SpawnStormCashout" in source
    assert "Projectile.NewProjectile(" in source
    assert "ProjectileID.Starfury" in source


def test_hidden_lab_runtime_gate_waits_for_result_and_evaluates_contract() -> None:
    async def run() -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            request_file = tmp / "forge_lab_hidden_request.json"
            result_file = tmp / "forge_lab_hidden_result.json"

            async def write_result_after_request() -> None:
                while not request_file.exists():
                    await asyncio.sleep(0.001)

                request_payload = json.loads(request_file.read_text(encoding="utf-8"))
                result_payload = {
                    "candidate_id": request_payload["candidate_id"],
                    "run_id": request_payload["run_id"],
                    "package_key": request_payload["package_key"],
                    "loop_family": request_payload["loop_family"],
                    "events": [
                        {
                            "event_type": "seed_triggered",
                            "timestamp_ms": 100,
                            "run_id": request_payload["run_id"],
                        },
                        {
                            "event_type": "escalate_triggered",
                            "timestamp_ms": 450,
                            "run_id": request_payload["run_id"],
                            "stack_count": 1,
                        },
                        {
                            "event_type": "escalate_triggered",
                            "timestamp_ms": 700,
                            "run_id": request_payload["run_id"],
                            "stack_count": 2,
                        },
                        {
                            "event_type": "cashout_triggered",
                            "timestamp_ms": 900,
                            "run_id": request_payload["run_id"],
                            "stack_count": 3,
                        },
                    ],
                }
                result_file.write_text(json.dumps(result_payload), encoding="utf-8")

            writer = asyncio.create_task(write_result_after_request())
            try:
                with (
                    mock.patch.object(
                        orchestrator, "HIDDEN_LAB_REQUEST_FILE", request_file
                    ),
                    mock.patch.object(
                        orchestrator, "HIDDEN_LAB_RESULT_FILE", result_file
                    ),
                ):
                    verdict = await orchestrator.run_hidden_lab_runtime_gate(
                        finalist={
                            "candidate_id": "cand-10",
                            "package_key": "storm_brand",
                            "loop_family": "mark_cashout",
                            "manifest": {"item_name": "Storm Staff"},
                            "behavior_contract": {
                                "seed_event": "seed_triggered",
                                "escalate_event": "escalate_triggered",
                                "cashout_event": "cashout_triggered",
                                "max_hits_to_cashout": 3,
                                "max_time_to_cashout_ms": 2500,
                            },
                        },
                        timeout_s=0.1,
                        poll_interval_s=0.001,
                    )
            finally:
                await writer

            request_payload = json.loads(request_file.read_text(encoding="utf-8"))
            assert request_payload["candidate_id"] == "cand-10"
            assert request_payload["run_id"]
            assert verdict["candidate_id"] == "cand-10"
            assert verdict["passed_runtime_gate"] is True

    asyncio.run(run())


def test_hidden_lab_runtime_gate_evaluates_failure_result_without_timeout() -> None:
    async def run() -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            request_file = tmp / "forge_lab_hidden_request.json"
            result_file = tmp / "forge_lab_hidden_result.json"

            async def write_result_after_request() -> None:
                while not request_file.exists():
                    await asyncio.sleep(0.001)

                request_payload = json.loads(request_file.read_text(encoding="utf-8"))
                result_payload = {
                    "candidate_id": request_payload["candidate_id"],
                    "run_id": request_payload["run_id"],
                    "package_key": request_payload["package_key"],
                    "loop_family": request_payload["loop_family"],
                    "events": [
                        {
                            "event_type": "seed_triggered",
                            "timestamp_ms": 100,
                            "run_id": request_payload["run_id"],
                        },
                        {
                            "event_type": "escalate_triggered",
                            "timestamp_ms": 450,
                            "run_id": request_payload["run_id"],
                            "stack_count": 1,
                        },
                        {
                            "event_type": "candidate_completed",
                            "timestamp_ms": 1000,
                            "run_id": request_payload["run_id"],
                        },
                    ],
                }
                result_file.write_text(json.dumps(result_payload), encoding="utf-8")

            writer = asyncio.create_task(write_result_after_request())
            try:
                with (
                    mock.patch.object(
                        orchestrator, "HIDDEN_LAB_REQUEST_FILE", request_file
                    ),
                    mock.patch.object(
                        orchestrator, "HIDDEN_LAB_RESULT_FILE", result_file
                    ),
                ):
                    verdict = await orchestrator.run_hidden_lab_runtime_gate(
                        finalist={
                            "candidate_id": "cand-11",
                            "package_key": "storm_brand",
                            "loop_family": "mark_cashout",
                            "manifest": {"item_name": "Storm Staff"},
                            "behavior_contract": {
                                "seed_event": "seed_triggered",
                                "escalate_event": "escalate_triggered",
                                "cashout_event": "cashout_triggered",
                                "max_hits_to_cashout": 3,
                                "max_time_to_cashout_ms": 2500,
                            },
                        },
                        timeout_s=0.1,
                        poll_interval_s=0.001,
                    )
            finally:
                await writer

            assert verdict["candidate_id"] == "cand-11"
            assert verdict["passed_runtime_gate"] is False
            assert verdict["runtime_gate_reason"] == "missing cashout event"

    asyncio.run(run())


def test_behavior_contract_anchors_cashout_timing_to_latest_seed_before_cashout() -> (
    None
):
    result = load_lab_result(
        {
            "candidate_id": "cand-seed-reset",
            "run_id": "run-seed-reset",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "events": [
                {"event_type": "seed_triggered", "timestamp_ms": 100, "cast_id": 1},
                {"event_type": "seed_triggered", "timestamp_ms": 1000, "cast_id": 2},
                {
                    "event_type": "escalate_triggered",
                    "timestamp_ms": 1300,
                    "cast_id": 2,
                    "stack_count": 1,
                },
                {
                    "event_type": "escalate_triggered",
                    "timestamp_ms": 1700,
                    "cast_id": 2,
                    "stack_count": 2,
                },
                {
                    "event_type": "cashout_triggered",
                    "timestamp_ms": 2200,
                    "cast_id": 2,
                    "stack_count": 3,
                },
            ],
        }
    )

    contract = build_hidden_lab_request(
        finalist={
            "candidate_id": "cand-seed-reset",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "behavior_contract": {
                "seed_event": "seed_triggered",
                "escalate_event": "escalate_triggered",
                "cashout_event": "cashout_triggered",
                "max_hits_to_cashout": 3,
                "max_time_to_cashout_ms": 2500,
            },
            "manifest": {"item_name": "Storm Staff"},
        }
    ).behavior_contract

    from core.runtime_contracts import evaluate_behavior_contract

    verdict = evaluate_behavior_contract(contract, result)

    assert verdict.passed is True
    assert verdict.observed_hits_to_cashout == 3
    assert verdict.observed_time_to_cashout_ms == 1200


def test_behavior_contract_ignores_earlier_whiff_seed_when_cashout_has_later_cast_id() -> (
    None
):
    result = load_lab_result(
        {
            "candidate_id": "cand-whiff",
            "run_id": "run-whiff",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "events": [
                {"event_type": "seed_triggered", "timestamp_ms": 100, "cast_id": 1},
                {"event_type": "seed_triggered", "timestamp_ms": 1800, "cast_id": 2},
                {
                    "event_type": "escalate_triggered",
                    "timestamp_ms": 2050,
                    "cast_id": 2,
                    "stack_count": 1,
                },
                {
                    "event_type": "escalate_triggered",
                    "timestamp_ms": 2300,
                    "cast_id": 2,
                    "stack_count": 2,
                },
                {
                    "event_type": "cashout_triggered",
                    "timestamp_ms": 2600,
                    "cast_id": 2,
                    "stack_count": 3,
                },
            ],
        }
    )

    contract = build_hidden_lab_request(
        finalist={
            "candidate_id": "cand-whiff",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "behavior_contract": {
                "seed_event": "seed_triggered",
                "escalate_event": "escalate_triggered",
                "cashout_event": "cashout_triggered",
                "max_hits_to_cashout": 3,
                "max_time_to_cashout_ms": 2500,
            },
            "manifest": {"item_name": "Storm Staff"},
        }
    ).behavior_contract

    from core.runtime_contracts import evaluate_behavior_contract

    verdict = evaluate_behavior_contract(contract, result)

    assert verdict.passed is True
    assert verdict.observed_hits_to_cashout == 3
    assert verdict.observed_time_to_cashout_ms == 800


def test_hidden_lab_runtime_gate_ignores_stale_result_for_reused_candidate_id() -> None:
    async def run() -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            request_file = tmp / "forge_lab_hidden_request.json"
            result_file = tmp / "forge_lab_hidden_result.json"

            async def write_results_after_request() -> None:
                while not request_file.exists():
                    await asyncio.sleep(0.001)

                request_payload = json.loads(request_file.read_text(encoding="utf-8"))
                stale_payload = {
                    "candidate_id": request_payload["candidate_id"],
                    "run_id": "run-stale",
                    "package_key": request_payload["package_key"],
                    "loop_family": request_payload["loop_family"],
                    "events": [
                        {
                            "event_type": "seed_triggered",
                            "timestamp_ms": 100,
                            "run_id": "run-stale",
                        },
                        {
                            "event_type": "candidate_completed",
                            "timestamp_ms": 300,
                            "run_id": "run-stale",
                        },
                    ],
                }
                result_file.write_text(json.dumps(stale_payload), encoding="utf-8")

                await asyncio.sleep(0.02)

                fresh_payload = {
                    "candidate_id": request_payload["candidate_id"],
                    "run_id": request_payload["run_id"],
                    "package_key": request_payload["package_key"],
                    "loop_family": request_payload["loop_family"],
                    "events": [
                        {
                            "event_type": "seed_triggered",
                            "timestamp_ms": 100,
                            "run_id": request_payload["run_id"],
                        },
                        {
                            "event_type": "cashout_triggered",
                            "timestamp_ms": 200,
                            "run_id": request_payload["run_id"],
                            "stack_count": 1,
                        },
                    ],
                }
                result_file.write_text(json.dumps(fresh_payload), encoding="utf-8")

            writer = asyncio.create_task(write_results_after_request())
            try:
                with (
                    mock.patch.object(
                        orchestrator, "HIDDEN_LAB_REQUEST_FILE", request_file
                    ),
                    mock.patch.object(
                        orchestrator, "HIDDEN_LAB_RESULT_FILE", result_file
                    ),
                ):
                    verdict = await orchestrator.run_hidden_lab_runtime_gate(
                        finalist={
                            "candidate_id": "cand-12",
                            "package_key": "storm_brand",
                            "loop_family": "mark_cashout",
                            "manifest": {"item_name": "Storm Staff"},
                            "behavior_contract": {
                                "seed_event": "seed_triggered",
                                "escalate_event": "escalate_triggered",
                                "cashout_event": "cashout_triggered",
                                "max_hits_to_cashout": 3,
                                "max_time_to_cashout_ms": 2500,
                            },
                        },
                        timeout_s=0.2,
                        poll_interval_s=0.001,
                    )
            finally:
                await writer

            assert verdict["candidate_id"] == "cand-12"
            assert verdict["passed_runtime_gate"] is True

    asyncio.run(run())
