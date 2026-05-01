"""Tests for agents/core/combat_packages.py."""

from __future__ import annotations

import pytest

from core.combat_packages import LegacyProjection, resolve_combat_package


def test_storm_brand_resolves_expected_modules_and_legacy_projection() -> None:
    resolved = resolve_combat_package(
        package_key="storm_brand",
        content_type="Weapon",
        sub_type="Staff",
        delivery_style="direct",
        payoff_rate="fast",
        fx_profile="celestial_shock",
    )

    assert resolved.package_key == "storm_brand"
    assert resolved.delivery_module == "direct_seed_bolt"
    assert resolved.combo_module == "npc_marks_3"
    assert resolved.finisher_module == "starfall_burst"
    assert resolved.presentation_module == "celestial_shock"
    assert resolved.player_state_kind == "none"
    assert resolved.npc_state_kind == "mark_counter"
    assert resolved.legacy_projection == LegacyProjection(
        shot_style="direct",
        custom_projectile=True,
        shoot_projectile=None,
        projectile_visuals_required=True,
    )


def test_invalid_package_subtype_combination_raises_value_error() -> None:
    with pytest.raises(ValueError, match="storm_brand"):
        resolve_combat_package(
            package_key="storm_brand",
            content_type="Weapon",
            sub_type="Sword",
            delivery_style="direct",
            payoff_rate="fast",
            fx_profile="celestial_shock",
        )


@pytest.mark.parametrize(
    (
        "package_key",
        "payoff_rate",
        "fx_profile",
        "combo_module",
        "finisher_module",
        "player_state_kind",
        "npc_state_kind",
    ),
    [
        (
            "orbit_furnace",
            "medium",
            "ember_forge",
            "player_satellites_4",
            "ember_divebomb",
            "satellite_orbit",
            "none",
        ),
        (
            "frost_shatter",
            "fast",
            "glacial_burst",
            "npc_freeze_threshold",
            "crystal_fan_burst",
            "none",
            "freeze_counter",
        ),
    ],
)
def test_other_registered_packages_resolve_expected_modules(
    package_key: str,
    payoff_rate: str,
    fx_profile: str,
    combo_module: str,
    finisher_module: str,
    player_state_kind: str,
    npc_state_kind: str,
) -> None:
    resolved = resolve_combat_package(
        package_key=package_key,
        content_type="Weapon",
        sub_type="Staff",
        delivery_style="direct",
        payoff_rate=payoff_rate,
        fx_profile=fx_profile,
    )

    assert resolved.package_key == package_key
    assert resolved.delivery_module == "direct_seed_bolt"
    assert resolved.combo_module == combo_module
    assert resolved.finisher_module == finisher_module
    assert resolved.presentation_module == fx_profile
    assert resolved.player_state_kind == player_state_kind
    assert resolved.npc_state_kind == npc_state_kind
    assert resolved.legacy_projection == LegacyProjection(
        shot_style="direct",
        custom_projectile=False,
        shoot_projectile=None,
        projectile_visuals_required=False,
    )


@pytest.mark.parametrize(
    ("package_key", "delivery_style", "payoff_rate", "match"),
    [
        ("void_package", "direct", "fast", "void_package"),
        ("storm_brand", "arc", "fast", "delivery_style"),
        ("storm_brand", "direct", "slow", "payoff_rate"),
    ],
)
def test_unsupported_inputs_raise_value_error(
    package_key: str,
    delivery_style: str,
    payoff_rate: str,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        resolve_combat_package(
            package_key=package_key,
            content_type="Weapon",
            sub_type="Staff",
            delivery_style=delivery_style,
            payoff_rate=payoff_rate,
            fx_profile="celestial_shock",
        )
