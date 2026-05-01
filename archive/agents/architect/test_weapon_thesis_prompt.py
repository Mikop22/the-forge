"""Tests for the weapon thesis prompt research layer."""

from __future__ import annotations

from architect import prompts
from architect.research_evidence import RESEARCH_RULES
from architect import weapon_thesis_prompt
from architect.weapon_thesis_prompt import SYSTEM_PROMPT


def test_system_prompt_mentions_seed_and_cashout() -> None:
    prompt = SYSTEM_PROMPT.lower()

    assert "seed" in prompt
    assert "cashout" in prompt


def test_research_rules_include_source_and_affected_fields() -> None:
    assert any(
        rule.source
        and rule.affected_generation_fields
        and rule.affected_judge_categories
        for rule in RESEARCH_RULES
    )


def test_system_prompt_renders_research_registry_entries() -> None:
    for rule in RESEARCH_RULES:
        assert rule.source in SYSTEM_PROMPT
        assert rule.distilled_design_rule in SYSTEM_PROMPT
        for field in rule.affected_generation_fields:
            assert f"`{field}`" in SYSTEM_PROMPT
        for category in rule.affected_judge_categories:
            assert f"`{category}`" in SYSTEM_PROMPT


def test_prompt_router_exports_weapon_thesis_prompt_builder() -> None:
    assert prompts.build_weapon_thesis_prompt is weapon_thesis_prompt.build_prompt


def test_prompt_router_exposes_weapon_thesis_prompt_builder() -> None:
    prompt = prompts.build_weapon_thesis_prompt()

    assert prompt is not None
