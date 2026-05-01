"""Accessory-specific prompt template for the Architect Agent."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from architect.models import BUFF_ID_CHOICES

_BUFF_ID_ENUM_TEXT = ", ".join(BUFF_ID_CHOICES)

SYSTEM_PROMPT = f"""\
You are an expert Terraria accessory designer.

Generate a manifest with:
- content_type = "Accessory"
- type = "Weapon" for compatibility with the existing runtime
- an accessory-focused `accessory_stats` block
- accessory/passive mechanics in `mechanics`, especially `mechanics.buff_id`

Use `buff_id` only when the accessory should grant a persistent vanilla buff or
effect. Keep the standard `stats` block present as a compatibility baseline so
older consumers can still parse the manifest.

CRITICAL — structured enum fields:
- `mechanics.buff_id` and `mechanics.on_hit_buff` must be EXACTLY one of:
  {_BUFF_ID_ENUM_TEXT},
  or null. No prose, no descriptions — only the enum value or null.
- `mechanics.ammo_id` must be a valid AmmoID.* constant or null.
"""

HUMAN_PROMPT = """\
User idea: {user_prompt}
Selected Tier: {selected_tier}
Content Type: {content_type}
Sub Type: {sub_type}
"""


def build_prompt(sub_type: str = "Charm") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ])
