"""Deterministic structural critique for free-form Forge codegen.

The critique layer validates correctness hazards without offering a primitive
library or menu of effects. Codegen remains free-form; this module only rejects
generated C# that would compile poorly, crash, or ignore pipeline contracts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping

from core.csharp_parse import balanced_brace_block, first_modprojectile_setdefaults_body

SymbolRegistry = Mapping[str, set[str]]

# Heuristic windows (characters / counts), not game constants.
_DUST_CADENCE_LOOKBACK_CHARS = 600
_MIN_SPECTACLE_TRAIL_CACHE_LENGTH = 14


DEFAULT_VALID_SYMBOLS: dict[str, set[str]] = {}

DEFAULT_PROJECTILE_FRAME_COUNTS: dict[str, int] = {
    "ProjectileID.MagicMissile": 1,
    "ProjectileID.AmethystBolt": 1,
    "ProjectileID.WoodenArrowFriendly": 1,
    "ProjectileID.Bullet": 1,
}


@dataclass(frozen=True)
class CritiqueIssue:
    rule: str
    message: str


@dataclass(frozen=True)
class CritiqueResult:
    passed: bool
    issues: list[CritiqueIssue] = field(default_factory=list)


@dataclass(frozen=True)
class CritiqueContext:
    manifest: dict
    valid_symbols: SymbolRegistry = field(default_factory=lambda: DEFAULT_VALID_SYMBOLS)
    projectile_frame_counts: Mapping[str, int] = field(
        default_factory=lambda: DEFAULT_PROJECTILE_FRAME_COUNTS
    )
    relative_path: str = ""


def critique_generated_code(
    cs_code: str, context: CritiqueContext | None = None
) -> CritiqueResult:
    context = context or CritiqueContext(manifest={})
    issues: list[CritiqueIssue] = []
    issues.extend(_invalid_vanilla_symbols(cs_code, context.valid_symbols))
    issues.extend(_vanilla_frame_mismatches(cs_code, context.projectile_frame_counts))
    issues.extend(_predraw_frame_slicing_issues(cs_code))
    issues.extend(_missing_trail_cache(cs_code))
    issues.extend(_unthrottled_dust(cs_code))
    issues.extend(_hitbox_mismatches(cs_code, context.manifest))
    issues.extend(_mechanics_ir_issues(cs_code, context.manifest))
    issues.extend(_spectacle_plan_issues(cs_code, context.manifest))
    issues.extend(_mod_subclass_issues(cs_code))
    issues.extend(_namespace_path_issues(cs_code, context.relative_path))
    return CritiqueResult(passed=not issues, issues=issues)


def _invalid_vanilla_symbols(
    cs_code: str, valid_symbols: SymbolRegistry
) -> list[CritiqueIssue]:
    issues: list[CritiqueIssue] = []
    for id_type in ("ProjectileID", "ItemID", "SoundID", "DustID", "BuffID", "TileID"):
        valid = valid_symbols.get(id_type)
        if valid is None:
            continue
        for match in re.finditer(rf"\b{id_type}\.(\w+)\b", cs_code):
            symbol = match.group(1)
            if id_type == "ProjectileID" and symbol == "Sets":
                continue
            if symbol not in valid:
                issues.append(
                    CritiqueIssue(
                        "valid_vanilla_symbol",
                        f"{id_type}.{symbol} is not present in the vanilla ID registry.",
                    )
                )
    return issues


def _vanilla_frame_mismatches(
    cs_code: str, projectile_frame_counts: Mapping[str, int]
) -> list[CritiqueIssue]:
    frame_match = re.search(
        r"Main\.projFrames\[Type\]\s*=\s*(\d+|[A-Za-z_]\w*)\s*;", cs_code
    )
    if not frame_match:
        return []
    texture_match = re.search(
        r'Texture\s*=>\s*"Terraria/Images/Projectile_"\s*\+\s*(ProjectileID\.\w+)',
        cs_code,
    )
    if not texture_match:
        return []
    projectile_id = texture_match.group(1)
    expected = projectile_frame_counts.get(projectile_id)
    if expected is None:
        return []
    actual = _resolve_int_expr(cs_code, frame_match.group(1))
    if actual is None:
        return []
    if actual == expected:
        return []
    return [
        CritiqueIssue(
            "vanilla_frame_count",
            f"{projectile_id} frame count mismatch: Main.projFrames[Type]={actual}, registry={expected}.",
        )
    ]


def _predraw_frame_slicing_issues(cs_code: str) -> list[CritiqueIssue]:
    frame_match = re.search(
        r"Main\.projFrames\[Type\]\s*=\s*(\d+|[A-Za-z_]\w*)\s*;", cs_code
    )
    if not frame_match:
        return []
    frame_count = _resolve_int_expr(cs_code, frame_match.group(1))
    if frame_count == 1:
        return []
    predraw_body = _method_body(cs_code, "PreDraw")
    if not predraw_body:
        return []
    if "Projectile.frame" not in predraw_body:
        return [
            CritiqueIssue(
                "predraw_frame_slicing",
                "PreDraw frame slicing must use Projectile.frame when Main.projFrames[Type] is set.",
            )
        ]
    has_height_slice = re.search(
        r"\.Height\s*/\s*(?:FrameCount|Main\.projFrames\[Type\]|\d+)", predraw_body
    )
    has_source_rect = "Rectangle" in predraw_body or "frame" in predraw_body
    if has_height_slice and has_source_rect:
        return []
    return [
        CritiqueIssue(
            "predraw_frame_slicing",
            "PreDraw frame slicing must derive source rectangle height from the frame count.",
        )
    ]


def _missing_trail_cache(cs_code: str) -> list[CritiqueIssue]:
    reads_old_positions = "Projectile.oldPos" in cs_code or "Projectile.oldRot" in cs_code
    has_trail_cache = "ProjectileID.Sets.TrailCacheLength[Type]" in cs_code
    if not reads_old_positions or has_trail_cache:
        return []
    return [
        CritiqueIssue(
            "trail_cache_required",
            "Projectile.oldPos/oldRot reads require ProjectileID.Sets.TrailCacheLength[Type] in SetStaticDefaults.",
        )
    ]


def _unthrottled_dust(cs_code: str) -> list[CritiqueIssue]:
    ai_body = _method_body(cs_code, "AI")
    dust_calls = list(
        re.finditer(r"Dust\.NewDust(?:Perfect|Direct)?\s*\(", ai_body)
    )
    for call in dust_calls:
        prefix = ai_body[max(0, call.start() - _DUST_CADENCE_LOOKBACK_CHARS) : call.start()]
        if _has_dust_cadence(prefix):
            continue
        return [
            CritiqueIssue(
                "dust_throttle",
                "Dust.NewDust/Dust.NewDustPerfect/Dust.NewDustDirect in AI() must be inside a cadence throttle.",
            )
        ]
    return []


def _hitbox_mismatches(cs_code: str, manifest: dict) -> list[CritiqueIssue]:
    if not re.search(r"class\s+\w+\s*:\s*(?:[\w.]+\.)?ModProjectile\b", cs_code):
        return []
    projectile_visuals = manifest.get("projectile_visuals")
    if not isinstance(projectile_visuals, dict):
        return []
    hitbox_size = projectile_visuals.get("hitbox_size")
    if not isinstance(hitbox_size, list) or len(hitbox_size) != 2:
        return []
    try:
        expected_width, expected_height = [int(value) for value in hitbox_size]
    except (TypeError, ValueError):
        return []

    setdefaults_body = first_modprojectile_setdefaults_body(cs_code)
    width_match = re.search(r"Projectile\.width\s*=\s*(\d+)\s*;", setdefaults_body)
    height_match = re.search(r"Projectile\.height\s*=\s*(\d+)\s*;", setdefaults_body)
    if not width_match or not height_match:
        return [
            CritiqueIssue(
                "projectile_hitbox",
                "Projectile hitbox must match projectile_visuals.hitbox_size "
                f"{hitbox_size}; missing Projectile.width or Projectile.height assignment.",
            )
        ]

    actual_width = int(width_match.group(1))
    actual_height = int(height_match.group(1))
    if (actual_width, actual_height) == (expected_width, expected_height):
        return []
    return [
        CritiqueIssue(
            "projectile_hitbox",
            "Projectile hitbox must match projectile_visuals.hitbox_size "
            f"{hitbox_size}; found Projectile.width={actual_width}, "
            f"Projectile.height={actual_height}.",
        )
    ]


def _spectacle_plan_issues(cs_code: str, manifest: dict) -> list[CritiqueIssue]:
    plan = manifest.get("spectacle_plan")
    if not isinstance(plan, dict) or not str(plan.get("fantasy", "")).strip():
        return []
    if not re.search(r"class\s+\w+\s*:\s*(?:[\w.]+\.)?ModProjectile\b", cs_code):
        return []

    issues: list[CritiqueIssue] = []
    predraw_body = _method_body(cs_code, "PreDraw")
    if not predraw_body:
        issues.append(
            CritiqueIssue(
                "spectacle_predraw",
                "spectacle_plan projectiles must implement custom PreDraw multi-pass rendering.",
            )
        )
    else:
        draw_calls = len(re.findall(r"Main\.EntitySpriteDraw\s*\(", predraw_body))
        if draw_calls < 2:
            issues.append(
                CritiqueIssue(
                    "spectacle_predraw",
                    "spectacle_plan PreDraw must use multiple draw passes, not a single sprite draw.",
                )
            )
        if "Projectile.oldPos" not in predraw_body and "Projectile.oldRot" not in predraw_body:
            issues.append(
                CritiqueIssue(
                    "spectacle_trail",
                    "spectacle_plan PreDraw must render a visible oldPos/oldRot trail.",
                )
            )

    trail_match = re.search(
        r"ProjectileID\.Sets\.TrailCacheLength\[Type\]\s*=\s*(\d+|[A-Za-z_]\w*)\s*;",
        cs_code,
    )
    trail_len = _resolve_int_expr(cs_code, trail_match.group(1)) if trail_match else None
    if trail_len is None or trail_len < _MIN_SPECTACLE_TRAIL_CACHE_LENGTH:
        issues.append(
            CritiqueIssue(
                "spectacle_trail",
                "spectacle_plan projectiles need TrailCacheLength[Type] >= "
                f"{_MIN_SPECTACLE_TRAIL_CACHE_LENGTH} for readable afterimages.",
            )
        )

    if not _has_spectacle_timing(cs_code):
        issues.append(
            CritiqueIssue(
                "spectacle_ai_phase",
                "spectacle_plan projectiles need an AI timer/phase so movement has authored personality.",
            )
        )

    payoff_names = r"(?:Burst|Collapse|Detonate|Implode|Explode|Payoff)"
    has_payoff_method = re.search(
        rf"\b(?:private|public|protected)?\s*void\s+{payoff_names}\s*\(",
        cs_code,
    )
    calls_payoff = any(
        re.search(rf"\b{payoff_names}\s*\(", _method_body(cs_code, hook))
        for hook in ("OnKill", "OnHitNPC", "OnTileCollide")
    )
    has_inline_payoff = any(
        _hook_has_inline_payoff(_method_body(cs_code, hook))
        for hook in ("OnKill", "OnHitNPC", "OnTileCollide")
    )
    has_secondary_payoff = _hook_spawns_secondary_payoff(cs_code)
    if (
        (not has_payoff_method or not calls_payoff)
        and not has_inline_payoff
        and not has_secondary_payoff
    ):
        issues.append(
            CritiqueIssue(
                "spectacle_payoff",
                "spectacle_plan projectiles need an impact payoff in hit/kill/collide hooks.",
            )
        )
    issues.extend(_forbidden_spectacle_mechanic_issues(cs_code, plan))
    issues.extend(_world_interaction_issues(cs_code, plan))

    return issues


def _mechanics_ir_issues(cs_code: str, manifest: dict) -> list[CritiqueIssue]:
    ir = manifest.get("mechanics_ir")
    if not isinstance(ir, dict):
        return []
    if not re.search(r"class\s+\w+\s*:\s*(?:[\w.]+\.)?ModProjectile\b", cs_code):
        return []

    issues: list[CritiqueIssue] = []
    normalized_code = _normalize_term(cs_code)
    for forbidden in _plan_terms(ir, "forbidden_atoms"):
        normalized_forbidden = _normalize_term(forbidden)
        if normalized_forbidden == "targetstackcashout" and any(
            token in normalized_code
            for token in ("instabilitystacks", "markcount", "getglobalnpc", "stackdecay")
        ):
            issues.append(
                CritiqueIssue(
                    "mechanics_ir_forbidden_atom",
                    "mechanics_ir forbids target_stack_cashout, but generated code appears to use per-target stack/cashout state.",
                )
            )
        if normalized_forbidden == "starfallburst" and any(
            token in normalized_code for token in ("starfall", "starfury", "fallingstar")
        ):
            issues.append(
                CritiqueIssue(
                    "mechanics_ir_forbidden_atom",
                    "mechanics_ir forbids starfall_burst, but generated code appears to include starfall behavior.",
                )
            )

    atoms = ir.get("atoms")
    if not isinstance(atoms, list):
        return issues
    kinds = {
        str(atom.get("kind"))
        for atom in atoms
        if isinstance(atom, dict) and str(atom.get("kind", "")).strip()
    }
    for kind in sorted(kinds):
        if _mechanics_atom_has_evidence(kind, cs_code):
            continue
        issues.append(
            CritiqueIssue(
                "mechanics_ir_missing_atom",
                f"mechanics_ir atom {kind!r} has no clear implementation evidence in generated code.",
            )
        )
    return issues


def _mechanics_atom_has_evidence(kind: str, cs_code: str) -> bool:
    ai_body = _method_body(cs_code, "AI")
    predraw_body = _method_body(cs_code, "PreDraw")
    normalized_code = _normalize_term(cs_code)
    normalized_ai = _normalize_term(ai_body)
    if kind == "charge_phase":
        has_timer = bool(
            re.search(
                r"Projectile\.(?:ai|localAI)\[[^\]]+\]\s*(?:\+\+|=|<|>|<=|>=)",
                ai_body,
            )
        )
        has_staging = any(
            token in cs_code
            for token in (
                "Projectile.friendly = false",
                "CanDamage()",
                "ChargeTicks",
                "chargeTicks",
                "ChargeFrames",
                "chargeFrames",
            )
        )
        return has_timer and has_staging
    if kind == "singularity_projectile":
        return (
            "ModProjectile" in cs_code
            and (
                "Projectile.scale" in cs_code
                or "Lighting.AddLight" in cs_code
                or "Projectile.rotation" in cs_code
            )
            and "ProjectileID.Bullet" not in cs_code
        )
    if kind == "gravity_pull_field":
        scans_npcs = (
            "Main.npc" in cs_code
            or "foreach (NPC" in cs_code
            or "for (int n" in cs_code
            or "for (int i = 0; i < Main.maxNPCs" in cs_code
        )
        pull_math = any(
            token in cs_code
            for token in (
                "Projectile.Center -",
                "Projectile.Center-",
                "SafeNormalize",
                "Normalize()",
                "pull",
                "Pull",
            )
        )
        return scans_npcs and pull_math
    if kind == "rift_trail":
        return (
            ("Projectile.oldPos" in cs_code or "Projectile.oldRot" in cs_code)
            and predraw_body
            and any(token in normalized_code for token in ("black", "shadowflame", "rift", "fringe", "distortion"))
        )
    if kind == "implosion_payoff":
        has_named_payoff = any(
            token in normalized_code
            for token in ("collapse", "implode", "implosion", "shockring")
        )
        has_payoff_hook = any(
            _method_body(cs_code, hook)
            for hook in ("OnKill", "OnHitNPC", "OnTileCollide")
        )
        has_burst_shape = "Projectile.Resize" in cs_code or re.search(r"for\s*\(", cs_code)
        return bool(has_named_payoff and has_payoff_hook and has_burst_shape)
    if kind == "shock_ring_damage":
        return any(token in normalized_code for token in ("shockring", "resize", "radius", "ring"))
    if kind == "bounded_terrain_carve":
        has_tile_break = "WorldGen.KillTile" in cs_code or "WorldGen.KillWall" in cs_code
        has_bounds = "WorldGen.InWorld" in cs_code and (
            "tile_limit" in normalized_code
            or "tilelimit" in normalized_code
            or "breakCount" in cs_code
            or "brokenTiles" in cs_code
            or re.search(r"\b(?:x|i)\s*<=\s*\w+\s*\+\s*\d+", cs_code)
        )
        return bool(has_tile_break and has_bounds)
    if kind == "beam_lance":
        has_line_collision = any(
            token in cs_code
            for token in (
                "Collision.CheckAABBvLineCollision",
                "Utils.PlotTileLine",
                "Colliding(",
                "Vector2.Dot",
            )
        )
        has_beam_shape = any(
            token in normalized_code
            for token in ("beamlength", "laserlength", "lancelength", "maxlength")
        ) or any(token in predraw_body for token in ("EntitySpriteDraw", "DrawLine"))
        return has_line_collision and has_beam_shape
    if kind == "delayed_detonation":
        has_delay = any(
            token in normalized_code
            for token in ("delay", "detonation", "detonate", "primed", "planted")
        ) or bool(re.search(r"Projectile\.(?:ai|localAI)\[[^\]]+\]\s*[<>]=?\s*\d+", cs_code))
        has_payoff = "Projectile.Damage()" in cs_code or "Projectile.Resize" in cs_code
        return has_delay and has_payoff
    if kind == "summoned_construct":
        helper_spawn = "Projectile.NewProjectile" in cs_code
        helper_type = bool(
            re.search(r"ModContent\.ProjectileType<\w*(?:Construct|Eye|Helper|Sigil)\w*>", cs_code)
        )
        return helper_spawn and helper_type
    if kind == "orbiting_convergence":
        has_orbit = any(
            token in cs_code
            for token in ("MathHelper.TwoPi", "ToRotationVector2()", "RotatedBy(")
        ) or all(token in cs_code for token in ("MathF.Sin", "MathF.Cos"))
        has_convergence = any(
            token in normalized_code
            for token in ("converge", "convergence", "fusion", "fuse", "satellite")
        )
        return has_orbit and has_convergence
    if kind == "portal_hop":
        has_reposition = any(
            token in cs_code
            for token in ("Projectile.position =", "Projectile.Center =", "Teleport")
        )
        has_visual = any(token in normalized_code for token in ("portal", "rift", "oldposition"))
        return has_reposition and has_visual
    if kind == "ricochet_path":
        has_bounce = "OnTileCollide" in cs_code and any(
            token in cs_code for token in ("oldVelocity", "*= -", "bounce", "Bounce")
        )
        has_limit = any(token in normalized_code for token in ("ricochet", "bouncecount", "bouncesleft"))
        return has_bounce and has_limit
    return True


def _has_spectacle_timing(cs_code: str) -> bool:
    bodies = "\n".join(
        body for body in (_method_body(cs_code, "AI"), _method_body(cs_code, "PreDraw")) if body
    )
    if not bodies:
        return False
    return bool(
        re.search(
            r"Projectile\.(?:ai|localAI)\[|Projectile\.frameCounter|Main\.GameUpdateCount|"
            r"\b\w*(?:Timer|Counter|Phase|phase|Pulse|pulse|Charge|charge|Age|age)\w*\b",
            bodies,
        )
    )


def _forbidden_spectacle_mechanic_issues(
    cs_code: str, plan: dict
) -> list[CritiqueIssue]:
    forbidden = _plan_terms(plan, "must_not_include") + _plan_terms(
        plan, "must_not_feel_like"
    )
    if not forbidden:
        return []

    normalized_code = _normalize_term(cs_code)
    checks = {
        "starfall": ("starfall", "starfury", "fallingstar", "star"),
        "celestialmarks": ("stormbrand", "markcount", "markstate", "marktime"),
        "markcashout": (
            "cashout",
            "markcount",
            "markstate",
            "marktime",
            "instabilitystacks",
            "targetstate",
            "getglobalnpc",
        ),
        "bulletpacing": ("projectileid.bullet",),
        "bullet": ("projectileid.bullet",),
        "genericbullet": ("projectileid.bullet",),
        "simplefireball": ("balloffire", "fireball"),
        "genericmissiletrail": ("magicmissile",),
    }
    issues: list[CritiqueIssue] = []
    for term in forbidden:
        normalized_term = _normalize_term(term)
        needles = checks.get(normalized_term, (normalized_term,))
        if any(_normalize_term(needle) in normalized_code for needle in needles):
            issues.append(
                CritiqueIssue(
                    "spectacle_forbidden_mechanic",
                    f"spectacle_plan forbids {term!r}, but generated code appears to include it.",
                )
            )
    return issues


def _world_interaction_issues(cs_code: str, plan: dict) -> list[CritiqueIssue]:
    basis = plan.get("basis")
    if not isinstance(basis, dict):
        return []
    requested = " ".join(_plan_terms(basis, "world_interaction")).lower()
    if not any(
        token in requested
        for token in ("terrain carve", "tile scorch", "break", "mine", "carve")
    ):
        return []
    if any(token in requested for token in ("terrain carve", "break", "mine", "carve")):
        if "WorldGen.KillTile" in cs_code or "WorldGen.KillWall" in cs_code:
            return []
        return [
            CritiqueIssue(
                "spectacle_world_interaction",
                "spectacle_plan world_interaction requests terrain carving/breaking, but code has no bounded WorldGen.KillTile/KillWall interaction.",
            )
        ]
    tile_ops = (
        "WorldGen.KillTile",
        "WorldGen.KillWall",
        "WorldGen.PlaceTile",
        "Framing.GetTileSafely",
        "Main.tile",
    )
    if any(op in cs_code for op in tile_ops):
        return []
    return [
        CritiqueIssue(
            "spectacle_world_interaction",
            "spectacle_plan world_interaction requests terrain/tile behavior, but code has no bounded tile interaction.",
        )
    ]


def _plan_terms(plan: dict, key: str) -> list[str]:
    raw = plan.get(key)
    if isinstance(raw, list):
        return [str(v) for v in raw if str(v).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw]
    return []


def _normalize_term(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _hook_has_inline_payoff(body: str) -> bool:
    if not body:
        return False
    has_fx = (
        "Dust.NewDust" in body
        or "Gore.NewGore" in body
        or "Projectile.NewProjectile" in body
        or "SoundEngine.PlaySound" in body
    )
    has_loop_or_resize = "for (" in body or "Projectile.Resize" in body
    return has_fx and has_loop_or_resize


def _hook_spawns_secondary_payoff(cs_code: str) -> bool:
    has_secondary_damage = "Projectile.Damage()" in cs_code or "Projectile.Resize" in cs_code
    if not has_secondary_damage:
        return False
    for hook in ("OnKill", "OnHitNPC", "OnTileCollide"):
        hook_body = _method_body(cs_code, hook)
        if not hook_body:
            continue
        if _body_spawns_mod_projectile(hook_body):
            return True
        for method_name in _called_method_names(hook_body):
            method_body = _method_body(cs_code, method_name)
            if _body_spawns_mod_projectile(method_body):
                return True
    return False


def _body_spawns_mod_projectile(body: str) -> bool:
    return "Projectile.NewProjectile" in body and "ModContent.ProjectileType<" in body


def _called_method_names(body: str) -> list[str]:
    names: list[str] = []
    for match in re.finditer(r"\b([A-Z]\w*)\s*\(", body):
        name = match.group(1)
        if name in {"Math", "MathF", "Vector2", "Color", "SoundEngine", "Dust", "Gore"}:
            continue
        names.append(name)
    return names


def _mod_subclass_issues(cs_code: str) -> list[CritiqueIssue]:
    subclasses = re.findall(r"class\s+\w+\s*:\s*(?:[\w.]+\.)?Mod\b", cs_code)
    if not subclasses:
        return []
    return [
        CritiqueIssue(
            "single_mod_subclass",
            "Generated code must not declare a Mod subclass; the project entry class is supplied separately.",
        )
    ]


def _namespace_path_issues(cs_code: str, relative_path: str) -> list[CritiqueIssue]:
    issues: list[CritiqueIssue] = []
    item_namespace = re.search(
        r"namespace\s+([^{\s]+)[\s\S]*?class\s+\w+\s*:\s*(?:[\w.]+\.)?ModItem\b",
        cs_code,
    )
    projectile_namespace = re.search(
        r"namespace\s+([^{\s]+)[\s\S]*?class\s+\w+\s*:\s*(?:[\w.]+\.)?ModProjectile\b",
        cs_code,
    )
    if item_namespace and not item_namespace.group(1).startswith(
        "ForgeGeneratedMod.Content.Items"
    ):
        issues.append(
            CritiqueIssue(
                "item_namespace_path",
                "ModItem classes must live in namespace ForgeGeneratedMod.Content.Items or a child namespace.",
            )
        )
    projectile_ns = projectile_namespace.group(1) if projectile_namespace else ""
    if projectile_namespace and relative_path.startswith("Content/Projectiles"):
        if not projectile_ns.startswith("ForgeGeneratedMod.Content.Projectiles"):
            issues.append(
                CritiqueIssue(
                    "projectile_path_namespace",
                    "Content/Projectiles files must use namespace ForgeGeneratedMod.Content.Projectiles or a child namespace.",
                )
            )
    elif projectile_namespace and not (
        projectile_ns.startswith("ForgeGeneratedMod.Content.Projectiles")
        or projectile_ns.startswith("ForgeGeneratedMod.Content.Items")
    ):
        issues.append(
            CritiqueIssue(
                "projectile_namespace_path",
                "ModProjectile classes must live under ForgeGeneratedMod.Content.Projectiles or ForgeGeneratedMod.Content.Items when emitted in the item file.",
            )
        )
    if relative_path.startswith("Content/Items") and not item_namespace:
        issues.append(
            CritiqueIssue(
                "item_path_namespace",
                "Content/Items files must contain a ModItem in a ForgeGeneratedMod.Content.Items namespace.",
            )
        )
    if relative_path.startswith("Content/Projectiles") and not projectile_namespace:
        issues.append(
            CritiqueIssue(
                "projectile_path_namespace",
                "Content/Projectiles files must contain a ModProjectile in a ForgeGeneratedMod.Content.Projectiles namespace.",
            )
        )
    return issues


def _has_dust_cadence(prefix: str) -> bool:
    if "Main.rand.NextBool" in prefix:
        return True
    if "Main.GameUpdateCount" in prefix and "%" in prefix:
        return True
    return bool(re.search(r"(?:Projectile\.)?(?:ai|localAI|frameCounter)\[[^\]]+\]\s*%\s*\d+", prefix)) or bool(
        re.search(r"\b\w*(?:Timer|Counter|Frame|frame)\w*\s*%\s*\d+", prefix)
    )


def _resolve_int_expr(cs_code: str, expr: str) -> int | None:
    expr = expr.strip()
    if expr.isdigit():
        return int(expr)
    const_match = re.search(
        rf"\bconst\s+int\s+{re.escape(expr)}\s*=\s*(\d+)\s*;", cs_code
    )
    if const_match:
        return int(const_match.group(1))
    return None


def _method_body(cs_code: str, method_name: str) -> str:
    """Extract method body; whitespace/comments inside body are preserved."""
    match = re.search(
        rf"\b(?:public|private|protected|internal)?\s*(?:override\s+)?[\w<>.\[\]]+\s+{re.escape(method_name)}\s*\([^)]*\)",
        cs_code,
    )
    if not match:
        return ""
    open_idx = cs_code.find("{", match.end())
    if open_idx == -1:
        return ""
    return balanced_brace_block(cs_code, open_idx)
