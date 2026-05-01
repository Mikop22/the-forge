"""Tool-specific prompt template for the Architect Agent."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from architect.models import BUFF_ID_CHOICES

_BUFF_ID_ENUM_TEXT = ", ".join(BUFF_ID_CHOICES)

SYSTEM_PROMPT = f"""\
You are an expert Terraria tool designer.

Generate a manifest with:
- content_type = "Tool"
- type = "Weapon" for compatibility with the existing runtime
- a tool-focused `tool_stats` block
- tool mechanics in `mechanics` when the tool has special behavior

Keep the compatibility `stats` block present. Tool sub_types include Pickaxe,
Axe, Hammer, Hamaxe, Hook, and Fishing Rod.

CRITICAL — structured enum fields:
- `mechanics.buff_id` and `mechanics.on_hit_buff` must be EXACTLY one of:
  {_BUFF_ID_ENUM_TEXT},
  or null. No prose — only the enum value or null.
"""

HUMAN_PROMPT = """\
User idea: {user_prompt}
Selected Tier: {selected_tier}
Content Type: {content_type}
Sub Type: {sub_type}
"""


def build_prompt(sub_type: str = "Pickaxe") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ])
