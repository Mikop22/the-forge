"""Tests for agents/core/weapon_lab_models.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.weapon_lab_models import CandidateRecord, JudgeScore, SearchBudget


def test_candidate_record_captures_rejection_reason() -> None:
    candidate = CandidateRecord(
        candidate_id="candidate-007",
        weapon_thesis={
            "fantasy": "lightning brand that banks marks for a cashout",
            "combat_package": "storm_brand",
            "delivery_style": "direct",
            "payoff_rate": "fast",
            "loop_family": "mark_cashout",
        },
        search_budget=SearchBudget(max_candidates=12, finalist_count=3, reroll_limit=2),
        rejection_reason="fails readability gate",
    )

    assert candidate.rejection_reason == "fails readability gate"


def test_search_budget_rejects_finalists_above_max_candidates() -> None:
    with pytest.raises(ValidationError):
        SearchBudget(max_candidates=2, finalist_count=3, reroll_limit=1)


def test_judge_score_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        JudgeScore(
            candidate_id="candidate-001",
            judge_id="judge-a",
            category="fantasy",
            score=8,
        )
