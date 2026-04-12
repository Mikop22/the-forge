# Combat Package V2 Implementation Plan

Archived summary of the package-first combat work.

## Goal

Replace free-form projectile-first authoring with bounded combat packages that lower deterministically into legacy fields.

## Phase-1 Bounds

- Packages: `storm_brand`, `orbit_furnace`, `frost_shatter`
- FX profiles: `celestial_shock`, `ember_forge`, `glacial_burst`
- Compiled mod path is the main target.
- Legacy projectile fields remain supported as fallback plumbing.

## Main Architecture

1. Add a shared combat package registry/resolver.
2. Let `Architect` emit package fields.
3. Resolve package metadata into `resolved_combat`.
4. Derive legacy projectile fields automatically.
5. Keep `Forge Master` package-aware while preserving legacy fallback behavior.

## Success Criteria

- Valid package-first manifests.
- Deterministic lowering to legacy fields.
- Existing legacy behavior still works.
- Builds still pass through Gatekeeper.
- Live injection still works for at least one generated package weapon.

## Why This Was Compressed

The original file mostly contained task-by-task execution detail. The bounded scope and architecture are the durable parts.

**Step 1: Write the failing test**

Add a prompt-contract assertion:

```python
from architect.weapon_prompt import SYSTEM_PROMPT


def test_weapon_prompt_prefers_combat_packages():
    assert "mechanics.combat_package" in SYSTEM_PROMPT
    assert "ProjectileID.* only for explicit vanilla homage weapons" in SYSTEM_PROMPT
    assert "legacy fallback" in SYSTEM_PROMPT
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest architect/test_architect_models.py -v`
Expected: FAIL because the prompt still teaches `shot_style` / `ProjectileID` as primary.

**Step 3: Write minimal implementation**

Update the prompt contract so it says:

- primary authoring path is `combat_package`
- allowed packages are only the phase-1 registry keys
- allowed `delivery_style` values are bounded
- `fx_profile` is chosen from authored profiles
- raw `ProjectileID.*` is for homage weapons only
- `shot_style`, `custom_projectile`, and `shoot_projectile` are compatibility/internal fields, not primary design knobs

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest architect/test_architect_models.py tests/test_projectile_pipeline_fixes.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add architect/weapon_prompt.py architect/test_architect_models.py
git commit -m "feat: switch architect prompt to package-first authoring"
```

### Task 4: Make Forge Master Routing Package-Aware

**Files:**
- Modify: `agents/forge_master/models.py:48-81`
- Modify: `agents/forge_master/forge_master.py:82-100`
- Modify: `agents/forge_master/templates/snippets.py:1602-1630`
- Modify: `agents/forge_master/test_forge_templates.py:25-149`

**Step 1: Write the failing test**

```python
def test_combat_package_template_wins_over_legacy_style():
    snippet = get_reference_snippet(
        sub_type="Staff",
        custom_projectile=False,
        shot_style="direct",
        combat_package="storm_brand",
    )
    assert "starfall" in snippet.lower()


def test_legacy_routing_still_works_without_combat_package():
    snippet = get_reference_snippet(
        sub_type="Staff",
        custom_projectile=False,
        shot_style="sky_strike",
        combat_package=None,
    )
    assert snippet == SKY_STRIKE_TEMPLATE
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest forge_master/test_forge_templates.py -v`
Expected: FAIL because `combat_package` is not supported.

**Step 3: Write minimal implementation**

Update `forge_master/models.py` to accept:

- package-facing mechanics fields
- `presentation`
- `resolved_combat`

Update `get_reference_snippet(...)` so routing priority is:

1. `combat_package`
2. legacy non-direct `shot_style`
3. legacy `custom_projectile`
4. subtype fallback

Add phase-1 package templates only:

- `STORM_BRAND_TEMPLATE`
- `ORBIT_FURNACE_TEMPLATE`
- `FROST_SHATTER_TEMPLATE`

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest forge_master/test_forge_templates.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add forge_master/models.py forge_master/forge_master.py forge_master/templates/snippets.py forge_master/test_forge_templates.py
git commit -m "feat: add package-aware forge master routing"
```

### Task 5: Teach Forge Master Prompt And Reviewer Package Semantics

**Files:**
- Modify: `agents/forge_master/prompts.py:33-149`
- Modify: `agents/forge_master/reviewer.py:64-149`
- Modify: `agents/forge_master/test_forge_reviewer.py:19-111`

**Step 1: Write the failing test**

```python
def test_reviewer_requires_storm_brand_loop_for_package_manifest():
    reviewer = _make_reviewer()
    bad_review = ReviewOutput(
        approved=False,
        issues=[
            ReviewIssue(
                severity="critical",
                category="combat_package",
                description="storm_brand missing mark stack and finisher trigger",
                suggested_fix="Implement hit-applied marks and third-mark starfall cash-out",
            )
        ],
        summary="missing package loop",
    )
    reviewer._review_chain = MagicMock()
    reviewer._review_chain.invoke.return_value = bad_review

    manifest = {"item_name": "StormBrand", "mechanics": {"combat_package": "storm_brand"}}
    _, final_review = reviewer.review(manifest, "class StormBrand {}")
    assert final_review.approved is False
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest forge_master/test_forge_reviewer.py -v`
Expected: FAIL because package-specific review rules do not exist.

**Step 3: Write minimal implementation**

In `prompts.py`:

- prefer `resolved_combat` when present
- add explicit instructions for:
  - `storm_brand`
  - `orbit_furnace`
  - `frost_shatter`
- preserve legacy `shot_style` instructions for fallback manifests

In `reviewer.py` add package checks for:

