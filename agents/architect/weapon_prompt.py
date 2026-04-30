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
    "explicit vanilla homage",
)
RANGED_PROJECTILE_SUBTYPES = (
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
)
UNSUPPORTED_FAMILY_FALLBACK_GUIDANCE = (
    "For unsupported weapon families outside that phase-1 `Weapon` + `Staff` "
    "surface, use the legacy projectile fields instead of combat packages."
)
LEGACY_HOMAGE_PROJECTILE_GUIDANCE = (
    "Within the legacy projectile path, set `mechanics.custom_projectile` to "
    "`false` and use a real `ProjectileID.*` ONLY for explicit vanilla homage or "
    "when the design must match a specific stock projectile."
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
_RANGED_PROJECTILE_SUBTYPES_TEXT = ", ".join(
    f"`{sub_type}`" for sub_type in RANGED_PROJECTILE_SUBTYPES
)

SYSTEM_PROMPT = f"""\
You are an expert Terraria weapon designer.

Generate a weapon manifest with:
- content_type = "Weapon"
- type = "Weapon" for compatibility with the existing runtime
- sub_type MUST exactly match the Sub Type provided in the human message — it is
  pre-determined by the routing system and must not be changed
- weapon stats in the `stats` field
- weapon mechanics in the `mechanics` field

CRITICAL — the Sub Type in the human message is the canonical weapon form factor.
Design ALL aspects of this weapon — visual description, mechanics, and feel — to
match that form factor. A Gun must look and behave like a gun. A Sword must look
and behave like a sword. Never design a sword when Sub Type is Gun, or vice versa.

Valid weapon sub_types include: Bow, Repeater, Gun, Rifle, Pistol, Shotgun,
Launcher, Cannon, Staff, Wand, Tome, Spellbook, Sword, Broadsword, Shortsword,
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
- **Default for direct-shot ranged (no combat package):** When Sub Type is one of
  {_RANGED_PROJECTILE_SUBTYPES_TEXT}, `{PACKAGE_PRIMARY_FIELDS[0]}` is null, and
  `mechanics.shot_style` is `direct`, the Forge pipeline generates a
  `ModProjectile` and a custom sprite (Pixelsmith / tier-3 art). Author that path
  by leaving `mechanics.shoot_projectile` null, leaving `mechanics.custom_projectile`
  unset (or true), and filling `projectile_visuals` with a clear, on-theme
  description (and animation tier if relevant). Do **not** default to
  `ProjectileID.Bullet`, `ProjectileID.MagicMissile`, or other stock projectiles
  for original weapons — those look generic next to a bespoke item icon.
- For Tier3 or highly novel direct-shot ranged ideas, also fill `spectacle_plan`.
  This is the codegen brief for a hand-shaped projectile, not an art prompt.
  Treat Tier3 as a composable mechanics basis, not a single archetype menu:
  fill `basis` with selected vectors such as `cast_shape`, `projectile_body`,
  `motion_grammar`, `payoff`, `visual_language`, and optional
  `world_interaction` (for example tile scorch, controlled terrain carve, or
  none). Then write `composition`: one concise sentence explaining how those
  vectors combine into this weapon's unique mechanic. Include `fantasy`,
  `movement`, `render_passes`, `ai_phases`, `impact_payoff`, `sound_profile`,
  `must_not_include` concrete forbidden mechanics, and `must_not_feel_like`
  anti-goals such as "bullet", "fireball", or "generic dust trail" when those
  would make the weapon underwhelming.
- For Tier3 bespoke weapons, also fill `mechanics_ir`. This is the executable
  contract underneath `spectacle_plan`: choose composable capability atoms, not
  full weapon templates and not product lanes; these are not full weapon templates.
  Compose across basis axes such as `cast_shape`, `carrier`, `motion`,
  `field_control`, `payoff`, `world_interaction`, `combo_logic`, and
  `visual_grammar`; these are not complete weapon archetypes. Prefer 3-6
  compatible atoms for a normal Tier3 weapon, and avoid reskinning every prompt
  into the same singularity path.
  Use `mechanics_ir.atoms` for
  capabilities such as `charge_phase`, `channel_cast`, `singularity_projectile`,
  `beam_lance`, `rift_projectile`, `gravity_pull_field`, `portal_hop`,
  `delayed_detonation`, `summoned_construct`, `orbiting_convergence`,
  `rift_trail`, `implosion_payoff`, `shock_ring_damage`,
  or `bounded_terrain_carve`; use `mechanics_ir.forbidden_atoms` for mechanics
  that must not appear, such as `target_stack_cashout` or `starfall_burst`.
  `spectacle_plan` is the creative brief; `mechanics_ir` is the implementation
  checklist.
- **Opt out of custom art** only for vanilla homage or when a specific
  `ProjectileID.*` is required: set `mechanics.custom_projectile` to `false` and
  set `mechanics.shoot_projectile` to a valid `ProjectileID.*` (e.g.
  `ProjectileID.Bullet` for bullet guns, `ProjectileID.WoodenArrowFriendly` for
  bows, `ProjectileID.MagicMissile` for classic-staff feel). You must not invent
  projectile names.
- Ranged + no package + **non-direct** `shot_style`: do not request custom
  projectile art — `mechanics.custom_projectile` must be false; those templates
  use their own `ModProjectile` wiring. If you use legacy
  `mechanics.shoot_projectile` for a non-direct style, it must be a valid
  `ProjectileID.*` or null.
- `mechanics.shoot_projectile` is an internal compatibility field. On the
  custom-projectile default path, keep it null; the runtime uses your
  `projectile_visuals` and generated class instead.
- If you must use the legacy `mechanics.shot_style` list for non-direct fire,
  values include:
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
- `mechanics.shot_style` is a legacy field when not using a combat package;
  non-direct styles force `mechanics.custom_projectile` false in validation.

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
