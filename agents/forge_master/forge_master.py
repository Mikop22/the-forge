"""Forge Master Agent – converts an Architect manifest into compilable C# + hjson."""

from __future__ import annotations

import json
import os
import re
import textwrap

from core.agent_warnings import suppress_langchain_pydantic_warnings

suppress_langchain_pydantic_warnings()

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

try:
    from forge_master.critique import CritiqueContext, critique_generated_code
    from forge_master.models import CSharpOutput, ForgeError, ForgeManifest, ForgeOutput
    from forge_master.prompts import build_codegen_prompt, build_repair_prompt
    from forge_master.reviewer import ReviewOutput, WeaponReviewer
    from forge_master.templates import (
        DAMAGE_CLASS_MAP,
        TOOL_POWER_LINES,
        USE_STYLE_MAP,
        get_reference_snippet,
        validate_cs,
    )
except ImportError:
    from critique import CritiqueContext, critique_generated_code
    from models import CSharpOutput, ForgeError, ForgeManifest, ForgeOutput
    from prompts import build_codegen_prompt, build_repair_prompt
    from reviewer import ReviewOutput, WeaponReviewer
    from templates import (
        DAMAGE_CLASS_MAP,
        TOOL_POWER_LINES,
        USE_STYLE_MAP,
        get_reference_snippet,
        validate_cs,
    )

_MAX_ATTEMPTS = 3


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _critique_violations(manifest: dict, cs_code: str) -> list[str]:
    item_name = str(manifest.get("item_name") or "GeneratedItem")
    critique = critique_generated_code(
        cs_code,
        CritiqueContext(
            manifest=manifest,
            relative_path=f"Content/Items/{item_name}.cs",
        ),
    )
    return [f"CRITIQUE: [{issue.rule}] {issue.message}" for issue in critique.issues]


def _strip_csharp_comments(code: str) -> str:
    code = re.sub(r"/\*[\s\S]*?\*/", "", code)
    return re.sub(r"//.*", "", code)


