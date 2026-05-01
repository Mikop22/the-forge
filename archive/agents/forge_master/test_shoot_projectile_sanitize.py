"""Tests for mechanics.shoot_projectile normalization on guns vs staves."""

from __future__ import annotations

import copy

from forge_master.shoot_projectile_sanitize import sanitize_shoot_projectile


def _base(sub: str, sp: str) -> dict:
    return {
        "item_name": "T",
        "sub_type": sub,
        "tooltip": "A void weapon with purple energy",
        "display_name": "T",
        "visuals": {"description": "matte black with violet core"},
        "mechanics": {
            "shoot_projectile": sp,
            "custom_projectile": False,
            "shot_style": "direct",
        },
    }


def test_pistol_magic_missile_to_amethyst_when_voidish() -> None:
    m = _base("Pistol", "ProjectileID.MagicMissile")
    sanitize_shoot_projectile(m)
    assert m["mechanics"]["shoot_projectile"] == "ProjectileID.AmethystBolt"


def test_pistol_magic_missile_to_bullet_when_not_voidish() -> None:
    m = _base("Pistol", "ProjectileID.MagicMissile")
    m["tooltip"] = "A basic sidearm"
    m["visuals"] = {"description": "standard steel frame"}
    sanitize_shoot_projectile(m)
    assert m["mechanics"]["shoot_projectile"] == "ProjectileID.Bullet"


def test_staff_unchanged() -> None:
    m = _base("Staff", "ProjectileID.MagicMissile")
    m["mechanics"]["shoot_projectile"] = "ProjectileID.MagicMissile"
    before = copy.deepcopy(m)
    sanitize_shoot_projectile(m)
    assert m == before


def test_bow_magic_missile_to_arrow() -> None:
    m = _base("Bow", "ProjectileID.MagicMissile")
    m["visuals"] = {"description": "wooden bow"}
    sanitize_shoot_projectile(m)
    assert m["mechanics"]["shoot_projectile"] == "ProjectileID.WoodenArrowFriendly"


def test_custom_projectile_skipped() -> None:
    m = _base("Pistol", "ProjectileID.MagicMissile")
    m["mechanics"]["custom_projectile"] = True
    before = copy.deepcopy(m)
    sanitize_shoot_projectile(m)
    assert m == before
