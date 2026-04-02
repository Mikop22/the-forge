"""Architect Agent – converts a user idea + tier into a balanced item manifest."""

from __future__ import annotations

import json

from langchain_openai import ChatOpenAI

try:  # Prefer package imports to avoid cross-agent module name collisions.
    from architect.models import (
        TIER_TABLE,
        VALID_TIERS,
        ItemManifest,
        LLMItemOutput,
        resolve_crafting,
    )
    from architect.prompts import build_prompt
    from architect.reference_finder import BrowserReferenceFinder
    from architect.reference_policy import HybridReferenceApprover, ReferencePolicy
except ImportError:  # Fallback for direct script execution from the folder.
    from models import (
        TIER_TABLE,
        VALID_TIERS,
        ItemManifest,
        LLMItemOutput,
        resolve_crafting,
    )
    from prompts import build_prompt
    from reference_finder import BrowserReferenceFinder
    from reference_policy import HybridReferenceApprover, ReferencePolicy


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

    def __init__(self, model_name: str = "gpt-5.4") -> None:
        self._llm = ChatOpenAI(model=model_name, timeout=120)
        self._prompt = build_prompt()
        # LCEL chain: prompt -> LLM with structured Pydantic output
        self._chain = self._prompt | self._llm.with_structured_output(LLMItemOutput)
        self._reference_policy = ReferencePolicy(
            finder=BrowserReferenceFinder(),
            approver=HybridReferenceApprover(model_name=model_name),
            max_retries=1,
        )

    def generate_manifest(self, prompt: str, tier: str, crafting_station: str | None = None) -> dict:
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
        if tier not in VALID_TIERS:
            raise ValueError(
                f"Unknown tier: {tier!r}. Must be one of {sorted(VALID_TIERS)}"
            )

        tier_data = TIER_TABLE[tier]

        # 1. Deterministic crafting resolution (fallback)
        crafting = resolve_crafting(prompt, tier, crafting_station)

        # 2. Invoke the LLM chain
        llm_result: LLMItemOutput = self._chain.invoke({
            "user_prompt": prompt,
            "selected_tier": tier,
            "damage_min": tier_data["damage"][0],
            "damage_max": tier_data["damage"][1],
            "use_time_min": tier_data["use_time"][0],
            "use_time_max": tier_data["use_time"][1],
        })

        # 3. Merge LLM output with deterministic crafting fields.
        #    LLM overrides take priority when the user was explicit;
        #    deterministic values fill in anything the LLM left null.
        data = llm_result.model_dump()
        llm_crafting = data.get("mechanics", {})
        for key in ("crafting_material", "crafting_cost", "crafting_tile"):
            if not llm_crafting.get(key):
                data["mechanics"][key] = crafting[key]
        reference_data = self._reference_policy.resolve(
            prompt=prompt,
            reference_needed=bool(data.get("reference_needed", False)),
            reference_subject=data.get("reference_subject"),
            item_type=data.get("type", ""),
            sub_type=data.get("sub_type", ""),
        )
        data.update(reference_data)
        self._enforce_reference_fidelity_prompting(data)

        # 4. Validate & clamp via ItemManifest (tier-aware)
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
            projectile_clause = (
                "Keep projectile design consistent with the same reference style language."
            )
            if projectile_clause.lower() not in proj_desc.lower():
                projectile_visuals["description"] = (
                    f"{proj_desc}. {projectile_clause}" if proj_desc else projectile_clause
                )
            data["projectile_visuals"] = projectile_visuals


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    agent = ArchitectAgent()

    user_prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "A sword made of slime that shoots bouncing balls"
    )
    selected_tier = sys.argv[2] if len(sys.argv) > 2 else "Tier1_Starter"

    result = agent.generate_manifest(user_prompt, selected_tier)
    print(json.dumps(result, indent=2))
