"""Expert Terraria mod reviewer — validates weapon logic correctness.

This module provides a post-generation review step that verifies the generated
C# code actually implements the intended weapon behavior from the manifest.
Unlike ``validate_cs`` (which catches API hallucinations), the reviewer checks
*game logic*: does a channeled staff actually set ``Item.channel = true``?  Does
a homing projectile scan for NPCs?  Are the manifest stats reflected in code?

The reviewer returns structured feedback.  Critical issues trigger a repair
loop (up to ``max_attempts`` rounds) before the code is accepted or rejected.
"""

from __future__ import annotations

import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Structured output models
# ---------------------------------------------------------------------------


class ReviewIssue(BaseModel):
    """A single issue found by the reviewer."""

    severity: str = Field(
        description="One of: 'critical' (will not work in-game), "
        "'warning' (may cause subtle bugs), 'info' (style/best-practice)."
    )
    category: str = Field(
        description="Short category tag, e.g. 'shot_style_mismatch', "
        "'missing_buff', 'wrong_damage_class', 'stats_mismatch', "
        "'projectile_logic', 'runtime_crash'."
    )
    description: str = Field(description="Human-readable explanation of the issue.")
    suggested_fix: str = Field(
        description="Concrete code-level suggestion to resolve the issue."
    )


class ReviewOutput(BaseModel):
    """Structured output from the reviewer."""

    approved: bool = Field(
        description="True if the code is ready to ship — "
        "no critical or warning issues remain."
    )
    issues: list[ReviewIssue] = Field(
        default_factory=list,
        description="All issues found, ordered by severity (critical first).",
    )
    summary: str = Field(description="One-paragraph summary of the review verdict.")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

