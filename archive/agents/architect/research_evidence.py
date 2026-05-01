"""Research-backed evidence registry for architect prompt layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchEvidence:
    source: str
    distilled_design_rule: str
    affected_generation_fields: tuple[str, ...]
    affected_judge_categories: tuple[str, ...]


RESEARCH_RULES: tuple[ResearchEvidence, ...] = (
    ResearchEvidence(
        source="weapon-lab hidden audition notes: combat loop heuristics",
        distilled_design_rule=(
            "Center each thesis on one strong player verb with a clear seed and "
            "cashout instead of a pile of equal-strength effects."
        ),
        affected_generation_fields=(
            "weapon_thesis.fantasy",
            "weapon_thesis.loop_family",
            "behavior_contract.loop_family",
        ),
        affected_judge_categories=("clarity", "differentiation"),
    ),
    ResearchEvidence(
        source="weapon-lab hidden audition notes: payoff timing review",
        distilled_design_rule=(
            "Show visible escalation fast and let the payoff land inside 1-3s so "
            "judges can read the loop without extended setup."
        ),
        affected_generation_fields=(
            "weapon_thesis.payoff_rate",
            "behavior_contract.payoff_rate",
            "sprite_thesis.motion_profile",
        ),
        affected_judge_categories=("clarity", "readability"),
    ),
    ResearchEvidence(
        source="weapon-lab hidden audition notes: spectacle ladder review",
        distilled_design_rule=(
            "Define a signature sound and a spectacle ladder so every stage of the "
            "loop reads as building toward a memorable finish."
        ),
        affected_generation_fields=(
            "art_direction.palette",
            "art_direction.material_language",
            "sprite_thesis.readability_hook",
        ),
        affected_judge_categories=("readability", "differentiation"),
    ),
    ResearchEvidence(
        source="weapon-lab hidden audition notes: behavior change rubric",
        distilled_design_rule=(
            "Prefer mechanics that change how the player moves, aims, times, or "
            "positions rather than simply firing another projectile."
        ),
        affected_generation_fields=(
            "weapon_thesis.delivery_style",
            "behavior_contract.delivery_style",
            "behavior_contract.hard_gates",
        ),
        affected_judge_categories=("clarity", "differentiation"),
    ),
)
