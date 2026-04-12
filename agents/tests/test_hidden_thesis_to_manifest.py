from __future__ import annotations

from architect.architect import ArchitectAgent
from architect.thesis_generator import ThesisFinalist
from core.runtime_capabilities import RuntimeCapabilityMatrix
from core.weapon_lab_models import WeaponThesis


def _make_finalist(
    *,
    package_key: str = "storm_brand",
    payoff_rate: str = "fast",
    fantasy: str = "storm brand staff that marks targets, then cashes out in a starfall burst",
    reasons: list[str] | None = None,
) -> ThesisFinalist:
    return ThesisFinalist(
        candidate_id="candidate-001",
        thesis=WeaponThesis(
            fantasy=fantasy,
            combat_package=package_key,
            delivery_style="direct",
            payoff_rate=payoff_rate,
            loop_family="mark_cashout",
        ),
        total_score=9.0,
        reasons=reasons or [],
    )


def _make_agent() -> ArchitectAgent:
    agent = ArchitectAgent.__new__(ArchitectAgent)
    agent._runtime_capability_matrix = RuntimeCapabilityMatrix.default()
    agent._reference_policy = type(
        "StubReferencePolicy",
        (),
        {
            "resolve": staticmethod(
                lambda **_: {
                    "reference_needed": False,
                    "reference_subject": None,
                    "reference_image_url": None,
                    "reference_notes": "reference_not_requested",
                }
            )
        },
    )()
    return agent


