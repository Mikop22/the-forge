"""Pydantic models, tier lookup tables, and crafting resolution for the Architect Agent."""

from __future__ import annotations

import logging
import re
import sys
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

try:
    from core.combat_packages import (
        CombatPackageLiteral,
        DeliveryStyleLiteral,
        FxProfileLiteral,
        PayoffRateLiteral,
        ResolvedCombat,
        resolve_combat_package,
    )
except ImportError:
    from pathlib import Path as _Path0

    _parent0 = str(_Path0(__file__).resolve().parent.parent)
    if _parent0 not in sys.path:
        sys.path.insert(0, _parent0)
    from core.combat_packages import (  # type: ignore
        CombatPackageLiteral,
        DeliveryStyleLiteral,
        FxProfileLiteral,
        PayoffRateLiteral,
        ResolvedCombat,
        resolve_combat_package,
    )

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hard-coded balance tables
# ---------------------------------------------------------------------------

TIER_TABLE: dict[str, dict] = {
    "Tier1_Starter": {
        "damage": (8, 15),
        "use_time": (20, 30),
        "rarity": "ItemRarityID.White",
        "crafting_cost": (5, 10),
        "crafting_tile": "TileID.WorkBenches",
        "default_materials": ["ItemID.Wood", "ItemID.IronBar"],
    },
    "Tier2_Dungeon": {
        "damage": (25, 40),
        "use_time": (18, 25),
        "rarity": "ItemRarityID.Orange",
        "crafting_cost": (10, 20),
        "crafting_tile": "TileID.Anvils",
        "default_materials": ["ItemID.Bone", "ItemID.GoldenKey"],
    },
    "Tier3_Hardmode": {
        "damage": (45, 65),
        "use_time": (15, 22),
        "rarity": "ItemRarityID.Pink",
        "crafting_cost": (15, 30),
        "crafting_tile": "TileID.Anvils",
        "default_materials": ["ItemID.SoulofLight", "ItemID.MythrilBar"],
    },
    "Tier4_Endgame": {
        "damage": (150, 300),
        "use_time": (8, 15),
        "rarity": "ItemRarityID.Red",
        "crafting_cost": (20, 50),
        "crafting_tile": "TileID.Anvils",
        "default_materials": ["ItemID.LuminiteBar", "ItemID.FragmentSolar"],
    },
}

VALID_TIERS = set(TIER_TABLE.keys())
VALID_CONTENT_TYPES = {"Weapon", "Accessory", "Summon", "Consumable", "Tool"}

# --- Buff IDs: one tuple drives set, sorted prompt line, and Literal (no drift). ---
BUFF_ID_TUPLE: tuple[str, ...] = (
    "BuffID.CursedInferno",
    "BuffID.Frostburn",
    "BuffID.ManaSickness",
    "BuffID.OnFire",
    "BuffID.Poisoned",
    "BuffID.ShadowFlame",
    "BuffID.Slimed",
    "BuffID.WellFed",
    "BuffID.Weak",
)
VALID_BUFF_IDS: frozenset[str] = frozenset(BUFF_ID_TUPLE)
BUFF_ID_CHOICES: tuple[str, ...] = tuple(sorted(BUFF_ID_TUPLE))
# Explicit Literal (Python 3.9 cannot use Literal[*tuple] — requires 3.11+)
BuffIDLiteral = Literal[
    "BuffID.CursedInferno",
    "BuffID.Frostburn",
    "BuffID.ManaSickness",
    "BuffID.OnFire",
    "BuffID.Poisoned",
    "BuffID.ShadowFlame",
    "BuffID.Slimed",
    "BuffID.WellFed",
    "BuffID.Weak",
]

# --- Ammo IDs: same pattern. ---
AMMO_ID_TUPLE: tuple[str, ...] = (
    "AmmoID.Arrow",
    "AmmoID.Bullet",
    "AmmoID.Coin",
    "AmmoID.Dart",
    "AmmoID.Flare",
    "AmmoID.Gel",
    "AmmoID.Rocket",
    "AmmoID.Sand",
    "AmmoID.Snowball",
)
VALID_AMMO_IDS: frozenset[str] = frozenset(AMMO_ID_TUPLE)
AMMO_ID_CHOICES: tuple[str, ...] = tuple(sorted(AMMO_ID_TUPLE))
AmmoIDLiteral = Literal[
    "AmmoID.Arrow",
    "AmmoID.Bullet",
    "AmmoID.Coin",
    "AmmoID.Dart",
    "AmmoID.Flare",
    "AmmoID.Gel",
    "AmmoID.Rocket",
    "AmmoID.Sand",
    "AmmoID.Snowball",
]

