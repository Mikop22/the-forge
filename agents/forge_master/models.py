"""Pydantic models for the Forge Master agent."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_pascal_case(name: str) -> str:
    """Sanitize a string into a valid PascalCase C# identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", " ", name)
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
    return "".join(word.capitalize() for word in cleaned.split())


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
    custom_projectile: bool = False
    crafting_material: str
    crafting_cost: int
    crafting_tile: str


class ProjectileVisuals(BaseModel):
    """Visual specification for a custom projectile sprite."""
    description: str = ""
    icon_size: list[int] = Field(default=[16, 16])


class ForgeManifest(BaseModel):
    """Validated input contract from the Architect agent."""

    item_name: str
    display_name: str
    tooltip: str = ""
    type: str = "Weapon"
    sub_type: str = "Sword"
    stats: ManifestStats
    mechanics: ManifestMechanics
    projectile_visuals: Optional[ProjectileVisuals] = None

    @field_validator("item_name", mode="before")
    @classmethod
    def sanitize_item_name(cls, v: str) -> str:
        return _to_pascal_case(str(v))


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
