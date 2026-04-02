"""Pydantic models, tier lookup tables, and crafting resolution for the Architect Agent."""

from __future__ import annotations

import re
import sys
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

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
VALID_BUFF_IDS = {
    "BuffID.OnFire",
    "BuffID.Frostburn",
    "BuffID.Slimed",
    "BuffID.WellFed",
    "BuffID.ManaSickness",
    "BuffID.Poisoned",
    "BuffID.ShadowFlame",
    "BuffID.CursedInferno",
}
VALID_AMMO_IDS = {
    "AmmoID.Arrow",
    "AmmoID.Bullet",
    "AmmoID.Rocket",
    "AmmoID.Dart",
    "AmmoID.Sand",
    "AmmoID.Gel",
    "AmmoID.Snowball",
    "AmmoID.Coin",
    "AmmoID.Flare",
}

# User-facing crafting station name → tModLoader TileID constant
STATION_TILE_MAP: dict[str, str] = {
    "By Hand":            "",                              # no tile required
    "Workbench":          "TileID.WorkBenches",
    "Iron Anvil":         "TileID.Anvils",
    "Mythril Anvil":      "TileID.MythrilAnvil",
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


def _clamp_icon_size(icon_size: list[int], lo: int, hi: int, default: list[int]) -> list[int]:
    if not isinstance(icon_size, list) or len(icon_size) != 2:
        icon_size = default
    w, h = int(icon_size[0]), int(icon_size[1])
    return [_clamp(w, lo, hi), _clamp(h, lo, hi)]


def resolve_crafting(user_prompt: str, tier: str, crafting_station: str | None = None) -> dict:
    """Deterministically resolve crafting material, cost, and tile from the
    user prompt and selected tier.  Thematic keywords take priority; the tier
    default is used as a fallback.
    """
    if tier not in VALID_TIERS:
        raise ValueError(f"Unknown tier: {tier!r}. Must be one of {sorted(VALID_TIERS)}")

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
    icon_size: list[int] = Field(default=[32, 32])

    @field_validator("icon_size", mode="before")
    @classmethod
    def clamp_icon_size(cls, v):
        return _clamp_icon_size(v, lo=32, hi=64, default=[32, 32])


class ProjectileVisuals(BaseModel):
    """Visual specification for a custom projectile sprite."""
    description: str = ""
    icon_size: list[int] = Field(default=[16, 16])

    @field_validator("icon_size", mode="before")
    @classmethod
    def clamp_icon_size(cls, v):
        return _clamp_icon_size(v, lo=10, hi=50, default=[16, 16])


class LLMMechanics(BaseModel):
    shoot_projectile: Optional[str] = None
    on_hit_buff: Optional[str] = None
    buff_id: Optional[str] = None
    ammo_id: Optional[str] = None
    custom_projectile: bool = False
    crafting_material: Optional[str] = None
    crafting_cost: Optional[int] = None
    crafting_tile: Optional[str] = None

    @field_validator("on_hit_buff", "buff_id", mode="before")
    @classmethod
    def validate_buff_ids(cls, value):
        if value in (None, ""):
            return None
        value = str(value)
        if value not in VALID_BUFF_IDS:
            raise ValueError(
                f"Unknown BuffID: {value!r}. Must be one of {sorted(VALID_BUFF_IDS)}"
            )
        return value

    @field_validator("ammo_id", mode="before")
    @classmethod
    def validate_ammo_ids(cls, value):
        if value in (None, ""):
            return None
        value = str(value)
        if value not in VALID_AMMO_IDS:
            raise ValueError(
                f"Unknown AmmoID: {value!r}. Must be one of {sorted(VALID_AMMO_IDS)}"
            )
        return value


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
    content_type: Literal["Weapon", "Accessory", "Summon", "Consumable", "Tool"] = "Weapon"
    type: str = "Weapon"
    sub_type: str = "Sword"
    stats: LLMStats
    visuals: LLMVisuals = Field(default_factory=LLMVisuals)
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
            values["use_time"] = _clamp(int(values.get("use_time", ut_lo)), ut_lo, ut_hi)
            values["rarity"] = td["rarity"]
        return values


class Visuals(BaseModel):
    color_palette: list[str] = Field(default_factory=list)
    description: str = ""
    icon_size: list[int] = Field(default=[32, 32])

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
        return _clamp_icon_size(v, lo=32, hi=64, default=[32, 32])


class Mechanics(BaseModel):
    shoot_projectile: Optional[str] = None
    on_hit_buff: Optional[str] = None
    buff_id: Optional[str] = None
    ammo_id: Optional[str] = None
    custom_projectile: bool = False
    crafting_material: str
    crafting_cost: int
    crafting_tile: str

    @field_validator("on_hit_buff", "buff_id", mode="before")
    @classmethod
    def validate_buff_ids(cls, value):
        if value in (None, ""):
            return None
        value = str(value)
        if value not in VALID_BUFF_IDS:
            raise ValueError(
                f"Unknown BuffID: {value!r}. Must be one of {sorted(VALID_BUFF_IDS)}"
            )
        return value

    @field_validator("ammo_id", mode="before")
    @classmethod
    def validate_ammo_ids(cls, value):
        if value in (None, ""):
            return None
        value = str(value)
        if value not in VALID_AMMO_IDS:
            raise ValueError(
                f"Unknown AmmoID: {value!r}. Must be one of {sorted(VALID_AMMO_IDS)}"
            )
        return value


try:
    from utils import to_pascal_case as _to_pascal_case
except ImportError:
    # Fallback: parent directory may not be on sys.path
    from pathlib import Path as _Path
    _parent = str(_Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from utils import to_pascal_case as _to_pascal_case


class ItemManifest(BaseModel):
    """Fully validated item manifest – the contract for downstream agents."""
    item_name: str
    display_name: str
    tooltip: str = ""
    content_type: Literal["Weapon", "Accessory", "Summon", "Consumable", "Tool"] = "Weapon"
    type: str = "Weapon"
    sub_type: str = "Sword"
    stats: Stats
    visuals: Visuals = Field(default_factory=Visuals)
    mechanics: Mechanics
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
            values["content_type"] = legacy_type if legacy_type in VALID_CONTENT_TYPES else "Weapon"
        return values

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
