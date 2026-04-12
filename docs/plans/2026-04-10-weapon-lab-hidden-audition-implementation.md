# Weapon Lab Hidden Audition Implementation Plan

Archived implementation sketch for the hidden-audition weapon lab.

## Goal

Build a pipeline that generates multiple weapon theses, scores them, validates them with art and runtime evidence, and reveals only the winner.

## Planned Workstreams

1. Runtime capability matrix and telemetry events.
2. Candidate archive and ranking policy.
3. Research-informed thesis prompting.
4. Hidden thesis generation and judging.
5. Package-first finalist expansion.
6. Bounded art-direction profiles and sprite gates.
7. Hidden sprite audition.
8. Runtime behavior contracts and lab evaluation.
9. Final winner gate before the TUI reveal.

## Main Constraints

- Do not surface weak candidates.
- Do not declare a winner before art and runtime evidence exist.
- Keep implementation bounded to the current runtime and package surface.

## Why This Was Compressed

The original file was a long execution script with step-by-step test snippets. For handoff, the workstreams and constraints carry most of the value.

```python
from architect.thesis_judges import hard_reject_thesis
from core.weapon_lab_models import WeaponThesis


def test_hard_reject_thesis_rejects_no_cashout_loop():
    thesis = WeaponThesis.model_validate(
        {
            "fantasy": "plain bolt staff",
            "player_verb": "fire bolts",
            "seed": "shoot",
            "escalate": "none",
            "cashout": "none",
            "time_to_payoff": "slow",
            "reliability_aid": "none",
            "movement_or_spacing_hook": "none",
            "spectacle_ladder": ["spark"],
            "signature_sound": "generic",
        }
    )
    assert hard_reject_thesis(thesis) is not None
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest architect/test_thesis_generator.py architect/test_thesis_judges.py -v`
Expected: FAIL because the calibrated thesis pipeline does not exist.

**Step 3: Write minimal implementation**

Add a thesis generation path that can:

- request `N` theses for one prompt
- validate them through `WeaponThesis`
- hard-reject obvious losers
- score survivors through bounded judges
- compare against anchors
- record judge disagreements
- return the top `K` finalists with scores and reasons

Do not select a final winner here. This task only creates ranked finalists.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest architect/test_thesis_generator.py architect/test_thesis_judges.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add architect/thesis_generator.py architect/thesis_judges.py architect/test_thesis_generator.py architect/test_thesis_judges.py architect/architect.py
git commit -m "feat: add calibrated thesis tournament"
```

### Task 5: Expand Ranked Finalists Into Supported Runtime Families

**Files:**
- Modify: `agents/architect/architect.py`
- Modify: `agents/architect/models.py`
- Modify: `agents/architect/weapon_prompt.py`
- Create: `agents/tests/test_hidden_thesis_to_manifest.py`
- Modify: `agents/tests/test_combat_package_pipeline.py`

**Step 1: Write the failing test**

```python
def test_staff_finalist_does_not_surface_legacy_direct_projectile_by_default():
    result = build_manifest_from_ranked_finalist(
        prompt="celestial storm brand staff",
        finalist={
            "fantasy": "celestial execution staff",
            "player_verb": "brand and condemn",
            "seed": "apply mark",
            "escalate": "marks intensify to three",
            "cashout": "starfall rupture",
            "time_to_payoff": "fast",
            "reliability_aid": "slight homing",
            "movement_or_spacing_hook": "keep line of sight",
            "spectacle_ladder": ["chime", "crackle", "thunder tear"],
            "signature_sound": "glass-thunder",
        },
        content_type="Weapon",
        sub_type="Staff",
        tier="Tier2_Dungeon",
    )
    assert result["mechanics"]["combat_package"] == "storm_brand"
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_hidden_thesis_to_manifest.py tests/test_combat_package_pipeline.py -v`
Expected: FAIL because finalist expansion is not yet package-first on the supported surface.

**Step 3: Write minimal implementation**

Add finalist expansion that:

- takes a ranked finalist
- checks the runtime capability matrix
- maps it into package-first behavior on the supported staff surface
- treats legacy-only outputs as a losing outcome unless explicitly marked as homage/simple fallback
- records why a fallback was allowed when it happens

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_hidden_thesis_to_manifest.py tests/test_combat_package_pipeline.py architect/test_architect_models.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add architect/architect.py architect/models.py architect/weapon_prompt.py tests/test_hidden_thesis_to_manifest.py tests/test_combat_package_pipeline.py
git commit -m "feat: expand finalists into supported runtime manifests"
```

