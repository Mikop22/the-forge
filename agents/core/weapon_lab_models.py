"""Bounded data models for the hidden weapon lab audition flow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.combat_packages import (
    CombatPackageLiteral,
    DeliveryStyleLiteral,
    PayoffRateLiteral,
)
from core.runtime_capabilities import LoopFamilyLiteral

SpriteMotionLiteral = Literal["snappy", "weighty", "gliding"]
HardGateCategoryLiteral = Literal["clarity", "readability", "differentiation"]
JudgeCategoryLiteral = HardGateCategoryLiteral
JudgeDisagreementPolicyLiteral = Literal["review_outliers"]
TieBreakPolicyLiteral = Literal["highest_clarity_then_lowest_variance"]


class WeaponThesis(BaseModel):
    """Combat-facing thesis for a single candidate."""

    model_config = ConfigDict(frozen=True)

    fantasy: str = Field(..., min_length=1)
    combat_package: CombatPackageLiteral
    delivery_style: DeliveryStyleLiteral
    payoff_rate: PayoffRateLiteral
    loop_family: LoopFamilyLiteral


class SpriteThesis(BaseModel):
    """Small bounded description of sprite intent."""

    model_config = ConfigDict(frozen=True)

    silhouette: str = Field(..., min_length=1)
    motion_profile: SpriteMotionLiteral
    readability_hook: str = Field(..., min_length=1)


class ArtDirection(BaseModel):
    """Compact visual strategy record for a candidate."""

    model_config = ConfigDict(frozen=True)

    palette: str = Field(..., min_length=1)
    silhouette: str = Field(..., min_length=1)
    material_language: str = Field(..., min_length=1)


class BehaviorContract(BaseModel):
    """What the runtime should reliably express for the candidate."""

    model_config = ConfigDict(frozen=True)

    loop_family: LoopFamilyLiteral
    delivery_style: DeliveryStyleLiteral
    payoff_rate: PayoffRateLiteral
    hard_gates: tuple[HardGateCategoryLiteral, ...] = Field(default_factory=tuple)


class SearchBudget(BaseModel):
    """Small search controls for the audition pass."""

    model_config = ConfigDict(frozen=True)

    max_candidates: int = Field(..., ge=1)
    finalist_count: int = Field(..., ge=1)
    reroll_limit: int = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "SearchBudget":
        if self.finalist_count > self.max_candidates:
            raise ValueError("finalist_count cannot exceed max_candidates")
        return self


class CandidateRecord(BaseModel):
    """Stored state for a single candidate through the audition."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., min_length=1)
    weapon_thesis: WeaponThesis
    sprite_thesis: SpriteThesis | None = None
    art_direction: ArtDirection | None = None
    behavior_contract: BehaviorContract | None = None
    search_budget: SearchBudget
    finalist: bool = False
    rejection_reason: str | None = None
    reroll_parent_id: str | None = None


class JudgeScore(BaseModel):
    """Single judge score for one candidate and category."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., min_length=1)
    judge_id: str = Field(..., min_length=1)
    category: JudgeCategoryLiteral
    score: int = Field(..., ge=0, le=10)
    notes: str | None = None


class AnchorSets(BaseModel):
    """Reference anchors the judges can compare against."""

    model_config = ConfigDict(frozen=True)

    good: tuple[str, ...] = Field(..., min_length=1)
    bad: tuple[str, ...] = Field(..., min_length=1)


class RankStabilityKnobs(BaseModel):
    """Knobs that keep shortlists from thrashing between passes."""

    model_config = ConfigDict(frozen=True)

    preserve_top_n: int = Field(..., ge=0)
    minimum_margin_for_rerank: float = Field(..., ge=0.0)


class RankingPolicy(BaseModel):
    """Explicit ranking policy for the hidden audition."""

    model_config = ConfigDict(frozen=True)

    hard_gate_categories: tuple[HardGateCategoryLiteral, ...]
    anchor_sets: AnchorSets
    judge_disagreement_policy: JudgeDisagreementPolicyLiteral
    tie_break_policy: TieBreakPolicyLiteral
    rank_stability: RankStabilityKnobs

    @classmethod
    def default(cls) -> "RankingPolicy":
        return cls(
            hard_gate_categories=("clarity", "readability", "differentiation"),
            anchor_sets=AnchorSets(
                good=("clear silhouette", "payoff lands fast"),
                bad=("muddy read", "generic elemental swap"),
            ),
            judge_disagreement_policy="review_outliers",
            tie_break_policy="highest_clarity_then_lowest_variance",
            rank_stability=RankStabilityKnobs(
                preserve_top_n=2,
                minimum_margin_for_rerank=0.5,
            ),
        )
