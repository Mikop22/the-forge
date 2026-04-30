from architect.mechanics_basis import BASIS_ATOMS, atom_by_kind, atoms_for_axis


def test_mechanics_basis_contains_spanning_axes() -> None:
    axes = {atom.axis for atom in BASIS_ATOMS}

    assert "cast_shape" in axes
    assert "carrier" in axes
    assert "motion" in axes
    assert "field_control" in axes
    assert "payoff" in axes
    assert "world_interaction" in axes
    assert "combo_logic" in axes
    assert "visual_grammar" in axes


def test_gravity_pull_atom_declares_evidence_and_compatibility() -> None:
    atom = atom_by_kind("gravity_pull_field")

    assert atom.axis == "field_control"
    assert "singularity_projectile" in atom.compatible_with
    assert any("Main.npc" in evidence for evidence in atom.evidence)
    assert atom.tier_min == "Tier3_Hardmode"


def test_atoms_for_axis_filters_basis() -> None:
    carriers = atoms_for_axis("carrier")

    assert carriers
    assert all(atom.axis == "carrier" for atom in carriers)