- seed trigger exists
- escalate state is represented
- finisher trigger is reachable
- state resets or consumes correctly
- presentation escalates on finisher

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest forge_master/test_forge_reviewer.py forge_master/test_forge_templates.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add forge_master/prompts.py forge_master/reviewer.py forge_master/test_forge_reviewer.py forge_master/test_forge_templates.py
git commit -m "feat: teach forge master package semantics"
```

### Task 6: Add End-To-End Package Regression Harness

**Files:**
- Create: `agents/tests/fixtures/combat_package_prompts.json`
- Create: `agents/tests/test_combat_package_pipeline.py`
- Modify: `agents/tests/test_projectile_pipeline_fixes.py:90-211`
- Reuse: `agents/orchestrator_smoke.py`
- Reuse: `agents/tests/test_orchestrator_smoke.py:13-61`

**Step 1: Write the failing test**

```python
def test_package_manifest_keeps_visuals_and_template_routing():
    manifest = {
        "item_name": "StormBrand",
        "display_name": "Storm Brand",
        "content_type": "Weapon",
        "sub_type": "Staff",
        "stats": {"damage": 12, "knockback": 4.0, "use_time": 24, "rarity": "ItemRarityID.White"},
        "visuals": {"description": "a crackling blue staff", "color_palette": [], "icon_size": [48, 48]},
        "mechanics": {
            "combat_package": "storm_brand",
            "delivery_style": "direct",
            "payoff_rate": "fast",
            "crafting_material": "ItemID.Wood",
            "crafting_cost": 5,
            "crafting_tile": "TileID.WorkBenches",
        },
        "presentation": {"fx_profile": "celestial_shock"},
    }
    parsed = ForgeManifest.model_validate(manifest)
    snippet = get_reference_snippet(
        parsed.sub_type,
        parsed.mechanics.custom_projectile,
        shot_style=parsed.mechanics.shot_style,
        combat_package=parsed.mechanics.combat_package,
    )
    assert parsed.projectile_visuals is not None
    assert "starfall" in snippet.lower()
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_combat_package_pipeline.py tests/test_projectile_pipeline_fixes.py tests/test_orchestrator_smoke.py -v`
Expected: FAIL until the previous tasks land.

**Step 3: Write minimal implementation**

Add:

- one regression test per phase-1 package
- one legacy fallback test proving old `shot_style` manifests still work
- one smoke path proving orchestrator helpers still accept ready-status flows after package manifests are introduced

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_combat_package_pipeline.py tests/test_projectile_pipeline_fixes.py tests/test_orchestrator_smoke.py -v`
Expected: PASS

Then run the broader targeted suite:

Run: `./.venv/bin/pytest core/test_combat_packages.py architect/test_architect_models.py forge_master/test_forge_templates.py forge_master/test_forge_reviewer.py tests/test_projectile_pipeline_fixes.py tests/test_combat_package_pipeline.py tests/test_orchestrator_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/fixtures/combat_package_prompts.json tests/test_combat_package_pipeline.py tests/test_projectile_pipeline_fixes.py
git commit -m "test: add combat package regression harness"
```

### Task 7: Headless Build And Live Inject Validation

**Files:**
- No new files required if earlier tasks pass
- Verification paths:
  - `agents/gatekeeper/gatekeeper.py:148-543`
  - `agents/gatekeeper/tmod_build.sh:1-15`
  - `agents/orchestrator.py:330-465`
  - `mod/ForgeConnector/ForgeConnectorSystem.cs:175-286`
  - `mod/ForgeConnector/ForgeConnectorSystem.cs:956-1071`

**Step 1: Run isolated orchestrator smoke**

Run: `./.venv/bin/python orchestrator_smoke.py`
Expected: reaches `ready` in a temporary HOME without touching the real ModSources tree.

**Step 2: Run the targeted Python suites again before build**

Run: `./.venv/bin/pytest core/test_combat_packages.py architect/test_architect_models.py forge_master/test_forge_templates.py forge_master/test_forge_reviewer.py tests/test_projectile_pipeline_fixes.py tests/test_combat_package_pipeline.py tests/test_orchestrator_smoke.py -v`
Expected: PASS

**Step 3: Run the compiled-path flow through the normal app**

Run from `BubbleTeaTerminal/`: `go run .`
Expected: TUI reaches the usual forge flow and the compiled path still produces a build-ready item.

**Step 4: Validate headless tModLoader build feedback**

Use the Gatekeeper-backed path and confirm:

- no schema errors
- no template routing regressions
- no missing projectile sprite regressions
- no tModLoader build failures for the package weapons

**Step 5: Validate manual live reload with ForgeConnector enabled**

With tModLoader running and `ForgeConnector` enabled:

- generate at least one `storm_brand` weapon
- confirm inject/reload from staging
- confirm `ForgeConnector` writes `item_injected` or `item_pending`
- confirm the item appears in-game
- verify the generated weapon clearly exhibits seed, escalate, and cash-out behavior

**Step 6: Commit**

```bash
git add .
git commit -m "feat: ship package-first compiled weapon generation"
```

Only do this after the targeted suites and manual smoke pass.

## Execution Notes For Subagent-Driven Development

- Before implementing, invoke `superpowers:subagent-driven-development`.
- Dispatch one fresh subagent per numbered task above.
- Review each task result in the main session before moving on.
- Run the specified tests after every task, not only at the end.
- Do not parallelize tasks that share manifest contracts or routing logic; those must stay sequential.
- Safe parallelism is acceptable inside a task only for read-only exploration or independent test reads.

## Out Of Scope For This Plan

- Full `ForgeConnector` runtime package execution
- Free-form combo rules or finisher rules authored by the LLM
- More than three combat packages
- More than three presentation profiles
- Broad rework of non-weapon content types
