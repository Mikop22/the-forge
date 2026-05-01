from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BasisAtom:
    kind: str
    axis: str
    compatible_with: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    risk: str = "low"
    tier_min: str = "Tier3_Hardmode"
    notes: str = ""


BASIS_ATOMS: tuple[BasisAtom, ...] = (
    BasisAtom(
        "charge_phase",
        "cast_shape",
        compatible_with=("singularity_projectile", "beam_lance", "staged_release"),
        requires=("custom_projectile",),
        evidence=("timer or ai counter", "pre-release friendly=false staging"),
    ),
    BasisAtom(
        "channel_cast",
        "cast_shape",
        compatible_with=("beam_lance", "gravity_pull_field", "summoned_construct"),
        requires=("custom_projectile",),
        evidence=("player.channel", "held projectile state"),
    ),
    BasisAtom(
        "staged_release",
        "cast_shape",
        compatible_with=("charge_phase", "delayed_detonation", "satellite_fusion"),
        requires=("custom_projectile",),
        evidence=("phase state", "release transition"),
    ),
    BasisAtom(
        "singularity_projectile",
        "carrier",
        compatible_with=("gravity_pull_field", "implosion_payoff", "rift_trail"),
        requires=("custom_projectile",),
        evidence=("ModProjectile", "scale pulse", "Lighting.AddLight"),
    ),
    BasisAtom(
        "beam_lance",
        "carrier",
        compatible_with=("charge_phase", "color_separation_distortion"),
        requires=("custom_projectile",),
        evidence=("Colliding line check", "beam length", "PreDraw beam"),
    ),
    BasisAtom(
        "rift_projectile",
        "carrier",
        compatible_with=("portal_hop", "rift_trail", "shock_ring_damage"),
        requires=("custom_projectile",),
        evidence=("rift state", "oldPos trail", "purple/black draw pass"),
    ),
    BasisAtom(
        "summoned_construct",
        "carrier",
        compatible_with=("beam_lance", "delayed_detonation"),
        requires=("custom_projectile",),
        evidence=("Projectile.NewProjectile helper", "helper class or state"),
        risk="medium",
    ),
    BasisAtom(
        "slow_drift",
        "motion",
        compatible_with=("singularity_projectile", "gravity_pull_field"),
        requires=("custom_projectile",),
        evidence=("low velocity", "velocity damping"),
    ),
    BasisAtom(
        "ricochet_path",
        "motion",
        compatible_with=("rift_trail", "delayed_detonation"),
        requires=("custom_projectile",),
        evidence=("OnTileCollide", "bounce counter"),
    ),
    BasisAtom(
        "portal_hop",
        "motion",
        compatible_with=("rift_projectile", "delayed_detonation"),
        requires=("custom_projectile",),
        evidence=("teleport or reposition", "old/new position effects"),
        risk="medium",
    ),
    BasisAtom(
        "gravity_pull_field",
        "field_control",
        compatible_with=("singularity_projectile", "implosion_payoff"),
        requires=("custom_projectile",),
        evidence=("Main.npc scan", "distance radius", "velocity pull"),
        risk="medium",
    ),
    BasisAtom(
        "time_slow_field",
        "field_control",
        compatible_with=("delayed_detonation", "beam_lance"),
        requires=("custom_projectile",),
        evidence=("NPC velocity damping", "radius check"),
        risk="medium",
    ),
    BasisAtom(
        "implosion_payoff",
        "payoff",
        compatible_with=("singularity_projectile", "gravity_pull_field"),
        requires=("custom_projectile",),
        evidence=("collapse phase", "Projectile.Damage", "radius resize"),
    ),
    BasisAtom(
        "shock_ring_damage",
        "payoff",
        compatible_with=("implosion_payoff", "rift_projectile"),
        requires=("custom_projectile",),
        evidence=("ring radius", "Colliding", "expanding scale"),
    ),
    BasisAtom(
        "delayed_detonation",
        "payoff",
        compatible_with=("staged_release", "rift_projectile"),
        requires=("custom_projectile",),
        evidence=("delay timer", "planted state", "delayed damage"),
    ),
    BasisAtom(
        "bounded_terrain_carve",
        "world_interaction",
        compatible_with=("implosion_payoff", "shock_ring_damage"),
        requires=("custom_projectile",),
        evidence=("WorldGen.KillTile", "tile limit", "bounded loop"),
        risk="high",
    ),
    BasisAtom(
        "tile_scorch",
        "world_interaction",
        compatible_with=("rift_trail", "beam_lance"),
        requires=("custom_projectile",),
        evidence=("tile coordinate loop", "bounded visual-only effect"),
        risk="medium",
    ),
    BasisAtom(
        "orbiting_convergence",
        "combo_logic",
        compatible_with=("satellite_fusion", "implosion_payoff"),
        requires=("custom_projectile",),
        evidence=("orbit math", "satellite state", "convergence payoff"),
    ),
    BasisAtom(
        "satellite_fusion",
        "combo_logic",
        compatible_with=("orbiting_convergence", "beam_lance"),
        requires=("custom_projectile",),
        evidence=("multiple projectiles or offsets", "fusion/release phase"),
    ),
    BasisAtom(
        "phase_swap",
        "combo_logic",
        compatible_with=("portal_hop", "beam_lance"),
        requires=("custom_projectile",),
        evidence=("phase enum/state", "behavior swap"),
    ),
    BasisAtom(
        "rift_trail",
        "visual_grammar",
        compatible_with=("rift_projectile", "singularity_projectile"),
        requires=("custom_projectile",),
        evidence=("oldPos trail", "black/violet draw pass"),
    ),
    BasisAtom(
        "inward_particle_flow",
        "visual_grammar",
        compatible_with=("gravity_pull_field", "singularity_projectile"),
        requires=("custom_projectile",),
        evidence=("dust velocity toward center", "radial particle loop"),
    ),
    BasisAtom(
        "color_separation_distortion",
        "visual_grammar",
        compatible_with=("beam_lance", "rift_projectile"),
        requires=("custom_projectile",),
        evidence=("multiple tinted draw passes", "offset/fringe draw"),
    ),
)


def atom_by_kind(kind: str) -> BasisAtom:
    for atom in BASIS_ATOMS:
        if atom.kind == kind:
            return atom
    raise KeyError(f"Unknown mechanics basis atom: {kind}")


def atoms_for_axis(axis: str) -> list[BasisAtom]:
    return [atom for atom in BASIS_ATOMS if atom.axis == axis]