### Task 6: Add Deterministic Sprite Gates And High-Level Art Direction Mapping

**Files:**
- Create: `agents/pixelsmith/art_direction.py`
- Create: `agents/pixelsmith/sprite_gates.py`
- Create: `agents/pixelsmith/test_art_direction.py`
- Create: `agents/pixelsmith/test_sprite_gates.py`
- Modify: `agents/pixelsmith/models.py`

**Step 1: Write the failing test**

```python
from pixelsmith.art_direction import map_art_direction_to_fal_strategy
from pixelsmith.sprite_gates import sprite_gate_report


def test_art_direction_maps_to_bounded_generation_strategy():
    strategy = map_art_direction_to_fal_strategy(
        {
            "sprite_strategy": "bold_silhouette",
            "detail_level": "medium",
            "contrast_profile": "dramatic",
            "reference_strength": "soft",
            "variant_budget": "wide",
        }
    )
    assert strategy["variant_count"] >= 2


def test_sprite_gate_report_flags_mushy_or_low_contrast_candidates(tmp_path):
    report = sprite_gate_report(tmp_path / "fake.png")
    assert hasattr(report, "passed")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest pixelsmith/test_art_direction.py pixelsmith/test_sprite_gates.py -v`
Expected: FAIL because the art-direction mapper and deterministic gates do not exist.

**Step 3: Write minimal implementation**

Add:

- bounded art-direction profiles
- deterministic mapping to internal FAL strategy buckets
- deterministic sprite-readability gates for:
  - occupancy
  - silhouette readability
  - contrast/value floor
  - center/background cleanup
  - projectile-size readability

Keep this task focused on strategy and gates. Do not wire the audition loop yet.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest pixelsmith/test_art_direction.py pixelsmith/test_sprite_gates.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add pixelsmith/art_direction.py pixelsmith/sprite_gates.py pixelsmith/test_art_direction.py pixelsmith/test_sprite_gates.py pixelsmith/models.py
git commit -m "feat: add art-direction mapping and sprite gates"
```

### Task 7: Add Hidden Sprite Audition For Finalists

**Files:**
- Modify: `agents/pixelsmith/pixelsmith.py`
- Modify: `agents/pixelsmith/variant_selector.py`
- Create: `agents/tests/test_pixelsmith_hidden_audition.py`
- Modify: `agents/orchestrator.py`

**Step 1: Write the failing test**

```python
def test_pixelsmith_hidden_audition_rejects_failed_sprite_gates():
    result = run_pixelsmith_hidden_audition_for_test("storm_brand")
    assert result["winner"] is not None
    assert all(c["passed_gates"] for c in result["finalists"])
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_pixelsmith_hidden_audition.py -v`
Expected: FAIL because Pixelsmith does not yet run a hidden audition for finalists.

**Step 3: Write minimal implementation**

Add:

- multi-candidate generation for finalists even in text-to-image mode
- gate each candidate with deterministic sprite gates first
- judge the surviving candidates for motif strength and family coherence
- record losers and reasons in the candidate archive

Still do not select the final weapon winner in this task. Only produce art-scored finalists.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_pixelsmith_hidden_audition.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add pixelsmith/pixelsmith.py pixelsmith/variant_selector.py tests/test_pixelsmith_hidden_audition.py orchestrator.py
git commit -m "feat: add hidden sprite audition for finalists"
```

### Task 8: Add Cross-Consistency Review Between Prompt, Thesis, Manifest, And Art

**Files:**
- Create: `agents/core/cross_consistency.py`
- Create: `agents/core/test_cross_consistency.py`
- Modify: `agents/orchestrator.py`
- Modify: `agents/forge_master/reviewer.py`
- Modify: `agents/forge_master/test_forge_reviewer.py`

**Step 1: Write the failing test**

