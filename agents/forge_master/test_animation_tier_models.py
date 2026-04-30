from __future__ import annotations

from forge_master.models import ForgeManifest


def test_forge_manifest_preserves_projectile_animation_tier() -> None:
    manifest = ForgeManifest.model_validate(
        {
            "item_name": "StormBrand",
            "display_name": "Storm Brand",
            "stats": {
                "damage": 10,
                "knockback": 4.0,
                "use_time": 20,
                "rarity": "ItemRarityID.Green",
            },
            "mechanics": {
                "crafting_material": "ItemID.Wood",
                "crafting_cost": 5,
                "crafting_tile": "TileID.WorkBenches",
            },
            "projectile_visuals": {
                "description": "animated sigil",
                "animation_tier": "vanilla_frames:4",
            },
        }
    )

    assert manifest.projectile_visuals is not None
    assert manifest.projectile_visuals.animation_tier == "vanilla_frames:4"


def test_forge_manifest_preserves_spectacle_plan() -> None:
    manifest = ForgeManifest.model_validate(
        {
            "item_name": "VoidVioletPistol",
            "display_name": "Void Violet",
            "sub_type": "Pistol",
            "stats": {
                "damage": 34,
                "knockback": 4.5,
                "use_time": 22,
                "rarity": "ItemRarityID.Orange",
            },
            "mechanics": {
                "custom_projectile": True,
                "shoot_projectile": None,
                "crafting_material": "ItemID.Bone",
                "crafting_cost": 15,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {
                "description": "large violet annihilation orb",
                "animation_tier": "generated_frames:3",
            },
            "spectacle_plan": {
                "fantasy": "compressed violet annihilation orb",
                "movement": "fast shot with gravitational wobble",
                "render_passes": ["afterimage trail", "outer glow", "white core"],
                "ai_phases": ["spawn flare", "cruise", "impact collapse"],
                "impact_payoff": "imploding ring and violet shock burst",
                "sound_profile": "deep magic shot and low impact pulse",
                "must_not_feel_like": ["bullet", "generic dust trail"],
            },
        }
    )

    assert manifest.spectacle_plan is not None
    assert manifest.spectacle_plan.fantasy.startswith("compressed violet")


def test_forge_manifest_preserves_composable_spectacle_basis() -> None:
    manifest = ForgeManifest.model_validate(
        {
            "item_name": "VoidConvergenceStaff",
            "display_name": "Void Convergence Staff",
            "stats": {
                "damage": 55,
                "knockback": 6,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Pink",
            },
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": True,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 12,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {"description": "violet singularity orb"},
            "spectacle_plan": {
                "fantasy": "hollow purple singularity",
                "basis": {
                    "projectile_body": ["singularity orb", "rift seam"],
                    "world_interaction": ["radial terrain carve"],
                },
                "composition": "A slow orb tears space and collapses terrain.",
                "must_not_include": ["starfall", "mark/cashout"],
            },
        }
    )

    assert manifest.spectacle_plan is not None
    assert "singularity orb" in manifest.spectacle_plan.basis.projectile_body
    assert "terrain" in manifest.spectacle_plan.composition
    assert "starfall" in manifest.spectacle_plan.must_not_include


def test_forge_manifest_preserves_tier3_mechanics_ir() -> None:
    manifest = ForgeManifest.model_validate(
        {
            "item_name": "VoidConvergenceStaff",
            "display_name": "Void Convergence Staff",
            "sub_type": "Staff",
            "stats": {
                "damage": 55,
                "knockback": 6,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Pink",
            },
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": True,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 12,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {"description": "violet singularity orb"},
            "spectacle_plan": {"fantasy": "hollow purple singularity"},
            "mechanics_ir": {
                "atoms": [
                    {"kind": "charge_phase", "duration_ticks": 18},
                    {"kind": "singularity_projectile", "speed": "slow"},
                    {"kind": "gravity_pull_field", "radius_tiles": 6},
                    {"kind": "implosion_payoff", "radius_tiles": 7},
                    {"kind": "bounded_terrain_carve", "radius_tiles": 2},
                ],
                "forbidden_atoms": ["target_stack_cashout", "starfall_burst"],
                "composition": "charge and collapse a terrain-carving singularity",
            },
        }
    )

    assert manifest.mechanics_ir is not None
    assert [atom.kind for atom in manifest.mechanics_ir.atoms][:2] == [
        "charge_phase",
        "singularity_projectile",
    ]
    assert "starfall_burst" in manifest.mechanics_ir.forbidden_atoms


def test_forge_manifest_preserves_slot_references() -> None:
    manifest = ForgeManifest.model_validate(
        {
            "item_name": "VoidConvergenceStaff",
            "display_name": "Void Convergence Staff",
            "sub_type": "Staff",
            "stats": {
                "damage": 55,
                "knockback": 6,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Pink",
            },
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": True,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 12,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {"description": "violet singularity orb"},
            "references": {
                "item": {"needed": False, "generation_mode": "text_to_image"},
                "projectile": {
                    "needed": True,
                    "subject": "Gojo Hollow Purple from JJK",
                    "protected_terms": ["gojo", "hollow purple", "jjk"],
                    "image_url": "https://example.test/hollow-purple.png",
                    "generation_mode": "image_to_image",
                },
            },
        }
    )

    assert manifest.references.projectile.needed is True
    assert manifest.references.projectile.generation_mode == "image_to_image"
    assert manifest.references.projectile.image_url.endswith("hollow-purple.png")


def test_forge_manifest_preserves_expanded_mechanics_atoms() -> None:
    manifest = ForgeManifest.model_validate(
        {
            "item_name": "RiftLanceStaff",
            "display_name": "Rift Lance Staff",
            "sub_type": "Staff",
            "stats": {
                "damage": 55,
                "knockback": 6,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Pink",
            },
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": True,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 12,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {"description": "rift lance"},
            "mechanics_ir": {
                "atoms": [
                    {"kind": "beam_lance", "duration_ticks": 36},
                    {"kind": "delayed_detonation", "duration_ticks": 45},
                    {
                        "kind": "summoned_construct",
                        "notes": "temporary eye opens the rift",
                    },
                    {"kind": "portal_hop", "count": 3},
                    {"kind": "ricochet_path", "count": 2},
                    {"kind": "color_separation_distortion", "width_tiles": 3},
                ]
            },
        }
    )

    assert manifest.mechanics_ir is not None
    assert [atom.kind for atom in manifest.mechanics_ir.atoms] == [
        "beam_lance",
        "delayed_detonation",
        "summoned_construct",
        "portal_hop",
        "ricochet_path",
        "color_separation_distortion",
    ]
    assert manifest.mechanics_ir.atoms[5].width_tiles == 3
