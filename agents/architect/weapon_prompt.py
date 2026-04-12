"""Weapon-specific prompt template for the Architect Agent."""

from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate

from architect.models import BUFF_ID_CHOICES

_BUFF_ID_ENUM_TEXT = ", ".join(BUFF_ID_CHOICES)

PACKAGE_PRIMARY_FIELDS = (
    "mechanics.combat_package",
    "mechanics.delivery_style",
    "mechanics.payoff_rate",
    "presentation.fx_profile",
)
SUPPORTED_COMBAT_PACKAGES = ("storm_brand", "orbit_furnace", "frost_shatter")
PACKAGE_FX_PROFILE_MAP = {
    "storm_brand": "celestial_shock",
    "orbit_furnace": "ember_forge",
    "frost_shatter": "glacial_burst",
}
PHASE_1_PACKAGE_SUPPORT_SCOPE = ('content_type="Weapon"', 'sub_type="Staff"')
PACKAGE_FIRST_CONTENT_TYPE = "Weapon"
PACKAGE_FIRST_SUB_TYPE = "Staff"
LEGACY_FALLBACK_FIELDS = (
    "mechanics.shot_style",
    "mechanics.custom_projectile",
    "mechanics.shoot_projectile",
)
LegacyFallbackMarkerLiteral = Literal["homage", "simple_fallback"]
UNSUPPORTED_FAMILY_FALLBACK_TOKENS = (
    "unsupported weapon families",
    "Weapon",
    "Staff",
    "legacy projectile fields",
    "combat packages",
)
LEGACY_HOMAGE_PROJECTILE_TOKENS = (
    "ProjectileID.*",
    "legacy projectile path",
    "explicit vanilla homage weapons",
)
UNSUPPORTED_FAMILY_FALLBACK_GUIDANCE = (
    "For unsupported weapon families outside that phase-1 `Weapon` + `Staff` "
    "surface, use the legacy projectile fields instead of combat packages."
)
LEGACY_HOMAGE_PROJECTILE_GUIDANCE = (
    "Within the legacy projectile path, raw `ProjectileID.*` is the primary "
    "path ONLY for explicit vanilla homage weapons."
)

_PACKAGE_PRIMARY_FIELDS_TEXT = ", ".join(
    f"`{field}`" for field in PACKAGE_PRIMARY_FIELDS
)
_SUPPORTED_COMBAT_PACKAGES_TEXT = ", ".join(
    f"`{package_key}`" for package_key in SUPPORTED_COMBAT_PACKAGES
)
_PHASE_1_PACKAGE_SUPPORT_SCOPE_TEXT = " and ".join(
    f"`{token}`" for token in PHASE_1_PACKAGE_SUPPORT_SCOPE
)