def _balanced_block(text: str, open_idx: int) -> str:
    depth = 0
    for idx in range(open_idx, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
            continue
        if char != "}":
            continue
        depth -= 1
        if depth == 0:
            return text[open_idx + 1 : idx]
    return ""


def _first_modprojectile_setdefaults_body(cs_code: str) -> str:
    code = _strip_csharp_comments(cs_code)
    for class_match in re.finditer(
        r"class\s+\w+\s*:\s*(?:[\w.]+\.)?ModProjectile\b", code
    ):
        class_open = code.find("{", class_match.end())
        if class_open == -1:
            continue
        class_body = _balanced_block(code, class_open)
        method_match = re.search(r"override\s+void\s+SetDefaults\s*\(\s*\)", class_body)
        if not method_match:
            continue
        method_open = class_body.find("{", method_match.end())
        if method_open == -1:
            continue
        return _balanced_block(class_body, method_open)
    return ""


def _validate_projectile_hitbox_contract(manifest: dict, cs_code: str) -> list[str]:
    """Ensure generated projectile dimensions honor Pixelsmith-derived hitbox size."""
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

    setdefaults_body = _first_modprojectile_setdefaults_body(cs_code)
    width_match = re.search(r"Projectile\.width\s*=\s*(\d+)\s*;", setdefaults_body)
    height_match = re.search(r"Projectile\.height\s*=\s*(\d+)\s*;", setdefaults_body)
    if not width_match or not height_match:
        return [
            "Projectile hitbox must match projectile_visuals.hitbox_size "
            f"{hitbox_size}; missing Projectile.width or Projectile.height assignment."
        ]

    actual_width = int(width_match.group(1))
    actual_height = int(height_match.group(1))
    if (actual_width, actual_height) == (expected_width, expected_height):
        return []

    return [
        "Projectile hitbox must match projectile_visuals.hitbox_size "
        f"{hitbox_size}; found Projectile.width={actual_width}, "
        f"Projectile.height={actual_height}."
    ]


class CoderAgent:
    """Generates tModLoader 1.4.4 C# source and hjson localization files.

    Usage::

        agent = CoderAgent()
        result = agent.write_code(manifest_dict)
        # result["cs_code"], result["hjson_code"], result["status"]
    """

    def __init__(
        self, model_name: str = "gpt-5.4", bespoke_model_name: str = "gpt-5.5"
    ) -> None:
        standard_reasoning = os.getenv("FORGE_CODEGEN_REASONING_EFFORT", "high")
        bespoke_reasoning = os.getenv("FORGE_BESPOKE_REASONING_EFFORT", "medium")
        standard_timeout = _env_int("FORGE_CODEGEN_TIMEOUT_SECONDS", 300)
        bespoke_timeout = _env_int("FORGE_BESPOKE_TIMEOUT_SECONDS", 300)

        # GPT-5 Nano does not support the temperature parameter.
        self._llm = ChatOpenAI(
            model=model_name,
            timeout=standard_timeout,
            reasoning_effort=standard_reasoning,
        )
        self._bespoke_llm = (
            self._llm
            if bespoke_model_name == model_name
            else ChatOpenAI(
                model=bespoke_model_name,
                timeout=bespoke_timeout,
                reasoning_effort=bespoke_reasoning,
            )
        )

        # Code generation: prompt → LLM → structured Pydantic output
        self._gen_chain = build_codegen_prompt() | self._llm.with_structured_output(
            CSharpOutput
        )
        self._bespoke_gen_chain = (
            build_codegen_prompt()
            | self._bespoke_llm.with_structured_output(CSharpOutput)
        )
        self._bespoke_max_attempts = max(
            1, _env_int("FORGE_BESPOKE_VALIDATION_ATTEMPTS", _MAX_ATTEMPTS)
        )
        self._bespoke_review_enabled = _env_bool(
            "FORGE_BESPOKE_REVIEW_ENABLED", False
        )
        self._review_enabled = _env_bool("FORGE_REVIEW_ENABLED", True)

        # Repair: prompt → LLM → raw string (corrected C# source)
        self._repair_chain = build_repair_prompt() | self._llm | StrOutputParser()

        # Logic review step
        self._reviewer = WeaponReviewer(model_name=model_name)

    @staticmethod
    def _uses_bespoke_codegen(manifest: dict) -> bool:
        plan = manifest.get("spectacle_plan")
        return isinstance(plan, dict) and bool(str(plan.get("fantasy", "")).strip())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_code(self, manifest: dict) -> dict:
        """Generate a C# ModItem file and hjson localization from *manifest*.

        Parameters
        ----------
        manifest : dict
            JSON-serializable manifest conforming to :class:`ForgeManifest`.

        Returns
        -------
        dict
            A :class:`ForgeOutput`-shaped dict with ``cs_code``, ``hjson_code``,
            and ``status``.
        """
        try:
            from forge_master.shoot_projectile_sanitize import sanitize_shoot_projectile
        except ImportError:
            from shoot_projectile_sanitize import sanitize_shoot_projectile

        sanitize_shoot_projectile(manifest)
        parsed = ForgeManifest.model_validate(manifest)
        validated_manifest = parsed.model_dump()

        sub_type = parsed.sub_type
        damage_class = DAMAGE_CLASS_MAP.get(sub_type, "DamageClass.Melee")
        use_style = USE_STYLE_MAP.get(sub_type, "ItemUseStyleID.Swing")
        uses_bespoke_manifest = self._uses_bespoke_codegen(validated_manifest)
        tool_power_lines = _render_tool_power_lines(parsed)
        reference_snippet = _reference_snippet_for_codegen(
            parsed, uses_bespoke=uses_bespoke_manifest
        )

        # 1. Invoke LLM for C# generation
        bespoke_chain = getattr(self, "_bespoke_gen_chain", None)
        gen_chain = (
            bespoke_chain
            if bespoke_chain is not None and uses_bespoke_manifest
            else self._gen_chain
        )
        is_bespoke = bespoke_chain is not None and gen_chain is bespoke_chain
        max_attempts = (
            getattr(self, "_bespoke_max_attempts", 2) if is_bespoke else _MAX_ATTEMPTS
        )
        llm_result: CSharpOutput = gen_chain.invoke(
            {
                "manifest_json": json.dumps(validated_manifest, indent=2),
                "damage_class": damage_class,
                "use_style": use_style,
                "tool_power_lines": tool_power_lines,
                "reference_snippet": reference_snippet,
            }
        )

        cs_code = _strip_markdown_fences(llm_result.code)

        # 2. Validate against 1.4.4 rules
        violations = (
            validate_cs(cs_code)
            + _validate_projectile_hitbox_contract(validated_manifest, cs_code)
            + _critique_violations(validated_manifest, cs_code)
        )
        attempt = 1

        while violations and attempt < max_attempts:
            error_str = "VALIDATION ERRORS:\n" + "\n".join(violations)
            cs_code = self._repair(cs_code, error_str, validated_manifest)
            violations = (
                validate_cs(cs_code)
                + _validate_projectile_hitbox_contract(validated_manifest, cs_code)
                + _critique_violations(validated_manifest, cs_code)
            )
            attempt += 1

        if violations:
            return ForgeOutput(
                status="error",
                cs_code=cs_code,
                error=ForgeError(
                    code="VALIDATION",
                    message=f"Failed to resolve API hallucination after {max_attempts} attempts: "
                    + "; ".join(violations),
                ),
            ).model_dump()

        # 3. Game-logic review
        if not getattr(self, "_review_enabled", True):
            review_output = ReviewOutput(approved=True, issues=[], summary="Skipped by FORGE_REVIEW_ENABLED=false")
        elif is_bespoke and not getattr(self, "_bespoke_review_enabled", False):
            review_output = ReviewOutput(approved=True, issues=[], summary="Skipped for bespoke deterministic path")
        else:
            cs_code, review_output = self._reviewer.review(validated_manifest, cs_code)

        if not review_output.approved:
            issue_list = [
                f"[{i.severity}] {i.category}: {i.description}"
                for i in review_output.issues
            ]
            return ForgeOutput(
                status="error",
                cs_code=cs_code,
                error=ForgeError(
                    code="LOGIC",
                    message="Compiler validation passed, but game-logic review failed: "
                    + "; ".join(issue_list),
                ),
            ).model_dump()

        final_violations = (
            validate_cs(cs_code)
            + _validate_projectile_hitbox_contract(validated_manifest, cs_code)
            + _critique_violations(validated_manifest, cs_code)
        )
        if final_violations:
            return ForgeOutput(
                status="error",
                cs_code=cs_code,
                error=ForgeError(
                    code="VALIDATION",
                    message="Post-review validation failed: "
                    + "; ".join(final_violations),
                ),
            ).model_dump()

        # 4. Generate hjson deterministically
        hjson_code = self._generate_hjson(
            item_name=parsed.item_name,
            display_name=parsed.display_name,
            tooltip=parsed.tooltip,
        )

        return ForgeOutput(
            cs_code=cs_code,
            hjson_code=hjson_code,
            status="success",
        ).model_dump()

    def fix_code(
        self, error_log: str, original_code: str, manifest: dict | None = None
    ) -> dict:
        """Repair previously generated C# code using a compiler error.

        Parameters
        ----------
        error_log : str
            Raw compiler error output (e.g. ``error CS0103: ...``).
        original_code : str
            The C# source that failed to compile.

        Returns
        -------
        dict
            A :class:`ForgeOutput`-shaped dict.  On success, ``cs_code``
            contains the repaired source.  On failure (after 3 attempts),
            ``status`` is ``"error"`` with a :class:`ForgeError` payload.
        """
        cs_code = original_code
        error_code = _extract_error_code(error_log)

        # NOTE: fix_code intentionally skips the WeaponReviewer.  This path is
        # a fast emergency repair triggered by a real tModLoader compiler error;
        # adding the LLM review loop would double latency on an already-failed
        # item.  The orchestrator will surface the repaired code for a full
        # write_code re-run if game-logic validation is also required.
        for attempt in range(_MAX_ATTEMPTS):
            cs_code = self._repair(cs_code, error_log, manifest or {})
            violations = validate_cs(cs_code) + _validate_projectile_hitbox_contract(
                manifest or {}, cs_code
            )

            if not violations:
                return ForgeOutput(cs_code=cs_code, status="success").model_dump()

            # Feed validation failures back as the error for the next attempt.
            error_log = "VALIDATION ERRORS:\n" + "\n".join(violations)

        return ForgeOutput(
            status="error",
            cs_code=cs_code,
            error=ForgeError(
                code=error_code,
                message=f"Failed to resolve API hallucination after {_MAX_ATTEMPTS} attempts.",
            ),
        ).model_dump()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _repair(
        self, original_code: str, error_log: str, manifest: dict | None = None
    ) -> str:
        """Invoke the repair chain and return cleaned C# source."""
        raw = self._repair_chain.invoke(
            {
                "manifest_json": json.dumps(manifest or {}, indent=2),
                "original_code": original_code,
                "error_log": error_log,
            }
        )
        return _strip_markdown_fences(raw)

    @staticmethod
    def _generate_hjson(
        item_name: str,
        display_name: str,
        tooltip: str,
        mod_name: str = "ForgeGeneratedMod",
    ) -> str:
        """Deterministically produce the hjson localization file.

        DisplayName and Tooltip are emitted as JSON string literals (via
        :func:`json.dumps`) so newlines, ``}``, and Terraria markup like
        ``[c/rrggbb:...]`` cannot break the Hjson structure.
        """
        quoted_display = json.dumps(display_name, ensure_ascii=False)
        quoted_tooltip = json.dumps(tooltip, ensure_ascii=False)
        return textwrap.dedent(f"""\
            Mods: {{
            \t{mod_name}: {{
            \t\tItems: {{
            \t\t\t{item_name}: {{
            \t\t\t\tDisplayName: {quoted_display}
            \t\t\t\tTooltip: {quoted_tooltip}
            \t\t\t}}
            \t\t}}
            \t}}
            }}""")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _reference_combat_package_key(
    parsed: ForgeManifest, *, uses_bespoke: bool = False
) -> str | None:
    if uses_bespoke:
        return None
    if parsed.resolved_combat is not None:
        return parsed.resolved_combat.package_key
    return parsed.mechanics.combat_package


def _reference_snippet_for_codegen(parsed: ForgeManifest, *, uses_bespoke: bool) -> str:
    if uses_bespoke:
        if parsed.mechanics_ir is not None:
            try:
                from forge_master.tier3_executor import render_tier3_skeleton
            except ImportError:
                from tier3_executor import render_tier3_skeleton

            return render_tier3_skeleton(parsed.model_dump())
        return """\
// Bespoke Tier-3 skeleton. Do not copy legacy package mechanics.
// Derive behavior from manifest.spectacle_plan, projectile_visuals, and stats.
// Required shape: ModItem shoots a custom ModProjectile in this file.
public class ExampleSpectacleProjectile : ModProjectile
{
    public override void SetStaticDefaults()
    {
        ProjectileID.Sets.TrailCacheLength[Type] = 18;
        ProjectileID.Sets.TrailingMode[Type] = 2;
    }

    public override void AI()
    {
        // Use an explicit timer/phase and implement the manifest composition.
    }

    public override bool PreDraw(ref Color lightColor)
    {
        // Draw oldPos trail, glow, and core passes using TextureAssets.Projectile[Type].
        return false;
    }
}"""
    return get_reference_snippet(
        parsed.sub_type,
        parsed.mechanics.custom_projectile,
        shot_style=parsed.mechanics.shot_style,
        combat_package=_reference_combat_package_key(parsed, uses_bespoke=False),
    )


def _render_tool_power_lines(parsed: ForgeManifest) -> str:
    renderer = TOOL_POWER_LINES.get(parsed.sub_type)
    if renderer is None or parsed.tool_stats is None:
        return ""
    return renderer(parsed.tool_stats.model_dump())


def _strip_markdown_fences(text: str) -> str:
    """Remove ```csharp ... ``` wrappers if the LLM included them."""
    text = text.strip()
    text = re.sub(r"^```(?:csharp|cs)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _extract_error_code(error_log: str) -> str:
    """Extract the first CSxxxx error code from a compiler log."""
    match = re.search(r"(CS\d{4})", error_log)
    return match.group(1) if match else "UNKNOWN"


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    agent = CoderAgent()

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            manifest = json.load(f)
    else:
        manifest = {
            "item_name": "GelatinousBlade",
            "display_name": "Gelatinous Blade",
            "tooltip": "A blade made of solidified slime.",
            "type": "Weapon",
            "sub_type": "Sword",
            "stats": {
                "damage": 18,
                "knockback": 4.0,
                "crit_chance": 4,
                "use_time": 25,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Green",
            },
            "mechanics": {
                "shoot_projectile": "ProjectileID.SlimeBall",
                "on_hit_buff": "BuffID.Slimed",
                "crafting_material": "ItemID.Gel",
                "crafting_cost": 20,
                "crafting_tile": "TileID.Anvils",
            },
        }

    result = agent.write_code(manifest)
    print(json.dumps(result, indent=2))
