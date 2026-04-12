from __future__ import annotations

import orchestrator


def test_build_hidden_batch_recovery_plan_discards_weak_batches_and_uses_explicit_budgets() -> (
    None
):
    plan = orchestrator.build_hidden_batch_recovery_plan(
        candidate_archive={
            "prompt": "forge a hidden audition storm weapon",
            "theses": {
                "candidate-001": {
                    "fantasy": "lightning marks targets before a storm-brand cashout",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                "candidate-002": {
                    "fantasy": "storm-brand lightning marks targets before the cashout",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
            },
            "finalists": ["candidate-001", "candidate-002"],
            "judge_scores": {
                "candidate-001": [
                    {
                        "candidate_id": "candidate-001",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 5,
                    }
                ],
                "candidate-002": [
                    {
                        "candidate_id": "candidate-002",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 6,
                    }
                ],
            },
            "rejection_reasons": {
                "candidate-001": "failed hidden batch",
                "candidate-002": "failed hidden batch",
            },
        },
        failed_batches=3,
        quality_threshold=8.0,
    )

    assert plan["discard_batch"] is True
    assert plan["recovery_mode"].search_profile == "wild"
    assert plan["recovery_mode"].quality_threshold == 8.0
    assert plan["search_budget"] == {
        "max_candidates": 10,
        "finalist_count": 2,
        "reroll_limit": 3,
    }
    assert plan["deduped_candidate_ids"] == ["candidate-002"]
    assert plan["recovery_candidates"] == []


def test_build_hidden_batch_recovery_plan_mutates_and_crossbreeds_near_misses_without_lowering_threshold() -> (
    None
):
    plan = orchestrator.build_hidden_batch_recovery_plan(
        candidate_archive={
            "prompt": "forge a hidden audition astral weapon",
            "theses": {
                "candidate-010": {
                    "fantasy": "astral marks stack into a verdict burst",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                "candidate-011": {
                    "fantasy": "moonlit marks collapse into a furnace verdict",
                    "combat_package": "orbit_furnace",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
            },
            "finalists": ["candidate-010", "candidate-011"],
            "judge_scores": {
                "candidate-010": [
                    {
                        "candidate_id": "candidate-010",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 8,
                    },
                    {
                        "candidate_id": "candidate-010",
                        "judge_id": "judge-b",
                        "category": "differentiation",
                        "score": 8,
                    },
                ],
                "candidate-011": [
                    {
                        "candidate_id": "candidate-011",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 8,
                    },
                    {
                        "candidate_id": "candidate-011",
                        "judge_id": "judge-b",
                        "category": "differentiation",
                        "score": 7,
                    },
                ],
            },
            "rejection_reasons": {
                "candidate-010": "lost after hidden batch review",
                "candidate-011": "lost after hidden batch review",
            },
        },
        failed_batches=3,
        quality_threshold=8.5,
    )

    assert plan["discard_batch"] is False
    assert plan["recovery_mode"].quality_threshold == 8.5
    assert [candidate["strategy"] for candidate in plan["recovery_candidates"]] == [
        "mutate",
        "mutate",
        "crossbreed",
    ]
    assert plan["recovery_candidates"][0]["search_budget"] == plan["search_budget"]
    assert plan["candidate_archive"].reroll_ancestry == {
        "recovery-001": ["candidate-010"],
        "recovery-002": ["candidate-011"],
        "recovery-003": ["candidate-010", "candidate-011"],
    }


def test_build_hidden_batch_recovery_plan_honors_explicit_search_budget_cap() -> None:
    from core.weapon_lab_models import SearchBudget

    plan = orchestrator.build_hidden_batch_recovery_plan(
        candidate_archive={
            "prompt": "forge a hidden audition celestial weapon",
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
                        "score": 8,
                    },
                ],
            },
            "rejection_reasons": {
                "candidate-101": "lost after hidden batch review",
                "candidate-102": "lost after hidden batch review",
            },
        },
        failed_batches=0,
        quality_threshold=8.5,
        search_budget=SearchBudget(max_candidates=2, finalist_count=2, reroll_limit=1),
    )

    assert plan["search_budget"] == {
        "max_candidates": 2,
        "finalist_count": 2,
        "reroll_limit": 1,
    }
    assert len(plan["recovery_candidates"]) == 2
    assert [candidate["candidate_id"] for candidate in plan["recovery_candidates"]] == [
        "recovery-001",
        "recovery-002",
    ]
    assert plan["candidate_archive"].reroll_ancestry == {
        "recovery-001": ["candidate-101"],
        "recovery-002": ["candidate-102"],
    }


def test_build_hidden_batch_recovery_plan_keeps_explicit_budget_authoritative_after_escalation() -> (
    None
):
    from core.weapon_lab_models import SearchBudget

    plan = orchestrator.build_hidden_batch_recovery_plan(
        candidate_archive={
            "prompt": "forge a hidden audition celestial weapon",
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
                        "score": 8,
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
        search_budget=SearchBudget(max_candidates=2, finalist_count=2, reroll_limit=1),
    )

    assert plan["recovery_mode"].search_profile == "wild"
    assert plan["search_budget"] == {
        "max_candidates": 2,
        "finalist_count": 2,
        "reroll_limit": 1,
    }
    assert len(plan["recovery_candidates"]) == 2
    assert [candidate["candidate_id"] for candidate in plan["recovery_candidates"]] == [
        "recovery-001",
        "recovery-002",
    ]


def test_build_hidden_batch_recovery_plan_coerces_dict_shaped_search_budget() -> None:
    plan = orchestrator.build_hidden_batch_recovery_plan(
        candidate_archive={
            "prompt": "forge a hidden audition celestial weapon",
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
                    }
                ],
                "candidate-102": [
                    {
                        "candidate_id": "candidate-102",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 8,
                    }
                ],
            },
            "rejection_reasons": {
                "candidate-101": "lost after hidden batch review",
                "candidate-102": "lost after hidden batch review",
            },
        },
        failed_batches=3,
        quality_threshold=8.5,
        search_budget={
            "max_candidates": 2,
            "finalist_count": 2,
            "reroll_limit": 1,
        },
    )

    assert plan["search_budget"] == {
        "max_candidates": 2,
        "finalist_count": 2,
        "reroll_limit": 1,
    }
    assert plan["recovery_mode"].search_budget.model_dump() == plan["search_budget"]


