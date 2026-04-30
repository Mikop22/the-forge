"""Normalize manifest ``mechanics.shoot_projectile`` for gun vs staff conventions.

The LLM sometimes assigns ``ProjectileID.MagicMissile`` to pistols and other guns;
that ID is for staff/wand-style magic shots and does not read as a gun or as
void/purple arcane.  We correct to bullet-type or a purple gem bolt when the
item flavor calls for it.
"""

from __future__ import annotations

import re
from typing import Any

# Ranged subtypes that fire bullets (not arrows / rockets) — see architect weapon_prompt.
_GUN_BULLET = frozenset({"Pistol", "Shotgun", "Rifle", "Gun"})
_ARROW = frozenset({"Bow", "Repeater"})
_STAFF_LIKE = frozenset({"Staff", "Wand", "Spellbook", "Tome"})

# Projectiles that belong on magic staves, not on bullet guns.
_STAFF_BOLT_ON_GUN = frozenset(
    {
        "ProjectileID.MagicMissile",
        "ProjectileID.WaterBolt",
    }
)

# Obvious fire balls — replace when the item is clearly void/purple themed.
_FIRE_FLAVOR_SHOOTS = frozenset(
    {
        "ProjectileID.BallofFire",
        "ProjectileID.Fireball",
    }
)

_VOID_FLAVOR = re.compile(
    r"void|violet|purple|shadow|hollow|umbral|abyss|arcane|obsidian|night|"
    r"nether|soul|eclipse|malignant|Dungeon|underworld",
    re.IGNORECASE,
)


def _flavor_blob(manifest: dict[str, Any]) -> str:
    parts: list[str] = [
        str(manifest.get("tooltip") or ""),
        str(manifest.get("display_name") or ""),
    ]
    vis = manifest.get("visuals")
    if isinstance(vis, dict):
        parts.append(str(vis.get("description") or ""))
    pv = manifest.get("projectile_visuals")
    if isinstance(pv, dict):
        parts.append(str(pv.get("description") or ""))
    return " ".join(parts)


def sanitize_shoot_projectile(manifest: dict[str, Any]) -> None:
    """Mutate *manifest* ``mechanics.shoot_projectile`` in place when needed."""
    mech = manifest.get("mechanics")
    if not isinstance(mech, dict) or mech.get("custom_projectile"):
        return
    sub = str(manifest.get("sub_type") or "").strip()
    if sub in _STAFF_LIKE:
        return
    sp = str(mech.get("shoot_projectile") or "").strip()
    if not sp:
        return
    text = _flavor_blob(manifest)
    voidish = bool(_VOID_FLAVOR.search(text))

    if sub in _GUN_BULLET:
        if sp in _STAFF_BOLT_ON_GUN:
            mech["shoot_projectile"] = (
                "ProjectileID.AmethystBolt" if voidish else "ProjectileID.Bullet"
            )
        elif voidish and sp in _FIRE_FLAVOR_SHOOTS:
            mech["shoot_projectile"] = "ProjectileID.AmethystBolt"
        return

    if sub in _ARROW and sp in _STAFF_BOLT_ON_GUN:
        mech["shoot_projectile"] = "ProjectileID.WoodenArrowFriendly"
        return

    if sub == "Launcher" and sp in _STAFF_BOLT_ON_GUN:
        mech["shoot_projectile"] = "ProjectileID.RocketI"
        return

    if sub == "Cannon" and sp in _STAFF_BOLT_ON_GUN:
        mech["shoot_projectile"] = "ProjectileID.Boulder"
