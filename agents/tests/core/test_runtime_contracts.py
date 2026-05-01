from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.runtime_contracts import (
    _manifest_runtime_identity,
    BehaviorContract,
    evaluate_behavior_contract,
    runtime_result_has_terminal_evidence,
)
from core.runtime_lab_contract import load_lab_result


def test_behavior_contract_tracks_bounded_runtime_event_expectations() -> None:
    contract = BehaviorContract.model_validate(
        {
            "seed_event": "seed_triggered",
            "escalate_event": "escalate_triggered",
            "cashout_event": "cashout_triggered",
            "max_hits_to_cashout": 3,
            "max_time_to_cashout_ms": 2500,
        }
    )

    assert contract.max_hits_to_cashout == 3


def test_behavior_contract_rejects_arbitrary_event_names() -> None:
    with pytest.raises(ValidationError):
        BehaviorContract.model_validate(
            {
                "seed_event": "mark_applied",
                "escalate_event": "mark_incremented",
                "cashout_event": "starfall_triggered",
                "max_hits_to_cashout": 3,
                "max_time_to_cashout_ms": 2500,
            }
        )


def test_behavior_contract_passes_when_runtime_evidence_meets_gate() -> None:
    contract = BehaviorContract.model_validate(
        {
            "seed_event": "seed_triggered",
            "escalate_event": "escalate_triggered",
            "cashout_event": "cashout_triggered",
            "max_hits_to_cashout": 3,
            "max_time_to_cashout_ms": 2500,
        }
    )
    result = load_lab_result(
        {
            "candidate_id": "cand-1",
            "run_id": "run-101",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "events": [
                {"event_type": "seed_triggered", "timestamp_ms": 100},
                {
                    "event_type": "escalate_triggered",
                    "timestamp_ms": 450,
                    "stack_count": 1,
                },
                {
                    "event_type": "escalate_triggered",
                    "timestamp_ms": 700,
                    "stack_count": 2,
                },
                {
                    "event_type": "cashout_triggered",
                    "timestamp_ms": 900,
                    "stack_count": 3,
                },
            ],
        }
    )

    evaluation = evaluate_behavior_contract(contract, result)

    assert evaluation.passed is True
    assert evaluation.observed_hits_to_cashout == 3
    assert evaluation.observed_time_to_cashout_ms == 800


def test_behavior_contract_fails_when_cashout_never_arrives() -> None:
    contract = BehaviorContract.model_validate(
        {
            "seed_event": "seed_triggered",
            "escalate_event": "escalate_triggered",
            "cashout_event": "cashout_triggered",
            "max_hits_to_cashout": 3,
            "max_time_to_cashout_ms": 2500,
        }
    )
    result = load_lab_result(
        {
            "candidate_id": "cand-2",
            "run_id": "run-102",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "events": [
                {"event_type": "seed_triggered", "timestamp_ms": 100},
                {
                    "event_type": "escalate_triggered",
                    "timestamp_ms": 450,
                    "stack_count": 1,
                },
                {"event_type": "candidate_completed", "timestamp_ms": 1000},
            ],
        }
    )

    evaluation = evaluate_behavior_contract(contract, result)

    assert evaluation.passed is False
    assert evaluation.fail_reason == "missing cashout event"


def test_runtime_result_has_terminal_evidence_for_seed_only_completion() -> None:
    result = load_lab_result(
        {
            "candidate_id": "cand-3",
            "run_id": "run-103",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "events": [
                {"event_type": "seed_triggered", "timestamp_ms": 100},
                {"event_type": "candidate_completed", "timestamp_ms": 1200},
            ],
        }
    )

    assert runtime_result_has_terminal_evidence(result) is True


def test_runtime_result_has_no_terminal_evidence_for_partial_loop() -> None:
    result = load_lab_result(
        {
            "candidate_id": "cand-4",
            "run_id": "run-104",
            "package_key": "storm_brand",
            "loop_family": "mark_cashout",
            "events": [
                {"event_type": "seed_triggered", "timestamp_ms": 100},
                {
                    "event_type": "escalate_triggered",
                    "timestamp_ms": 450,
                    "stack_count": 1,
                },
            ],
        }
    )

    assert runtime_result_has_terminal_evidence(result) is False


def test_manifest_runtime_identity_derives_loop_family_from_package_path() -> None:
    assert _manifest_runtime_identity(
        {
            "mechanics": {"combat_package": "storm_brand"},
            "resolved_combat": {"package_key": "storm_brand"},
        }
    ) == {"package_key": "storm_brand", "loop_family": "mark_cashout"}


def test_manifest_runtime_identity_does_not_advertise_unsupported_hidden_lab_packages() -> (
    None
):
    assert _manifest_runtime_identity(
        {
            "mechanics": {"combat_package": "orbit_furnace"},
            "resolved_combat": {"package_key": "orbit_furnace"},
        }
    ) == {"package_key": "orbit_furnace"}
