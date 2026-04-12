from __future__ import annotations

import importlib

from architect.thesis_generator import ThesisTournament
from architect.thesis_judges import build_default_thesis_judges
from core.weapon_lab_archive import WeaponLabArchive
from core.weapon_lab_models import RankingPolicy


class _PromptAwareThesisGenerator:
    def __init__(self) -> None:
        self.generated: list[dict[str, str]] = []

    def generate(
        self,
        *,
        prompt: str,
        thesis_count: int,
        selected_tier: str,
        content_type: str,
        sub_type: str,
    ) -> list[dict[str, str]]:
        del thesis_count, selected_tier, content_type, sub_type
        generic = "generic elemental lightning mark that cashes out in a standard burst"
        if "novel" in prompt.lower() and "lightning clone" in prompt.lower():
            novel = "clear fast orbit marks collapse into an astral furnace burst"
        else:
            novel = "clear fast lightning marks burst into a starfall cashout"

        self.generated = [
            {
                "fantasy": generic,
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
            {
                "fantasy": novel,
                "combat_package": "orbit_furnace",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
            {
                "fantasy": "lightning marks targets with no finish somehow",
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
        ]
        return list(self.generated)


def _import_orchestrator():
    return importlib.import_module("orchestrator")


def test_novelty_sensitive_prompt_uses_real_judges_and_complete_archive() -> None:
    generator = _PromptAwareThesisGenerator()
    tournament = ThesisTournament(
        thesis_generator=generator,
        judges=build_default_thesis_judges(),
        ranking_policy=RankingPolicy.default(),
    )

    result = tournament.generate_ranked_finalists(
        prompt=(
            "forge a staff that feels novel, avoids another lightning clone, "
            "and still reads as a clear mark-then-cashout loop"
        ),
        thesis_count=3,
        finalist_count=2,
        selected_tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    archive = WeaponLabArchive(
        prompt=result.prompt,
        theses={
            f"candidate-{index:03d}": thesis
            for index, thesis in enumerate(generator.generated, start=1)
        },
        finalists=[finalist.candidate_id for finalist in result.finalists],
        judge_scores={
            finalist.candidate_id: finalist.judge_scores
            for finalist in result.finalists
        },
        rejection_reasons=result.rejection_reasons,
    )
    scored = _import_orchestrator()._score_hidden_batch_finalists(archive)

    assert [finalist.candidate_id for finalist in result.finalists] == [
        "candidate-002",
        "candidate-001",
    ]
    assert archive.finalists == ["candidate-002", "candidate-001"]
    assert set(archive.theses) == {"candidate-001", "candidate-002", "candidate-003"}
    assert archive.rejection_reasons == {
        "candidate-003": "missing a readable seed-and-cashout loop"
    }
    assert archive.theses["candidate-002"].combat_package == "orbit_furnace"
    assert any(
        note == "risks bad anchor: generic elemental swap"
        for note in result.finalists[1].anchor_notes
    )
    assert [candidate_id for candidate_id, _ in scored] == archive.finalists
    assert scored[0][1] > scored[1][1]
