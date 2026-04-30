from __future__ import annotations

from forge_master.tier3_executor import render_tier3_skeleton


def test_tier3_executor_renders_singularity_skeleton() -> None:
    manifest = {
        "item_name": "VoidConvergenceStaff",
        "display_name": "Void Convergence Staff",
        "sub_type": "Staff",
        "stats": {
            "damage": 58,
            "knockback": 5.5,
            "use_time": 20,
            "rarity": "ItemRarityID.Pink",
        },
        "mechanics": {
            "crafting_material": "ItemID.SoulofLight",
            "crafting_cost": 22,
            "crafting_tile": "TileID.Anvils",
        },
        "projectile_visuals": {
            "hitbox_size": [22, 22],
            "animation_tier": "generated_frames:3",
        },
        "mechanics_ir": {
            "atoms": [
                {"kind": "charge_phase", "duration_ticks": 18},
                {"kind": "singularity_projectile", "speed": "slow"},
                {"kind": "gravity_pull_field", "radius_tiles": 6},
                {"kind": "implosion_payoff", "radius_tiles": 7},
                {
                    "kind": "bounded_terrain_carve",
                    "radius_tiles": 2,
                    "tile_limit": 8,
                },
            ]
        },
    }

    code = render_tier3_skeleton(manifest)

    assert "class VoidConvergenceStaffProjectile : ModProjectile" in code
    assert "ChargeTicks" in code
    assert "WorldGen.KillTile" in code
    assert "ProjectileID.Sets.TrailCacheLength[Type]" in code
    assert "Projectile.width = 22;" in code
    assert "Projectile.height = 22;" in code
