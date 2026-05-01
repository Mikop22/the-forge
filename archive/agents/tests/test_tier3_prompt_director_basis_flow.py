import pytest

from architect.prompt_director import enhance_prompt
from architect.ranged_defaults import apply_default_custom_projectile


@pytest.mark.parametrize(
    ("prompt", "expected_terms", "expected_atoms"),
    [
        (
            "a staff that shoots gojo's hollow purple from jjk",
            ["gojo", "hollow purple", "jjk"],
            {"charge_phase", "singularity_projectile", "gravity_pull_field"},
        ),
        (
            "a cursed pistol that opens a rift under enemies",
            [],
            {"rift_projectile", "rift_trail", "shock_ring_damage"},
        ),
        (
            "a bow that plants delayed void marks then collapses them",
            [],
            {"delayed_detonation", "implosion_payoff"},
        ),
        (
            "a wand that fires a sweeping moon beam lance",
            [],
            {"beam_lance", "charge_phase"},
        ),
        (
            "a hammer that sends a ground rupture forward",
            [],
            {"bounded_terrain_carve", "shock_ring_damage"},
        ),
    ],
)
def test_prompt_director_and_basis_golden_prompts(
    prompt: str, expected_terms: list[str], expected_atoms: set[str]
) -> None:
    director = enhance_prompt(prompt, tier="Tier3_Hardmode")
    assert director.raw_prompt == prompt
    for term in expected_terms:
        assert term in director.protected_reference_terms
    if expected_terms:
        assert director.reference_slots.projectile.protected_terms

    data = {
        "item_name": "GoldenTest",
        "display_name": "Golden Test",
        "type": "weapon",
        "content_type": "Weapon",
        "sub_type": "Staff",
        "tier": "Tier3_Hardmode",
        "mechanics": {"custom_projectile": None, "shoot_projectile": None},
        "projectile_visuals": {
            "description": "test projectile",
            "icon_size": [20, 20],
        },
    }
    apply_default_custom_projectile(data, director.enhanced_prompt, "Tier3_Hardmode")

    kinds = {atom["kind"] for atom in data["mechanics_ir"]["atoms"]}
    assert len(kinds) >= 2
    assert expected_atoms.issubset(kinds)
