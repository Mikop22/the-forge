import json
from unittest.mock import MagicMock, patch


import sys
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from forge_master.prompts import CODEGEN_SYSTEM
from forge_master.forge_master import CoderAgent
from forge_master.models import CSharpOutput
from forge_master.reviewer import (
    REVIEW_SYSTEM,
    ReviewIssue,
    ReviewOutput,
    WeaponReviewer,
)
from core.cross_consistency import apply_hidden_audition_consistency_gate
from pixelsmith.models import PixelsmithReviewedHiddenAuditionOutput
from forge_master.templates import SWORD_TEMPLATE


_PHASE1_PACKAGES = ("storm_brand", "orbit_furnace", "frost_shatter")
_RESOLVED_COMBAT_PATHS = (
    "resolved_combat.package_key",
    "resolved_combat.delivery_module",
    "resolved_combat.combo_module",
    "resolved_combat.finisher_module",
    "resolved_combat.presentation_module",
)


def _make_reviewer() -> WeaponReviewer:
    """Construct a WeaponReviewer without hitting the OpenAI API key check."""
    with patch("forge_master.reviewer.ChatOpenAI", return_value=MagicMock()):
        return WeaponReviewer(model_name="gpt-4o-mini")


def test_reviewer_approves_good_code():
    reviewer = _make_reviewer()

    mock_review_output = ReviewOutput(approved=True, issues=[], summary="Looks good!")
    reviewer._review_chain = MagicMock()
    reviewer._review_chain.invoke.return_value = mock_review_output

    manifest = {
        "item_name": "TestSword",
        "mechanics": {"shot_style": "direct", "custom_projectile": False},
    }
    cs_code = "class TestSword {}"

    new_code, final_review = reviewer.review(manifest, cs_code)

    assert final_review.approved is True
    assert final_review.summary == "Looks good!"
    assert new_code == cs_code
    reviewer._review_chain.invoke.assert_called_once()


def test_reviewer_fixes_bad_code():
    reviewer = _make_reviewer()

    reviewer._review_chain = MagicMock()
    reviewer._fix_chain = MagicMock()

    bad_review = ReviewOutput(
        approved=False,
        issues=[
            ReviewIssue(
                severity="critical",
                category="shot_style",
                description="Missing Item.channel",
                suggested_fix="Add Item.channel=true to SetDefaults",
            )
        ],
        summary="Missing channel",
    )

    good_review = ReviewOutput(approved=True, issues=[], summary="Fixed")

    # First call returns bad, second call returns good
    reviewer._review_chain.invoke.side_effect = [bad_review, good_review]
    reviewer._fix_chain.invoke.return_value = "class FixedTestSword {}"

    manifest = {"item_name": "TestSword", "mechanics": {"shot_style": "channeled"}}
    cs_code = "class TestSword {}"

    new_code, final_review = reviewer.review(manifest, cs_code)

    assert new_code == "class FixedTestSword {}"
    assert final_review.approved is True
    assert reviewer._review_chain.invoke.call_count == 2
    assert reviewer._fix_chain.invoke.call_count == 1


def test_reviewer_info_only_issues_approved():
    """Info-only issues should approve without mutating the original ReviewOutput."""
    reviewer = _make_reviewer()

    info_review = ReviewOutput(
        approved=False,
        issues=[
            ReviewIssue(
                severity="info",
                category="style",
                description="Could use a helper method",
                suggested_fix="Extract method",
            )
        ],
        summary="Only style issues",
    )
    reviewer._review_chain = MagicMock()
    reviewer._review_chain.invoke.return_value = info_review

    manifest = {"item_name": "TestSword", "mechanics": {"shot_style": "direct"}}
    _, final_review = reviewer.review(manifest, "class TestSword {}")

    assert final_review.approved is True
    # Original LLM result should not have been mutated
    assert info_review.approved is False


def test_codegen_prompt_mentions_resolved_combat_packages_and_legacy_shot_style():
    assert "resolved_combat" in CODEGEN_SYSTEM
    assert "source of truth" in CODEGEN_SYSTEM
    assert (
        "`resolved_combat.package_key` is the authoritative package selector"
        in CODEGEN_SYSTEM
    )
    assert (
        "`mechanics.combat_package` as the human-readable package selector that should align with `resolved_combat.package_key`"
        in CODEGEN_SYSTEM
    )
    assert "fallback manifests" not in CODEGEN_SYSTEM

    for field_path in _RESOLVED_COMBAT_PATHS:
        assert f"`{field_path}`" in CODEGEN_SYSTEM

    for package_name in _PHASE1_PACKAGES:
        assert f"`{package_name}`" in CODEGEN_SYSTEM

    assert "freeform interpretation" in CODEGEN_SYSTEM
    assert "If no package is present" in CODEGEN_SYSTEM
    assert '"sky_strike"' in CODEGEN_SYSTEM


def test_review_prompt_mentions_combat_package_criteria_and_legacy_shot_style():
    assert "resolved_combat" in REVIEW_SYSTEM
    assert "source of truth" in REVIEW_SYSTEM
    assert (
        "Use `mechanics.combat_package` as the human-readable package label that should match `resolved_combat.package_key`."
        in REVIEW_SYSTEM
    )
    assert "fall back" not in REVIEW_SYSTEM

    for field_path in _RESOLVED_COMBAT_PATHS:
        assert f"`{field_path}`" in REVIEW_SYSTEM

    for package_name in _PHASE1_PACKAGES:
        assert f"`{package_name}`" in REVIEW_SYSTEM

    assert "seed trigger exists" in REVIEW_SYSTEM
    assert "escalate state is represented" in REVIEW_SYSTEM
    assert "finisher trigger" in REVIEW_SYSTEM
    assert "reachable" in REVIEW_SYSTEM
    assert "resets or consumes correctly" in REVIEW_SYSTEM
    assert "escalates on" in REVIEW_SYSTEM
    assert "finisher" in REVIEW_SYSTEM
    assert '"channeled"' in REVIEW_SYSTEM
    assert '"sky_strike"' in REVIEW_SYSTEM


