"""Default `custom_projectile` and projectile art for direct-shot ranged weapons."""

from __future__ import annotations

from architect.models import RANGED_PROJECTILE_SUBTYPES


def apply_default_custom_projectile(
    data: dict, user_prompt: str, selected_tier: str = ""
) -> None:
    """Set ``mechanics.custom_projectile`` to True for legacy ranged (no package).

    The Forge + Pixelsmith pipeline then emits a :class:`ModProjectile` and a
    generated sprite instead of a vanilla :class:`ProjectileID` stand-in.

    Opt out by setting ``mechanics.custom_projectile`` to ``False`` and a real
    ``ProjectileID.*`` in ``mechanics.shoot_projectile`` (vanilla homage). If the
    model sets ``custom_projectile`` to false but leaves ``shoot_projectile``
    empty, that is treated as a schema default, not a completed opt-out.
    """
    mech = data.get("mechanics")
    if not isinstance(mech, dict):
        return
    if mech.get("combat_package"):
        _seed_spectacle_plan(
            data, user_prompt, selected_tier, str(data.get("sub_type", ""))
        )
        return
    st = str(data.get("sub_type", ""))
    if st not in RANGED_PROJECTILE_SUBTYPES:
        return
    if str(mech.get("shot_style", "direct")) != "direct":
        sp = mech.get("shoot_projectile")
        if str(selected_tier).startswith("Tier3") and (
            sp is None or not str(sp).strip()
        ):
            mech["shot_style"] = "direct"
        else:
            return
    if mech.get("custom_projectile") is False:
        sp = mech.get("shoot_projectile")
        if sp is not None and str(sp).strip():
            return
        # ``False`` + no ProjectileID: treat as schema default, not a real
        # vanilla-homage opt-out (opt-out must supply a ``ProjectileID.*``).
    mech["custom_projectile"] = True
    mech["shoot_projectile"] = None

    vis = data.get("visuals") if isinstance(data.get("visuals"), dict) else {}
    item_look = str(vis.get("description", "")).strip()
    snippet = (user_prompt or "").strip()[:240]
    line = (
        f"Single projectile for this {st}. {item_look} "
        f"Energy core, readable silhouette, Terraria scale."
    )
    if not item_look and snippet:
        line = f"Single projectile: {snippet}"

    pv = data.get("projectile_visuals")
    if isinstance(pv, dict) and str(pv.get("description", "")).strip():
        _seed_spectacle_plan(data, user_prompt, selected_tier, st)
        return
    anim = "static"
    icon: list[int] = [20, 20]
    if isinstance(pv, dict):
        anim = str(pv.get("animation_tier") or "static")
        ico = pv.get("icon_size")
        if isinstance(ico, list) and len(ico) == 2:
            try:
                icon = [int(ico[0]), int(ico[1])]
            except (TypeError, ValueError):
                pass
    data["projectile_visuals"] = {
        "description": line,
        "animation_tier": anim,
        "icon_size": icon,
    }
    _seed_spectacle_plan(data, user_prompt, selected_tier, st)


