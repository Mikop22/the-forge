from stress_tier3_basis import DEFAULT_PROMPTS, run_deterministic_stress


def test_default_tier3_stress_prompt_set_matches_user_batch() -> None:
    assert DEFAULT_PROMPTS == [
        "a staff that shoots gojo's hollow purple from jjk",
        "a wand that fires a sweeping moon beam lance",
        "a cursed pistol that opens rifts under enemies",
        "a bow that plants delayed void marks then collapses them",
        "a hammer that sends a ground rupture forward and breaks weak blocks",
        "a tome that summons a temporary eye that fires a beam for the player",
        "a spear that throws orbiting shards which converge into one final strike",
        "a gun that fires a ricocheting portal round that tears space at each bounce",
    ]


def test_deterministic_stress_covers_expected_basis_families() -> None:
    expected_atoms = {
        DEFAULT_PROMPTS[0]: {"charge_phase", "singularity_projectile", "gravity_pull_field"},
        DEFAULT_PROMPTS[1]: {"charge_phase", "beam_lance"},
        DEFAULT_PROMPTS[2]: {"rift_projectile", "rift_trail", "shock_ring_damage"},
        DEFAULT_PROMPTS[3]: {"delayed_detonation", "implosion_payoff"},
        DEFAULT_PROMPTS[4]: {"bounded_terrain_carve", "shock_ring_damage"},
        DEFAULT_PROMPTS[5]: {"summoned_construct", "beam_lance"},
        DEFAULT_PROMPTS[6]: {"orbiting_convergence", "satellite_fusion"},
        DEFAULT_PROMPTS[7]: {"ricochet_path", "portal_hop", "rift_trail"},
    }

    results = run_deterministic_stress(DEFAULT_PROMPTS)

    assert len(results) == len(DEFAULT_PROMPTS)
    for result in results:
        assert result.passed, result.failures
        assert expected_atoms[result.prompt].issubset(set(result.atom_kinds))


def test_deterministic_stress_preserves_projectile_reference_slot() -> None:
    [result] = run_deterministic_stress([DEFAULT_PROMPTS[0]])

    assert result.protected_reference_terms == ["gojo", "hollow purple", "jjk"]
    assert result.projectile_reference_subject == "Gojo Hollow Purple from JJK"