```python
def test_cross_consistency_rejects_art_that_does_not_match_mechanic_fantasy():
    verdict = evaluate_cross_consistency(
        prompt="celestial storm condemnation staff",
        thesis={"fantasy": "condemn marked targets with starfall"},
        manifest={"mechanics": {"combat_package": "storm_brand"}},
        item_visual_summary="plain wooden wand with no celestial motif",
        projectile_visual_summary="generic blue orb",
    )
    assert verdict.passed is False
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest core/test_cross_consistency.py forge_master/test_forge_reviewer.py -v`
Expected: FAIL because no cross-consistency gate exists.

**Step 3: Write minimal implementation**

Add a gate that compares:

- prompt
- thesis
- final manifest
- art outputs and art summaries

Record a score and fail reason. Wire it into the hidden pipeline after art audition, before any winner selection.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest core/test_cross_consistency.py forge_master/test_forge_reviewer.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add core/cross_consistency.py core/test_cross_consistency.py orchestrator.py forge_master/reviewer.py forge_master/test_forge_reviewer.py
git commit -m "feat: add thesis-manifest-art consistency gate"
```

### Task 9: Add Runtime Telemetry Plumbing In ForgeConnector

**Files:**
- Create: `mod/ForgeConnector/ForgeLabTelemetry.cs`
- Modify: `mod/ForgeConnector/ForgeConnectorSystem.cs`
- Modify: `mod/ForgeConnector/ForgeItemGlobal.cs`
- Modify: `mod/ForgeConnector/ForgeProjectileGlobal.cs`
- Create: `agents/tests/test_runtime_lab_contract.py`

**Step 1: Write the failing test**

```python
def test_runtime_lab_contract_result_accepts_seed_escalate_cashout_events():
    result = load_lab_result(
        {
            "candidate_id": "cand-1",
            "events": [
                {"event_type": "seed_triggered", "timestamp_ms": 100},
                {"event_type": "escalate_triggered", "timestamp_ms": 450},
                {"event_type": "cashout_triggered", "timestamp_ms": 900},
            ],
        }
    )
    assert result.candidate_id == "cand-1"
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_runtime_lab_contract.py -v`
Expected: FAIL because runtime telemetry plumbing and result parsing do not exist.

**Step 3: Write minimal implementation**

Add runtime telemetry plumbing that can emit at least:

- `seed_triggered`
- `escalate_triggered`
- `cashout_triggered`
- optional `fx_marker`
- optional `audio_marker`

The first version can be package-family-limited. The key is to make behavior evidence available to the hidden lab.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_runtime_lab_contract.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add mod/ForgeConnector/ForgeLabTelemetry.cs mod/ForgeConnector/ForgeConnectorSystem.cs mod/ForgeConnector/ForgeItemGlobal.cs mod/ForgeConnector/ForgeProjectileGlobal.cs tests/test_runtime_lab_contract.py
git commit -m "feat: add runtime telemetry plumbing for weapon lab"
```

### Task 10: Add Behavior Contracts And Hidden Lab Eval Handshake

**Files:**
- Create: `agents/core/runtime_contracts.py`
- Create: `agents/core/test_runtime_contracts.py`
- Modify: `agents/orchestrator.py`
- Modify: `mod/ForgeConnector/ForgeConnectorSystem.cs`

**Step 1: Write the failing test**

```python
from core.runtime_contracts import BehaviorContract


def test_behavior_contract_tracks_seed_escalate_cashout_expectations():
    contract = BehaviorContract.model_validate(
        {
            "seed_event": "mark_applied",
            "escalate_event": "mark_incremented",
            "cashout_event": "starfall_triggered",
            "max_hits_to_cashout": 3,
            "max_time_to_cashout_ms": 2500,
        }
    )
    assert contract.max_hits_to_cashout == 3
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest core/test_runtime_contracts.py tests/test_runtime_lab_contract.py -v`
Expected: FAIL because the behavior contract and hidden lab handshake do not exist.

**Step 3: Write minimal implementation**

Add:

- `BehaviorContract`
- hidden lab request/result files
- orchestrator wait loop for runtime evidence
- result evaluation against the contract