def _seed_spectacle_plan(
    data: dict, user_prompt: str, selected_tier: str, sub_type: str
) -> None:
    """Seed a high-ceiling codegen brief for Tier-3 bespoke projectiles."""
    if not str(selected_tier).startswith("Tier3"):
        return

    prompt = (user_prompt or "").strip()
    prompt_low = prompt.lower()
    visuals = data.get("visuals") if isinstance(data.get("visuals"), dict) else {}
    projectile_visuals = (
        data.get("projectile_visuals")
        if isinstance(data.get("projectile_visuals"), dict)
        else {}
    )
    desc = str(projectile_visuals.get("description") or "").strip()
    item_desc = str(visuals.get("description") or "").strip()

    fantasy_subject = desc or item_desc or prompt or f"bespoke {sub_type} projectile"
    is_singularity = any(
        token in prompt_low
        for token in (
            "hollow purple",
            "gojo",
            "singularity",
            "black hole",
            "void orb",
            "annihilation orb",
        )
    )
    color_word = "violet" if any(
        token in prompt_low
        for token in ("purple", "violet", "hollow purple", "gojo", "void")
    ) else "themed"
    intent_family = _tier3_intent_family(prompt_low, is_singularity)
    if intent_family == "singularity":
        basis = {
            "cast_shape": ["charge-up", "staged release"],
            "projectile_body": ["singularity orb", "rift seam"],
            "motion_grammar": ["slow oppressive drift", "gravity pull", "path tearing"],
            "payoff": ["implosion", "shock ring", "lingering rift"],
            "visual_language": [
                "black core / bright rim",
                "distortion ring",
                "multi-pass glow",
            ],
            "world_interaction": ["radial terrain carve", "tile scorch"],
        }
        composition = (
            "A charged staff releases a slow violet singularity that pulls dust inward, "
            "tears a short rift along its path, then collapses into an implosion and "
            "expanding shock ring that can scar nearby terrain."
        )
        movement = (
            "slow oppressive drift with gravitational pull, path tearing, and a heavy "
            "scale pulse instead of bullet pacing"
        )
        impact = (
            "one-time implosion that pulls dust inward, expands a violet shock ring, "
            "and performs controlled terrain scarring"
        )
        must_not = [
            "starfall",
            "celestial marks",
            "mark/cashout",
            "bullet pacing",
            "simple fireball",
            "generic missile trail",
        ]
    elif intent_family == "rift":
        basis = {
            "cast_shape": ["staged release"],
            "projectile_body": ["rift projectile", "space tear"],
            "motion_grammar": ["opens under enemies", "path tearing"],
            "payoff": ["shock ring", "rift burst"],
            "visual_language": ["black-violet slit", "distortion fringe"],
            "world_interaction": ["none"],
        }
        composition = "A rift opens near enemies, tears space briefly, then bursts outward."
        movement = "short spatial tear with a readable rift trail"
        impact = "rift burst followed by a compact shock ring"
        must_not = ["bullet", "fireball", "generic dust trail"]
    elif intent_family == "delayed":
        basis = {
            "cast_shape": ["staged release"],
            "projectile_body": ["planted curse mark"],
            "motion_grammar": ["plants then waits"],
            "payoff": ["delayed detonation", "implosion"],
            "visual_language": ["tight sigil glow", "inward collapse"],
            "world_interaction": ["none"],
        }
        composition = "A shot plants a curse mark that waits briefly, then collapses inward."
        movement = "delayed planted state instead of immediate impact"
        impact = "delayed implosion at the planted mark"
        must_not = ["bullet", "fireball", "instant pop"]
    elif intent_family == "beam":
        basis = {
            "cast_shape": ["charge-up", "held beam"],
            "projectile_body": ["beam lance"],
            "motion_grammar": ["screen-line sweep"],
            "payoff": ["beam bloom"],
            "visual_language": ["color-separated lance", "distortion fringe"],
            "world_interaction": ["none"],
        }
        composition = "A charged wand releases a sweeping lance beam with a bright bloom."
        movement = "charged line attack with controlled sweep"
        impact = "beam bloom at the lance end"
        must_not = ["bullet", "fireball", "generic dust trail"]
    elif intent_family == "rupture":
        basis = {
            "cast_shape": ["staged release"],
            "projectile_body": ["ground rupture"],
            "motion_grammar": ["forward terrain wave"],
            "payoff": ["shock ring", "terrain rupture"],
            "visual_language": ["crack glow", "dust wall"],
            "world_interaction": ["bounded terrain carve", "tile scorch"],
        }
        composition = "A ground wave ruptures forward and carves a bounded scar."
        movement = "forward crawling rupture along terrain"
        impact = "bounded terrain carve with a shock burst"
        must_not = ["bullet", "fireball", "air-only projectile"]
    else:
        basis = {
            "cast_shape": ["instant release"],
            "projectile_body": ["bespoke energy body"],
            "motion_grammar": ["strong forward silhouette", "scale pulse"],
            "payoff": ["impact burst"],
            "visual_language": ["long afterimage trail", "soft outer glow", "bright core"],
            "world_interaction": ["none"],
        }
        composition = (
            f"A custom {color_word} projectile combines the selected basis vectors "
            "into one readable signature attack for this weapon."
        )
        movement = (
            "fast direct shot with subtle gravitational wobble, scale pulse, "
            "and strong forward silhouette"
        )
        impact = "imploding dust pull followed by an outward shock ring"
        must_not = ["bullet", "fireball", "generic dust trail"]

    seeded = {
        "fantasy": f"{fantasy_subject}; a readable {color_word} signature attack",
        "basis": basis,
        "composition": composition,
        "movement": movement,
        "render_passes": [
            "long afterimage trail",
            "soft outer glow",
            "bright core sprite",
        ],
        "ai_phases": ["spawn flare", "cruise", "impact collapse"],
        "impact_payoff": impact,
        "sound_profile": "distinct shot sound plus low magic impact pulse",
        "must_not_include": must_not,
        "must_not_feel_like": ["bullet", "fireball", "generic dust trail"],
    }
    existing = data.get("spectacle_plan")
    if isinstance(existing, dict) and str(existing.get("fantasy", "")).strip():
        data["spectacle_plan"] = _merge_spectacle_plan(existing, seeded)
    else:
        data["spectacle_plan"] = seeded
    _seed_mechanics_ir(data, intent_family)


