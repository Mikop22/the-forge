"""Pydantic models for the Pixelsmith art-generation agent."""

from __future__ import annotations

import re
import sys
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from core.cross_consistency import CrossConsistencyVerdict
from core.weapon_lab_archive import WeaponLabArchive

try:
    from core.utils import to_pascal_case as _to_pascal_case
except ImportError:
    from pathlib import Path as _Path

    _parent = str(_Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from core.utils import to_pascal_case as _to_pascal_case


# ---------------------------------------------------------------------------
# Input models — slice of the Architect manifest
# ---------------------------------------------------------------------------

ArtDirectionProfileLiteral = Literal["conservative", "balanced", "exploratory"]
GenerationStrategyBucketLiteral = Literal["tight", "balanced", "wide"]
SpriteKindLiteral = Literal["item", "projectile"]


class ArtDirectionStrategy(BaseModel):
    """High-level generation strategy derived from a bounded art profile."""

    profile: ArtDirectionProfileLiteral
    strategy_bucket: GenerationStrategyBucketLiteral
    variant_count: int = Field(ge=1)
    prompt_intensity: Literal["literal", "balanced", "expressive"]


class SpriteGateCheck(BaseModel):
    """Single deterministic sprite gate result."""

    passed: bool
    value: float
    threshold: float
    comparator: Literal["min", "max"]
    detail: str = ""


class SpriteGateReport(BaseModel):
    """Deterministic gate summary for a rendered sprite candidate."""

    sprite_kind: SpriteKindLiteral
    passed: bool
    foreground_bbox: list[int] = Field(default_factory=list)
    checks: dict[str, SpriteGateCheck] = Field(default_factory=dict)


class VisualSpec(BaseModel):
    """Visual specification for a standard item sprite."""

    description: str = ""
    color_palette: list[str] = Field(default_factory=list)
    icon_size: list[int] = Field(default=[32, 32])
    art_direction_profile: ArtDirectionProfileLiteral = "balanced"

    @field_validator("color_palette", mode="before")
    @classmethod
    def validate_hex(cls, v: list) -> list[str]:
        validated = []
        for c in v:
            c = str(c).strip()
            if re.match(r"^#[0-9A-Fa-f]{6}$", c):
                validated.append(c)
        return validated

    @field_validator("icon_size", mode="before")
    @classmethod
    def validate_icon_size(cls, v: list) -> list[int]:
        if len(v) != 2 or any(d < 1 for d in v):
            raise ValueError("icon_size must be [width, height] with positive values")
        return [int(d) for d in v]


class ProjectileVisualSpec(BaseModel):
    """Visual specification for a custom projectile sprite."""

    description: str = ""
    icon_size: list[int] = Field(default=[16, 16])
    art_direction_profile: ArtDirectionProfileLiteral = "balanced"

    @field_validator("icon_size", mode="before")
    @classmethod
    def validate_icon_size(cls, v: list) -> list[int]:
        if len(v) != 2 or any(d < 1 for d in v):
            raise ValueError("icon_size must be [width, height] with positive values")
        return [int(d) for d in v]


class PixelsmithInput(BaseModel):
    """Validated input contract — the relevant slice of an Architect manifest."""

    item_name: str
    type: Literal["Weapon", "Armor", "Projectile", "Material"] = "Weapon"
    sub_type: str = "Sword"
    visuals: VisualSpec = Field(default_factory=VisualSpec)
    projectile_visuals: Optional[ProjectileVisualSpec] = None
    generation_mode: Literal["text_to_image", "image_to_image"] = "text_to_image"
    reference_image_url: Optional[str] = None
    reference_subject: Optional[str] = None
    reference_notes: Optional[str] = None

    @field_validator("item_name", mode="before")
    @classmethod
    def sanitize_item_name(cls, v: str) -> str:
        return _to_pascal_case(str(v))


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class PixelsmithError(BaseModel):
    """Error detail returned when generation fails."""

    code: str = Field(
        description="Short error category, e.g. 'GENERATION', 'PROCESSING'."
    )
    message: str = Field(description="Human-readable failure description.")
    detail: Optional[str] = Field(
        default=None,
        description="Raw technical message (preserved for tests/debugging).",
    )


class PixelsmithOutput(BaseModel):
    """Final output returned by ``ArtistAgent.generate_asset``."""

    item_sprite_path: str = ""
    projectile_sprite_path: Optional[str] = None
    status: Literal["success", "error"] = "success"
    error: Optional[PixelsmithError] = None


class PixelsmithArtScore(BaseModel):
    """Small scored judgement for an art audition candidate."""

    motif_strength: float = Field(ge=0.0, le=10.0)
    family_coherence: float = Field(ge=0.0, le=10.0)
    notes: str = ""


class PixelsmithHiddenAuditionCandidate(BaseModel):
    """One surviving candidate from the hidden art audition."""

    candidate_id: str
    sprite_gate_report: SpriteGateReport
    motif_strength: float = 0.0
    family_coherence: float = 0.0
    judge_notes: str = ""


class PixelsmithObservedArtSignals(BaseModel):
    """Small typed winner-side art signals for consistency checks."""

    item_motif_strength: float = Field(default=0.0, ge=0.0, le=10.0)
    item_family_coherence: float = Field(default=0.0, ge=0.0, le=10.0)
    item_sprite_gate_passed: bool = False


class PixelsmithHiddenAuditionFinalist(BaseModel):
    """Typed art-scored result for one thesis finalist."""

    finalist_id: str
    item_name: str
    item_sprite_path: str
    projectile_sprite_path: str = ""
    item_visual_summary: str = ""
    projectile_visual_summary: str = ""
    observed_art_signals: PixelsmithObservedArtSignals = Field(
        default_factory=PixelsmithObservedArtSignals
    )
    winner_candidate_id: str
    winner_art_scores: PixelsmithArtScore
    winner_sprite_gate_report: SpriteGateReport
    surviving_candidates: list[PixelsmithHiddenAuditionCandidate] = Field(
        default_factory=list
    )


class PixelsmithHiddenAuditionOutput(BaseModel):
    """Hidden Pixelsmith audition output without final weapon selection."""

    status: Literal["success", "error"] = "success"
    art_scored_finalists: list[PixelsmithHiddenAuditionFinalist] = Field(
        default_factory=list
    )
    candidate_archive: WeaponLabArchive
    error: Optional[PixelsmithError] = None


class PixelsmithReviewedHiddenAuditionOutput(PixelsmithHiddenAuditionOutput):
    """Hidden audition output plus explicit cross-consistency verdicts."""

    cross_consistency_reports: dict[str, CrossConsistencyVerdict] = Field(
        default_factory=dict
    )
