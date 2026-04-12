from __future__ import annotations

from architect.architect import ArchitectAgent
from architect.thesis_generator import ThesisFinalist
from core.runtime_capabilities import RuntimeCapabilityMatrix
from core.weapon_lab_archive import WeaponLabArchive
from core.weapon_lab_models import WeaponThesis


class _StubReferencePolicy:
    def resolve(self, **_: object) -> dict[str, object]:
        return {
            "reference_needed": False,
            "reference_subject": None,
            "reference_image_url": None,
            "reference_notes": None,
        }


def _make_agent() -> ArchitectAgent:
    agent = ArchitectAgent.__new__(ArchitectAgent)
    agent._runtime_capability_matrix = RuntimeCapabilityMatrix.default()
    agent._reference_policy = _StubReferencePolicy()
    return agent


def _make_finalist(candidate_id: str, fantasy: str, package_key: str) -> ThesisFinalist:
    return ThesisFinalist(
        candidate_id=candidate_id,
        thesis=WeaponThesis(
            fantasy=fantasy,
            combat_package=package_key,
            delivery_style="direct",
            payoff_rate="fast",
            loop_family="mark_cashout",
        ),
        total_score=8.5,
    )


def test_ambiguous_staff_prompt_expands_to_package_first_finalists() -> None:
    prompt = "forge a staff that brands enemies, then drops an astral verdict"
    finalists = [
        _make_finalist(
            "candidate-001",
            "lightning brand staff that marks targets before a starfall verdict",
            "storm_brand",
        ),
        _make_finalist(
            "candidate-002",
            "orbiting embers tag targets before a forge collapse verdict",
            "orbit_furnace",
        ),
    ]
    archive = WeaponLabArchive(
        prompt=prompt,
        theses={candidate.candidate_id: candidate.thesis for candidate in finalists},
        finalists=[candidate.candidate_id for candidate in finalists],
    )
    agent = _make_agent()

    manifests = [
        agent.expand_thesis_finalist_to_manifest(
            finalist=finalist,
            prompt=archive.prompt,
            tier="Tier2_Dungeon",
            content_type="Weapon",
            sub_type="Staff",
        )
        for finalist in finalists
    ]

    assert archive.finalists == ["candidate-001", "candidate-002"]
    assert [manifest["mechanics"]["combat_package"] for manifest in manifests] == [
        "storm_brand",
        "orbit_furnace",
    ]
    assert all(manifest["fallback_reason"] is None for manifest in manifests)
    assert all(manifest["sub_type"] == "Staff" for manifest in manifests)
    assert [manifest["resolved_combat"]["package_key"] for manifest in manifests] == [
        "storm_brand",
        "orbit_furnace",
    ]
