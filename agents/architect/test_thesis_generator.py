"""Tests for thesis finalist generation."""

from __future__ import annotations

from architect.architect import ArchitectAgent
from architect.thesis_generator import ThesisTournament
from core.weapon_lab_models import (
    AnchorSets,
    JudgeScore,
    RankStabilityKnobs,
    RankingPolicy,
    WeaponThesis,
)


class FakeThesisGenerator:
    def __init__(self, theses: list[dict[str, str]]) -> None:
        self.theses = theses
        self.calls: list[tuple[str, int, str, str, str]] = []

    def generate(
        self,
        *,
        prompt: str,
        thesis_count: int,
        selected_tier: str,
        content_type: str,
        sub_type: str,
    ) -> list[dict[str, str]]:
        self.calls.append((prompt, thesis_count, selected_tier, content_type, sub_type))
        return list(self.theses)


class FakeJudge:
    def __init__(
        self, judge_id: str, category_scores: dict[str, dict[str, int]]
    ) -> None:
        self.judge_id = judge_id
        self.category_scores = category_scores

    def judge(
        self,
        *,
        candidate_id: str,
        thesis: WeaponThesis,
        anchors: object,
    ) -> list[JudgeScore]:
        return [
            JudgeScore(
                candidate_id=candidate_id,
                judge_id=self.judge_id,
                category=category,
                score=score,
                notes=f"{self.judge_id} saw {category} in {thesis.combat_package}",
            )
            for category, score in self.category_scores[candidate_id].items()
        ]


