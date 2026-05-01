from architect.models import ItemManifest


def test_package_lowering_still_autofills_projectile_visuals() -> None:
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
            "visuals": {
                "description": "A star-forged staff crackling with stormlight."
            },
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

    assert manifest.projectile_visuals is not None
    assert manifest.projectile_visuals.description == manifest.visuals.description
    assert manifest.projectile_visuals.icon_size == [16, 16]
