"""Hard-bounded combat package resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CombatPackageLiteral = Literal["storm_brand", "orbit_furnace", "frost_shatter"]
DeliveryStyleLiteral = Literal["direct"]
PayoffRateLiteral = Literal["fast", "medium"]
FxProfileLiteral = Literal["celestial_shock", "ember_forge", "glacial_burst"]


@dataclass(frozen=True)
class LegacyProjection:
    shot_style: str
    custom_projectile: bool
    shoot_projectile: str | None
    projectile_visuals_required: bool


@dataclass(frozen=True)
class ResolvedCombat:
    package_key: CombatPackageLiteral
    delivery_module: str
    combo_module: str
    finisher_module: str
    presentation_module: str
    player_state_kind: str
    npc_state_kind: str
    legacy_projection: LegacyProjection


_SUPPORTED_CONTENT = ("Weapon", "Staff")
_SUPPORTED_DELIVERY_STYLES = ("direct",)
_SUPPORTED_PAYOFF_RATES = ("fast", "medium")

_PACKAGE_REGISTRY: dict[
    CombatPackageLiteral,
    tuple[str, str, str, str, str, LegacyProjection],
] = {
    "storm_brand": (
        "direct_seed_bolt",
        "npc_marks_3",
        "starfall_burst",
        "none",
        "mark_counter",
        LegacyProjection(
            shot_style="direct",
            custom_projectile=True,
            shoot_projectile=None,
            projectile_visuals_required=True,
        ),
    ),
    "orbit_furnace": (
        "direct_seed_bolt",
        "player_satellites_4",
        "ember_divebomb",
        "satellite_orbit",
        "none",
        LegacyProjection(
            shot_style="direct",
            custom_projectile=False,
            shoot_projectile=None,
            projectile_visuals_required=False,
        ),
    ),
    "frost_shatter": (
        "direct_seed_bolt",
        "npc_freeze_threshold",
        "crystal_fan_burst",
        "none",
        "freeze_counter",
        LegacyProjection(
            shot_style="direct",
            custom_projectile=False,
            shoot_projectile=None,
            projectile_visuals_required=False,
        ),
    ),
}


def _raise_unsupported(axis: str, value: str, package_key: str) -> None:
    raise ValueError(f"Unsupported {axis} for combat package {package_key}: {value}")


def resolve_combat_package(
    *,
    package_key: CombatPackageLiteral,
    content_type: str,
    sub_type: str,
    delivery_style: DeliveryStyleLiteral,
    payoff_rate: PayoffRateLiteral,
    fx_profile: FxProfileLiteral,
) -> ResolvedCombat:
    if package_key not in _PACKAGE_REGISTRY:
        _raise_unsupported("package_key", package_key, package_key)

    if delivery_style not in _SUPPORTED_DELIVERY_STYLES:
        _raise_unsupported("delivery_style", delivery_style, package_key)

    if payoff_rate not in _SUPPORTED_PAYOFF_RATES:
        _raise_unsupported("payoff_rate", payoff_rate, package_key)

    if (content_type, sub_type) != _SUPPORTED_CONTENT:
        _raise_unsupported(
            "content_type/sub_type", f"{content_type}/{sub_type}", package_key
        )

    (
        delivery_module,
        combo_module,
        finisher_module,
        player_state_kind,
        npc_state_kind,
        legacy_projection,
    ) = _PACKAGE_REGISTRY[package_key]
    return ResolvedCombat(
        package_key=package_key,
        delivery_module=delivery_module,
        combo_module=combo_module,
        finisher_module=finisher_module,
        presentation_module=fx_profile,
        player_state_kind=player_state_kind,
        npc_state_kind=npc_state_kind,
        legacy_projection=legacy_projection,
    )