def test_staff_finalist_expands_to_package_first_manifest() -> None:
    agent = _make_agent()

    manifest = agent.expand_thesis_finalist_to_manifest(
        finalist=_make_finalist(),
        prompt="forge a storm brand hidden audition staff",
        tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert manifest["mechanics"]["combat_package"] == "storm_brand"
    assert manifest["mechanics"]["delivery_style"] == "direct"
    assert manifest["mechanics"]["payoff_rate"] == "fast"
    assert manifest["resolved_combat"]["package_key"] == "storm_brand"
    assert manifest["fallback_reason"] is None


def test_staff_finalist_synthesizes_imageable_package_visual_brief() -> None:
    agent = _make_agent()
    fantasy = (
        "storm brand staff that marks targets every 1-3s, then cashes out in a "
        "rewarding starfall burst"
    )

    manifest = agent.expand_thesis_finalist_to_manifest(
        finalist=_make_finalist(fantasy=fantasy),
        prompt="forge a storm brand hidden audition staff",
        tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    visual_description = manifest["visuals"]["description"]

    assert visual_description != fantasy
    assert "staff" in visual_description.lower()
    assert "storm" in visual_description.lower()
    assert "mark" not in visual_description.lower()
    assert "cashout" not in visual_description.lower()
    assert "rewarding" not in visual_description.lower()
    assert "1-3s" not in visual_description.lower()


def test_staff_finalist_synthesizes_projectile_visual_brief_from_package_prompt() -> (
    None
):
    agent = _make_agent()
    fantasy = (
        "storm brand staff that marks targets every 1-3s, then cashes out in a "
        "rewarding starfall burst"
    )

    manifest = agent.expand_thesis_finalist_to_manifest(
        finalist=_make_finalist(fantasy=fantasy),
        prompt="forge a storm brand hidden audition staff",
        tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    projectile_description = manifest["projectile_visuals"]["description"]

    assert projectile_description != fantasy
    assert projectile_description != manifest["visuals"]["description"]
    assert (
        "bolt" in projectile_description.lower()
        or "sigil" in projectile_description.lower()
    )
    assert "cashout" not in projectile_description.lower()
    assert "rewarding" not in projectile_description.lower()
    assert "1-3s" not in projectile_description.lower()


def test_staff_finalist_expands_with_hidden_runtime_gate_contract_fields() -> None:
    agent = _make_agent()

    manifest = agent.expand_thesis_finalist_to_manifest(
        finalist=_make_finalist(),
        prompt="forge a storm brand hidden audition staff",
        tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert manifest["candidate_id"] == "candidate-001"
    assert manifest["package_key"] == "storm_brand"
    assert manifest["loop_family"] == "mark_cashout"
    assert manifest["behavior_contract"] == {
        "seed_event": "seed_triggered",
        "escalate_event": "escalate_triggered",
        "cashout_event": "cashout_triggered",
        "max_hits_to_cashout": 3,
        "max_time_to_cashout_ms": 2500,
    }
    assert manifest["weapon_thesis"] == {
        "fantasy": (
            "storm brand staff that marks targets, then cashes out in a starfall burst"
        ),
        "combat_package": "storm_brand",
        "delivery_style": "direct",
        "payoff_rate": "fast",
        "loop_family": "mark_cashout",
    }


def test_staff_finalist_expansion_reuses_manifest_finalization_behaviors() -> None:
    agent = _make_agent()
    agent._reference_policy = type(
        "StubReferencePolicy",
        (),
        {
            "resolve": staticmethod(
                lambda **_: {
                    "reference_needed": True,
                    "reference_subject": "storm brand relic",
                    "reference_image_url": "https://example.com/storm-brand.png",
                    "reference_notes": "approved_reference",
                }
            )
        },
    )()

    manifest = agent.expand_thesis_finalist_to_manifest(
        finalist=_make_finalist(),
        prompt="forge a storm brand hidden audition staff",
        tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
        crafting_station="Workbench",
    )

    assert manifest["mechanics"]["crafting_tile"] == "TileID.WorkBenches"
    assert manifest["generation_mode"] == "image_to_image"
    assert manifest["reference_subject"] == "storm brand relic"
    assert (
        "Preserve exact subject identity for storm brand relic"
        in manifest["visuals"]["description"]
    )


def test_unsupported_family_still_falls_back_to_legacy_projection() -> None:
    agent = _make_agent()

    manifest = agent.expand_thesis_finalist_to_manifest(
        finalist=_make_finalist(),
        prompt="forge a storm brand hidden audition sword",
        tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Sword",
    )

    assert manifest["mechanics"]["combat_package"] is None
    assert manifest["mechanics"]["shot_style"] == "direct"
    assert manifest["resolved_combat"] is None
    assert manifest["fallback_reason"] == (
        "allowed legacy fallback: runtime surface Weapon/Sword does not support mark_cashout"
    )


def test_supported_staff_ignores_unbounded_homage_words_without_explicit_marker() -> (
    None
):
    agent = _make_agent()

    manifest = agent.expand_thesis_finalist_to_manifest(
        finalist=_make_finalist(
            fantasy="storm brand homage staff that marks targets, then cashes out in a starfall burst",
            reasons=["judge mentioned homage vibes"],
        ),
        prompt="forge a storm brand homage staff",
        tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
    )

    assert manifest["mechanics"]["combat_package"] == "storm_brand"
    assert manifest["resolved_combat"]["package_key"] == "storm_brand"
    assert manifest["fallback_reason"] is None


def test_supported_staff_fallback_requires_explicit_homage_or_simple_fallback_marker() -> (
    None
):
    agent = _make_agent()

    manifest = agent.expand_thesis_finalist_to_manifest(
        finalist=_make_finalist(),
        prompt="forge a storm brand homage staff",
        tier="Tier2_Dungeon",
        content_type="Weapon",
        sub_type="Staff",
        legacy_fallback_marker="homage",
    )

    assert manifest["mechanics"]["combat_package"] is None
    assert manifest["mechanics"]["shot_style"] == "direct"
    assert manifest["resolved_combat"] is None
    assert manifest["fallback_reason"] == (
        "allowed legacy fallback: explicit homage marker on supported Weapon/Staff surface"
    )
    assert "package_key" not in manifest
    assert "loop_family" not in manifest
    assert "behavior_contract" not in manifest
    assert manifest["weapon_thesis"] == {
        "fantasy": (
            "storm brand staff that marks targets, then cashes out in a starfall burst"
        ),
        "combat_package": "storm_brand",
        "delivery_style": "direct",
        "payoff_rate": "fast",
        "loop_family": "mark_cashout",
    }
