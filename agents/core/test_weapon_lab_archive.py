"""Tests for agents/core/weapon_lab_archive.py."""

from __future__ import annotations

from core.weapon_lab_archive import WeaponLabArchive


def test_weapon_lab_archive_stores_required_audition_fields() -> None:
    archive = WeaponLabArchive.model_validate(
        {
            "prompt": "forge a fast lightning staff",
            "theses": {
                "candidate-001": {
                    "fantasy": "lightning brand that banks marks for a cashout",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                }
            },
            "finalists": ["candidate-001"],
            "art_strategies": {
                "candidate-001": {
                    "palette": "storm gold",
                    "silhouette": "forked staff",
                    "material_language": "brass filigree",
                },
            },
            "judge_scores": {
                "candidate-001": [
                    {
                        "candidate_id": "candidate-001",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 9,
                        "notes": "clear power fantasy",
                    }
                ]
            },
            "rejection_reasons": {"candidate-002": "fails differentiation gate"},
            "reroll_ancestry": {"candidate-003": ["candidate-001"]},
            "final_winner_rationale": "candidate-001 wins on clarity and payoff",
        }
    )

    assert archive.prompt == "forge a fast lightning staff"
    assert archive.finalists == ["candidate-001"]
    assert archive.theses["candidate-001"].combat_package == "storm_brand"
    assert archive.art_strategies["candidate-001"].palette == "storm gold"
    assert archive.judge_scores["candidate-001"][0].category == "clarity"
    assert archive.rejection_reasons["candidate-002"] == "fails differentiation gate"
    assert archive.reroll_ancestry["candidate-003"] == ["candidate-001"]
    assert archive.final_winner_rationale == "candidate-001 wins on clarity and payoff"
