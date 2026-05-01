"""Tests for thesis judge helpers."""

from __future__ import annotations

from architect.thesis_judges import (
    ClarityJudge,
    build_default_thesis_judges,
    detect_judge_disagreements,
    hard_reject_thesis,
    summarize_anchor_alignment,
)
from core.weapon_lab_models import AnchorSets, JudgeScore, WeaponThesis


def _thesis(*, fantasy: str) -> WeaponThesis:
    return WeaponThesis(
        fantasy=fantasy,
        combat_package="storm_brand",
        delivery_style="direct",
        payoff_rate="fast",
        loop_family="mark_cashout",
    )


def test_hard_reject_thesis_rejects_thesis_without_real_cashout_loop() -> None:
    thesis = _thesis(
        fantasy="lightning staff that fires a stronger bolt every third shot"
    )

    assert hard_reject_thesis(thesis) == "missing a readable seed-and-cashout loop"


def test_detect_judge_disagreements_reports_outlier_category_spread() -> None:
    scores = [
        JudgeScore(
            candidate_id="candidate-001",
            judge_id="judge-a",
            category="clarity",
            score=9,
        ),
        JudgeScore(
            candidate_id="candidate-001",
            judge_id="judge-b",
            category="clarity",
            score=5,
        ),
        JudgeScore(
            candidate_id="candidate-001",
            judge_id="judge-a",
            category="readability",
            score=8,
        ),
        JudgeScore(
            candidate_id="candidate-001",
            judge_id="judge-b",
            category="readability",
            score=7,
        ),
    ]

    disagreements = detect_judge_disagreements(scores)

    assert disagreements == ["clarity disagreement: 9 vs 5"]


def test_clarity_judge_returns_bounded_clarity_score() -> None:
    judge = ClarityJudge()

    scores = judge.judge(
        candidate_id="candidate-001",
        thesis=_thesis(
            fantasy="lightning brand that marks targets, then cashes out in a fast starfall burst"
        ),
        anchors=AnchorSets(
            good=("clear silhouette", "payoff lands fast"),
            bad=("muddy read", "generic elemental swap"),
        ),
    )

    assert {score.category for score in scores} == {
        "clarity",
        "readability",
        "differentiation",
    }
    assert {score.judge_id for score in scores} == {"clarity-judge"}
    assert all(0 <= score.score <= 10 for score in scores)


def test_default_judges_can_produce_meaningful_disagreements() -> None:
    thesis = _thesis(
        fantasy="fast readable lightning mark that somehow cashes out in a starfall burst"
    )
    anchors = AnchorSets(
        good=("clear silhouette", "payoff lands fast"),
        bad=("muddy read", "generic elemental swap"),
    )

    scores = [
        score
        for judge in build_default_thesis_judges()
        for score in judge.judge(
            candidate_id="candidate-001", thesis=thesis, anchors=anchors
        )
    ]

    assert len(scores) == 9
    assert detect_judge_disagreements(scores) == ["clarity disagreement: 9 vs 6"]


def test_summarize_anchor_alignment_only_reports_positive_match_when_supported() -> (
    None
):
    thesis = _thesis(fantasy="storm marks targets and cashes out in a slow burst")

    notes = summarize_anchor_alignment(
        thesis,
        AnchorSets(
            good=("clear silhouette", "payoff lands fast"),
            bad=("muddy read", "generic elemental swap"),
        ),
    )

    assert "tracks good anchor: payoff lands fast" not in notes