def test_build_hidden_batch_recovery_plan_cap_prefers_stronger_near_misses() -> None:
    from core.weapon_lab_models import SearchBudget

    plan = orchestrator.build_hidden_batch_recovery_plan(
        candidate_archive={
            "prompt": "forge a hidden audition celestial weapon",
            "theses": {
                "candidate-201": {
                    "fantasy": "celestial marks wobble into a small burst",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                "candidate-202": {
                    "fantasy": "astral marks collapse into a verdict burst",
                    "combat_package": "orbit_furnace",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
                "candidate-203": {
                    "fantasy": "moonlit marks collapse into a furnace burst",
                    "combat_package": "orbit_furnace",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                },
            },
            "finalists": ["candidate-201", "candidate-202", "candidate-203"],
            "judge_scores": {
                "candidate-201": [
                    {
                        "candidate_id": "candidate-201",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 8,
                    },
                    {
                        "candidate_id": "candidate-201",
                        "judge_id": "judge-b",
                        "category": "differentiation",
                        "score": 7,
                    },
                ],
                "candidate-202": [
                    {
                        "candidate_id": "candidate-202",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 9,
                    },
                    {
                        "candidate_id": "candidate-202",
                        "judge_id": "judge-b",
                        "category": "differentiation",
                        "score": 8,
                    },
                ],
                "candidate-203": [
                    {
                        "candidate_id": "candidate-203",
                        "judge_id": "judge-a",
                        "category": "clarity",
                        "score": 8,
                    },
                    {
                        "candidate_id": "candidate-203",
                        "judge_id": "judge-b",
                        "category": "differentiation",
                        "score": 8,
                    },
                ],
            },
            "rejection_reasons": {
                "candidate-201": "lost after hidden batch review",
                "candidate-202": "lost after hidden batch review",
                "candidate-203": "lost after hidden batch review",
            },
        },
        failed_batches=0,
        quality_threshold=8.5,
        search_budget=SearchBudget(max_candidates=2, finalist_count=2, reroll_limit=1),
    )

    assert [
        candidate["source_candidate_ids"] for candidate in plan["recovery_candidates"]
    ] == [
        ("candidate-202",),
        ("candidate-203",),
    ]
    assert plan["candidate_archive"].reroll_ancestry == {
        "recovery-001": ["candidate-202"],
        "recovery-002": ["candidate-203"],
    }