def test_thesis_tournament_returns_ranked_finalists_and_rejection_reasons() -> None:
    tournament = ThesisTournament(
        thesis_generator=FakeThesisGenerator(
            [
                {
                    "fantasy": "lightning brand that marks targets, then cashes out in a fast starfall burst",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                {
                    "fantasy": "embers orbit the caster, then divebomb marked enemies for a furnace collapse",
                    "combat_package": "orbit_furnace",
                    "delivery_style": "direct",
                    "payoff_rate": "medium",
                    "loop_family": "mark_cashout",
                },
                {
                    "fantasy": "ice staff that fires a colder bolt every few attacks",
                    "combat_package": "frost_shatter",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
            ]
        ),
        judges=(
            FakeJudge(
                "judge-a",
                {
                    "candidate-001": {
                        "clarity": 9,
                        "readability": 8,
                        "differentiation": 8,
                    },
                    "candidate-002": {
                        "clarity": 7,
                        "readability": 8,
                        "differentiation": 9,
                    },
                },
            ),
            FakeJudge(
                "judge-b",
                {
                    "candidate-001": {
                        "clarity": 6,
                        "readability": 8,
                        "differentiation": 7,
                    },
                    "candidate-002": {
                        "clarity": 8,
                        "readability": 7,
                        "differentiation": 8,
                    },
                },
            ),
        ),
        ranking_policy=RankingPolicy.default(),
    )

    result = tournament.generate_ranked_finalists(
        prompt="forge a hidden audition lightning staff",
        thesis_count=3,
        finalist_count=2,
        selected_tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert [finalist.candidate_id for finalist in result.finalists] == [
        "candidate-002",
        "candidate-001",
    ]
    assert result.finalists[0].total_score > result.finalists[1].total_score
    assert "candidate-003" in result.rejection_reasons
    assert result.rejection_reasons["candidate-003"] == (
        "missing a readable seed-and-cashout loop"
    )
    assert result.finalists[1].judge_disagreements == ["clarity disagreement: 9 vs 6"]
    assert result.finalists[0].anchor_notes
    assert result.finalists[1].score_breakdown == {
        "clarity": 7.5,
        "readability": 8.0,
        "differentiation": 7.5,
    }


def test_architect_agent_delegates_to_thesis_tournament() -> None:
    expected = object()

    class StubTournament:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def generate_ranked_finalists(self, **kwargs: object) -> object:
            self.calls.append(kwargs)
            return expected

    tournament = StubTournament()
    agent = ArchitectAgent.__new__(ArchitectAgent)
    agent._thesis_tournament = tournament

    result = agent.generate_thesis_finalists(
        prompt="forge a hidden audition lightning staff",
        thesis_count=4,
        finalist_count=2,
        selected_tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert result is expected
    assert tournament.calls == [
        {
            "prompt": "forge a hidden audition lightning staff",
            "thesis_count": 4,
            "finalist_count": 2,
            "selected_tier": "Tier2_Dungeon",
            "content_type": "Weapon",
            "sub_type": "Staff",
        }
    ]


def test_architect_agent_uses_built_in_bounded_judges_by_default(monkeypatch) -> None:
    class DummyChatOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def with_structured_output(self, schema):
            return object()

    class DummyReferencePolicy:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class DummyTournament:
        def __init__(self, *, thesis_generator, judges, ranking_policy) -> None:
            self.thesis_generator = thesis_generator
            self.judges = judges
            self.ranking_policy = ranking_policy

    monkeypatch.setattr("architect.architect.ChatOpenAI", DummyChatOpenAI)
    monkeypatch.setattr("architect.architect.ReferencePolicy", DummyReferencePolicy)
    monkeypatch.setattr("architect.architect.BrowserReferenceFinder", lambda: object())
    monkeypatch.setattr(
        "architect.architect.HybridReferenceApprover", lambda model_name: object()
    )
    monkeypatch.setattr(
        "architect.architect.LLMWeaponThesisGenerator", lambda model_name: object()
    )
    monkeypatch.setattr("architect.architect.ThesisTournament", DummyTournament)

    agent = ArchitectAgent()

    assert len(agent._thesis_tournament.judges) == 3
    assert {judge.judge_id for judge in agent._thesis_tournament.judges} == {
        "clarity-judge",
        "readability-judge",
        "differentiation-judge",
    }


def test_default_judge_path_records_disagreements() -> None:
    from architect.thesis_judges import build_default_thesis_judges

    tournament = ThesisTournament(
        thesis_generator=FakeThesisGenerator(
            [
                {
                    "fantasy": "fast readable lightning mark that somehow cashes out in a starfall burst",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                }
            ]
        ),
        judges=build_default_thesis_judges(),
        ranking_policy=RankingPolicy.default(),
    )

    result = tournament.generate_ranked_finalists(
        prompt="forge a hidden audition lightning staff",
        thesis_count=1,
        finalist_count=1,
        selected_tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert result.finalists[0].judge_disagreements == ["clarity disagreement: 9 vs 6"]


def test_ranking_policy_controls_scored_categories_and_small_margin_reranks() -> None:
    tournament = ThesisTournament(
        thesis_generator=FakeThesisGenerator(
            [
                {
                    "fantasy": "fast readable lightning mark that cashes out in a starfall burst",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                {
                    "fantasy": "orbit forge that marks enemies and cashes out in a collapse",
                    "combat_package": "orbit_furnace",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
            ]
        ),
        judges=(
            FakeJudge(
                "judge-a",
                {
                    "candidate-001": {
                        "clarity": 9,
                        "readability": 2,
                        "differentiation": 2,
                    },
                    "candidate-002": {
                        "clarity": 8,
                        "readability": 10,
                        "differentiation": 10,
                    },
                },
            ),
            FakeJudge(
                "judge-b",
                {
                    "candidate-001": {
                        "clarity": 9,
                        "readability": 2,
                        "differentiation": 2,
                    },
                    "candidate-002": {
                        "clarity": 8,
                        "readability": 10,
                        "differentiation": 10,
                    },
                },
            ),
        ),
        ranking_policy=RankingPolicy(
            hard_gate_categories=("clarity",),
            anchor_sets=AnchorSets(
                good=("clear silhouette", "payoff lands fast"),
                bad=("muddy read", "generic elemental swap"),
            ),
            judge_disagreement_policy="review_outliers",
            tie_break_policy="highest_clarity_then_lowest_variance",
            rank_stability=RankStabilityKnobs(
                preserve_top_n=2,
                minimum_margin_for_rerank=2.0,
            ),
        ),
    )

    result = tournament.generate_ranked_finalists(
        prompt="forge a hidden audition lightning staff",
        thesis_count=2,
        finalist_count=2,
        selected_tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert [finalist.candidate_id for finalist in result.finalists] == [
        "candidate-001",
        "candidate-002",
    ]
    assert result.finalists[0].score_breakdown == {"clarity": 9.0}


def test_total_score_does_not_include_hidden_bonus_outside_policy_surface() -> None:
    tournament = ThesisTournament(
        thesis_generator=FakeThesisGenerator(
            [
                {
                    "fantasy": "lightning mark that cashes out in a fast burst",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                {
                    "fantasy": "lightning mark that cashes out in a burst",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "medium",
                    "loop_family": "mark_cashout",
                },
            ]
        ),
        judges=(
            FakeJudge(
                "judge-a",
                {
                    "candidate-001": {
                        "clarity": 8,
                        "readability": 8,
                        "differentiation": 8,
                    },
                    "candidate-002": {
                        "clarity": 8,
                        "readability": 8,
                        "differentiation": 8,
                    },
                },
            ),
        ),
        ranking_policy=RankingPolicy.default(),
    )

    result = tournament.generate_ranked_finalists(
        prompt="forge a hidden audition lightning staff",
        thesis_count=2,
        finalist_count=2,
        selected_tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert [finalist.total_score for finalist in result.finalists] == [8.0, 8.0]


def test_single_pass_rank_stability_does_not_use_candidate_id_as_prior_rank() -> None:
    tournament = ThesisTournament(
        thesis_generator=FakeThesisGenerator(
            [
                {
                    "fantasy": "mark cashout loop with weaker clarity",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                {
                    "fantasy": "mark cashout loop with stronger clarity",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
            ]
        ),
        judges=(
            FakeJudge(
                "judge-a",
                {
                    "candidate-001": {
                        "clarity": 7,
                        "readability": 7,
                        "differentiation": 7,
                    },
                    "candidate-002": {
                        "clarity": 8,
                        "readability": 8,
                        "differentiation": 8,
                    },
                },
            ),
        ),
        ranking_policy=RankingPolicy(
            hard_gate_categories=("clarity", "readability", "differentiation"),
            anchor_sets=AnchorSets(
                good=("clear silhouette", "payoff lands fast"),
                bad=("muddy read", "generic elemental swap"),
            ),
            judge_disagreement_policy="review_outliers",
            tie_break_policy="highest_clarity_then_lowest_variance",
            rank_stability=RankStabilityKnobs(
                preserve_top_n=2,
                minimum_margin_for_rerank=5.0,
            ),
        ),
    )

    result = tournament.generate_ranked_finalists(
        prompt="forge a hidden audition lightning staff",
        thesis_count=2,
        finalist_count=2,
        selected_tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert [finalist.candidate_id for finalist in result.finalists] == [
        "candidate-002",
        "candidate-001",
    ]
