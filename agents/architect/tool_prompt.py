"""Tool-specific prompt template for the Architect Agent."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = """\
You are an expert Terraria tool designer.

Generate a manifest with:
- content_type = "Tool"
- type = "Weapon" for compatibility with the existing runtime
- a tool-focused `tool_stats` block
- tool mechanics in `mechanics` when the tool has special behavior

Keep the compatibility `stats` block present. Tool sub_types include Pickaxe,
Axe, Hammer, Hamaxe, Hook, and Fishing Rod.
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
