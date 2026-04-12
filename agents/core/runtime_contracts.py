"""Behavior contracts and hidden lab runtime gate helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.combat_packages import CombatPackageLiteral
from core.runtime_capabilities import LoopFamilyLiteral
from core.runtime_lab_contract import RuntimeLabResult, load_lab_result

RuntimeSeedEventLiteral = Literal["seed_triggered"]
RuntimeEscalateEventLiteral = Literal["escalate_triggered"]
RuntimeCashoutEventLiteral = Literal["cashout_triggered"]
_SUPPORTED_HIDDEN_LAB_RUNTIME: dict[CombatPackageLiteral, LoopFamilyLiteral] = {
    "storm_brand": "mark_cashout",
}


class BehaviorContract(BaseModel):
    """Small bounded contract for the first runtime gate."""

    model_config = ConfigDict(frozen=True)

    seed_event: RuntimeSeedEventLiteral
    escalate_event: RuntimeEscalateEventLiteral
    cashout_event: RuntimeCashoutEventLiteral
    max_hits_to_cashout: int = Field(..., ge=1)
    max_time_to_cashout_ms: int = Field(..., ge=0)


class HiddenLabRequest(BaseModel):
    """File-based request payload for one hidden lab runtime check."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["inject"] = "inject"
    candidate_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    package_key: CombatPackageLiteral
    loop_family: LoopFamilyLiteral
    manifest: dict[str, Any] = Field(default_factory=dict)
    sprite_path: str = ""
    projectile_sprite_path: str = ""
    behavior_contract: BehaviorContract

    @model_validator(mode="after")
    def validate_manifest_runtime_identity(self) -> "HiddenLabRequest":
        manifest_runtime = _manifest_runtime_identity(self.manifest)
        manifest_package_key = manifest_runtime.get("package_key")
        if manifest_package_key and manifest_package_key != self.package_key:
            raise ValueError("manifest package_key does not match runtime payload")

        manifest_loop_family = manifest_runtime.get("loop_family")
        if manifest_loop_family and manifest_loop_family != self.loop_family:
            raise ValueError("manifest loop_family does not match runtime payload")

        supported_loop_family = _SUPPORTED_HIDDEN_LAB_RUNTIME.get(self.package_key)
        if supported_loop_family != self.loop_family:
            raise ValueError(
                "hidden lab runtime telemetry only supports storm_brand/mark_cashout"
            )

        return self


class HiddenLabResult(RuntimeLabResult):
    """File-based runtime evidence payload for one hidden lab request."""


class RuntimeGateEvaluation(BaseModel):
    """Pass/fail outcome for the first runtime gate."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    fail_reason: str | None = None
    observed_hits_to_cashout: int | None = None
    observed_time_to_cashout_ms: int | None = None


def load_hidden_lab_request(payload: dict[str, Any]) -> HiddenLabRequest:
    return HiddenLabRequest.model_validate(payload)


def _manifest_runtime_identity(manifest: Mapping[str, Any]) -> dict[str, str]:
    mechanics = manifest.get("mechanics")
    resolved_combat = manifest.get("resolved_combat")
    mechanics_data = mechanics if isinstance(mechanics, Mapping) else {}
    resolved_combat_data = (
        resolved_combat if isinstance(resolved_combat, Mapping) else {}
    )
    package_key = str(
        resolved_combat_data.get("package_key")
        or mechanics_data.get("combat_package")
        or ""
    ).strip()
    loop_family = str(
        resolved_combat_data.get("loop_family")
        or _SUPPORTED_HIDDEN_LAB_RUNTIME.get(package_key)  # type: ignore[arg-type]
        or ""
    ).strip()
    result: dict[str, str] = {}
    if package_key:
        result["package_key"] = package_key
    if loop_family:
        result["loop_family"] = loop_family
    return result


def build_hidden_lab_request(
    *,
    finalist: Mapping[str, Any],
    candidate_id: str | None = None,
    sprite_path: str | None = None,
    projectile_sprite_path: str | None = None,
) -> HiddenLabRequest:
    runtime_manifest = finalist.get("manifest")
    payload = {
        "candidate_id": str(candidate_id or finalist.get("candidate_id") or ""),
        "run_id": str(finalist.get("run_id") or uuid4().hex),
        "package_key": finalist.get("package_key"),
        "loop_family": finalist.get("loop_family"),
        "manifest": (
            runtime_manifest if isinstance(runtime_manifest, dict) else dict(finalist)
        ),
        "sprite_path": str(sprite_path or finalist.get("sprite_path") or ""),
        "projectile_sprite_path": str(
            projectile_sprite_path
            if projectile_sprite_path is not None
            else finalist.get("projectile_sprite_path") or ""
        ),
        "behavior_contract": finalist.get("behavior_contract"),
    }
    return HiddenLabRequest.model_validate(payload)


def load_hidden_lab_result(payload: dict[str, Any]) -> HiddenLabResult:
    return HiddenLabResult.model_validate(load_lab_result(payload).model_dump())


def runtime_result_has_terminal_evidence(result: RuntimeLabResult) -> bool:
    return any(
        event.event_type in {"candidate_completed", "cashout_triggered"}
        for event in result.events
    )


def evaluate_behavior_contract(
    contract: BehaviorContract, result: RuntimeLabResult
) -> RuntimeGateEvaluation:
    cashout_index = next(
        (
            index
            for index, event in enumerate(result.events)
            if event.event_type == contract.cashout_event
        ),
        None,
    )
    if cashout_index is None:
        return RuntimeGateEvaluation(passed=False, fail_reason="missing cashout event")

    cashout_event = result.events[cashout_index]
    cashout_cast_id = cashout_event.cast_id
    seed_index = next(
        (
            index
            for index in range(cashout_index - 1, -1, -1)
            if result.events[index].event_type == contract.seed_event
            and (
                cashout_cast_id is None
                or result.events[index].cast_id == cashout_cast_id
            )
        ),
        None,
    )
    if seed_index is None:
        return RuntimeGateEvaluation(passed=False, fail_reason="missing seed event")

    seed_event = result.events[seed_index]
    observed_hits_to_cashout = cashout_event.stack_count or (
        1
        + sum(
            1
            for event in result.events[seed_index + 1 : cashout_index]
            if event.event_type == contract.escalate_event
            and (cashout_cast_id is None or event.cast_id == cashout_cast_id)
        )
    )
    observed_time_to_cashout_ms = cashout_event.timestamp_ms - seed_event.timestamp_ms

    if observed_hits_to_cashout > contract.max_hits_to_cashout:
        return RuntimeGateEvaluation(
            passed=False,
            fail_reason="cashout exceeded hit budget",
            observed_hits_to_cashout=observed_hits_to_cashout,
            observed_time_to_cashout_ms=observed_time_to_cashout_ms,
        )

    if observed_time_to_cashout_ms > contract.max_time_to_cashout_ms:
        return RuntimeGateEvaluation(
            passed=False,
            fail_reason="cashout exceeded time budget",
            observed_hits_to_cashout=observed_hits_to_cashout,
            observed_time_to_cashout_ms=observed_time_to_cashout_ms,
        )

    return RuntimeGateEvaluation(
        passed=True,
        observed_hits_to_cashout=observed_hits_to_cashout,
        observed_time_to_cashout_ms=observed_time_to_cashout_ms,
    )
