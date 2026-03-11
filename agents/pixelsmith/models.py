"""Pydantic models for the Pixelsmith art-generation agent."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Input models — slice of the Architect manifest
# ---------------------------------------------------------------------------

class VisualSpec(BaseModel):
    """Visual specification for a standard item sprite."""

    description: str = ""
    color_palette: list[str] = Field(default_factory=list)
    icon_size: list[int] = Field(default=[32, 32])

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
        cleaned = re.sub(r"[^a-zA-Z0-9]", " ", str(v))
        cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
        return "".join(word.capitalize() for word in cleaned.split())


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class PixelsmithError(BaseModel):
    """Error detail returned when generation fails."""

    code: str = Field(description="Short error category, e.g. 'GENERATION', 'PROCESSING'.")
    message: str = Field(description="Human-readable failure description.")


class PixelsmithOutput(BaseModel):
    """Final output returned by ``ArtistAgent.generate_asset``."""

    item_sprite_path: str = ""
    projectile_sprite_path: Optional[str] = None
    status: Literal["success", "error"] = "success"
    error: Optional[PixelsmithError] = None
