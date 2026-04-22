"""Architect Agent – converts a user idea + tier into a balanced item manifest."""

from __future__ import annotations

import json
from typing import Optional

from core.agent_warnings import suppress_langchain_pydantic_warnings

suppress_langchain_pydantic_warnings()

from langchain_openai import ChatOpenAI


PACKAGE_VISUAL_BRIEFS = {
    "storm_brand": "forked celestial storm staff with a glowing blue-white star crystal and brass filigree",
    "orbit_furnace": "ember-forged staff with a bronze ring crown and orbiting orange coals",
    "frost_shatter": "icy crystal staff with fractured blue shard prongs and silver bindings",
}

PACKAGE_PROJECTILE_BRIEFS = {
    "storm_brand": "sharp blue-white lightning sigil bolt with a star-bright crystal core",
    "orbit_furnace": "small orange ember orb with a bright molten core and soot halo",
    "frost_shatter": "cold blue crystal shard bolt with a white frost glow",
}

try:  # Prefer package imports to avoid cross-agent module name collisions.
    from architect.models import (
        TIER_TABLE,
        VALID_TIERS,
        ItemManifest,
        LLMItemOutput,
        resolve_crafting,
    )
    from architect import prompts as prompt_router
    from architect.weapon_prompt import (
        LegacyFallbackMarkerLiteral,
        PACKAGE_FIRST_CONTENT_TYPE,
        PACKAGE_FIRST_SUB_TYPE,
        PACKAGE_FX_PROFILE_MAP,
    )
    from architect.reference_finder import BrowserReferenceFinder
    from architect.reference_policy import HybridReferenceApprover, ReferencePolicy
    from architect.thesis_generator import (
        LLMWeaponThesisGenerator,
        ThesisFinalist,
        ThesisTournament,
        WeaponThesisGenerator,
    )
    from architect.thesis_judges import ThesisJudge, build_default_thesis_judges
    from core.runtime_capabilities import RuntimeCapabilityMatrix
    from core.runtime_contracts import BehaviorContract as HiddenBehaviorContract
    from core.weapon_lab_models import RankingPolicy
except ImportError:  # Fallback for direct script execution from the folder.
    from models import (
        TIER_TABLE,
        VALID_TIERS,
        ItemManifest,
        LLMItemOutput,
        resolve_crafting,
    )
    import prompts as prompt_router
    from weapon_prompt import (
        LegacyFallbackMarkerLiteral,
        PACKAGE_FIRST_CONTENT_TYPE,
        PACKAGE_FIRST_SUB_TYPE,
        PACKAGE_FX_PROFILE_MAP,
    )
    from reference_finder import BrowserReferenceFinder
    from reference_policy import HybridReferenceApprover, ReferencePolicy
    from thesis_generator import (
        LLMWeaponThesisGenerator,
        ThesisFinalist,
        ThesisTournament,
        WeaponThesisGenerator,
    )
    from thesis_judges import ThesisJudge, build_default_thesis_judges
    from core.runtime_capabilities import RuntimeCapabilityMatrix
    from core.runtime_contracts import BehaviorContract as HiddenBehaviorContract
    from core.weapon_lab_models import RankingPolicy


