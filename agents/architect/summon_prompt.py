"""Summon-specific prompt template for the Architect Agent."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = """\
You are an expert Terraria summon weapon designer.

Generate a manifest with:
- content_type = "Summon"
- type = "Weapon" for compatibility with the existing runtime
- a summon-focused `summon_stats` block
- summon mechanics in `mechanics`, especially a valid `buff_id` when the item
  needs a minion-summoning buff

Keep the compatibility `stats` block present. Describe the summon as a staff,
whip, or similar summon weapon presentation.
"""

HUMAN_PROMPT = """\
User idea: {user_prompt}
Selected Tier: {selected_tier}
Content Type: {content_type}
Sub Type: {sub_type}
"""


def build_prompt(sub_type: str = "Staff") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ])
