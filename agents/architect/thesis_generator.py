"""Minimal thesis tournament that returns ranked finalists, not a winner."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import pvariance
from typing import Literal, Protocol

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field

from architect import prompts as prompt_router
from architect.thesis_judges import (
    ThesisJudge,
    average_scores_by_category,
    detect_judge_disagreements,
    hard_reject_thesis,
    summarize_anchor_alignment,
)
from core.recovery_mode import RecoveryMode, fingerprint_thesis
from core.weapon_lab_models import JudgeScore, RankingPolicy, WeaponThesis


def _thesis_content_sort_key(thesis: WeaponThesis) -> tuple[str, str, str, str, str]:
    return (
        thesis.fantasy.lower(),
        thesis.combat_package,
        thesis.delivery_style,
        thesis.payoff_rate,
        thesis.loop_family,
    )


def _finalist_recovery_sort_key(
    finalist: ThesisFinalist,
) -> tuple[float, float, float, str, str, str, str, str]:
    return (
        -finalist.total_score,
        -finalist.score_breakdown.get("clarity", 0.0),
        ThesisTournament._score_variance(finalist.judge_scores),
        *_thesis_content_sort_key(finalist.thesis),
    )


class WeaponThesisGenerator(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        thesis_count: int,
        selected_tier: str,
        content_type: str,
        sub_type: str,
    ) -> list[WeaponThesis]: ...


class ThesisFinalist(BaseModel):
    """Ranked surviving thesis plus scoring context."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., min_length=1)
    thesis: WeaponThesis
    total_score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    judge_scores: list[JudgeScore] = Field(default_factory=list)
    judge_disagreements: list[str] = Field(default_factory=list)
    anchor_notes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ThesisTournamentResult(BaseModel):
    """Explicit finalist ranking output for the thesis audition phase."""

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(..., min_length=1)
    finalists: list[ThesisFinalist] = Field(default_factory=list)
    rejection_reasons: dict[str, str] = Field(default_factory=dict)