def _tier3_intent_family(prompt_low: str, is_singularity: bool) -> str:
    if is_singularity:
        return "singularity"
    if any(token in prompt_low for token in ("summon", "summons", "temporary eye", "construct")):
        return "summon"
    if any(token in prompt_low for token in ("orbit", "orbiting", "converge", "converges")):
        return "orbit"
    if any(token in prompt_low for token in ("ricochet", "ricocheting", "bounce", "portal")):
        return "portal_ricochet"
    if any(token in prompt_low for token in ("rift", "tear space", "tears space", "opens under")):
        return "rift"
    if any(token in prompt_low for token in ("delayed", "plants", "mark", "curse")):
        return "delayed"
    if any(token in prompt_low for token in ("beam", "lance", "laser", "sweep")):
        return "beam"
    if any(token in prompt_low for token in ("ground", "rupture", "quake", "terrain")):
        return "rupture"
    return "generic"


def _seed_mechanics_ir(data: dict, intent_family: str) -> None:
    if intent_family == "singularity":
        seeded = {
            "atoms": [
                {"kind": "charge_phase", "duration_ticks": 18},
                {
                    "kind": "singularity_projectile",
                    "speed": "slow",
                    "scale_pulse": True,
                },
                {
                    "kind": "gravity_pull_field",
                    "radius_tiles": 6,
                    "strength": "medium",
                },
                {"kind": "rift_trail", "strength": "medium"},
                {"kind": "implosion_payoff", "radius_tiles": 7},
                {"kind": "shock_ring_damage", "radius_tiles": 8},
                {
                    "kind": "bounded_terrain_carve",
                    "radius_tiles": 2,
                    "tile_limit": 8,
                },
            ],
            "forbidden_atoms": ["target_stack_cashout", "starfall_burst"],
            "composition": (
                "Charge, release a slow singularity, pull enemies and dust inward, "
                "tear a rift trail, then implode into a shock ring and bounded "
                "terrain carve."
            ),
        }
    elif intent_family == "rift":
        seeded = {
            "atoms": [
                {"kind": "rift_projectile", "strength": "medium"},
                {"kind": "rift_trail", "strength": "medium"},
                {"kind": "shock_ring_damage", "radius_tiles": 5},
            ],
            "forbidden_atoms": [],
            "composition": "Open a rift projectile, leave a spatial tear, then burst outward.",
        }
    elif intent_family == "delayed":
        seeded = {
            "atoms": [
                {"kind": "delayed_detonation", "duration_ticks": 45},
                {"kind": "implosion_payoff", "radius_tiles": 5},
            ],
            "forbidden_atoms": [],
            "composition": "Plant a delayed state, then implode at the marked point.",
        }
    elif intent_family == "beam":
        seeded = {
            "atoms": [
                {"kind": "charge_phase", "duration_ticks": 18},
                {"kind": "beam_lance", "duration_ticks": 36, "length_tiles": 18},
                {"kind": "color_separation_distortion", "strength": "medium"},
            ],
            "forbidden_atoms": [],
            "composition": "Charge and release a sweeping beam lance with distortion fringe.",
        }
    elif intent_family == "rupture":
        seeded = {
            "atoms": [
                {
                    "kind": "bounded_terrain_carve",
                    "radius_tiles": 2,
                    "tile_limit": 12,
                },
                {"kind": "shock_ring_damage", "radius_tiles": 5},
                {"kind": "tile_scorch", "strength": "medium"},
            ],
            "forbidden_atoms": [],
            "composition": "Send a ground rupture forward with bounded terrain interaction.",
        }
    elif intent_family == "summon":
        seeded = {
            "atoms": [
                {"kind": "summoned_construct", "duration_ticks": 90},
                {"kind": "beam_lance", "duration_ticks": 36, "length_tiles": 18},
                {"kind": "color_separation_distortion", "strength": "medium"},
            ],
            "forbidden_atoms": [],
            "composition": "Summon a temporary construct that performs the beam attack.",
        }
    elif intent_family == "orbit":
        seeded = {
            "atoms": [
                {"kind": "orbiting_convergence", "count": 3},
                {"kind": "satellite_fusion", "count": 3},
                {"kind": "implosion_payoff", "radius_tiles": 5},
            ],
            "forbidden_atoms": [],
            "composition": "Throw orbiting shards that converge and fuse into a final strike.",
        }
    elif intent_family == "portal_ricochet":
        seeded = {
            "atoms": [
                {"kind": "ricochet_path", "count": 3},
                {"kind": "portal_hop", "count": 3},
                {"kind": "rift_trail", "strength": "medium"},
            ],
            "forbidden_atoms": [],
            "composition": "Fire a ricocheting portal round that tears space at each bounce.",
        }
    else:
        seeded = {
            "atoms": [
                {"kind": "rift_trail", "strength": "light"},
                {"kind": "shock_ring_damage", "radius_tiles": 4},
            ],
            "forbidden_atoms": [],
            "composition": "Create a readable Tier-3 projectile with a trail and payoff.",
        }

    existing = data.get("mechanics_ir")
    if isinstance(existing, dict):
        data["mechanics_ir"] = _merge_mechanics_ir(existing, seeded)
    else:
        data["mechanics_ir"] = seeded


