"""Prompt router for the Architect Agent."""

from __future__ import annotations

from architect.accessory_prompt import build_prompt as build_accessory_prompt
from architect.consumable_prompt import build_prompt as build_consumable_prompt
from architect.summon_prompt import build_prompt as build_summon_prompt
from architect.tool_prompt import build_prompt as build_tool_prompt
from architect.weapon_thesis_prompt import build_prompt as build_weapon_thesis_prompt
from architect.weapon_prompt import build_prompt as build_weapon_prompt
from architect.models import VALID_CONTENT_TYPES

DEFAULT_SUB_TYPES = {
    "Weapon": "Sword",
    "Accessory": "Charm",
    "Summon": "Staff",
    "Consumable": "Potion",
    "Tool": "Pickaxe",
}


def _normalize_content_type(content_type: str | None) -> str:
    content_type = str(content_type or "Weapon").strip()
    for allowed in VALID_CONTENT_TYPES:
        if content_type.lower() == allowed.lower():
            return allowed
    raise ValueError(
        f"Unknown content_type: {content_type!r}. Must be one of {sorted(VALID_CONTENT_TYPES)}"
    )


def normalize_content_type(content_type: str | None) -> str:
    return _normalize_content_type(content_type)


def build_prompt(content_type: str = "Weapon", sub_type: str = ""):
    """Return the content-type-specific ChatPromptTemplate."""
    normalized = _normalize_content_type(content_type)
    resolved_sub_type = sub_type or DEFAULT_SUB_TYPES[normalized]
    if normalized == "Weapon":
        return build_weapon_prompt(resolved_sub_type)
    if normalized == "Accessory":
        return build_accessory_prompt(resolved_sub_type)
    if normalized == "Summon":
        return build_summon_prompt(resolved_sub_type)
    if normalized == "Consumable":
        return build_consumable_prompt(resolved_sub_type)
    if normalized == "Tool":
        return build_tool_prompt(resolved_sub_type)
    raise ValueError(f"Unsupported content_type: {normalized!r}")
