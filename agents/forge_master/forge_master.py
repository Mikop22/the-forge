"""Forge Master Agent – converts an Architect manifest into compilable C# + hjson."""

from __future__ import annotations

import json
import re
import textwrap

from core.agent_warnings import suppress_langchain_pydantic_warnings

suppress_langchain_pydantic_warnings()

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

try:
    from forge_master.models import CSharpOutput, ForgeError, ForgeManifest, ForgeOutput
    from forge_master.prompts import build_codegen_prompt, build_repair_prompt
    from forge_master.reviewer import WeaponReviewer
    from forge_master.templates import (
        DAMAGE_CLASS_MAP,
        USE_STYLE_MAP,
        get_reference_snippet,
        validate_cs,
    )
except ImportError:
    from models import CSharpOutput, ForgeError, ForgeManifest, ForgeOutput
    from prompts import build_codegen_prompt, build_repair_prompt
    from reviewer import WeaponReviewer
    from templates import (
        DAMAGE_CLASS_MAP,
        USE_STYLE_MAP,
        get_reference_snippet,
        validate_cs,
    )

_MAX_ATTEMPTS = 3


class CoderAgent:
    """Generates tModLoader 1.4.4 C# source and hjson localization files.

    Usage::

        agent = CoderAgent()
        result = agent.write_code(manifest_dict)
        # result["cs_code"], result["hjson_code"], result["status"]
    """

    def __init__(self, model_name: str = "gpt-5.4") -> None:
        # GPT-5 Nano does not support the temperature parameter.
        self._llm = ChatOpenAI(model=model_name, timeout=300, reasoning_effort="high")

        # Code generation: prompt → LLM → structured Pydantic output
        self._gen_chain = build_codegen_prompt() | self._llm.with_structured_output(
            CSharpOutput
        )

        # Repair: prompt → LLM → raw string (corrected C# source)
        self._repair_chain = build_repair_prompt() | self._llm | StrOutputParser()

        # Logic review step
        self._reviewer = WeaponReviewer(model_name=model_name)

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
        parsed = ForgeManifest.model_validate(manifest)
        validated_manifest = parsed.model_dump()

        sub_type = parsed.sub_type
        damage_class = DAMAGE_CLASS_MAP.get(sub_type, "DamageClass.Melee")
        use_style = USE_STYLE_MAP.get(sub_type, "ItemUseStyleID.Swing")
        custom_projectile = parsed.mechanics.custom_projectile
        shot_style = parsed.mechanics.shot_style
        combat_package = _reference_combat_package_key(parsed)
        reference_snippet = get_reference_snippet(
            sub_type,
            custom_projectile,
            shot_style=shot_style,
            combat_package=combat_package,
        )

        # 1. Invoke LLM for C# generation
        llm_result: CSharpOutput = self._gen_chain.invoke(
            {
                "manifest_json": json.dumps(validated_manifest, indent=2),
                "damage_class": damage_class,
                "use_style": use_style,
                "reference_snippet": reference_snippet,
            }
        )

        cs_code = _strip_markdown_fences(llm_result.code)

        # 2. Validate against 1.4.4 rules
        violations = validate_cs(cs_code)
        attempt = 1

        while violations and attempt < _MAX_ATTEMPTS:
            error_str = "VALIDATION ERRORS:\n" + "\n".join(violations)
            cs_code = self._repair(cs_code, error_str)
            violations = validate_cs(cs_code)
            attempt += 1

        if violations:
            return ForgeOutput(
                status="error",
                error=ForgeError(
                    code="VALIDATION",
                    message=f"Failed to resolve API hallucination after {_MAX_ATTEMPTS} attempts: "
                    + "; ".join(violations),
                ),
            ).model_dump()

        # 3. Game-logic review
        cs_code, review_output = self._reviewer.review(validated_manifest, cs_code)

        if not review_output.approved:
            issue_list = [
                f"[{i.severity}] {i.category}: {i.description}"
                for i in review_output.issues
            ]
            return ForgeOutput(
                status="error",
                error=ForgeError(
                    code="LOGIC",
                    message="Compiler validation passed, but game-logic review failed: "
                    + "; ".join(issue_list),
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

    def fix_code(self, error_log: str, original_code: str) -> dict:
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
            cs_code = self._repair(cs_code, error_log)
            violations = validate_cs(cs_code)

            if not violations:
                return ForgeOutput(cs_code=cs_code, status="success").model_dump()

            # Feed validation failures back as the error for the next attempt.
            error_log = "VALIDATION ERRORS:\n" + "\n".join(violations)

        return ForgeOutput(
            status="error",
            error=ForgeError(
                code=error_code,
                message=f"Failed to resolve API hallucination after {_MAX_ATTEMPTS} attempts.",
            ),
        ).model_dump()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _repair(self, original_code: str, error_log: str) -> str:
        """Invoke the repair chain and return cleaned C# source."""
        raw = self._repair_chain.invoke(
            {
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
        """Deterministically produce the hjson localization file."""
        return textwrap.dedent(f"""\
            Mods: {{
            \t{mod_name}: {{
            \t\tItems: {{
            \t\t\t{item_name}: {{
            \t\t\t\tDisplayName: {display_name}
            \t\t\t\tTooltip: {tooltip}
            \t\t\t}}
            \t\t}}
            \t}}
            }}""")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _reference_combat_package_key(parsed: ForgeManifest) -> str | None:
    if parsed.resolved_combat is not None:
        return parsed.resolved_combat.package_key
    return parsed.mechanics.combat_package


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
