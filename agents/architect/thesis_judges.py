"""Bounded judge helpers for thesis finalist ranking."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Protocol

from core.weapon_lab_models import AnchorSets, JudgeScore, WeaponThesis

_SEED_HINTS = ("mark", "bank", "charge", "stack", "orbit", "seed", "prime")
_CASHOUT_HINTS = (
    "cashout",
    "burst",
    "detonate",
    "collapse",
    "shatter",
    "starfall",
    "divebomb",
)


class ThesisJudge(Protocol):
    """Small contract for bounded thesis judges."""

    def judge(
        self,
        *,
        candidate_id: str,
        thesis: WeaponThesis,
        anchors: AnchorSets,
    ) -> list[JudgeScore]: ...


_CATEGORY_HINTS = {
    "clarity": {
        "positive": ("mark", "cash", "burst", "starfall", "clear"),
        "negative": ("generic", "somehow", "thing"),
    },
    "readability": {
        "positive": ("fast", "readable", "clear", "orbit"),
        "negative": ("busy", "muddy", "clutter", "somehow"),
    },
    "differentiation": {
        "positive": ("orbit", "divebomb", "starfall", "collapse"),
        "negative": ("generic", "elemental", "standard"),
    },
}


class _BoundedJudge:
    """Deterministic judge that scores every ranking category."""

    judge_id: str
    adjustments: dict[str, int]

    def judge(
        self,
        *,
        candidate_id: str,
        thesis: WeaponThesis,
        anchors: AnchorSets,
    ) -> list[JudgeScore]:
        fantasy = thesis.fantasy.lower()
        scores: list[JudgeScore] = []
        for category, hints in _CATEGORY_HINTS.items():
            score = 5
            score += sum(1 for token in hints["positive"] if token in fantasy)
            score -= sum(1 for token in hints["negative"] if token in fantasy)
            if category == "readability" and _matches_anchor(
                fantasy, "clear silhouette"
            ):
                score += 1
            if category == "differentiation" and _matches_anchor(
                fantasy, "generic elemental swap"
            ):
                score -= 2
            score += self.adjustments.get(category, 0)
            bounded_score = max(0, min(score, 10))
            scores.append(
                JudgeScore(
                    candidate_id=candidate_id,
                    judge_id=self.judge_id,
                    category=category,
                    score=bounded_score,
                    notes=f"{self.judge_id} scored {category} as {bounded_score}/10",
                )
            )
        return scores


class ClarityJudge(_BoundedJudge):
    judge_id = "clarity-judge"
    adjustments = {"clarity": 1, "readability": 0, "differentiation": 0}


class ReadabilityJudge(_BoundedJudge):
    judge_id = "readability-judge"
    adjustments = {"clarity": 0, "readability": 2, "differentiation": 0}


class DifferentiationJudge(_BoundedJudge):
    judge_id = "differentiation-judge"
    adjustments = {"clarity": -2, "readability": 0, "differentiation": 1}


def build_default_thesis_judges() -> tuple[ThesisJudge, ...]:
    """Small built-in deterministic judges for the default thesis path."""

    return (ClarityJudge(), ReadabilityJudge(), DifferentiationJudge())


def hard_reject_thesis(thesis: WeaponThesis) -> str | None:
    """Reject obviously non-viable theses before judge scoring."""

    fantasy = thesis.fantasy.lower()
    has_seed = any(token in fantasy for token in _SEED_HINTS)
    has_cashout = any(token in fantasy for token in _CASHOUT_HINTS)
    if not (has_seed and has_cashout):
        return "missing a readable seed-and-cashout loop"
    return None


def detect_judge_disagreements(
    scores: Sequence[JudgeScore], threshold: int = 3
) -> list[str]:
    """Record categories where bounded judges materially disagree."""

    by_category: dict[str, list[int]] = defaultdict(list)
    for score in scores:
        by_category[score.category].append(score.score)

    disagreements: list[str] = []
    for category in sorted(by_category):
        values = by_category[category]
        if len(values) < 2:
            continue
        low = min(values)
        high = max(values)
        if high - low >= threshold:
            disagreements.append(f"{category} disagreement: {high} vs {low}")
    return disagreements


def summarize_anchor_alignment(thesis: WeaponThesis, anchors: AnchorSets) -> list[str]:
    """Keep anchor comparison simple and explicit for early tournament passes."""

    fantasy = thesis.fantasy.lower()
    notes: list[str] = []
    for anchor in anchors.good:
        if _matches_anchor(fantasy, anchor):
            notes.append(f"tracks good anchor: {anchor}")
    for anchor in anchors.bad:
        if _matches_anchor(fantasy, anchor):
            notes.append(f"risks bad anchor: {anchor}")
    if not notes:
        notes.append(f"compared against anchor set starting from: {anchors.good[0]}")
    return notes


def average_scores_by_category(scores: Sequence[JudgeScore]) -> dict[str, float]:
    """Average bounded judge scores by category."""

    by_category: dict[str, list[int]] = defaultdict(list)
    for score in scores:
        by_category[score.category].append(score.score)
    return {
        category: round(sum(values) / len(values), 2)
        for category, values in sorted(by_category.items())
    }


def _matches_anchor(fantasy: str, anchor: str) -> bool:
    if anchor == "payoff lands fast":
        return any(token in fantasy for token in _CASHOUT_HINTS) and any(
            token in fantasy for token in ("fast", "quick", "instant")
        )
    if anchor == "clear silhouette":
        return any(token in fantasy for token in ("clear", "readable", "silhouette"))
    if anchor == "muddy read":
        return any(token in fantasy for token in ("muddy", "busy", "clutter"))
    if anchor == "generic elemental swap":
        return "generic" in fantasy and "elemental" in fantasy
    return anchor.lower() in fantasy
