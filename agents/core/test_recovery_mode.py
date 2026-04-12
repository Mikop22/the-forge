from __future__ import annotations

from core.recovery_mode import dedupe_near_identical_candidates, next_recovery_mode
from core.weapon_lab_models import SearchBudget, WeaponThesis


def _thesis(*, fantasy: str, combat_package: str = "storm_brand") -> WeaponThesis:
    return WeaponThesis(
        fantasy=fantasy,
        combat_package=combat_package,
        delivery_style="direct",
        payoff_rate="fast",
        loop_family="mark_cashout",
    )


def test_next_recovery_mode_becomes_wild_after_three_failed_batches_without_lowering_quality_bar() -> (
    None
):
    mode = next_recovery_mode(
        failed_batches=3,
        base_budget=SearchBudget(max_candidates=6, finalist_count=2, reroll_limit=1),
        quality_threshold=8.5,
    )

    assert mode.search_profile == "wild"
    assert mode.novelty_bias > 1
    assert mode.quality_threshold == 8.5
    assert mode.allow_quality_drop is False
    assert mode.search_budget.max_candidates == 10
    assert mode.search_budget.finalist_count == 2
    assert mode.search_budget.reroll_limit == 3


def test_dedupe_near_identical_candidates_keeps_only_one_fingerprint_match() -> None:
    candidates = [
        _thesis(fantasy="lightning marks targets before a storm-brand cashout"),
        _thesis(fantasy="storm-brand lightning marks targets before the cashout"),
        _thesis(
            fantasy="embers orbit the caster before a furnace collapse",
            combat_package="orbit_furnace",
        ),
    ]

    deduped = dedupe_near_identical_candidates(candidates)

    assert [candidate.combat_package for candidate in deduped] == [
        "storm_brand",
        "orbit_furnace",
    ]