REVIEW_SYSTEM = """\
You are an **expert Terraria mod designer and tModLoader 1.4.4 code reviewer**.

Your ONLY job is to verify that the generated C# code will **function correctly
in-game** according to the weapon manifest.  You do NOT care about compilation
errors — assume the code compiles.  You care about **game-logic correctness**.

## What to check

### 1. combat_package / resolved_combat implementation
If the manifest includes a combat package, `resolved_combat` is required and is
the source of truth for combat behavior. Use `mechanics.combat_package` as the human-readable package label that should match `resolved_combat.package_key`.
Check `resolved_combat.package_key`, `resolved_combat.delivery_module`,
`resolved_combat.combo_module`, `resolved_combat.finisher_module`, and
`resolved_combat.presentation_module` explicitly when present. Those resolved
fields win over any freeform interpretation.
For the phase-1 packages, verify the code reflects the package semantics:

- **`storm_brand`**: `delivery_module` seed trigger exists, `combo_module`
  escalate state is represented, `finisher_module` finisher trigger is
  reachable, the state resets or consumes correctly, and
  `presentation_module` escalates on finisher.
- **`orbit_furnace`**: `delivery_module` orbit/heat trigger exists,
  `combo_module` escalate state is represented, `finisher_module` furnace
  payoff is reachable, the state resets or consumes correctly, and
  `presentation_module` escalates on finisher.
- **`frost_shatter`**: `delivery_module` chill/mark trigger exists,
  `combo_module` escalate state is represented, `finisher_module` shatter
  payoff is reachable, the state resets or consumes correctly, and
  `presentation_module` escalates on finisher.

### 2. shot_style implementation
If the manifest does not include a combat package, apply the legacy
`shot_style` rules below. Each shot_style requires specific patterns. Verify
these are present:

- **"direct"**: Item.shoot is set, basic Shoot() or no override needed.
- **"channeled"**: Item.channel = true, Item.noUseGraphic = true,
  CanUseItem limits to one active projectile, ModProjectile AI checks
  player.channel each frame, calls Kill() on release, sets player.heldProj,
  uses SetDummyItemTime(2), Projectile.timeLeft = 2.
- **"homing"**: ModProjectile AI scans for nearest NPC and steers toward it.
- **"sky_strike"**: Shoot() override spawns projectiles from above the screen
  (high Y position).  Should NOT generate a custom ModProjectile.
- **"boomerang"**: Item.noUseGraphic = true, ModProjectile has outward + return
  phases in AI(), uses ai[0] or similar for phase tracking.
- **"orbit"**: ModProjectile positions around player using sin/cos, velocity
  set to zero, Center computed from player position + angle.
- **"explosion"**: ModProjectile OnKill() calls Projectile.Resize() for AoE,
  includes dust/sound effects.
- **"pierce"**: Projectile.penetrate = -1, tileCollide = false,
  usesLocalNPCImmunity = true, extraUpdates for visual speed.
- **"chain_lightning"**: ModProjectile OnHitNPC spawns a new projectile aimed
  at the nearest OTHER NPC, with a max chain count tracked via ai[] slots.

### 3. Manifest stats reflected in SetDefaults
- damage, knockBack, useTime / useAnimation, crit, autoReuse, rare should
  match or be close to the manifest values.

### 4. DamageType correctness
- Staff/Wand/Tome/Spellbook → DamageClass.Magic
- Bow/Gun/Repeater/Rifle/Pistol/Shotgun/Launcher/Cannon → DamageClass.Ranged
- Sword/Broadsword/Shortsword/Spear/Lance/Axe/Pickaxe/Hammer/Hamaxe → DamageClass.Melee

### 5. on_hit_buff / buff_id implementation
- If the manifest specifies on_hit_buff, there MUST be an OnHitNPC method
  that calls target.AddBuff() with the correct BuffID.

### 6. Projectile presence
- If custom_projectile is true OR shot_style is non-direct (except sky_strike),
  a ModProjectile class MUST exist in the code.
- If shot_style is "sky_strike", there should NOT be a custom ModProjectile.

### 7. Runtime safety
- No infinite loops in AI().
- No null reference risks (e.g. accessing Main.npc[i] without bounds check).
- player.heldProj set for channeled weapons.
- Projectile.timeLeft managed properly for channeled/orbit so projectile
  doesn't expire prematurely.

### 8. Crafting recipe
- AddRecipes() should use CreateRecipe(), AddIngredient(), AddTile(), Register().
- Ingredients and tile should match the manifest's crafting_material,
  crafting_cost, and crafting_tile.

## Severity guide
- **critical**: The weapon will NOT function as intended in-game.  e.g.
  channeled weapon missing Item.channel = true, wrong shot_style pattern.
- **warning**: The weapon works but has subtle bugs.  e.g. missing
  localNPCHitCooldown on a piercing weapon, wrong dust type.
- **info**: Style or best practice.  e.g. could use a helper method,
  magic numbers without comments.

## Output rules
- Set `approved` to true ONLY if there are zero critical and zero warning issues.
- Be specific in `suggested_fix` — reference exact method names and property names.
- Do NOT flag compilation issues — that is handled by a separate validator."""

REVIEW_HUMAN = """\
## Weapon Manifest
```json
{manifest_json}
```

## Generated C# Code
```csharp
{cs_code}
```

Review the code above for game-logic correctness against the manifest."""


def build_review_prompt() -> ChatPromptTemplate:
    """Build the ChatPromptTemplate for the weapon logic review."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", REVIEW_SYSTEM),
            ("human", REVIEW_HUMAN),
        ]
    )


# ---------------------------------------------------------------------------
# Review-fix prompt (when the reviewer finds issues)
# ---------------------------------------------------------------------------

REVIEW_FIX_SYSTEM = """\
You are an expert C# developer specializing in **tModLoader 1.4.4**.

You will receive:
1. The original weapon manifest (the desired behavior).
2. The current C# code.
3. A list of game-logic issues found by a reviewer.

Your job is to fix ONLY the listed issues while preserving everything else.
Do NOT change anything that isn't related to the reported issues.

Return ONLY the corrected, complete C# source file.  No markdown fences, \
no explanations."""

REVIEW_FIX_HUMAN = """\
## Weapon Manifest
```json
{manifest_json}
```

