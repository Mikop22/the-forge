"""Consumable-specific prompt template for the Architect Agent."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = """\
You are an expert Terraria consumable designer.

Generate a manifest with:
- content_type = "Consumable"
- type = "Weapon" for compatibility with the existing runtime
- a consumable-focused `consumable_stats` block
- consumable mechanics in `mechanics`, especially `ammo_id` or `buff_id`
  when the item behaves like ammo or applies a vanilla buff

Keep the compatibility `stats` block present. The consumable may be a potion,
thrown item, buff item, or ammo-like item depending on the prompt.
"""

HUMAN_PROMPT = """\
User idea: {user_prompt}
Selected Tier: {selected_tier}
Content Type: {content_type}
Sub Type: {sub_type}
"""


def build_prompt(sub_type: str = "Potion") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ])
