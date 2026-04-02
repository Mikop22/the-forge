"""Weapon-specific prompt template for the Architect Agent."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = """\
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

Use `mechanics.on_hit_buff` for any on-hit debuff and `mechanics.shoot_projectile`
for projectile weapons. Keep crafting data empty unless the user explicitly
describes a recipe.
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
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ])
