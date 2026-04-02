# Polished Forge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand The Forge into a multi-content generator with content-type-specific manifest generation, terminal preview and iteration, and reliable runtime injection for accessories, summons, consumables, and tools.

**Architecture:** The work splits into three main seams. The Python architect/orchestrator pipeline becomes content-type-aware and validates richer manifests. The ForgeConnector runtime grows new data fields, buff template slots, and AI/default application logic while keeping template-pool safety. The Bubble Tea TUI moves from a linear forge flow into a typed wizard plus preview loop that can reprompt art, tweak stats, and inject the accepted result.

**Tech Stack:** Python 3 with Pydantic and LangChain, Go with Bubble Tea and image/png, C# for tModLoader globals/templates, pytest, go test

---

### Task 1: Architect prompt router and manifest models

**Files:**
- Modify: `agents/architect/architect.py`
- Modify: `agents/architect/models.py`
- Modify: `agents/orchestrator.py`
- Create: `agents/architect/weapon_prompt.py`
- Create: `agents/architect/accessory_prompt.py`
- Create: `agents/architect/summon_prompt.py`
- Create: `agents/architect/consumable_prompt.py`
- Create: `agents/architect/tool_prompt.py`
- Modify: `agents/architect/prompts.py`
- Test: `agents/test_polished_architect.py`

**Step 1: Write the failing tests**

Create `agents/test_polished_architect.py` covering:
- prompt routing by `content_type`
- manifest validation for accessory, summon, consumable, and tool shapes
- BuffID and AmmoID whitelist rejection
- orchestrator forwarding `content_type` and `sub_type` from the request

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest agents/test_polished_architect.py -v`
Expected: FAIL because router/types/tests do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- typed LLM output / validated manifest models per content family
- shared tier tables plus content-specific balance tables
- `build_prompt(content_type)` dispatch
- `ArchitectAgent.generate_manifest(..., content_type, sub_type)` dispatch
- whitelist validators and clamp logging for BuffID/AmmoID domains
- orchestrator request parsing for `content_type` and `sub_type`

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest agents/test_polished_architect.py -v`
Expected: PASS

**Step 5: Run broader Python verification**

Run: `python3 -m pytest agents/test_polished_architect.py agents/test_orchestrator_smoke.py -v`
Expected: PASS, excluding known unrelated baseline failures in `agents/test_orchestrator.py`.

---

### Task 2: Runtime data model, buff templates, and connector parsing

**Files:**
- Modify: `mod/ForgeConnector/ForgeManifestStore.cs`
- Modify: `mod/ForgeConnector/ForgeConnectorSystem.cs`
- Create: `mod/ForgeConnector/Content/Buffs/ForgeTemplateBuff.cs`
- Create: `mod/ForgeConnector/ForgeBuffGlobal.cs`

**Step 1: Extend manifest-facing regression coverage**

Ensure the Python tests from Task 1 assert the connector-required fields exist for:
- `type`
- `sub_type`
- summon minion and buff fields
- consumable fields
- tool fields

**Step 2: Run build baseline**

Run: `dotnet build mod/ForgeConnector/ForgeConnector.csproj`
Expected: PASS on the worktree baseline.

**Step 3: Write minimal implementation**

Implement:
- new item, projectile, and buff data fields in `ForgeManifestStore`
- 25 generic `ForgeBuff` template slots and registration
- `ParseManifest` branching per content family
- `ParseProjectile` support for summon minions and hooks
- safe defaults for accessory, consumable, tool, and summon content

**Step 4: Run build to verify it passes**

Run: `dotnet build mod/ForgeConnector/ForgeConnector.csproj`
Expected: PASS

---

### Task 3: Item and projectile globals for content-type behavior

**Files:**
- Modify: `mod/ForgeConnector/ForgeItemGlobal.cs`
- Modify: `mod/ForgeConnector/ForgeProjectileGlobal.cs`

**Step 1: Define the behavior checklist**

Verify implementation against:
- accessories skip normal weapon use behavior
- summon staves use Summon damage and linked buff
- consumables set stack, heal, buff, and ammo semantics
- fishing rods set fishing power
- hook projectiles use hook AI style
- minion follower AI loops through idle, search, chase, and contact behavior

**Step 2: Write minimal implementation**

Implement:
- item defaults per content type
- summon buff hookup and minion defaults
- projectile AI mode dispatch for `straight`, `hook`, and `minion_follower`
- minion targeting and chase behavior using stored parameters

**Step 3: Run build to verify it passes**

Run: `dotnet build mod/ForgeConnector/ForgeConnector.csproj`
Expected: PASS

---

### Task 4: Bubble Tea wizard and preview loop

**Files:**
- Modify: `BubbleTeaTerminal/main.go`
- Modify: `BubbleTeaTerminal/main_test.go`

**Step 1: Write the failing Go tests**

Extend `BubbleTeaTerminal/main_test.go` with tests for:
- wizard flow selecting content type then context-specific sub-type
- request payloads including `content_type` and `sub_type`
- preview action handling (`reprompt`, `tweak stats`, `accept`, `discard`)
- stat tweaks mutating the staged manifest

**Step 2: Run tests to verify they fail**

Run: `go test ./...`
Expected: FAIL on the new tests before implementation.

**Step 3: Write minimal implementation**

Implement:
- new content-type-first wizard state
- context-specific subtype choices
- preview screen with action menu
- reprompt input mode and manifest reuse
- inline stat tweaking for numeric fields
- inject/discard flow from preview instead of immediate staging

**Step 4: Run tests to verify they pass**

Run: `go test ./...`
Expected: PASS

---

### Task 5: ASCII sprite rendering and animation framing

**Files:**
- Modify: `BubbleTeaTerminal/main.go`
- Modify: `BubbleTeaTerminal/main_test.go`

**Step 1: Write failing renderer and animation tests**

Add tests covering:
- PNG downscale to terminal blocks
- transparent pixel handling
- animation frame selection per content or use style
- summon, accessory, and consumable presentation differences

**Step 2: Run targeted tests to verify they fail**

Run: `go test ./... -run 'TestASCII|TestPreview|TestAnimation' -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement:
- PNG loader and downscaler
- ANSI 256 nearest-color mapping
- half-block rendering with transparency support
- cached frames for preview
- simple animation frame generation for swing, shoot, thrust, summon, accessory, and consumable states

**Step 4: Run Go verification**

Run: `go test ./...`
Expected: PASS

---

### Task 6: End-to-end verification and cleanup

**Files:**
- Review all changed files above

**Step 1: Run full verification**

Run:
- `python3 -m pytest agents/test_polished_architect.py agents/test_orchestrator_smoke.py -v`
- `go test ./...`
- `dotnet build mod/ForgeConnector/ForgeConnector.csproj`

Expected:
- targeted Python tests PASS
- Go tests PASS
- connector build PASS
- unrelated baseline failure in `agents/test_orchestrator.py` remains unchanged unless touched during implementation

**Step 2: Manual sanity check**

Run the TUI locally against the orchestrator and confirm:
- request payload includes type and subtype
- preview appears before injection
- reprompt and stat tweak rewrite the staged manifest

**Step 3: Review and summarize remaining gaps**

Document any residual risks around:
- minion AI edge cases
- hook behavior nuances
- terminal color fidelity across environments
