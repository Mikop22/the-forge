import unittest
from typing import get_args

import pytest
from pydantic import ValidationError

from architect import weapon_prompt
from architect.models import (
    AMMO_ID_CHOICES,
    AMMO_ID_TUPLE,
    AmmoIDLiteral,
    BUFF_ID_CHOICES,
    BUFF_ID_TUPLE,
    BuffIDLiteral,
    ItemManifest,
    LLMMechanics,
    Mechanics,
    SHOT_STYLE_CHOICES,
    VALID_AMMO_IDS,
    VALID_BUFF_IDS,
    _normalize_buff_id,
)
from forge_master.models import ManifestMechanics


def _base_manifest(**overrides):
    data = {
        "item_name": "TestItem",
        "display_name": "Test Item",
        "tooltip": "A test item.",
        "content_type": "Weapon",
        "type": "Weapon",
        "sub_type": "Sword",
        "stats": {
            "damage": 20,
            "knockback": 4.0,
            "crit_chance": 4,
            "use_time": 20,
            "auto_reuse": True,
            "rarity": "ItemRarityID.Green",
        },
        "visuals": {},
        "mechanics": {
            "shot_style": "direct",
            "custom_projectile": False,
            "crafting_material": "ItemID.Wood",
            "crafting_cost": 5,
            "crafting_tile": "TileID.WorkBenches",
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    return data


class IdRegistryInvariantTests(unittest.TestCase):
    def test_buff_ids_single_source(self) -> None:
        self.assertEqual(set(BUFF_ID_CHOICES), set(VALID_BUFF_IDS))
        self.assertEqual(len(BUFF_ID_CHOICES), len(VALID_BUFF_IDS))

    def test_ammo_ids_single_source(self) -> None:
        self.assertEqual(set(AMMO_ID_CHOICES), set(VALID_AMMO_IDS))
        self.assertEqual(len(AMMO_ID_CHOICES), len(VALID_AMMO_IDS))

    def test_buff_literal_matches_tuple(self) -> None:
        self.assertEqual(set(get_args(BuffIDLiteral)), set(BUFF_ID_TUPLE))

    def test_ammo_literal_matches_tuple(self) -> None:
        self.assertEqual(set(get_args(AmmoIDLiteral)), set(AMMO_ID_TUPLE))

    def test_shot_style_literal_matches_across_models(self) -> None:
        """shot_style Literal in forge_master must match architect's SHOT_STYLE_CHOICES."""
        fm_choices = set(
            get_args(ManifestMechanics.model_fields["shot_style"].annotation)
        )
        self.assertEqual(fm_choices, set(SHOT_STYLE_CHOICES))


class BuffNormalizationTests(unittest.TestCase):
    def test_on_hit_buff_accepts_sentence_containing_on_fire(self) -> None:
        mechanics = LLMMechanics(
            on_hit_buff="Inflicts a brief random elemental effect: On Fire! or Chilled"
        )
        self.assertEqual(mechanics.on_hit_buff, "BuffID.OnFire")

    def test_on_hit_buff_accepts_canonical_form(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="BuffID.Frostburn")
        self.assertEqual(mechanics.on_hit_buff, "BuffID.Frostburn")

    def test_on_hit_buff_accepts_bare_name(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="Frostburn")
        self.assertEqual(mechanics.on_hit_buff, "BuffID.Frostburn")

    def test_on_hit_buff_accepts_display_alias(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="On Fire!")
        self.assertEqual(mechanics.on_hit_buff, "BuffID.OnFire")

    def test_on_hit_buff_accepts_weak(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="Weak")
        self.assertEqual(mechanics.on_hit_buff, "BuffID.Weak")

    def test_on_hit_buff_accepts_buffid_weak(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="BuffID.Weak")
        self.assertEqual(mechanics.on_hit_buff, "BuffID.Weak")

    def test_on_hit_buff_prose_with_frostburn(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="Applies Frostburn to enemies on contact")
        self.assertEqual(mechanics.on_hit_buff, "BuffID.Frostburn")

    def test_on_hit_buff_prose_with_cursed_inferno(self) -> None:
        mechanics = LLMMechanics(
            on_hit_buff="Inflicts Cursed Inferno debuff for 3 seconds"
        )
        self.assertEqual(mechanics.on_hit_buff, "BuffID.CursedInferno")

    def test_on_hit_buff_prose_with_shadow_flame(self) -> None:
        mechanics = LLMMechanics(
            on_hit_buff="Has a chance to inflict Shadow Flame on hit"
        )
        self.assertEqual(mechanics.on_hit_buff, "BuffID.ShadowFlame")

    def test_on_hit_buff_null_passthrough(self) -> None:
        mechanics = LLMMechanics(on_hit_buff=None)
        self.assertIsNone(mechanics.on_hit_buff)

    def test_on_hit_buff_empty_string_becomes_none(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="")
        self.assertIsNone(mechanics.on_hit_buff)

    def test_on_hit_buff_total_garbage_falls_back_to_none(self) -> None:
        """Prose with no recognizable buff should fall back to None, not crash."""
        mechanics = LLMMechanics(
            on_hit_buff="Makes the enemy feel slightly uncomfortable"
        )
        self.assertIsNone(mechanics.on_hit_buff)

    def test_on_hit_buff_burning_prose_maps_to_on_fire(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="On hit, inflicts a brief burning effect")
        self.assertEqual(mechanics.on_hit_buff, "BuffID.OnFire")

    def test_buff_id_accepts_canonical(self) -> None:
        mechanics = LLMMechanics(buff_id="BuffID.WellFed")
        self.assertEqual(mechanics.buff_id, "BuffID.WellFed")

    def test_buff_id_prose_maps_like_on_hit(self) -> None:
        mechanics = LLMMechanics(buff_id="Grants Well Fed when used")
        self.assertEqual(mechanics.buff_id, "BuffID.WellFed")

    def test_on_hit_buff_unknown_buffid_constant_becomes_none(self) -> None:
        mechanics = LLMMechanics(on_hit_buff="BuffID.Chilled")
        self.assertIsNone(mechanics.on_hit_buff)


class MechanicsBuffNormalizationTests(unittest.TestCase):
    """``Mechanics`` duplicates buff validators — mirror key ``LLMMechanics`` cases."""

    def _base(self, **mech_kwargs):
        return Mechanics(
            crafting_material="ItemID.Wood",
            crafting_cost=5,
            crafting_tile="TileID.WorkBenches",
            **mech_kwargs,
        )

    def test_prose_frostburn_matches_llm_mechanics(self) -> None:
        m = self._base(on_hit_buff="Applies Frostburn on hit")
        self.assertEqual(m.on_hit_buff, "BuffID.Frostburn")

    def test_invalid_buffid_string_becomes_none(self) -> None:
        m = self._base(buff_id="BuffID.Venom")
        self.assertIsNone(m.buff_id)

    def test_channeled_coerces_custom_projectile_false(self) -> None:
        m = self._base(shot_style="channeled", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_direct_preserves_custom_projectile_true(self) -> None:
        m = self._base(shot_style="direct", custom_projectile=True)
        self.assertTrue(m.custom_projectile)


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Canonical forms — unchanged
        ("BuffID.OnFire", "BuffID.OnFire"),
        ("BuffID.Frostburn", "BuffID.Frostburn"),
        # Exact alias — existing coverage
        ("On Fire!", "BuffID.OnFire"),
        ("On Fire", "BuffID.OnFire"),
        # Case variants — newly hardened
        ("on fire!", "BuffID.OnFire"),
        ("ON FIRE!", "BuffID.OnFire"),
        ("on Fire", "BuffID.OnFire"),
        ("POISONED", "BuffID.Poisoned"),
        ("poisoned", "BuffID.Poisoned"),
        ("SLIMED", "BuffID.Slimed"),
        ("well fed", "BuffID.WellFed"),
        ("WELL FED", "BuffID.WellFed"),
        ("cursed inferno", "BuffID.CursedInferno"),
        ("CURSED INFERNO", "BuffID.CursedInferno"),
        ("shadow flame", "BuffID.ShadowFlame"),
        ("shadowflame", "BuffID.ShadowFlame"),
        ("SHADOWFLAME", "BuffID.ShadowFlame"),
        ("frostburn", "BuffID.Frostburn"),
        ("FROSTBURN", "BuffID.Frostburn"),
        # Completely unrecognised → None (no crash)
        ("completely_bogus", None),
        ("BuffID.Chilled", None),
    ],
)
def test_normalize_buff_id_variants(raw: str, expected):
    assert _normalize_buff_id(raw) == expected


class ShotStyleTests(unittest.TestCase):
    """shot_style field on LLMMechanics and Mechanics."""

    def test_llm_mechanics_defaults_to_direct(self) -> None:
        m = LLMMechanics()
        self.assertEqual(m.shot_style, "direct")

    def test_llm_mechanics_accepts_sky_strike(self) -> None:
        m = LLMMechanics(shot_style="sky_strike")
        self.assertEqual(m.shot_style, "sky_strike")

    def test_mechanics_defaults_to_direct(self) -> None:
        m = Mechanics(
            crafting_material="ItemID.Wood",
            crafting_cost=5,
            crafting_tile="TileID.WorkBenches",
        )
        self.assertEqual(m.shot_style, "direct")

    def test_mechanics_accepts_sky_strike(self) -> None:
        m = Mechanics(
            crafting_material="ItemID.Wood",
            crafting_cost=5,
            crafting_tile="TileID.WorkBenches",
            shot_style="sky_strike",
        )
        self.assertEqual(m.shot_style, "sky_strike")

    def test_llm_mechanics_accepts_all_styles(self) -> None:
        for style in (
            "homing",
            "boomerang",
            "orbit",
            "explosion",
            "pierce",
            "chain_lightning",
            "channeled",
        ):
            m = LLMMechanics(shot_style=style)
            self.assertEqual(m.shot_style, style)

    def test_mechanics_accepts_all_styles(self) -> None:
        for style in (
            "homing",
            "boomerang",
            "orbit",
            "explosion",
            "pierce",
            "chain_lightning",
            "channeled",
        ):
            m = Mechanics(
                crafting_material="ItemID.Wood",
                crafting_cost=5,
                crafting_tile="TileID.WorkBenches",
                shot_style=style,
            )
            self.assertEqual(m.shot_style, style)

    def test_llm_mechanics_rejects_invalid_shot_style(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            LLMMechanics(shot_style="orbital")


class CombatPackageManifestTests(unittest.TestCase):
    def test_llm_mechanics_requires_delivery_style_and_payoff_rate_for_package(
        self,
    ) -> None:
        with pytest.raises(
            ValidationError,
            match="combat_package requires delivery_style and payoff_rate",
        ):
            LLMMechanics(combat_package="storm_brand")

    def test_mechanics_requires_delivery_style_and_payoff_rate_for_package(
        self,
    ) -> None:
        with pytest.raises(
            ValidationError,
            match="combat_package requires delivery_style and payoff_rate",
        ):
            Mechanics(
                combat_package="storm_brand",
                crafting_material="ItemID.Wood",
                crafting_cost=5,
                crafting_tile="TileID.WorkBenches",
            )

    def test_llm_mechanics_accepts_bounded_combat_package_fields(self) -> None:
        mechanics = LLMMechanics(
            combat_package="storm_brand",
            delivery_style="direct",
            payoff_rate="fast",
        )

        self.assertEqual(mechanics.combat_package, "storm_brand")
        self.assertEqual(mechanics.delivery_style, "direct")
        self.assertEqual(mechanics.payoff_rate, "fast")

    def test_mechanics_accepts_bounded_combat_package_fields(self) -> None:
        mechanics = Mechanics(
            combat_package="storm_brand",
            delivery_style="direct",
            payoff_rate="fast",
            crafting_material="ItemID.Wood",
            crafting_cost=5,
            crafting_tile="TileID.WorkBenches",
        )

        self.assertEqual(mechanics.combat_package, "storm_brand")
        self.assertEqual(mechanics.delivery_style, "direct")
        self.assertEqual(mechanics.payoff_rate, "fast")

    def test_item_manifest_requires_delivery_style_and_payoff_rate_for_package(
        self,
    ) -> None:
        with pytest.raises(
            ValidationError,
            match="combat_package requires delivery_style and payoff_rate",
        ):
            ItemManifest.model_validate(
                {
                    "item_name": "StormBrand",
                    "display_name": "Storm Brand",
                    "tooltip": "Calls down marked thunder.",
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
                    "visuals": {},
                    "presentation": {"fx_profile": "celestial_shock"},
                    "mechanics": {
                        "combat_package": "storm_brand",
                        "crafting_material": "ItemID.FallenStar",
                        "crafting_cost": 12,
                        "crafting_tile": "TileID.Anvils",
                    },
                }
            )

    def test_item_manifest_lowers_combat_package_and_generates_projectile_visuals(
        self,
    ) -> None:
        manifest = ItemManifest.model_validate(
            {
                "item_name": "StormBrand",
                "display_name": "Storm Brand",
                "tooltip": "Calls down marked thunder.",
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
                "visuals": {},
                "presentation": {"fx_profile": "celestial_shock"},
                "mechanics": {
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "crafting_material": "ItemID.FallenStar",
                    "crafting_cost": 12,
                    "crafting_tile": "TileID.Anvils",
                },
            }
        )

        self.assertEqual(manifest.resolved_combat.package_key, "storm_brand")
        self.assertEqual(manifest.mechanics.shot_style, "direct")
        self.assertTrue(manifest.mechanics.custom_projectile)
        self.assertIsNotNone(manifest.projectile_visuals)

    def test_item_manifest_preserves_legacy_behavior_without_combat_package(
        self,
    ) -> None:
        manifest = ItemManifest.model_validate(
            {
                "item_name": "CinderBrand",
                "display_name": "Cinder Brand",
                "tooltip": "A fiery sword.",
                "content_type": "Weapon",
                "type": "Weapon",
                "sub_type": "Sword",
                "stats": {
                    "damage": 34,
                    "knockback": 5.5,
                    "crit_chance": 4,
                    "use_time": 22,
                    "auto_reuse": True,
                    "rarity": "ItemRarityID.Orange",
                },
                "visuals": {},
                "mechanics": {
                    "shot_style": "direct",
                    "custom_projectile": True,
                    "crafting_material": "ItemID.HellstoneBar",
                    "crafting_cost": 15,
                    "crafting_tile": "TileID.Anvils",
                },
            }
        )

        self.assertIsNone(manifest.resolved_combat)
        self.assertEqual(manifest.mechanics.shot_style, "direct")
        self.assertTrue(manifest.mechanics.custom_projectile)
        self.assertIsNotNone(manifest.projectile_visuals)

    def test_item_manifest_clears_injected_resolved_combat_without_combat_package(
        self,
    ) -> None:
        manifest = ItemManifest.model_validate(
            {
                "item_name": "CinderBrand",
                "display_name": "Cinder Brand",
                "tooltip": "A fiery sword.",
                "content_type": "Weapon",
                "type": "Weapon",
                "sub_type": "Sword",
                "stats": {
                    "damage": 34,
                    "knockback": 5.5,
                    "crit_chance": 4,
                    "use_time": 22,
                    "auto_reuse": True,
                    "rarity": "ItemRarityID.Orange",
                },
                "visuals": {},
                "mechanics": {
                    "shot_style": "direct",
                    "custom_projectile": True,
                    "crafting_material": "ItemID.HellstoneBar",
                    "crafting_cost": 15,
                    "crafting_tile": "TileID.Anvils",
                },
                "resolved_combat": {
                    "package_key": "storm_brand",
                    "delivery_module": "wrong",
                    "combo_module": "wrong",
                    "finisher_module": "wrong",
                    "presentation_module": "wrong",
                    "player_state_kind": "wrong",
                    "npc_state_kind": "wrong",
                    "legacy_projection": {
                        "shot_style": "homing",
                        "custom_projectile": False,
                        "shoot_projectile": "ProjectileID.Fireball",
                        "projectile_visuals_required": False,
                    },
                },
            }
        )

        self.assertIsNone(manifest.resolved_combat)

    def test_item_manifest_overwrites_stale_resolved_combat_from_package_inputs(
        self,
    ) -> None:
        manifest = ItemManifest.model_validate(
            {
                "item_name": "StormBrand",
                "display_name": "Storm Brand",
                "tooltip": "Calls down marked thunder.",
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
                "visuals": {},
                "presentation": {"fx_profile": "celestial_shock"},
                "mechanics": {
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "crafting_material": "ItemID.FallenStar",
                    "crafting_cost": 12,
                    "crafting_tile": "TileID.Anvils",
                },
                "resolved_combat": {
                    "package_key": "frost_shatter",
                    "delivery_module": "wrong",
                    "combo_module": "wrong",
                    "finisher_module": "wrong",
                    "presentation_module": "wrong",
                    "player_state_kind": "wrong",
                    "npc_state_kind": "wrong",
                    "legacy_projection": {
                        "shot_style": "homing",
                        "custom_projectile": False,
                        "shoot_projectile": "ProjectileID.Fireball",
                        "projectile_visuals_required": False,
                    },
                },
            }
        )

        self.assertEqual(manifest.resolved_combat.package_key, "storm_brand")
        self.assertEqual(manifest.resolved_combat.combo_module, "npc_marks_3")


@pytest.mark.parametrize(
    "sub_type",
    [
        "Pistol",
        "Shotgun",
        "Rifle",
        "Bow",
        "Repeater",
        "Gun",
        "Staff",
        "Wand",
        "Spellbook",
        "Tome",
        "Launcher",
        "Cannon",
    ],
)
def test_ranged_non_package_manifest_requires_shoot_projectile(sub_type: str) -> None:
    with pytest.raises(ValidationError, match="shoot_projectile"):
        ItemManifest.model_validate(_base_manifest(sub_type=sub_type))


def test_ranged_non_package_manifest_accepts_shoot_projectile() -> None:
    manifest = ItemManifest.model_validate(
        _base_manifest(
            sub_type="Pistol",
            mechanics={"shoot_projectile": "ProjectileID.Bullet"},
        )
    )

    assert manifest.mechanics.shoot_projectile == "ProjectileID.Bullet"


def test_combat_package_manifest_allows_null_shoot_projectile_after_lowering() -> None:
    manifest = ItemManifest.model_validate(
        _base_manifest(
            sub_type="Staff",
            presentation={"fx_profile": "celestial_shock"},
            mechanics={
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "shoot_projectile": "ProjectileID.BallofFire",
            },
        )
    )

    assert manifest.resolved_combat is not None
    assert manifest.mechanics.combat_package == "storm_brand"
    assert manifest.mechanics.shoot_projectile is None


class CustomProjectileCoercionTests(unittest.TestCase):
    """custom_projectile must be forced False when shot_style != 'direct'."""

    def test_channeled_coerces_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="channeled", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_homing_coerces_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="homing", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_orbit_coerces_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="orbit", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_sky_strike_coerces_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="sky_strike", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_boomerang_coerces_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="boomerang", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_explosion_coerces_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="explosion", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_pierce_coerces_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="pierce", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_chain_lightning_coerces_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="chain_lightning", custom_projectile=True)
        self.assertFalse(m.custom_projectile)

    def test_direct_preserves_custom_projectile_true(self) -> None:
        m = LLMMechanics(shot_style="direct", custom_projectile=True)
        self.assertTrue(m.custom_projectile)

    def test_direct_default_custom_projectile_false(self) -> None:
        m = LLMMechanics(shot_style="direct", custom_projectile=False)
        self.assertFalse(m.custom_projectile)

    def test_manifest_mechanics_channeled_coerces(self) -> None:
        m = ManifestMechanics(
            shot_style="channeled",
            custom_projectile=True,
            crafting_material="ItemID.Wood",
            crafting_cost=5,
            crafting_tile="TileID.WorkBenches",
        )
        self.assertFalse(m.custom_projectile)

    def test_manifest_mechanics_direct_preserves(self) -> None:
        m = ManifestMechanics(
            shot_style="direct",
            custom_projectile=True,
            crafting_material="ItemID.Wood",
            crafting_cost=5,
            crafting_tile="TileID.WorkBenches",
        )
        self.assertTrue(m.custom_projectile)


class WeaponPromptContractTests(unittest.TestCase):
    def test_weapon_prompt_describes_phase_1_package_contract(
        self,
    ) -> None:
        prompt = weapon_prompt.SYSTEM_PROMPT

        self.assertEqual(
            weapon_prompt.PACKAGE_PRIMARY_FIELDS,
            (
                "mechanics.combat_package",
                "mechanics.delivery_style",
                "mechanics.payoff_rate",
                "presentation.fx_profile",
            ),
        )
        self.assertEqual(
            weapon_prompt.SUPPORTED_COMBAT_PACKAGES,
            ("storm_brand", "orbit_furnace", "frost_shatter"),
        )
        self.assertEqual(
            weapon_prompt.PHASE_1_PACKAGE_SUPPORT_SCOPE,
            ('content_type="Weapon"', 'sub_type="Staff"'),
        )
        self.assertEqual(
            weapon_prompt.LEGACY_FALLBACK_FIELDS,
            (
                "mechanics.shot_style",
                "mechanics.custom_projectile",
                "mechanics.shoot_projectile",
            ),
        )
        self.assertEqual(
            weapon_prompt.UNSUPPORTED_FAMILY_FALLBACK_TOKENS,
            (
                "unsupported weapon families",
                "Weapon",
                "Staff",
                "legacy projectile fields",
                "combat packages",
            ),
        )
        self.assertEqual(
            weapon_prompt.LEGACY_HOMAGE_PROJECTILE_TOKENS,
            (
                "ProjectileID.*",
                "legacy projectile path",
                "explicit vanilla homage weapons",
            ),
        )

        for field in weapon_prompt.PACKAGE_PRIMARY_FIELDS:
            self.assertIn(field, prompt)

        for package_key in weapon_prompt.SUPPORTED_COMBAT_PACKAGES:
            self.assertIn(package_key, prompt)

        for scope_token in weapon_prompt.PHASE_1_PACKAGE_SUPPORT_SCOPE:
            self.assertIn(scope_token, prompt)

        for field in weapon_prompt.LEGACY_FALLBACK_FIELDS:
            self.assertIn(field, prompt)

        for token in weapon_prompt.UNSUPPORTED_FAMILY_FALLBACK_TOKENS:
            self.assertIn(token, prompt)

        for token in weapon_prompt.LEGACY_HOMAGE_PROJECTILE_TOKENS:
            self.assertIn(token, prompt)

    def test_weapon_prompt_requires_projectile_for_non_package_ranged_subtypes(
        self,
    ) -> None:
        prompt = weapon_prompt.SYSTEM_PROMPT

        for token in (
            "Pistol",
            "Shotgun",
            "Rifle",
            "Bow",
            "Repeater",
            "Gun",
            "Staff",
            "Wand",
            "Spellbook",
            "Tome",
            "Launcher",
            "Cannon",
            "mechanics.shoot_projectile",
            "combat_package",
            "ProjectileID.Bullet",
            "ProjectileID.WoodenArrowFriendly",
            "ProjectileID.MagicMissile",
        ):
            self.assertIn(token, prompt)


if __name__ == "__main__":
    unittest.main()
