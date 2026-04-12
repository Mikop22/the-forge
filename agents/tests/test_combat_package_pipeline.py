import json
from pathlib import Path

import pytest

from architect.models import ItemManifest
from forge_master import forge_master as forge_master_module
from forge_master.models import ForgeManifest
from forge_master.templates import (
    FROST_SHATTER_TEMPLATE,
    ORBIT_FURNACE_TEMPLATE,
    SKY_STRIKE_TEMPLATE,
    STORM_BRAND_TEMPLATE,
    get_reference_snippet,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "combat_package_prompts.json"


def _load_fixture_data() -> dict:
    assert FIXTURE_PATH.exists(), f"Missing combat package fixture: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_package_manifest(case: dict) -> dict:
    return {
        "item_name": case["item_name"],
        "display_name": case["display_name"],
        "tooltip": case["tooltip"],
        "content_type": "Weapon",
        "type": "Weapon",
        "sub_type": "Staff",
        "stats": {
            "damage": 34,
            "knockback": 5.5,
            "crit_chance": 4,
            "use_time": 22,
            "auto_reuse": True,
            "rarity": "ItemRarityID.Orange",
        },
        "visuals": {"description": case["visual_description"]},
        "presentation": {"fx_profile": case["fx_profile"]},
        "mechanics": {
            "combat_package": case["expected_package_key"],
            "delivery_style": "direct",
            "payoff_rate": case["payoff_rate"],
            "crafting_material": "ItemID.FallenStar",
            "crafting_cost": 12,
            "crafting_tile": "TileID.Anvils",
        },
    }


def _build_legacy_manifest(case: dict) -> dict:
    return {
        "item_name": case["item_name"],
        "display_name": case["display_name"],
        "tooltip": case["tooltip"],
        "content_type": "Weapon",
        "type": "Weapon",
        "sub_type": "Staff",
        "stats": {
            "damage": 28,
            "knockback": 4.5,
            "crit_chance": 4,
            "use_time": 24,
            "auto_reuse": True,
            "rarity": "ItemRarityID.Orange",
        },
        "visuals": {"description": case["visual_description"]},
        "mechanics": {
            "shot_style": case["shot_style"],
            "custom_projectile": case["custom_projectile"],
            "crafting_material": "ItemID.FallenStar",
            "crafting_cost": 10,
            "crafting_tile": "TileID.Anvils",
        },
    }


def _package_cases() -> list[tuple[str, dict, str]]:
    data = _load_fixture_data()["phase1_packages"]
    expected_templates = {
        "storm_brand": STORM_BRAND_TEMPLATE,
        "orbit_furnace": ORBIT_FURNACE_TEMPLATE,
        "frost_shatter": FROST_SHATTER_TEMPLATE,
    }
    return [
        (package_key, case, expected_templates[package_key])
        for package_key, case in data.items()
    ]


_PACKAGE_CASES = _package_cases()


@pytest.mark.parametrize(
    ("package_key", "case", "expected_template"),
    _PACKAGE_CASES,
    ids=[case["prompt"] for _, case, _ in _PACKAGE_CASES],
)
def test_package_manifest_survives_validation_and_routes_explicit_template(
    package_key: str, case: dict, expected_template: str
) -> None:
    assert package_key == case["expected_package_key"], case["prompt"]

    architect_manifest = ItemManifest.model_validate(_build_package_manifest(case))
    forge_manifest = ForgeManifest.model_validate(
        architect_manifest.model_dump(mode="json")
    )

    assert architect_manifest.resolved_combat is not None
    assert (
        architect_manifest.resolved_combat.package_key == case["expected_package_key"]
    )
    assert forge_manifest.resolved_combat is not None
    assert forge_manifest.resolved_combat.package_key == case["expected_package_key"]
    if case["expects_projectile_visuals"]:
        assert architect_manifest.projectile_visuals is not None
        assert (
            architect_manifest.projectile_visuals.description
            == case["visual_description"]
        )
    else:
        assert architect_manifest.projectile_visuals is None

    snippet = get_reference_snippet(
        forge_manifest.sub_type,
        forge_manifest.mechanics.custom_projectile,
        shot_style=forge_manifest.mechanics.shot_style,
        combat_package=forge_master_module._reference_combat_package_key(
            forge_manifest
        ),
    )

    assert snippet == expected_template, case["prompt"]


def test_forge_master_prefers_resolved_combat_package_key_when_manifest_drifts() -> (
    None
):
    case = _load_fixture_data()["phase1_packages"]["storm_brand"]
    manifest_data = _build_package_manifest(case)
    manifest_data["mechanics"]["combat_package"] = "frost_shatter"

    forge_manifest = ForgeManifest.model_validate(
        {
            **manifest_data,
            "resolved_combat": {
                "package_key": case["expected_package_key"],
                "delivery_module": "direct_seed_bolt",
                "combo_module": "npc_marks_3",
                "finisher_module": "starfall_burst",
                "presentation_module": case["fx_profile"],
                "player_state_kind": "none",
                "npc_state_kind": "mark_counter",
                "legacy_projection": {
                    "shot_style": "direct",
                    "custom_projectile": True,
                    "shoot_projectile": None,
                    "projectile_visuals_required": True,
                },
            },
        }
    )

    assert forge_manifest.mechanics.combat_package == "frost_shatter", case["prompt"]
    assert forge_manifest.resolved_combat is not None
    assert forge_manifest.resolved_combat.package_key == "storm_brand", case["prompt"]

    snippet = get_reference_snippet(
        forge_manifest.sub_type,
        forge_manifest.mechanics.custom_projectile,
        shot_style=forge_manifest.mechanics.shot_style,
        combat_package=forge_master_module._reference_combat_package_key(
            forge_manifest
        ),
    )

    assert snippet == STORM_BRAND_TEMPLATE, case["prompt"]


def test_legacy_shot_style_manifest_still_routes_without_combat_package() -> None:
    case = _load_fixture_data()["legacy_shot_style"]

    architect_manifest = ItemManifest.model_validate(_build_legacy_manifest(case))
    forge_manifest = ForgeManifest.model_validate(
        architect_manifest.model_dump(mode="json")
    )

    assert architect_manifest.resolved_combat is None
    assert forge_manifest.resolved_combat is None
    assert forge_manifest.mechanics.combat_package is None

    snippet = get_reference_snippet(
        forge_manifest.sub_type,
        forge_manifest.mechanics.custom_projectile,
        shot_style=forge_manifest.mechanics.shot_style,
        combat_package=forge_master_module._reference_combat_package_key(
            forge_manifest
        ),
    )

    assert snippet == SKY_STRIKE_TEMPLATE, case["prompt"]


def test_legacy_shot_style_manifest_preserves_auditable_fallback_reason() -> None:
    case = _load_fixture_data()["legacy_shot_style"]
    manifest_data = _build_legacy_manifest(case)
    manifest_data["fallback_reason"] = (
        "allowed legacy fallback: runtime surface Weapon/Sword does not support mark_cashout"
    )

    architect_manifest = ItemManifest.model_validate(manifest_data)
    forge_manifest = ForgeManifest.model_validate(
        architect_manifest.model_dump(mode="json")
    )

    assert architect_manifest.fallback_reason == manifest_data["fallback_reason"]
    assert forge_manifest.fallback_reason == manifest_data["fallback_reason"]
    assert forge_manifest.resolved_combat is None

    snippet = get_reference_snippet(
        forge_manifest.sub_type,
        forge_manifest.mechanics.custom_projectile,
        shot_style=forge_manifest.mechanics.shot_style,
        combat_package=forge_master_module._reference_combat_package_key(
            forge_manifest
        ),
    )

    assert snippet == SKY_STRIKE_TEMPLATE, case["prompt"]