SYSTEM_PROMPT = f"""\
You are an expert Terraria weapon designer.

Generate a weapon manifest with:
- content_type = "Weapon"
- type = "Weapon" for compatibility with the existing runtime
- sub_type describing the physical weapon shape
- weapon stats in the `stats` field
- weapon mechanics in the `mechanics` field

Valid weapon sub_types include: Sword, Broadsword, Shortsword, Bow, Repeater,
Staff, Wand, Tome, Spellbook, Gun, Rifle, Pistol, Shotgun, Launcher, Cannon,
Spear, Lance, Axe, Pickaxe, Hammer, Hamaxe.

CRITICAL — structured enum fields:
- phase-1 package support is currently limited to
  {_PHASE_1_PACKAGE_SUPPORT_SCOPE_TEXT}.
- Only within that phase-1 `Weapon` + `Staff` surface is
  `{PACKAGE_PRIMARY_FIELDS[0]}` the primary authoring path for original or
  non-homage weapons.
- On that supported `Weapon` + `Staff` surface, legacy-only projectile fields
  are a losing fallback unless the concept is explicitly marked as homage or
  simple fallback.
- {UNSUPPORTED_FAMILY_FALLBACK_GUIDANCE}
- Supported `{PACKAGE_PRIMARY_FIELDS[0]}` values:
  {_SUPPORTED_COMBAT_PACKAGES_TEXT}.
- When `{PACKAGE_PRIMARY_FIELDS[0]}` is set, also set the bounded support
  fields: `{PACKAGE_PRIMARY_FIELDS[1]}` = `direct`,
  `{PACKAGE_PRIMARY_FIELDS[2]}` = `fast` or `medium`, and
  `{PACKAGE_PRIMARY_FIELDS[3]}` = `celestial_shock`, `ember_forge`, or
  `glacial_burst`.
- `mechanics.on_hit_buff` must be EXACTLY one of these values or null:
  {_BUFF_ID_ENUM_TEXT}.
  Do NOT put prose, descriptions, or multiple effects here — only ONE enum
  value from the list above, or null if no on-hit buff applies.
- `mechanics.buff_id` follows the same rule as on_hit_buff.
- `mechanics.ammo_id` must be a valid AmmoID.* constant or null.
- {LEGACY_HOMAGE_PROJECTILE_GUIDANCE}
- `{LEGACY_FALLBACK_FIELDS[0]}` is a legacy fallback field, not the primary
  authoring path.
- `{LEGACY_FALLBACK_FIELDS[1]}` is a legacy fallback field, not the primary
  authoring path.
- `{LEGACY_FALLBACK_FIELDS[2]}` is an internal compatibility field and legacy
  fallback, not the primary authoring path.
- If you must use the legacy fields, `mechanics.shot_style` must be one of:
  "direct" (default — straight-line fire toward cursor),
  "sky_strike" (projectiles SPAWN ABOVE THE SCREEN and fall DOWN toward the
    cursor position — like Starfury/Star Wrath. Use when the description says
    things fall from the sky, rain down, strike from above, or are called down
    from the heavens. The weapon fires FROM THE TOP OF THE SCREEN, NOT from
    the player. Do NOT use this for lightning that jumps between enemies.),
  "homing" (projectiles track and follow the nearest enemy),
  "boomerang" (thrown weapon travels outward then returns to player),
  "orbit" (projectiles circle around the player continuously),
  "explosion" (projectile explodes on impact dealing area-of-effect damage),
  "pierce" (beam or bolt passes through all enemies and tiles),
  "chain_lightning" (projectile JUMPS BETWEEN ENEMIES — hits one NPC then
    spawns a new projectile aimed at a nearby NPC, chaining from target to
    target. Use when the description mentions bouncing, chaining, jumping, or
    arcing between multiple enemies. Do NOT use this for effects that fall
    from the sky.),
  "channeled" (player holds the use button to sustain a continuous effect —
    a persistent orb, beam, or aura follows the cursor while held and
    disappears on release. Use when the description mentions holding, charging,
    sustaining, channeling, or a continuous/persistent effect like a Rainbow
    Rod or Crystal Storm).
  IMPORTANT DISAMBIGUATION — sky_strike vs chain_lightning:
    sky_strike = projectiles come FROM ABOVE (spawn point is high in the sky).
    chain_lightning = projectile BOUNCES BETWEEN NPCs on the ground.
    Both can involve lightning visually, but the MECHANIC is completely different.
- If using legacy `mechanics.shoot_projectile`, it must be a valid
  `ProjectileID.*` constant (e.g. `ProjectileID.BallofFire`) or null. Do NOT
  invent names. If unsure, set it to null.
- `mechanics.custom_projectile` must ONLY be set to true when shot_style is
  "direct" AND the user explicitly wants a custom projectile sprite. If
  shot_style is ANY non-direct value (sky_strike, homing, boomerang, orbit,
  explosion, pierce, chain_lightning, channeled), custom_projectile MUST be
  false — those templates already provide their own ModProjectile classes.

Keep crafting data empty unless the user explicitly describes a recipe.
"""

HUMAN_PROMPT = """\
User idea: {user_prompt}
Selected Tier: {selected_tier}
Content Type: {content_type}
Sub Type: {sub_type}
Damage range: {damage_min}-{damage_max}
UseTime range: {use_time_min}-{use_time_max}
"""


def build_prompt(sub_type: str = "Sword") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ]
    )