This task should still avoid choosing a final winner. It should only determine whether a finalist passes the runtime gate.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest core/test_runtime_contracts.py tests/test_runtime_lab_contract.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add core/runtime_contracts.py core/test_runtime_contracts.py orchestrator.py mod/ForgeConnector/ForgeConnectorSystem.cs
git commit -m "feat: add hidden lab behavior contracts"
```

### Task 11: Add Pre-TUI Winner Selection Only After All Gates

**Files:**
- Modify: `agents/core/weapon_lab_archive.py`
- Modify: `agents/orchestrator.py`
- Create: `agents/tests/test_hidden_audition_pipeline.py`
- Modify: `agents/tests/test_orchestrator_smoke.py`

**Step 1: Write the failing test**

```python
def test_hidden_audition_pipeline_only_reveals_winner_after_runtime_gate():
    result = run_hidden_audition_for_test(prompt="storm brand staff")
    assert result["status"] == "ready"
    assert result["winner"]["passed_runtime_gate"] is True
    assert "losers" not in result["revealed_payload"]
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_hidden_audition_pipeline.py tests/test_orchestrator_smoke.py -v`
Expected: FAIL because winner selection is not yet deferred until after all gates.

**Step 3: Write minimal implementation**

Update the orchestrator so that:

- no candidate is treated as final before art and runtime evidence exist
- exactly one winner is selected after all gates
- only the winner reaches `_set_ready(...)`
- loser data remains internal/archive-only

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_hidden_audition_pipeline.py tests/test_orchestrator_smoke.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add core/weapon_lab_archive.py orchestrator.py tests/test_hidden_audition_pipeline.py tests/test_orchestrator_smoke.py
git commit -m "feat: reveal winners only after full hidden audition"
```

### Task 12: Add Wild Recovery Mode, Search Budgets, And Dedupe Rules

**Files:**
- Create: `agents/core/recovery_mode.py`
- Create: `agents/core/test_recovery_mode.py`
- Modify: `agents/architect/thesis_generator.py`
- Modify: `agents/orchestrator.py`
- Create: `agents/tests/test_recovery_hidden_batches.py`

**Step 1: Write the failing test**

```python
def test_recovery_mode_widens_search_without_lowering_threshold():
    mode = next_recovery_mode(failed_batches=3)
    assert mode.search_profile == "wild"
    assert mode.lower_quality_bar is False
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest core/test_recovery_mode.py tests/test_recovery_hidden_batches.py -v`
Expected: FAIL because recovery mode does not exist.

**Step 3: Write minimal implementation**

Add reroll logic that:

- discards weak hidden batches entirely
- uses explicit budgets
- fingerprints and dedupes near-identical candidates
- increases novelty search after repeated failures
- does not lower the quality threshold
- mutates or crossbreeds near-miss theses in recovery mode

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest core/test_recovery_mode.py tests/test_recovery_hidden_batches.py -v`
Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add core/recovery_mode.py core/test_recovery_mode.py architect/thesis_generator.py orchestrator.py tests/test_recovery_hidden_batches.py
git commit -m "feat: add wild recovery mode with budgets and dedupe"
```

### Task 13: Add Offline Eval Harness And Stress Suites

**Files:**
- Create: `agents/tests/stress/stress_test_weapon_lab_theses.py`
- Create: `agents/tests/stress/stress_test_pixelsmith_audition.py`
- Create: `agents/tests/stress/stress_test_ranking_stability.py`
- Create: `agents/tests/stress/stress_test_recovery_mode.py`
- Modify: `agents/tests/stress/stress_test_ambiguous_prompts.py`
- Modify: `agents/tests/test_orchestrator_smoke.py`

**Step 1: Write the failing test**

```python
def test_hidden_lab_rejects_direct_projectile_staff_for_storm_brand_prompt():
    result = run_hidden_lab_for_prompt("celestial storm brand staff")
    assert result["winner"]["manifest"]["mechanics"].get("combat_package") == "storm_brand"
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/stress/stress_test_weapon_lab_theses.py tests/stress/stress_test_pixelsmith_audition.py tests/stress/stress_test_ranking_stability.py tests/stress/stress_test_recovery_mode.py -v`
Expected: FAIL until the hidden lab pipeline and eval harness are fully wired.

**Step 3: Write minimal implementation**

Add stress coverage for:

- novelty-sensitive prompts
- ambiguous prompts
- ranking stability
- sprite-audition quality selection
- recovery-mode behavior
- staff package-surface enforcement

Where practical, use the candidate archive as the offline eval substrate.

**Step 4: Run test to verify it passes**

Run the targeted stress slice:

`./.venv/bin/pytest tests/stress/stress_test_weapon_lab_theses.py tests/stress/stress_test_pixelsmith_audition.py tests/stress/stress_test_ranking_stability.py tests/stress/stress_test_recovery_mode.py tests/stress/stress_test_ambiguous_prompts.py -v`

Expected: PASS

Then run the broad suite:

`./.venv/bin/pytest core/test_runtime_capabilities.py core/test_telemetry_events.py core/test_weapon_lab_models.py core/test_weapon_lab_archive.py core/test_weapon_lab_ranking.py core/test_cross_consistency.py core/test_runtime_contracts.py architect/test_weapon_thesis_prompt.py architect/test_thesis_generator.py architect/test_thesis_judges.py architect/test_architect_models.py pixelsmith/test_art_direction.py pixelsmith/test_sprite_gates.py forge_master/test_forge_templates.py forge_master/test_forge_reviewer.py forge_master/test_compilation_harness.py gatekeeper/test_gatekeeper_paths.py tests/test_hidden_thesis_to_manifest.py tests/test_pixelsmith_hidden_audition.py tests/test_runtime_lab_contract.py tests/test_hidden_audition_pipeline.py tests/test_recovery_hidden_batches.py tests/test_orchestrator_smoke.py -v`

Expected: PASS

**Step 5: Commit checkpoint**

```bash
git add tests/stress/stress_test_weapon_lab_theses.py tests/stress/stress_test_pixelsmith_audition.py tests/stress/stress_test_ranking_stability.py tests/stress/stress_test_recovery_mode.py tests/stress/stress_test_ambiguous_prompts.py tests/test_orchestrator_smoke.py
git commit -m "test: add hidden weapon lab eval and stress suites"
```

### Task 14: Live Validation And Final Expert Stress Pass

**Files:**
- No new files required if prior tasks pass
- Verification paths:
  - `agents/orchestrator.py`
  - `agents/orchestrator_smoke.py`
  - `agents/gatekeeper/gatekeeper.py`
  - `mod/ForgeConnector/ForgeConnectorSystem.cs`
  - `BubbleTeaTerminal/screen_forge.go`
  - `BubbleTeaTerminal/screen_staging.go`

**Step 1: Run orchestrator smoke**

Run: `./.venv/bin/python orchestrator_smoke.py`
Expected: PASS

**Step 2: Run headless Gatekeeper build for representative finalists**

Run isolated build validation for representative hidden-lab finalists.
Expected: success for selected finalists.

**Step 3: Run live instant inject validation in tModLoader**

With tModLoader + ForgeConnector running:

- submit a prompt through the hidden-audition path
- verify only the final winner appears in the TUI
- verify `forge_connector_status.json` reports `item_injected` or `item_pending`
- verify the runtime contract result file exists and the winner passed it

**Step 4: Dispatch final stress-test agents**

Use parallel testing agents for:

- thesis ranking edge cases
- sprite audition edge cases
- runtime contract / telemetry edge cases
- recovery-mode search drift

Require findings-first reports and fix any real issues before claiming completion.

**Step 5: Commit checkpoint**

```bash
git add .
git commit -m "feat: add hidden weapon lab audition pipeline"
```

Only do this if the user explicitly requests a commit at execution time.

## Execution Notes For Subagent-Driven Development

- Before implementation, invoke `superpowers:subagent-driven-development`.
- Use one fresh implementer subagent per numbered task.
- After each task, run:
  - spec review
  - code-quality review
  - the exact listed tests
- Do not start the next task while either review has open issues.
- After Task 13 and Task 14, dispatch parallel testing agents for a final stress pass.
- Because this plan is heavy on prompt and system design, give implementer subagents the relevant design doc section and the exact task text rather than making them rediscover intent.

## Practical Prompt-Writing Notes For Execution

When implementing the thesis prompt and art-direction prompts, keep the research findings visible and explicit:

- short payoff loops
- visible escalation
- signature sound ladders
- changed player behavior
- reliability after setup
- spectacle reserved for finisher beats

Do not let the prompt collapse into long lists of shot styles or generic fantasy adjectives.

## Out Of Scope For This Plan

- unrestricted raw FAL parameter control by the LLM
- fully free-form LLM-authored runtime combat code
- production-grade balance guarantees for all generated weapons