def test_reviewer_accepts_combat_package_manifest_path():
    reviewer = _make_reviewer()

    mock_review_output = ReviewOutput(
        approved=True, issues=[], summary="Combat package looks good!"
    )
    reviewer._review_chain = MagicMock()
    reviewer._review_chain.invoke.return_value = mock_review_output

    manifest = {
        "item_name": "StormBrand",
        "mechanics": {"combat_package": "storm_brand"},
        "resolved_combat": {
            "package_key": "storm_brand",
            "delivery_module": "seed_on_hit",
            "combo_module": "brand_charge_combo",
            "finisher_module": "brand_burst_finisher",
            "presentation_module": "storm_brand_fx",
        },
    }

    new_code, final_review = reviewer.review(manifest, "class StormBrand {}")

    assert final_review.approved is True
    assert new_code == "class StormBrand {}"
    reviewer._review_chain.invoke.assert_called_once()
    manifest_json = reviewer._review_chain.invoke.call_args.args[0]["manifest_json"]
    assert '"combat_package": "storm_brand"' in manifest_json
    assert '"resolved_combat"' in manifest_json
    assert '"package_key": "storm_brand"' in manifest_json


def test_write_code_uses_validated_manifest_for_codegen_and_review():
    agent = CoderAgent.__new__(CoderAgent)
    agent._gen_chain = MagicMock(
        invoke=MagicMock(return_value=CSharpOutput(code=SWORD_TEMPLATE))
    )
    agent._reviewer = MagicMock(
        review=MagicMock(
            return_value=(
                SWORD_TEMPLATE,
                ReviewOutput(approved=True, issues=[], summary="Looks good!"),
            )
        )
    )

    manifest = {
        "item_name": "my test sword!!!",
        "display_name": "My Test Sword",
        "tooltip": "Cuts things.",
        "stats": {
            "damage": 10,
            "knockback": 4.0,
            "use_time": 20,
            "rarity": "ItemRarityID.Green",
        },
        "mechanics": {
            "crafting_material": "ItemID.Wood",
            "crafting_cost": 5,
            "crafting_tile": "TileID.WorkBenches",
        },
    }

    result = agent.write_code(manifest)

    assert result["status"] == "success"

    manifest_json = agent._gen_chain.invoke.call_args.args[0]["manifest_json"]
    downstream_manifest = json.loads(manifest_json)
    assert downstream_manifest["item_name"] == "MyTestSword"
    assert "my test sword!!!" not in manifest_json

    reviewed_manifest = agent._reviewer.review.call_args.args[0]
    assert reviewed_manifest["item_name"] == "MyTestSword"
    assert reviewed_manifest["display_name"] == "My Test Sword"


def test_hidden_audition_consistency_review_rejects_mechanically_off_theme_art() -> (
    None
):
    finalists = [
        {
            "candidate_id": "candidate-001",
            "item_name": "StormBrand",
            "sub_type": "Staff",
            "mechanics": {"combat_package": "storm_brand"},
            "visuals": {"description": "celestial lightning staff with storm halo"},
            "weapon_thesis": {
                "fantasy": "condemn marked targets with starfall",
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
                "loop_family": "mark_cashout",
            },
        }
    ]
    art_audition = {
        "status": "success",
        "art_scored_finalists": [
            {
                "finalist_id": "candidate-001",
                "item_name": "StormBrand",
                "item_sprite_path": "/tmp/storm-brand-celestial.png",
                "item_visual_summary": "",
                "projectile_visual_summary": "",
                "observed_art_signals": {
                    "item_motif_strength": 2.0,
                    "item_family_coherence": 2.0,
                    "item_sprite_gate_passed": True,
                },
                "winner_candidate_id": "candidate-001-art-001",
                "winner_art_scores": {
                    "motif_strength": 2.0,
                    "family_coherence": 2.0,
                    "notes": "neutral note",
                },
                "winner_sprite_gate_report": {
                    "sprite_kind": "item",
                    "passed": True,
                    "foreground_bbox": [8, 6, 23, 25],
                    "checks": {},
                },
                "surviving_candidates": [
                    {
                        "candidate_id": "candidate-001-art-001",
                        "sprite_gate_report": {
                            "sprite_kind": "item",
                            "passed": True,
                            "foreground_bbox": [8, 6, 23, 25],
                            "checks": {},
                        },
                        "motif_strength": 2.0,
                        "family_coherence": 2.0,
                        "judge_notes": "neutral note",
                    }
                ],
            }
        ],
        "candidate_archive": {
            "prompt": "celestial storm condemnation staff",
            "theses": {
                "candidate-001": {
                    "fantasy": "condemn marked targets with starfall",
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                    "loop_family": "mark_cashout",
                }
            },
            "finalists": ["candidate-001"],
            "rejection_reasons": {},
        },
    }

    reviewed = apply_hidden_audition_consistency_gate(
        prompt="celestial storm condemnation staff",
        finalists=finalists,
        art_audition=art_audition,
    )
    validated = PixelsmithReviewedHiddenAuditionOutput.model_validate(reviewed)

    assert validated.art_scored_finalists == []
    assert validated.cross_consistency_reports["candidate-001"].passed is False
    assert (
        validated.cross_consistency_reports["candidate-001"].score
        < validated.cross_consistency_reports["candidate-001"].minimum_score
    )
    assert "candidate-001" in validated.candidate_archive.rejection_reasons
