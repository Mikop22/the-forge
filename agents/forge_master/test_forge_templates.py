"""Tests for forge_master template routing and validation."""

from __future__ import annotations

from pydantic import ValidationError

from forge_master.templates import (
    BOOMERANG_TEMPLATE,
    CHAIN_LIGHTNING_TEMPLATE,
    CHANNELED_TEMPLATE,
    CUSTOM_PROJECTILE_TEMPLATE,
    EXPLOSION_TEMPLATE,
    FROST_SHATTER_TEMPLATE,
    HOMING_TEMPLATE,
    ORBIT_FURNACE_TEMPLATE,
    ORBIT_TEMPLATE,
    PIERCE_TEMPLATE,
    SKY_STRIKE_TEMPLATE,
    STAFF_TEMPLATE,
    STORM_BRAND_TEMPLATE,
    SWORD_TEMPLATE,
    get_reference_snippet,
    validate_cs,
)
from forge_master.models import ForgeManifest

import pytest


class TestGetReferenceSnippet:
    def test_combat_package_wins_over_legacy_style_routing(self) -> None:
        assert (
            get_reference_snippet(
                "Staff",
                True,
                "sky_strike",
                combat_package="storm_brand",
            )
            == STORM_BRAND_TEMPLATE
        )

    def test_orbit_furnace_package_wins_over_matching_legacy_style(self) -> None:
        assert (
            get_reference_snippet(
                "Staff",
                False,
                "orbit",
                combat_package="orbit_furnace",
            )
            == ORBIT_FURNACE_TEMPLATE
        )

    def test_frost_shatter_package_routes_to_package_template(self) -> None:
        assert (
            get_reference_snippet(
                "Staff",
                False,
                "direct",
                combat_package="frost_shatter",
            )
            == FROST_SHATTER_TEMPLATE
        )

    def test_staff_direct_returns_staff_template(self) -> None:
        assert get_reference_snippet("Staff", False, "direct") == STAFF_TEMPLATE

    def test_staff_default_returns_staff_template(self) -> None:
        assert get_reference_snippet("Staff") == STAFF_TEMPLATE

    def test_staff_sky_strike_returns_sky_template(self) -> None:
        assert (
            get_reference_snippet("Staff", False, "sky_strike") == SKY_STRIKE_TEMPLATE
        )

    def test_sword_sky_strike_returns_sky_template(self) -> None:
        assert (
            get_reference_snippet("Sword", False, "sky_strike") == SKY_STRIKE_TEMPLATE
        )

    def test_custom_projectile_does_not_override_non_direct(self) -> None:
        """shot_style takes priority over custom_projectile for non-direct styles."""
        assert get_reference_snippet("Staff", True, "sky_strike") == SKY_STRIKE_TEMPLATE

    def test_custom_projectile_channeled_returns_channeled(self) -> None:
        assert get_reference_snippet("Staff", True, "channeled") == CHANNELED_TEMPLATE

    def test_custom_projectile_direct_returns_custom_template(self) -> None:
        assert (
            get_reference_snippet("Staff", True, "direct") == CUSTOM_PROJECTILE_TEMPLATE
        )

    def test_homing_returns_homing_template(self) -> None:
        assert get_reference_snippet("Staff", False, "homing") == HOMING_TEMPLATE

    def test_boomerang_returns_boomerang_template(self) -> None:
        assert get_reference_snippet("Sword", False, "boomerang") == BOOMERANG_TEMPLATE

    def test_orbit_returns_orbit_template(self) -> None:
        assert get_reference_snippet("Staff", False, "orbit") == ORBIT_TEMPLATE

    def test_explosion_returns_explosion_template(self) -> None:
        assert get_reference_snippet("Gun", False, "explosion") == EXPLOSION_TEMPLATE

    def test_pierce_returns_pierce_template(self) -> None:
        assert get_reference_snippet("Staff", False, "pierce") == PIERCE_TEMPLATE

    def test_chain_lightning_returns_chain_template(self) -> None:
        assert (
            get_reference_snippet("Staff", False, "chain_lightning")
            == CHAIN_LIGHTNING_TEMPLATE
        )

    def test_channeled_returns_channeled_template(self) -> None:
        assert get_reference_snippet("Staff", False, "channeled") == CHANNELED_TEMPLATE

    def test_unknown_subtype_falls_back_to_sword(self) -> None:
        assert get_reference_snippet("Scythe") == SWORD_TEMPLATE


_ALL_TEMPLATES = {
    "STORM_BRAND_TEMPLATE": STORM_BRAND_TEMPLATE,
    "ORBIT_FURNACE_TEMPLATE": ORBIT_FURNACE_TEMPLATE,
    "FROST_SHATTER_TEMPLATE": FROST_SHATTER_TEMPLATE,
    "SKY_STRIKE_TEMPLATE": SKY_STRIKE_TEMPLATE,
    "HOMING_TEMPLATE": HOMING_TEMPLATE,
    "BOOMERANG_TEMPLATE": BOOMERANG_TEMPLATE,
    "ORBIT_TEMPLATE": ORBIT_TEMPLATE,
    "EXPLOSION_TEMPLATE": EXPLOSION_TEMPLATE,
    "PIERCE_TEMPLATE": PIERCE_TEMPLATE,
    "CHAIN_LIGHTNING_TEMPLATE": CHAIN_LIGHTNING_TEMPLATE,
    "CHANNELED_TEMPLATE": CHANNELED_TEMPLATE,
}


