from __future__ import annotations

from core.cross_consistency import evaluate_cross_consistency


def test_cross_consistency_rejects_art_that_does_not_match_mechanic_fantasy() -> None:
    verdict = evaluate_cross_consistency(
        prompt="celestial storm condemnation staff",
        thesis={
            "fantasy": "condemn marked targets with starfall",
            "combat_package": "storm_brand",
        },
        manifest={
            "sub_type": "Staff",
            "mechanics": {"combat_package": "storm_brand"},
        },
        item_visual_summary="plain wooden wand with no celestial motif",
        projectile_visual_summary="generic blue orb",
    )

    assert verdict.passed is False
    assert verdict.score < verdict.minimum_score
    assert verdict.fail_reason is not None
    assert "storm_brand" in verdict.fail_reason


def test_cross_consistency_does_not_use_art_file_paths_as_primary_signal() -> None:
    verdict = evaluate_cross_consistency(
        prompt="celestial storm condemnation staff",
        thesis={
            "fantasy": "condemn marked targets with starfall",
            "combat_package": "storm_brand",
        },
        manifest={
            "sub_type": "Staff",
            "mechanics": {"combat_package": "storm_brand"},
        },
        item_visual_summary="plain wooden wand with no celestial motif",
        projectile_visual_summary="generic blue orb",
        item_art_output="/tmp/storm-brand-celestial.png",
    )

    assert verdict.passed is False
    assert verdict.score < verdict.minimum_score


def test_cross_consistency_rejects_low_structured_art_signals_even_with_neutral_prose() -> (
    None
):
    verdict = evaluate_cross_consistency(
        prompt="celestial storm condemnation staff",
        thesis={
            "fantasy": "condemn marked targets with starfall",
            "combat_package": "storm_brand",
        },
        manifest={
            "sub_type": "Staff",
            "mechanics": {"combat_package": "storm_brand"},
        },
        item_visual_summary="observed winner candidate",
        projectile_visual_summary="observed projectile candidate",
        item_motif_strength=2.0,
        item_family_coherence=2.5,
        item_sprite_gate_passed=True,
        item_secondary_summary="neutral note",
    )

    assert verdict.passed is False
    assert verdict.score < verdict.minimum_score


def test_cross_consistency_accepts_good_structured_signals_when_observed_summaries_are_absent() -> (
    None
):
    verdict = evaluate_cross_consistency(
        prompt="celestial storm condemnation staff",
        thesis={
            "fantasy": "condemn marked targets with starfall",
            "combat_package": "storm_brand",
        },
        manifest={
            "sub_type": "Staff",
            "mechanics": {"combat_package": "storm_brand"},
        },
        item_visual_summary="",
        projectile_visual_summary="",
        item_motif_strength=6.0,
        item_family_coherence=6.0,
        item_sprite_gate_passed=True,
        item_secondary_summary="neutral note",
        projectile_secondary_summary="observed candidate",
    )

    assert verdict.passed is True
    assert verdict.score >= verdict.minimum_score


def test_cross_consistency_does_not_use_art_file_paths_as_secondary_signal() -> None:
    verdict = evaluate_cross_consistency(
        prompt="celestial storm condemnation staff",
        thesis={
            "fantasy": "condemn marked targets with starfall",
            "combat_package": "storm_brand",
        },
        manifest={
            "sub_type": "Staff",
            "mechanics": {"combat_package": "storm_brand"},
        },
        item_visual_summary="plain wooden wand with no celestial motif",
        projectile_visual_summary="generic blue orb",
        item_secondary_summary="neutral note",
        projectile_secondary_summary="observed candidate",
        item_art_output="/tmp/storm_brand-celestial-starfall.png",
        projectile_art_output="/tmp/lightning-mark.png",
    )

    assert verdict.passed is False
    assert verdict.score < verdict.minimum_score


def test_cross_consistency_does_not_promote_weapon_thesis_into_execution_package() -> (
    None
):
    verdict = evaluate_cross_consistency(
        prompt="celestial storm condemnation staff",
        thesis={
            "fantasy": "condemn marked targets with starfall",
            "combat_package": "storm_brand",
        },
        manifest={
            "sub_type": "Staff",
            "mechanics": {"combat_package": None},
        },
        item_visual_summary="plain wooden wand with no celestial motif",
        projectile_visual_summary="generic blue orb",
    )

    assert verdict.passed is True
    assert verdict.score == 1.0
    assert verdict.fail_reason is None