## Current Code
```csharp
{cs_code}
```

## Review Issues to Fix
{review_issues}

Fix the issues above and return the complete corrected C# file."""


def build_review_fix_prompt() -> ChatPromptTemplate:
    """Build the ChatPromptTemplate for fixing reviewer-identified issues."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", REVIEW_FIX_SYSTEM),
            ("human", REVIEW_FIX_HUMAN),
        ]
    )


# ---------------------------------------------------------------------------
# Reviewer agent
# ---------------------------------------------------------------------------

_MAX_REVIEW_ATTEMPTS = 3


class WeaponReviewer:
    """Reviews generated C# code for Terraria weapon logic correctness.

    Usage::

        reviewer = WeaponReviewer()
        cs_code, review = reviewer.review(manifest_dict, cs_code)
        # cs_code may be updated if issues were found and fixed
        # review is the final ReviewOutput
    """

    def __init__(self, model_name: str = "gpt-5.4") -> None:
        self._review_llm = ChatOpenAI(
            model=model_name,
            timeout=300,
            reasoning_effort="high",
        )
        self._fix_llm = ChatOpenAI(
            model=model_name,
            timeout=300,
            reasoning_effort="high",
        )

        # Omit strict= for compatibility — matches the policy in forge_master.py
        # and architect.py where strict= is also omitted to avoid LangChain
        # version-skew issues.
        self._review_chain = (
            build_review_prompt()
            | self._review_llm.with_structured_output(ReviewOutput)
        )

        from langchain_core.output_parsers import StrOutputParser

        self._fix_chain = build_review_fix_prompt() | self._fix_llm | StrOutputParser()

    def review(
        self,
        manifest: dict,
        cs_code: str,
        max_attempts: int = _MAX_REVIEW_ATTEMPTS,
    ) -> tuple[str, ReviewOutput]:
        """Review and optionally fix the generated C# code.

        Parameters
        ----------
        manifest : dict
            The weapon manifest (same dict passed to ``CoderAgent.write_code``).
        cs_code : str
            The generated C# source code.
        max_attempts : int
            Maximum review → fix → re-review cycles.

        Returns
        -------
        tuple[str, ReviewOutput]
            The (possibly fixed) C# code and the final review result.
        """
        manifest_json = json.dumps(manifest, indent=2)

        for attempt in range(max_attempts):
            review_result: ReviewOutput = self._review_chain.invoke(
                {
                    "manifest_json": manifest_json,
                    "cs_code": cs_code,
                }
            )

            # If approved or only info-level issues, accept immediately
            if review_result.approved:
                return cs_code, review_result

            # Check if there are actionable issues (critical or warning)
            actionable = [
                i for i in review_result.issues if i.severity in ("critical", "warning")
            ]

            if not actionable:
                # Only info-level issues — approve without mutating the LLM result
                return cs_code, ReviewOutput(
                    approved=True,
                    issues=review_result.issues,
                    summary=review_result.summary,
                )

            # Format issues for the fix prompt
            issue_text = self._format_issues(actionable)

            # Attempt to fix
            raw_fix = self._fix_chain.invoke(
                {
                    "manifest_json": manifest_json,
                    "cs_code": cs_code,
                    "review_issues": issue_text,
                }
            )

            cs_code = _strip_fences(raw_fix)

        # Final review after last fix
        final_review: ReviewOutput = self._review_chain.invoke(
            {
                "manifest_json": manifest_json,
                "cs_code": cs_code,
            }
        )

        return cs_code, final_review

    @staticmethod
    def _format_issues(issues: list[ReviewIssue]) -> str:
        """Format issues into a readable string for the fix prompt."""
        lines = []
        for i, issue in enumerate(issues, 1):
            lines.append(
                f"{i}. [{issue.severity.upper()}] {issue.category}\n"
                f"   Problem: {issue.description}\n"
                f"   Fix: {issue.suggested_fix}"
            )
        return "\n\n".join(lines)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:csharp|cs)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
