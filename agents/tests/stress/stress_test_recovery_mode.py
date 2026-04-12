from __future__ import annotations

import importlib


def _import_orchestrator():
    return importlib.import_module("orchestrator")


def test_recovery_mode_keeps_quality_bar_and_archive_ancestry_for_near_misses() -> None:
    orchestrator = _import_orchestrator()

    plan = orchestrator.build_hidden_batch_recovery_plan(
        candidate_archive={
            "prompt": "forge a hidden audition celestial staff",
            "theses": {
                "candidate-101": {
                    "fantasy": "celestial marks collapse into a verdict burst",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                "candidate-102": {
                    "fantasy": "orbiting embers collapse into a forge burst",
                    "combat_package": "orbit_furnace",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
            },
            "finalists": ["candidate-101", "candidate-102"],
            "judge_scores": {
                "candidate-101": [
                    {
                        "candidate_id": "candidate-101",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 8,
                    },
                    {
                        "candidate_id": "candidate-101",
                        "judge_id": "judge-b",
                        "category": "differentiation",
                        "score": 8,
                    },
                ],
                "candidate-102": [
                    {
                        "candidate_id": "candidate-102",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 8,
                    },
                    {
                        "candidate_id": "candidate-102",
                        "judge_id": "judge-b",
                        "category": "differentiation",
                        "score": 7,
                    },
                ],
            },
            "rejection_reasons": {
                "candidate-101": "lost after hidden batch review",
                "candidate-102": "lost after hidden batch review",
            },
        },
        failed_batches=3,
        quality_threshold=8.5,
    )

    assert plan["discard_batch"] is False
    assert plan["recovery_mode"].search_profile == "wild"
    assert plan["recovery_mode"].allow_quality_drop is False
    assert plan["recovery_mode"].quality_threshold == 8.5
    assert [candidate["strategy"] for candidate in plan["recovery_candidates"]] == [
        "mutate",
        "mutate",
        "crossbreed",
    ]
    assert plan["candidate_archive"].reroll_ancestry == {
        "recovery-001": ["candidate-101"],
        "recovery-002": ["candidate-102"],
        "recovery-003": ["candidate-101", "candidate-102"],
    }