@pytest.mark.parametrize("name,template", _ALL_TEMPLATES.items())
def test_template_passes_validation(name: str, template: str) -> None:
    violations = validate_cs(template)
    assert violations == [], f"{name} has violations: {violations}"


@pytest.mark.parametrize(
    "name,template",
    [
        ("STORM_BRAND_TEMPLATE", STORM_BRAND_TEMPLATE),
        ("ORBIT_FURNACE_TEMPLATE", ORBIT_FURNACE_TEMPLATE),
        ("FROST_SHATTER_TEMPLATE", FROST_SHATTER_TEMPLATE),
    ],
)
def test_package_staff_templates_set_staff_animation_contract(
    name: str, template: str
) -> None:
    assert "public override void SetStaticDefaults()" in template, name
    assert "Item.staff[Type] = true;" in template, name


def test_package_templates_do_not_use_invalid_alias_projectile_constants() -> None:
    assert "ProjectileID.Fireball" not in ORBIT_FURNACE_TEMPLATE
    assert "ProjectileID.IceBolt" not in FROST_SHATTER_TEMPLATE


def test_storm_brand_template_uses_custom_projectile_reference_pattern() -> None:
    assert " : ModProjectile" in STORM_BRAND_TEMPLATE
    assert "ModContent.ProjectileType<" in STORM_BRAND_TEMPLATE
    assert "ProjectileID.ThunderStaffShot" not in STORM_BRAND_TEMPLATE


class TestForgeManifestShotStyle:
    def _manifest(self, **mech_overrides) -> ForgeManifest:
        mechanics = {
            "crafting_material": "ItemID.Wood",
            "crafting_cost": 5,
            "crafting_tile": "TileID.WorkBenches",
            **mech_overrides,
        }
        return ForgeManifest(
            item_name="TestItem",
            display_name="Test Item",
            stats={
                "damage": 10,
                "knockback": 4.0,
                "use_time": 20,
                "rarity": "ItemRarityID.Green",
            },
            mechanics=mechanics,
        )

    def test_default_shot_style(self) -> None:
        m = self._manifest()
        assert m.mechanics.shot_style == "direct"

    def test_sky_strike_shot_style(self) -> None:
        m = self._manifest(shot_style="sky_strike")
        assert m.mechanics.shot_style == "sky_strike"

    def test_missing_shot_style_defaults(self) -> None:
        m = self._manifest()
        assert m.mechanics.shot_style == "direct"

    def test_manifest_accepts_package_fields_and_resolved_combat(self) -> None:
        manifest = ForgeManifest(
            item_name="StormBrand",
            display_name="Storm Brand",
            presentation={"fx_profile": "celestial_shock"},
            resolved_combat={
                "package_key": "storm_brand",
                "delivery_module": "direct_seed_bolt",
                "combo_module": "npc_marks_3",
                "finisher_module": "starfall_burst",
                "presentation_module": "celestial_shock",
                "player_state_kind": "none",
                "npc_state_kind": "mark_counter",
                "legacy_projection": {
                    "shot_style": "direct",
                    "custom_projectile": True,
                    "shoot_projectile": None,
                    "projectile_visuals_required": True,
                },
            },
            stats={
                "damage": 10,
                "knockback": 4.0,
                "use_time": 20,
                "rarity": "ItemRarityID.Green",
            },
            mechanics={
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "crafting_material": "ItemID.Wood",
                "crafting_cost": 5,
                "crafting_tile": "TileID.WorkBenches",
            },
        )

        assert manifest.presentation is not None
        assert manifest.presentation.fx_profile == "celestial_shock"
        assert manifest.resolved_combat is not None
        assert manifest.mechanics.combat_package == "storm_brand"
        assert manifest.mechanics.delivery_style == "direct"
        assert manifest.mechanics.payoff_rate == "fast"
        assert manifest.resolved_combat.package_key == "storm_brand"

    def test_manifest_rejects_bare_combat_package_without_resolved_combat(self) -> None:
        with pytest.raises(ValidationError, match="resolved_combat"):
            ForgeManifest(
                item_name="StormBrand",
                display_name="Storm Brand",
                stats={
                    "damage": 10,
                    "knockback": 4.0,
                    "use_time": 20,
                    "rarity": "ItemRarityID.Green",
                },
                mechanics={
                    "combat_package": "storm_brand",
                    "crafting_material": "ItemID.Wood",
                    "crafting_cost": 5,
                    "crafting_tile": "TileID.WorkBenches",
                },
            )