# --- Shot-style choices: single source of truth for all models. ---
SHOT_STYLE_CHOICES: tuple[str, ...] = (
    "direct",
    "sky_strike",
    "homing",
    "boomerang",
    "orbit",
    "explosion",
    "pierce",
    "chain_lightning",
    "channeled",
)
ShotStyleLiteral = Literal[
    "direct",
    "sky_strike",
    "homing",
    "boomerang",
    "orbit",
    "explosion",
    "pierce",
    "chain_lightning",
    "channeled",
]

# Build lookup tables for bare-name -> prefixed-name normalization.
_BARE_BUFF_LOOKUP = {v.removeprefix("BuffID."): v for v in VALID_BUFF_IDS}
_BARE_AMMO_LOOKUP = {v.removeprefix("AmmoID."): v for v in VALID_AMMO_IDS}

# LLMs often emit the in-game display name instead of the BuffID field name.
_BUFF_DISPLAY_ALIASES: dict[str, str] = {
    "On Fire!": "BuffID.OnFire",
    "On Fire": "BuffID.OnFire",
    "OnFire!": "BuffID.OnFire",
    "Cursed Inferno": "BuffID.CursedInferno",
    "Shadow Flame": "BuffID.ShadowFlame",
    "Shadowflame": "BuffID.ShadowFlame",
    "Mana Sickness": "BuffID.ManaSickness",
    "Well Fed": "BuffID.WellFed",
    "WellFed": "BuffID.WellFed",
    "Frost Burn": "BuffID.Frostburn",
    "Frostburn": "BuffID.Frostburn",
    "Slimed": "BuffID.Slimed",
    "Poisoned": "BuffID.Poisoned",
    "Weak": "BuffID.Weak",
    "Weakness": "BuffID.Weak",
}
# Pre-lowercased for case-insensitive lookup without repeated .lower() calls at runtime.
_BUFF_DISPLAY_ALIASES_LOWER: dict[str, str] = {
    k.lower(): v for k, v in _BUFF_DISPLAY_ALIASES.items()
}


def _looks_like_buff_prose(value: str) -> bool:
    """Apply loose burn/poison heuristics only for sentence-like LLM output, not short tokens."""
    s = value.strip()
    if not s:
        return False
    if s.startswith("BuffID.") and s in VALID_BUFF_IDS:
        return False
    if s in VALID_BUFF_IDS:
        return False
    if s in _BUFF_DISPLAY_ALIASES:
        return False
    if s in _BARE_BUFF_LOOKUP or s in _BARE_BUFF_LOOKUP.values():
        return False
    if len(s) < 12 and " " not in s:
        return False
    if " " not in s and len(s) < 22:
        return False
    return True


