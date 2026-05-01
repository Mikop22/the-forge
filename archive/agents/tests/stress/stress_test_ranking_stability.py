from __future__ import annotations

from architect.thesis_generator import ThesisTournament
from architect.thesis_judges import build_default_thesis_judges
from core.weapon_lab_models import RankingPolicy


class _OrderedThesisGenerator:
    def __init__(self, theses: list[dict[str, str]]) -> None:
        self._theses = theses

    def generate(self, **_: object) -> list[dict[str, str]]:
        return list(self._theses)


def test_ranking_stability_breaks_exact_ties_deterministically_across_input_order() -> (
    None
):
    tied_a = "clear fast orbit mark cashout burst"
    tied_b = "orbit clear fast cashout mark burst"
    lower = "clear fast mark cashout burst"

    ordered_fantasies: list[list[str]] = []
    for theses in (
        [
            {
                "fantasy": tied_b,
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
            {
                "fantasy": tied_a,
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
            {
                "fantasy": lower,
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
        ],
        [
            {
                "fantasy": tied_a,
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
            {
                "fantasy": tied_b,
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
            {
                "fantasy": lower,
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
        ],
    ):
        tournament = ThesisTournament(
            thesis_generator=_OrderedThesisGenerator(theses),
            judges=build_default_thesis_judges(),
            ranking_policy=RankingPolicy.default(),
        )
        result = tournament.generate_ranked_finalists(
            prompt="forge a hidden audition verdict staff",
            thesis_count=3,
            finalist_count=3,
            selected_tier="Tier2_Dungeon",
            content_type="Weapon",
            sub_type="Staff",
        )
        ordered_fantasies.append(
            [finalist.thesis.fantasy for finalist in result.finalists]
        )

    assert ordered_fantasies == [
        [tied_a, tied_b, lower],
        [tied_a, tied_b, lower],
    ]


def test_ranking_stability_breaks_same_fantasy_ties_without_input_order_dependence() -> (
    None
):
    ordered_packages: list[list[str]] = []
    for theses in (
        [
            {
                "fantasy": "clear fast orbit mark cashout burst",
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
            {
                "fantasy": "clear fast orbit mark cashout burst",
                "combat_package": "orbit_furnace",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
        ],
        [
            {
                "fantasy": "clear fast orbit mark cashout burst",
                "combat_package": "orbit_furnace",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
            {
                "fantasy": "clear fast orbit mark cashout burst",
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
        ],
    ):
        tournament = ThesisTournament(
            thesis_generator=_OrderedThesisGenerator(theses),
            judges=build_default_thesis_judges(),
            ranking_policy=RankingPolicy.default(),
        )
        result = tournament.generate_ranked_finalists(
            prompt="forge a hidden audition verdict staff",
            thesis_count=2,
            finalist_count=2,
            selected_tier="Tier2_Dungeon",
            content_type="Weapon",
            sub_type="Staff",
        )
        ordered_packages.append(
            [finalist.thesis.combat_package for finalist in result.finalists]
        )

    assert ordered_packages == [
        ["orbit_furnace", "storm_brand"],
        ["orbit_furnace", "storm_brand"],
    ]
