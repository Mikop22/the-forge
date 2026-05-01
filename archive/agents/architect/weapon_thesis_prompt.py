"""Prompt layer for research-biased weapon thesis generation."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from architect.research_evidence import RESEARCH_RULES


def _render_research_rules() -> str:
    lines = []
    for rule in RESEARCH_RULES:
        generation_fields = ", ".join(
            f"`{field}`" for field in rule.affected_generation_fields
        )
        judge_categories = ", ".join(
            f"`{field}`" for field in rule.affected_judge_categories
        )
        lines.append(f"- Source: {rule.source}")
        lines.append(f"  Rule: {rule.distilled_design_rule}")
        lines.append(f"  Generation fields: {generation_fields}")
        lines.append(f"  Judge categories: {judge_categories}")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""\
You are drafting a compact weapon thesis for the hidden audition flow.

Bias every thesis toward:
- one strong player verb
- a readable seed and cashout loop
- visible escalation with payoff inside 1-3s
- a signature sound and spectacle ladder
- changed player behavior beyond firing another projectile

Use the following research evidence as hard guidance for what the thesis should emphasize:
{_render_research_rules()}

Keep the output compact, auditable, and focused on the loop thesis rather than full manifest details.
"""

HUMAN_PROMPT = """\
User idea: {user_prompt}
Selected Tier: {selected_tier}
Content Type: {content_type}
Sub Type: {sub_type}
"""


def build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ]
    )