class RecoveryThesisPolicy(BaseModel):
    """Structured mutation/crossbreed request for a recovery reroll."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., min_length=1)
    strategy: Literal["mutate", "crossbreed"]
    source_candidate_ids: tuple[str, ...] = Field(..., min_length=1)
    fingerprint: str = Field(..., min_length=1)
    prompt_hint: str = Field(..., min_length=1)
    search_budget: dict[str, int]
    quality_threshold: float = Field(..., ge=0.0)
    novelty_bias: int = Field(..., ge=0)


class LLMWeaponThesisGenerator:
    """Small prompt-backed thesis generator used by the agent entrypoint."""

    def __init__(self, model_name: str = "gpt-5.4") -> None:
        self._llm = ChatOpenAI(model=model_name, timeout=120)
        self._structured_llm = self._llm.with_structured_output(WeaponThesis)
        self._chain = prompt_router.build_weapon_thesis_prompt() | self._structured_llm

    def generate(
        self,
        *,
        prompt: str,
        thesis_count: int,
        selected_tier: str,
        content_type: str,
        sub_type: str,
    ) -> list[WeaponThesis]:
        payload = {
            "user_prompt": prompt,
            "selected_tier": selected_tier,
            "content_type": content_type,
            "sub_type": sub_type,
        }
        return [self._chain.invoke(payload) for _ in range(thesis_count)]


class ThesisTournament:
    """Generate, reject, score, and rank thesis finalists."""

    def __init__(
        self,
        *,
        thesis_generator: WeaponThesisGenerator,
        judges: Sequence[ThesisJudge],
        ranking_policy: RankingPolicy,
    ) -> None:
        self._thesis_generator = thesis_generator
        self._judges = tuple(judges)
        self._ranking_policy = ranking_policy

    def generate_ranked_finalists(
        self,
        *,
        prompt: str,
        thesis_count: int,
        finalist_count: int,
        selected_tier: str,
        content_type: str,
        sub_type: str,
    ) -> ThesisTournamentResult:
        raw_theses = self._thesis_generator.generate(
            prompt=prompt,
            thesis_count=thesis_count,
            selected_tier=selected_tier,
            content_type=content_type,
            sub_type=sub_type,
        )

        finalists: list[ThesisFinalist] = []
        rejection_reasons: dict[str, str] = {}

        for index, raw_thesis in enumerate(raw_theses[:thesis_count], start=1):
            candidate_id = f"candidate-{index:03d}"
            thesis = WeaponThesis.model_validate(raw_thesis)
            rejection_reason = hard_reject_thesis(thesis)
            if rejection_reason is not None:
                rejection_reasons[candidate_id] = rejection_reason
                continue

            judge_scores = self._judge_candidate(
                candidate_id=candidate_id, thesis=thesis
            )
            score_breakdown = self._score_breakdown(judge_scores)
            anchor_notes = summarize_anchor_alignment(
                thesis, self._ranking_policy.anchor_sets
            )
            total_score = self._total_score(score_breakdown=score_breakdown)
            disagreements = self._judge_disagreements(judge_scores)
            reasons = self._build_reasons(
                score_breakdown=score_breakdown,
                anchor_notes=anchor_notes,
                disagreements=disagreements,
            )
            finalists.append(
                ThesisFinalist(
                    candidate_id=candidate_id,
                    thesis=thesis,
                    total_score=total_score,
                    score_breakdown=score_breakdown,
                    judge_scores=judge_scores,
                    judge_disagreements=disagreements,
                    anchor_notes=anchor_notes,
                    reasons=reasons,
                )
            )

        finalists.sort(key=self._sort_key)
        finalists = self._apply_rank_stability(finalists)
        return ThesisTournamentResult(
            prompt=prompt,
            finalists=finalists[:finalist_count],
            rejection_reasons=rejection_reasons,
        )

    def _judge_candidate(
        self, *, candidate_id: str, thesis: WeaponThesis
    ) -> list[JudgeScore]:
        judge_scores: list[JudgeScore] = []
        for judge in self._judges:
            judge_scores.extend(
                judge.judge(
                    candidate_id=candidate_id,
                    thesis=thesis,
                    anchors=self._ranking_policy.anchor_sets,
                )
            )
        return judge_scores

    @staticmethod
    def _build_reasons(
        *,
        score_breakdown: Mapping[str, float],
        anchor_notes: Sequence[str],
        disagreements: Sequence[str],
    ) -> list[str]:
        reasons = [
            f"{category} average {score:.2f}"
            for category, score in sorted(
                score_breakdown.items(), key=lambda item: (-item[1], item[0])
            )
        ]
        reasons.extend(anchor_notes)
        reasons.extend(disagreements)
        return reasons

    def _score_breakdown(self, scores: Sequence[JudgeScore]) -> dict[str, float]:
        breakdown = average_scores_by_category(scores)
        allowed = set(self._ranking_policy.hard_gate_categories)
        return {
            category: score
            for category, score in breakdown.items()
            if category in allowed
        }

    def _judge_disagreements(self, scores: Sequence[JudgeScore]) -> list[str]:
        if self._ranking_policy.judge_disagreement_policy != "review_outliers":
            return []
        return detect_judge_disagreements(scores)

    def _sort_key(
        self, finalist: ThesisFinalist
    ) -> tuple[float, float, float, str, str, str, str, str]:
        if (
            self._ranking_policy.tie_break_policy
            != "highest_clarity_then_lowest_variance"
        ):
            return (
                -finalist.total_score,
                0.0,
                0.0,
                *_thesis_content_sort_key(finalist.thesis),
            )
        return (
            -finalist.total_score,
            -finalist.score_breakdown.get("clarity", 0.0),
            self._score_variance(finalist.judge_scores),
            *_thesis_content_sort_key(finalist.thesis),
        )

    def _apply_rank_stability(
        self, finalists: list[ThesisFinalist]
    ) -> list[ThesisFinalist]:
        return list(finalists)

    @staticmethod
    def _score_variance(scores: Sequence[JudgeScore]) -> float:
        values = [score.score for score in scores]
        return pvariance(values) if len(values) > 1 else 0.0

    @staticmethod
    def _total_score(*, score_breakdown: Mapping[str, float]) -> float:
        if not score_breakdown:
            return 0.0
        return round(sum(score_breakdown.values()) / len(score_breakdown), 2)


def build_recovery_thesis_policies(
    *, finalists: Sequence[ThesisFinalist], recovery_mode: RecoveryMode
) -> list[RecoveryThesisPolicy]:
    """Emit explicit mutation/crossbreed policies for recovery rerolls."""

    unique_finalists = _best_recovery_finalists_by_fingerprint(finalists)

    policies: list[RecoveryThesisPolicy] = []
    for index, finalist in enumerate(unique_finalists, start=1):
        policies.append(
            RecoveryThesisPolicy(
                candidate_id=f"recovery-{index:03d}",
                strategy="mutate",
                source_candidate_ids=(finalist.candidate_id,),
                fingerprint=fingerprint_thesis(finalist.thesis),
                prompt_hint=finalist.thesis.fantasy,
                search_budget=recovery_mode.search_budget.model_dump(),
                quality_threshold=recovery_mode.quality_threshold,
                novelty_bias=recovery_mode.novelty_bias,
            )
        )

    if len(unique_finalists) >= 2:
        first = unique_finalists[0]
        second = unique_finalists[1]
        policies.append(
            RecoveryThesisPolicy(
                candidate_id=f"recovery-{len(policies) + 1:03d}",
                strategy="crossbreed",
                source_candidate_ids=(first.candidate_id, second.candidate_id),
                fingerprint=(
                    f"{fingerprint_thesis(first.thesis)}+{fingerprint_thesis(second.thesis)}"
                ),
                prompt_hint=f"{first.thesis.fantasy} // {second.thesis.fantasy}",
                search_budget=recovery_mode.search_budget.model_dump(),
                quality_threshold=recovery_mode.quality_threshold,
                novelty_bias=recovery_mode.novelty_bias,
            )
        )

    return policies[: recovery_mode.search_budget.max_candidates]


def _best_recovery_finalists_by_fingerprint(
    finalists: Sequence[ThesisFinalist],
) -> list[ThesisFinalist]:
    selected: dict[str, ThesisFinalist] = {}
    for finalist in finalists:
        fingerprint = fingerprint_thesis(finalist.thesis)
        current = selected.get(fingerprint)
        if current is None or _finalist_recovery_sort_key(
            finalist
        ) < _finalist_recovery_sort_key(current):
            selected[fingerprint] = finalist
    return sorted(selected.values(), key=_finalist_recovery_sort_key)
