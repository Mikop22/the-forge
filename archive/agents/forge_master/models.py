"""Pydantic models for the Forge Master agent."""

from __future__ import annotations

import re
import sys
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

try:
    from architect.models import Presentation, ShotStyleLiteral
except ImportError:
    from pathlib import Path as _Path2

    _parent2 = str(_Path2(__file__).resolve().parent.parent)
    if _parent2 not in sys.path:
        sys.path.insert(0, _parent2)
    from architect.models import Presentation, ShotStyleLiteral

try:
    from core.combat_packages import (
        CombatPackageLiteral,
        DeliveryStyleLiteral,
        PayoffRateLiteral,
        ResolvedCombat,
    )
except ImportError:
    from pathlib import Path as _Path3

    _parent3 = str(_Path3(__file__).resolve().parent.parent)
    if _parent3 not in sys.path:
        sys.path.insert(0, _parent3)
    from core.combat_packages import (
        CombatPackageLiteral,
        DeliveryStyleLiteral,
        PayoffRateLiteral,
        ResolvedCombat,
    )

try:
    from core.utils import to_pascal_case as _to_pascal_case
except ImportError:
    from pathlib import Path as _Path

    _parent = str(_Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from core.utils import to_pascal_case as _to_pascal_case


# ---------------------------------------------------------------------------
# Input model – the Architect's manifest
# ---------------------------------------------------------------------------


class ManifestStats(BaseModel):
    damage: int
    knockback: float = 4.0
    crit_chance: int = 4
    use_time: int
    auto_reuse: bool = True
    rarity: str


class ManifestMechanics(BaseModel):
    shoot_projectile: Optional[str] = None
    on_hit_buff: Optional[str] = None
    combat_package: Optional[CombatPackageLiteral] = None
    delivery_style: Optional[DeliveryStyleLiteral] = None
    payoff_rate: Optional[PayoffRateLiteral] = None
    custom_projectile: bool = False
    shot_style: ShotStyleLiteral = "direct"
    crafting_material: str
    crafting_cost: int
    crafting_tile: str

    @model_validator(mode="after")
    def coerce_custom_projectile(self):
        """custom_projectile is only meaningful for shot_style='direct'."""
        if self.shot_style != "direct":
            self.custom_projectile = False
        return self


class ManifestToolStats(BaseModel):
    use_time: int = 0
    power: int = 0
    axe_power: int = 0
    pick_power: int = 0
    pickaxe_power: int = 0
    hammer_power: int = 0
    rarity: str = ""


class ProjectileVisuals(BaseModel):
    """Visual specification for a custom projectile sprite."""

    description: str = ""
    icon_size: list[int] = Field(default=[16, 16])
    foreground_bbox: list[int] = Field(default_factory=list)
    hitbox_size: list[int] = Field(default_factory=list)
    animation_tier: str = "static"

    @field_validator("animation_tier", mode="before")
    @classmethod
    def validate_animation_tier(cls, v: object) -> str:
        value = str(v or "static").strip()
        low = value.lower().replace(" ", "").replace("-", "_")
        if low in ("tier3", "tier_3", "t3"):
            return "generated_frames:3"
        if low in ("tier2", "tier_2", "t2"):
            return "generated_frames:2"
        if value == "static":
            return value
        if re.match(r"^(?:vanilla_frames|generated_frames):[1-9]\d*$", value):
            return value
        raise ValueError(
            "animation_tier must be static, vanilla_frames:N, or generated_frames:N"
        )


class SpectacleBasis(BaseModel):
    cast_shape: list[str] = Field(default_factory=list)
    projectile_body: list[str] = Field(default_factory=list)
    motion_grammar: list[str] = Field(default_factory=list)
    payoff: list[str] = Field(default_factory=list)
    visual_language: list[str] = Field(default_factory=list)
    world_interaction: list[str] = Field(default_factory=list)


class SpectaclePlan(BaseModel):
    """Authoring brief for bespoke Tier-3 projectile codegen."""

    fantasy: str = ""
    basis: SpectacleBasis = Field(default_factory=SpectacleBasis)
    composition: str = ""
    movement: str = ""
    render_passes: list[str] = Field(default_factory=list)
    ai_phases: list[str] = Field(default_factory=list)
    impact_payoff: str = ""
    sound_profile: str = ""
    must_not_include: list[str] = Field(default_factory=list)
    must_not_feel_like: list[str] = Field(default_factory=list)


MechanicsAtomKind = Literal[
    "charge_phase",
    "singularity_projectile",
    "beam_lance",
    "gravity_pull_field",
    "rift_trail",
    "implosion_payoff",
    "shock_ring_damage",
    "bounded_terrain_carve",
    "orbiting_convergence",
    "delayed_detonation",
    "summoned_construct",
    "channel_cast",
    "staged_release",
    "rift_projectile",
    "slow_drift",
    "ricochet_path",
    "portal_hop",
    "time_slow_field",
    "tile_scorch",
    "satellite_fusion",
    "phase_swap",
    "inward_particle_flow",
    "color_separation_distortion",
]


class MechanicsAtom(BaseModel):
    """Executable Tier-3 capability atom selected by the planner."""

    kind: MechanicsAtomKind
    duration_ticks: Optional[int] = None
    radius_tiles: Optional[int] = None
    tile_limit: Optional[int] = None
    speed: Optional[str] = None
    strength: Optional[str] = None
    scale_pulse: Optional[bool] = None
    count: Optional[int] = None
    width_tiles: Optional[int] = None
    length_tiles: Optional[int] = None
    angle_degrees: Optional[int] = None
    notes: str = ""


class MechanicsIR(BaseModel):
    """Typed executable contract for Tier-3 bespoke codegen."""

    atoms: list[MechanicsAtom] = Field(default_factory=list)
    forbidden_atoms: list[str] = Field(default_factory=list)
    composition: str = ""


class ReferenceSlot(BaseModel):
    needed: bool = False
    subject: str = ""
    protected_terms: list[str] = Field(default_factory=list)
    image_url: str = ""
    generation_mode: Literal["text_to_image", "image_to_image"] = "text_to_image"

    @model_validator(mode="after")
    def normalize_generation_mode(self):
        if self.image_url:
            self.generation_mode = "image_to_image"
        return self


class ReferenceSlots(BaseModel):
    item: ReferenceSlot = Field(default_factory=ReferenceSlot)
    projectile: ReferenceSlot = Field(default_factory=ReferenceSlot)


class ForgeManifest(BaseModel):
    """Validated input contract from the Architect agent."""

    item_name: str
    display_name: str
    tooltip: str = ""
    content_type: str = "Weapon"
    type: str = "Weapon"
    sub_type: str = "Sword"
    stats: ManifestStats
    mechanics: ManifestMechanics
    tool_stats: Optional[ManifestToolStats] = None
    presentation: Optional[Presentation] = None
    projectile_visuals: Optional[ProjectileVisuals] = None
    spectacle_plan: Optional[SpectaclePlan] = None
    mechanics_ir: Optional[MechanicsIR] = None
    references: ReferenceSlots = Field(default_factory=ReferenceSlots)
    resolved_combat: Optional[ResolvedCombat] = None
    fallback_reason: Optional[str] = None

    @field_validator("item_name", mode="before")
    @classmethod
    def sanitize_item_name(cls, v: str) -> str:
        return _to_pascal_case(str(v))

    @model_validator(mode="after")
    def require_resolved_combat_for_package_manifests(self):
        if self.mechanics.combat_package and self.resolved_combat is None:
            raise ValueError(
                "resolved_combat is required when mechanics.combat_package is present"
            )
        return self


# ---------------------------------------------------------------------------
# LLM structured-output schema
# ---------------------------------------------------------------------------


class CSharpOutput(BaseModel):
    """Schema given to ``with_structured_output()`` for code generation."""

    code: str = Field(description="Complete C# source file for the ModItem class.")


# ---------------------------------------------------------------------------
# Agent output models
# ---------------------------------------------------------------------------


class ForgeError(BaseModel):
    code: str = Field(description="Compiler error code, e.g. 'CS0103'.")
    message: str = Field(description="Human-readable failure description.")


class ForgeOutput(BaseModel):
    """Final output returned by ``CoderAgent.write_code``."""

    cs_code: str = ""
    hjson_code: str = ""
    status: Literal["success", "error"] = "success"
    error: Optional[ForgeError] = None