def _merge_mechanics_ir(existing: dict, seeded: dict) -> dict:
    merged = dict(existing)
    existing_atoms = merged.get("atoms")
    if not isinstance(existing_atoms, list):
        existing_atoms = []
    seen_kinds = {
        str(atom.get("kind"))
        for atom in existing_atoms
        if isinstance(atom, dict) and atom.get("kind")
    }
    for atom in seeded.get("atoms", []):
        kind = str(atom.get("kind")) if isinstance(atom, dict) else ""
        if kind and kind not in seen_kinds:
            existing_atoms.append(atom)
            seen_kinds.add(kind)
    merged["atoms"] = existing_atoms

    forbidden = merged.get("forbidden_atoms")
    if not isinstance(forbidden, list):
        forbidden = []
    seen_forbidden = {str(value).lower() for value in forbidden}
    for value in seeded.get("forbidden_atoms", []):
        if str(value).lower() not in seen_forbidden:
            forbidden.append(value)
            seen_forbidden.add(str(value).lower())
    merged["forbidden_atoms"] = forbidden

    if not str(merged.get("composition", "")).strip():
        merged["composition"] = seeded.get("composition", "")
    return merged


def _merge_spectacle_plan(existing: dict, seeded: dict) -> dict:
    """Keep LLM creativity but merge mandatory Tier-3 basis/anti-goal defaults."""
    merged = dict(existing)
    for key in ("fantasy", "composition", "movement", "impact_payoff", "sound_profile"):
        if not str(merged.get(key, "")).strip():
            merged[key] = seeded.get(key, "")

    existing_basis = (
        dict(merged.get("basis")) if isinstance(merged.get("basis"), dict) else {}
    )
    seeded_basis = seeded.get("basis") if isinstance(seeded.get("basis"), dict) else {}
    for dimension, values in seeded_basis.items():
        existing_values = existing_basis.get(dimension)
        if not isinstance(existing_values, list):
            existing_values = []
        seen = {str(value).lower() for value in existing_values}
        for value in values:
            if str(value).lower() not in seen:
                existing_values.append(value)
                seen.add(str(value).lower())
        existing_basis[dimension] = existing_values
    merged["basis"] = existing_basis

    for key in ("render_passes", "ai_phases", "must_not_include", "must_not_feel_like"):
        existing_values = merged.get(key)
        if not isinstance(existing_values, list):
            existing_values = []
        seen = {str(value).lower() for value in existing_values}
        for value in seeded.get(key, []):
            if str(value).lower() not in seen:
                existing_values.append(value)
                seen.add(str(value).lower())
        merged[key] = existing_values

    return merged