def _extract_buff_id_from_text(value: str) -> str | None:
    lowered = value.lower()

    for alias, canonical in sorted(
        _BUFF_DISPLAY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if alias.lower() in lowered:
            return canonical

    for bare_name, canonical in sorted(
        _BARE_BUFF_LOOKUP.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if re.search(rf"\b{re.escape(bare_name.lower())}\b", lowered):
            return canonical

    for buff_id in sorted(VALID_BUFF_IDS, key=len, reverse=True):
        if buff_id.lower() in lowered:
            return buff_id

    # Prose-only phrases (LLMs often omit exact BuffID tokens) — gated to avoid mis-mapping short tokens.
    if _looks_like_buff_prose(value):
        if "frostburn" in lowered.replace(" ", "") or re.search(
            r"\bfrost\s*burn\b", lowered
        ):
            return "BuffID.Frostburn"
        if re.search(r"\b(burning|burned)\b", lowered) or (
            re.search(r"\bburn\b", lowered) and "frost" not in lowered
        ):
            return "BuffID.OnFire"
        if re.search(r"\b(poisoned|poison)\b", lowered):
            return "BuffID.Poisoned"

    return None


def _normalize_buff_id(value: str) -> str | None:
    """Map free text or aliases to a canonical ``BuffID.*``, or ``None`` if unknown.

    Never returns invented strings — only members of :data:`VALID_BUFF_IDS` or ``None``.
    """
    s = str(value).strip()
    if not s:
        return None
    if s in VALID_BUFF_IDS:
        return s
    if s in _BUFF_DISPLAY_ALIASES:
        return _BUFF_DISPLAY_ALIASES[s]
    ci = _BUFF_DISPLAY_ALIASES_LOWER.get(s.lower())
    if ci is not None:
        return ci
    if s in _BARE_BUFF_LOOKUP:
        return _BARE_BUFF_LOOKUP[s]
    extracted = _extract_buff_id_from_text(s)
    if extracted in VALID_BUFF_IDS:
        return extracted
    return None


def _normalize_ammo_id(value: str) -> str:
    """Accept both ``'Arrow'`` and ``'AmmoID.Arrow'``."""
    if value in VALID_AMMO_IDS:
        return value
    return _BARE_AMMO_LOOKUP.get(value, value)


PROJECTILE_ID_ALIASES = {
    # Common LLM-generated names that don't match the actual ProjectileID field names:
    "ProjectileID.Fireball": "ProjectileID.BallofFire",
    "Fireball": "ProjectileID.BallofFire",
    "FireBall": "ProjectileID.BallofFire",
    "ProjectileID.FireBall": "ProjectileID.BallofFire",
    "FireBolt": "ProjectileID.BallofFire",
    "ProjectileID.FireBolt": "ProjectileID.BallofFire",
    "FlameOrb": "ProjectileID.BallofFire",
    "ProjectileID.FlameOrb": "ProjectileID.BallofFire",
    "SwordBeam": "ProjectileID.StarWrath",
    "ProjectileID.SwordBeam": "ProjectileID.StarWrath",
    "LightBeam": "ProjectileID.LightBlade",
    "ProjectileID.LightBeam": "ProjectileID.LightBlade",
    "LightBolt": "ProjectileID.LightBlade",
    "ProjectileID.LightBolt": "ProjectileID.LightBlade",
    "IceBeam": "ProjectileID.Blizzard",
    "ProjectileID.IceBeam": "ProjectileID.Blizzard",
    "IceBolt": "ProjectileID.IceSickle",
    "ProjectileID.IceBolt": "ProjectileID.IceSickle",
    "FrostBolt": "ProjectileID.FrostBoltSword",
    "ProjectileID.FrostBolt": "ProjectileID.FrostBoltSword",
    "FrostBeam": "ProjectileID.FrostBoltSword",
    "ProjectileID.FrostBeam": "ProjectileID.FrostBoltSword",
    "ShadowBolt": "ProjectileID.ShadowBeam",
    "ProjectileID.ShadowBolt": "ProjectileID.ShadowBeam",
    "DarkBolt": "ProjectileID.ShadowBeam",
    "ProjectileID.DarkBolt": "ProjectileID.ShadowBeam",
    "DarkBeam": "ProjectileID.ShadowBeam",
    "ProjectileID.DarkBeam": "ProjectileID.ShadowBeam",
    "MagicBolt": "ProjectileID.MagicMissile",
    "ProjectileID.MagicBolt": "ProjectileID.MagicMissile",
    "MagicBeam": "ProjectileID.MagicMissile",
    "ProjectileID.MagicBeam": "ProjectileID.MagicMissile",
    "VoidBolt": "ProjectileID.ShadowBeam",
    "ProjectileID.VoidBolt": "ProjectileID.ShadowBeam",
    "VoidBeam": "ProjectileID.ShadowBeam",
    "ProjectileID.VoidBeam": "ProjectileID.ShadowBeam",
    "StarBeam": "ProjectileID.Starfury",
    "ProjectileID.StarBeam": "ProjectileID.Starfury",
    "StarBolt": "ProjectileID.Starfury",
    "ProjectileID.StarBolt": "ProjectileID.Starfury",
    "LavaOrb": "ProjectileID.BallofFire",
    "ProjectileID.LavaOrb": "ProjectileID.BallofFire",
    "LavaBolt": "ProjectileID.BallofFire",
    "ProjectileID.LavaBolt": "ProjectileID.BallofFire",
    "ThunderBolt": "ProjectileID.BallLightning",
    "ProjectileID.ThunderBolt": "ProjectileID.BallLightning",
    "LightningBolt": "ProjectileID.BallLightning",
    "ProjectileID.LightningBolt": "ProjectileID.BallLightning",
}

# User-facing crafting station name → tModLoader TileID constant
STATION_TILE_MAP: dict[str, str] = {
    "By Hand": "",  # no tile required
    "Workbench": "TileID.WorkBenches",
    "Iron Anvil": "TileID.Anvils",
    "Mythril Anvil": "TileID.MythrilAnvil",
    "Ancient Manipulator": "TileID.LunarCraftingStation",
}

# Thematic keyword -> material mapping.  First match wins.
THEME_MATERIAL_MAP: dict[tuple[str, ...], str] = {
    ("fire", "magma", "hell"): "ItemID.HellstoneBar",
    ("ice", "frost", "cold"): "ItemID.IceBlock",
    ("jungle", "grass", "spore"): "ItemID.JungleSpores",
    ("dark", "evil", "shadow"): "ItemID.DemoniteBar",
    ("light", "holy", "angel"): "ItemID.HallowedBar",
}


# ---------------------------------------------------------------------------
# Crafting resolution (deterministic, no LLM)
# ---------------------------------------------------------------------------


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _clamp_icon_size(
    icon_size: list[int], lo: int, hi: int, default: list[int]
) -> list[int]:
    if not isinstance(icon_size, list) or len(icon_size) != 2:
        icon_size = default
    w, h = int(icon_size[0]), int(icon_size[1])
    return [_clamp(w, lo, hi), _clamp(h, lo, hi)]


def _normalize_projectile_id(value: str | None) -> str | None:
    if value in (None, ""):
        return None

    return PROJECTILE_ID_ALIASES.get(str(value), str(value))


def _lower_combat_package_fields(values: dict) -> dict:
    if not isinstance(values, dict):
        return values

    values["resolved_combat"] = None

    mechanics = values.get("mechanics")
    if not isinstance(mechanics, dict):
        return values

    combat_package = mechanics.get("combat_package")
    resolved_combat = None
    if combat_package:
        _require_combat_package_companion_fields(mechanics)

        presentation = values.get("presentation")
        if not isinstance(presentation, dict) or not presentation.get("fx_profile"):
            raise ValueError(
                "presentation.fx_profile is required when combat_package is set"
            )

        content_type = values.get("content_type") or values.get("type") or "Weapon"
        sub_type = values.get("sub_type") or "Sword"
        resolved_combat = resolve_combat_package(
            package_key=combat_package,
            content_type=content_type,
            sub_type=sub_type,
            delivery_style=mechanics.get("delivery_style"),
            payoff_rate=mechanics.get("payoff_rate"),
            fx_profile=presentation.get("fx_profile"),
        )
        legacy_projection = resolved_combat.legacy_projection
        mechanics["shot_style"] = legacy_projection.shot_style
        mechanics["custom_projectile"] = legacy_projection.custom_projectile
        mechanics["shoot_projectile"] = legacy_projection.shoot_projectile
        values["resolved_combat"] = resolved_combat

    projectile_visuals = values.get("projectile_visuals")
    projectile_visuals_required = False
    if resolved_combat is not None:
        projectile_visuals_required = (
            resolved_combat.legacy_projection.projectile_visuals_required
        )
    else:
        projectile_visuals_required = bool(mechanics.get("custom_projectile"))

    if projectile_visuals_required and projectile_visuals in (None, ""):
        visuals = (
            values.get("visuals") if isinstance(values.get("visuals"), dict) else {}
        )
        values["projectile_visuals"] = {
            "description": str(visuals.get("description") or ""),
        }

    return values


def _require_combat_package_companion_fields(model):
    def _get(source, field_name: str):
        if isinstance(source, dict):
            return source.get(field_name)
        return getattr(source, field_name, None)

    combat_package = _get(model, "combat_package")
    if not combat_package:
        return model

    missing_fields = [
        field_name
        for field_name in ("delivery_style", "payoff_rate")
        if _get(model, field_name) is None
    ]
    if missing_fields:
        required_fields = " and ".join(missing_fields)
        raise ValueError(f"combat_package requires {required_fields}")

    return model


def resolve_crafting(
    user_prompt: str, tier: str, crafting_station: str | None = None
) -> dict:
    """Deterministically resolve crafting material, cost, and tile from the
    user prompt and selected tier.  Thematic keywords take priority; the tier
    default is used as a fallback.
    """
    if tier not in VALID_TIERS:
        raise ValueError(
            f"Unknown tier: {tier!r}. Must be one of {sorted(VALID_TIERS)}"
        )

    tier_data = TIER_TABLE[tier]
    prompt_lower = user_prompt.lower()

    # Step A: scan for thematic keywords
    material: str | None = None
    for keywords, mat in THEME_MATERIAL_MAP.items():
        if any(kw in prompt_lower for kw in keywords):
            material = mat
            break

    # Step B: tier-based fallback
    if material is None:
        material = tier_data["default_materials"][0]

    # Step C: cost scaling – pick midpoint of tier range
    cost_lo, cost_hi = tier_data["crafting_cost"]
    crafting_cost = (cost_lo + cost_hi) // 2

    # Step D: honour explicit station override from the wizard
    tile = tier_data["crafting_tile"]
    if crafting_station and crafting_station in STATION_TILE_MAP:
        tile = STATION_TILE_MAP[crafting_station]

    return {
        "crafting_material": material,
        "crafting_cost": crafting_cost,
        "crafting_tile": tile,
    }


# ---------------------------------------------------------------------------
# Pydantic sub-models
# ---------------------------------------------------------------------------


class LLMStats(BaseModel):
    """Stats as produced by the LLM (unconstrained)."""

    damage: int
    knockback: float
    crit_chance: int = 4
    use_time: int
    auto_reuse: bool = True
    rarity: str = ""


class LLMVisuals(BaseModel):
    color_palette: list[str] = Field(default_factory=list)
    description: str = ""
    icon_size: list[int] = Field(default=[48, 48])

    @field_validator("icon_size", mode="before")
    @classmethod
    def clamp_icon_size(cls, v):
        return _clamp_icon_size(v, lo=40, hi=64, default=[48, 48])


class ProjectileVisuals(BaseModel):
    """Visual specification for a custom projectile sprite."""

    description: str = ""
    icon_size: list[int] = Field(default=[16, 16])

    @field_validator("icon_size", mode="before")
    @classmethod
    def clamp_icon_size(cls, v):
        return _clamp_icon_size(v, lo=10, hi=50, default=[16, 16])


class Presentation(BaseModel):
    fx_profile: FxProfileLiteral


class LLMMechanics(BaseModel):
    """Mechanics from the LLM.

    ``on_hit_buff`` / ``buff_id`` use :class:`BuffIDLiteral` so JSON Schema exposes a
    closed enum to the model; ``mode="before"`` validators still map prose aliases
    onto those same IDs (or ``None``).
    """

    shoot_projectile: Optional[str] = None
    on_hit_buff: Optional[BuffIDLiteral] = None
    buff_id: Optional[BuffIDLiteral] = None
    ammo_id: Optional[AmmoIDLiteral] = None
    combat_package: Optional[CombatPackageLiteral] = None
    delivery_style: Optional[DeliveryStyleLiteral] = None
    payoff_rate: Optional[PayoffRateLiteral] = None
    custom_projectile: bool = False
    shot_style: ShotStyleLiteral = "direct"
    crafting_material: Optional[str] = None
    crafting_cost: Optional[int] = None
    crafting_tile: Optional[str] = None

    @field_validator("on_hit_buff", "buff_id", mode="before")
    @classmethod
    def validate_buff_ids(cls, value):
        if value in (None, ""):
            return None
        raw = str(value)
        normalized = _normalize_buff_id(raw)
        if normalized is not None:
            return normalized
        log.warning("Dropping unrecognisable buff value from LLM: %r", raw)
        return None

    @field_validator("ammo_id", mode="before")
    @classmethod
    def validate_ammo_ids(cls, value):
        if value in (None, ""):
            return None
        normalized = _normalize_ammo_id(str(value))
        if normalized in VALID_AMMO_IDS:
            return normalized
        log.warning("Dropping unrecognisable ammo value from LLM: %r", value)
        return None

    @field_validator("shoot_projectile", mode="before")
    @classmethod
    def normalize_projectile_ids(cls, value):
        return _normalize_projectile_id(value)

    @model_validator(mode="after")
    def coerce_custom_projectile(self):
        """custom_projectile is only meaningful for shot_style='direct'."""
        if self.shot_style != "direct":
            self.custom_projectile = False
        return _require_combat_package_companion_fields(self)


class AccessoryStats(BaseModel):
    defense: int = 0
    life_regen: int = 0
    movement_speed: float = 0.0
    rarity: str = ""


class SummonStats(BaseModel):
    damage: int = 0
    knockback: float = 0.0
    use_time: int = 0
    minion_slots: float = 1.0
    rarity: str = ""


class ConsumableStats(BaseModel):
    use_time: int = 0
    heal_amount: int = 0
    mana_restore: int = 0
    stack_size: int = 1
    rarity: str = ""


class ToolStats(BaseModel):
    use_time: int = 0
    power: int = 0
    axe_power: int = 0
    pick_power: int = 0
    hammer_power: int = 0
    rarity: str = ""


class LLMItemOutput(BaseModel):
    """Schema given to `with_structured_output()`.  No clamping here."""

    item_name: str
    display_name: str
    tooltip: str = ""
    content_type: Literal["Weapon", "Accessory", "Summon", "Consumable", "Tool"] = (
        "Weapon"
    )
    type: str = "Weapon"
    sub_type: Optional[str] = None
    stats: LLMStats
    visuals: LLMVisuals = Field(default_factory=LLMVisuals)
    presentation: Optional[Presentation] = None
    mechanics: LLMMechanics = Field(default_factory=LLMMechanics)
    accessory_stats: Optional[AccessoryStats] = None
    summon_stats: Optional[SummonStats] = None
    consumable_stats: Optional[ConsumableStats] = None
    tool_stats: Optional[ToolStats] = None
    projectile_visuals: Optional[ProjectileVisuals] = None
    reference_needed: bool = False
    reference_subject: Optional[str] = None
    reference_image_url: Optional[str] = None
    generation_mode: Literal["text_to_image", "image_to_image"] = "text_to_image"
    reference_attempts: int = 0
    reference_notes: Optional[str] = None
    fallback_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Validated / clamped output models
# ---------------------------------------------------------------------------


class Stats(BaseModel):
    """Stats with tier-enforced clamping."""

    damage: int
    knockback: float
    crit_chance: int = 4
    use_time: int
    auto_reuse: bool = True
    rarity: str

    @model_validator(mode="before")
    @classmethod
    def clamp_to_tier(cls, values, info):  # noqa: N805
        ctx = info.context or {}
        tier = ctx.get("tier")
        if tier and tier in TIER_TABLE:
            td = TIER_TABLE[tier]
            dmg_lo, dmg_hi = td["damage"]
            ut_lo, ut_hi = td["use_time"]
            values["damage"] = _clamp(int(values.get("damage", dmg_lo)), dmg_lo, dmg_hi)
            values["use_time"] = _clamp(
                int(values.get("use_time", ut_lo)), ut_lo, ut_hi
            )
            values["rarity"] = td["rarity"]
        return values


class Visuals(BaseModel):
    color_palette: list[str] = Field(default_factory=list)
    description: str = ""
    icon_size: list[int] = Field(default=[48, 48])

    @field_validator("color_palette", mode="before")
    @classmethod
    def validate_hex(cls, v):
        validated = []
        for c in v:
            c = str(c).strip()
            if not re.match(r"^#[0-9A-Fa-f]{6}$", c):
                continue  # drop invalid hex codes silently
            validated.append(c)
        return validated

    @field_validator("icon_size", mode="before")
    @classmethod
    def clamp_icon_size(cls, v):
        return _clamp_icon_size(v, lo=40, hi=64, default=[48, 48])


class Mechanics(BaseModel):
    shoot_projectile: Optional[str] = None
    on_hit_buff: Optional[BuffIDLiteral] = None
    buff_id: Optional[BuffIDLiteral] = None
    ammo_id: Optional[AmmoIDLiteral] = None
    combat_package: Optional[CombatPackageLiteral] = None
    delivery_style: Optional[DeliveryStyleLiteral] = None
    payoff_rate: Optional[PayoffRateLiteral] = None
    custom_projectile: bool = False
    shot_style: ShotStyleLiteral = "direct"
    crafting_material: str
    crafting_cost: int
    crafting_tile: str

    @field_validator("on_hit_buff", "buff_id", mode="before")
    @classmethod
    def validate_buff_ids(cls, value):
        if value in (None, ""):
            return None
        raw = str(value)
        normalized = _normalize_buff_id(raw)
        if normalized is not None:
            return normalized
        log.warning("Dropping unrecognisable buff value: %r", raw)
        return None

    @field_validator("ammo_id", mode="before")
    @classmethod
    def validate_ammo_ids(cls, value):
        if value in (None, ""):
            return None
        normalized = _normalize_ammo_id(str(value))
        if normalized in VALID_AMMO_IDS:
            return normalized
        log.warning("Dropping unrecognisable ammo value: %r", value)
        return None

    @field_validator("shoot_projectile", mode="before")
    @classmethod
    def normalize_projectile_ids(cls, value):
        return _normalize_projectile_id(value)

    @model_validator(mode="after")
    def coerce_custom_projectile(self):
        """custom_projectile is only meaningful for shot_style='direct'."""
        if self.shot_style != "direct":
            self.custom_projectile = False
        return _require_combat_package_companion_fields(self)


try:
    from core.utils import to_pascal_case as _to_pascal_case
except ImportError:
    from pathlib import Path as _Path

    _parent = str(_Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from core.utils import to_pascal_case as _to_pascal_case


class ItemManifest(BaseModel):
    """Fully validated item manifest – the contract for downstream agents."""

    item_name: str
    display_name: str
    tooltip: str = ""
    content_type: Literal["Weapon", "Accessory", "Summon", "Consumable", "Tool"] = (
        "Weapon"
    )
    type: str = "Weapon"
    sub_type: str = "Sword"
    stats: Stats
    visuals: Visuals = Field(default_factory=Visuals)
    presentation: Optional[Presentation] = None
    mechanics: Mechanics
    accessory_stats: Optional[AccessoryStats] = None
    summon_stats: Optional[SummonStats] = None
    consumable_stats: Optional[ConsumableStats] = None
    tool_stats: Optional[ToolStats] = None
    projectile_visuals: Optional[ProjectileVisuals] = None
    resolved_combat: Optional[ResolvedCombat] = None
    reference_needed: bool = False
    reference_subject: Optional[str] = None
    reference_image_url: Optional[str] = None
    generation_mode: Literal["text_to_image", "image_to_image"] = "text_to_image"
    reference_attempts: int = 0
    reference_notes: Optional[str] = None
    fallback_reason: Optional[str] = None

    @field_validator("item_name", mode="before")
    @classmethod
    def sanitize_item_name(cls, v):
        return _to_pascal_case(str(v))

    @field_validator("content_type", mode="before")
    @classmethod
    def normalize_content_type(cls, value):
        if value in (None, ""):
            return "Weapon"
        value = str(value)
        if value not in VALID_CONTENT_TYPES:
            raise ValueError(
                f"Unknown content_type: {value!r}. Must be one of {sorted(VALID_CONTENT_TYPES)}"
            )
        return value

    @model_validator(mode="before")
    @classmethod
    def seed_legacy_defaults(cls, values):
        if not isinstance(values, dict):
            return values
        if "content_type" not in values or values.get("content_type") in (None, ""):
            legacy_type = values.get("type")
            values["content_type"] = (
                legacy_type if legacy_type in VALID_CONTENT_TYPES else "Weapon"
            )
        return _lower_combat_package_fields(values)

    @model_validator(mode="after")
    def normalize_reference_fields(self):
        if not self.reference_needed:
            self.reference_subject = None
            self.reference_image_url = None
            self.generation_mode = "text_to_image"
            if not self.reference_notes:
                self.reference_notes = "reference_not_requested"
            return self

        if self.reference_image_url:
            self.generation_mode = "image_to_image"
            return self

        self.generation_mode = "text_to_image"
        if not self.reference_notes:
            self.reference_notes = "reference_missing_or_rejected"
        return self