class ArchitectAgent:
    """Entry-point agent that produces a deterministic JSON manifest for
    downstream Coding and Art agents.

    Usage::

        agent = ArchitectAgent()
        manifest = agent.generate_manifest(
            prompt="A sword made of slime that shoots bouncing balls",
            tier="Tier1_Starter",
        )
    """

    def __init__(
        self,
        model_name: str = "gpt-5.4",
        thesis_generator: WeaponThesisGenerator | None = None,
        thesis_judges: tuple[ThesisJudge, ...] = (),
        ranking_policy: RankingPolicy | None = None,
        runtime_capability_matrix: RuntimeCapabilityMatrix | None = None,
    ) -> None:
        self._llm = ChatOpenAI(model=model_name, timeout=120)
        # Omit strict=... for compatibility with LangChain versions that do not forward it.
        self._structured_llm = self._llm.with_structured_output(LLMItemOutput)
        self._reference_policy = ReferencePolicy(
            finder=BrowserReferenceFinder(),
            approver=HybridReferenceApprover(model_name=model_name),
            max_retries=1,
        )
        self._thesis_tournament = ThesisTournament(
            thesis_generator=thesis_generator or LLMWeaponThesisGenerator(model_name),
            judges=thesis_judges or build_default_thesis_judges(),
            ranking_policy=ranking_policy or RankingPolicy.default(),
        )
        self._runtime_capability_matrix = (
            runtime_capability_matrix or RuntimeCapabilityMatrix.default()
        )

    def _build_chain(self, content_type: str, sub_type: str):
        prompt_template = prompt_router.build_prompt(content_type, sub_type)
        # LCEL chain: prompt -> LLM with structured Pydantic output
        return prompt_template | self._structured_llm

    def generate_manifest(
        self,
        prompt: str,
        tier: str,
        content_type: str = "Weapon",
        sub_type: str = "",
        crafting_station: str | None = None,
    ) -> dict:
        """Generate a fully validated item manifest.

        Parameters
        ----------
        prompt : str
            Natural-language item description from the user.
        tier : str
            One of ``Tier1_Starter``, ``Tier2_Dungeon``, ``Tier3_Hardmode``,
            ``Tier4_Endgame``.

        Returns
        -------
        dict
            JSON-serializable manifest conforming to :class:`ItemManifest`.

        Raises
        ------
        ValueError
            If *tier* is not a recognised tier key.
        """
        content_type = content_type or "Weapon"
        content_type = prompt_router.normalize_content_type(content_type)
        if tier not in VALID_TIERS:
            raise ValueError(
                f"Unknown tier: {tier!r}. Must be one of {sorted(VALID_TIERS)}"
            )

        tier_data = TIER_TABLE[tier]

        # 2. Invoke the LLM chain
        llm_result: LLMItemOutput = self._build_chain(content_type, sub_type).invoke(
            {
                "user_prompt": prompt,
                "selected_tier": tier,
                "content_type": content_type,
                "sub_type": sub_type,
                "damage_min": tier_data["damage"][0],
                "damage_max": tier_data["damage"][1],
                "use_time_min": tier_data["use_time"][0],
                "use_time_max": tier_data["use_time"][1],
            }
        )

        data = llm_result.model_dump()
        return self._finalize_manifest_data(
            data,
            prompt=prompt,
            tier=tier,
            content_type=content_type,
            sub_type=sub_type,
            crafting_station=crafting_station,
        )

    def generate_thesis_finalists(
        self,
        *,
        prompt: str,
        thesis_count: int,
        finalist_count: int,
        selected_tier: str,
        content_type: str = "Weapon",
        sub_type: str = "Staff",
    ):
        """Return ranked finalists for the thesis pass without choosing a winner."""

        return self._thesis_tournament.generate_ranked_finalists(
            prompt=prompt,
            thesis_count=thesis_count,
            finalist_count=finalist_count,
            selected_tier=selected_tier,
            content_type=content_type,
            sub_type=sub_type,
        )

    def expand_thesis_finalist_to_manifest(
        self,
        *,
        finalist: ThesisFinalist,
        prompt: str,
        tier: str,
        content_type: str = "Weapon",
        sub_type: str = "Staff",
        crafting_station: str | None = None,
        legacy_fallback_marker: Optional[LegacyFallbackMarkerLiteral] = None,
    ) -> dict:
        thesis = finalist.thesis
        package_key = thesis.combat_package
        fx_profile = PACKAGE_FX_PROFILE_MAP[package_key]
        title = package_key.replace("_", " ").title()
        visual_description = self._build_hidden_visual_brief(
            package_key=package_key,
            sub_type=sub_type,
        )
        projectile_description = self._build_hidden_projectile_brief(
            package_key=package_key,
            fallback_visual_description=visual_description,
        )
        visuals = {
            "description": visual_description,
            "art_direction_profile": "balanced",
        }
        base_data = {
            "item_name": f"{title} {sub_type}",
            "display_name": f"{title} {sub_type}",
            "tooltip": thesis.fantasy,
            "content_type": content_type,
            "type": content_type,
            "sub_type": sub_type,
            "stats": {
                "damage": TIER_TABLE[tier]["damage"][0],
                "knockback": 5.0,
                "crit_chance": 4,
                "use_time": TIER_TABLE[tier]["use_time"][0],
                "auto_reuse": True,
                "rarity": TIER_TABLE[tier]["rarity"],
            },
            "visuals": visuals,
            "reference_needed": False,
            "reference_subject": None,
            "reference_image_url": None,
            "reference_notes": None,
            "fallback_reason": None,
            "projectile_visuals": {
                "description": projectile_description,
                "art_direction_profile": "balanced",
            },
        }
        package_surface_supported = self._runtime_capability_matrix.supports(
            content_type=content_type,
            sub_type=sub_type,
            loop_family=thesis.loop_family,
        )
        explicit_fallback_allowed = legacy_fallback_marker is not None
        if package_surface_supported and not explicit_fallback_allowed:
            manifest = self._finalize_manifest_data(
                {
                    **base_data,
                    "presentation": {"fx_profile": fx_profile},
                    "mechanics": {
                        "combat_package": package_key,
                        "delivery_style": thesis.delivery_style,
                        "payoff_rate": thesis.payoff_rate,
                    },
                },
                prompt=prompt,
                tier=tier,
                content_type=content_type,
                sub_type=sub_type,
                crafting_station=crafting_station,
            )
            return self._attach_hidden_audition_context(
                manifest=manifest,
                finalist=finalist,
            )

        resolved_combat = ItemManifest.model_validate(
            self._finalize_manifest_data(
                {
                    **base_data,
                    "content_type": PACKAGE_FIRST_CONTENT_TYPE,
                    "type": PACKAGE_FIRST_CONTENT_TYPE,
                    "sub_type": PACKAGE_FIRST_SUB_TYPE,
                    "presentation": {"fx_profile": fx_profile},
                    "mechanics": {
                        "combat_package": package_key,
                        "delivery_style": thesis.delivery_style,
                        "payoff_rate": thesis.payoff_rate,
                    },
                },
                prompt=prompt,
                tier=tier,
                content_type=PACKAGE_FIRST_CONTENT_TYPE,
                sub_type=PACKAGE_FIRST_SUB_TYPE,
                crafting_station=crafting_station,
            )
        ).resolved_combat
        legacy_projection = resolved_combat.legacy_projection

        if explicit_fallback_allowed:
            fallback_reason = (
                "allowed legacy fallback: explicit "
                f"{legacy_fallback_marker.replace('_', ' ')} marker "
                f"on supported {content_type}/{sub_type} surface"
            )
        else:
            fallback_reason = (
                "allowed legacy fallback: runtime surface "
                f"{content_type}/{sub_type} does not support {thesis.loop_family}"
            )

        manifest = self._finalize_manifest_data(
            {
                **base_data,
                "fallback_reason": fallback_reason,
                "mechanics": {
                    "shot_style": legacy_projection.shot_style,
                    "custom_projectile": legacy_projection.custom_projectile,
                    "shoot_projectile": legacy_projection.shoot_projectile,
                },
            },
            prompt=prompt,
            tier=tier,
            content_type=content_type,
            sub_type=sub_type,
            crafting_station=crafting_station,
        )
        return self._attach_hidden_audition_context(
            manifest=manifest,
            finalist=finalist,
        )

    @staticmethod
    def _attach_hidden_audition_context(
        *, manifest: dict, finalist: ThesisFinalist
    ) -> dict:
        thesis = finalist.thesis
        context = {
            **manifest,
            "candidate_id": finalist.candidate_id,
            "weapon_thesis": thesis.model_dump(mode="json"),
        }
        if manifest.get("resolved_combat") is None:
            return context
        return {
            **context,
            "package_key": thesis.combat_package,
            "loop_family": thesis.loop_family,
            "behavior_contract": HiddenBehaviorContract(
                seed_event="seed_triggered",
                escalate_event="escalate_triggered",
                cashout_event="cashout_triggered",
                max_hits_to_cashout=3,
                max_time_to_cashout_ms=2500,
            ).model_dump(mode="json"),
        }

    @staticmethod
    def _build_hidden_visual_brief(*, package_key: str, sub_type: str) -> str:
        package_brief = PACKAGE_VISUAL_BRIEFS.get(package_key, "arcane weapon")
        if sub_type.lower() not in package_brief.lower():
            return f"{package_brief} {sub_type.lower()}"
        return package_brief

    @staticmethod
    def _build_hidden_projectile_brief(
        *, package_key: str, fallback_visual_description: str
    ) -> str:
        return PACKAGE_PROJECTILE_BRIEFS.get(package_key, fallback_visual_description)

    def _finalize_manifest_data(
        self,
        data: dict,
        *,
        prompt: str,
        tier: str,
        content_type: str,
        sub_type: str,
        crafting_station: str | None = None,
    ) -> dict:
        crafting = resolve_crafting(prompt, tier, crafting_station)
        data["content_type"] = content_type
        data["sub_type"] = sub_type or prompt_router.DEFAULT_SUB_TYPES.get(content_type, "Sword")
        data.setdefault("type", content_type)
        data.setdefault("mechanics", {})
        llm_crafting = data.get("mechanics", {})
        for key in ("crafting_material", "crafting_cost", "crafting_tile"):
            if not llm_crafting.get(key):
                data["mechanics"][key] = crafting[key]
        reference_data = self._reference_policy.resolve(
            prompt=prompt,
            reference_needed=bool(data.get("reference_needed", False)),
            reference_subject=data.get("reference_subject"),
            item_type=data.get("content_type", data.get("type", "")),
            sub_type=data.get("sub_type", sub_type),
        )
        data.update(reference_data)
        data["generation_mode"] = (
            "image_to_image" if data.get("reference_image_url") else "text_to_image"
        )
        self._enforce_reference_fidelity_prompting(data)
        manifest = ItemManifest.model_validate(data, context={"tier": tier})
        return manifest.model_dump()

    @staticmethod
    def _enforce_reference_fidelity_prompting(data: dict) -> None:
        """When reference mode is active, force the art prompt to prioritize
        object identity/silhouette fidelity over stylistic drift.
        """
        if data.get("generation_mode") != "image_to_image":
            return

        subject = str(data.get("reference_subject") or "the referenced subject").strip()
        fidelity_clause = (
            f"Preserve exact subject identity for {subject}; "
            "match the reference silhouette, proportions, and signature design motifs; "
            "do not redesign core geometry."
        )

        visuals = data.get("visuals") or {}
        description = str(visuals.get("description") or "").strip()
        if fidelity_clause.lower() not in description.lower():
            visuals["description"] = (
                f"{description}. {fidelity_clause}" if description else fidelity_clause
            )
        data["visuals"] = visuals

        projectile_visuals = data.get("projectile_visuals")
        if isinstance(projectile_visuals, dict):
            proj_desc = str(projectile_visuals.get("description") or "").strip()
            projectile_clause = "Keep projectile design consistent with the same reference style language."
            if projectile_clause.lower() not in proj_desc.lower():
                projectile_visuals["description"] = (
                    f"{proj_desc}. {projectile_clause}"
                    if proj_desc
                    else projectile_clause
                )
            data["projectile_visuals"] = projectile_visuals


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    agent = ArchitectAgent()

    user_prompt = (
        sys.argv[1]
        if len(sys.argv) > 1
        else ("A sword made of slime that shoots bouncing balls")
    )
    selected_tier = sys.argv[2] if len(sys.argv) > 2 else "Tier1_Starter"

    result = agent.generate_manifest(user_prompt, selected_tier)
    print(json.dumps(result, indent=2))
