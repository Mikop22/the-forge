# Plan: Three Product Fixes Surfaced by QA

**Context.** QA pass on 2026-04-26 surfaced three product issues that affect the demo or near-demo behavior. This plan groups them by independent root causes, scopes the fix per area, and bakes a Codex adversarial review into each phase.

## The three fixes

### Fix 1 — `generation_status.json` final-state race (DEMO-BLOCKING if reproduces in production)

**Symptom.** After a successful pipeline, the on-disk `generation_status.json` at ModSources root remains `{"status": "building", "stage_label": "Compilation successful. Finalizing...", "stage_pct": 95}` instead of `"status": "ready"`. The TUI watches this file (`BubbleTeaTerminal/internal/ipc/ipc.go:121,137-140`); a stuck `building` keeps the forge screen polling forever (`screen_forge.go:80-102`).

**Suspected root cause.** Two writers race on the same path:

- Gatekeeper writes `finishing` (mapped to `building` 95%) to `<mod_root>.parent / generation_status.json` via `_write_status` at `agents/gatekeeper/gatekeeper.py:376-384`. Path resolved dynamically per-call.
- Orchestrator writes `ready` (100%) via `_set_ready` → `_write_status` to `STATUS_FILE = _MOD_SOURCES / "generation_status.json"` at `agents/orchestrator.py:101,77`. Path captured **at module import time** as a module-level constant.

If `FORGE_MOD_SOURCES_DIR` (or the `core.paths.mod_sources_root()` resolution) returns different values between import time and runtime — e.g. because env was set after import, or the resolution involves a config file that changed — then orchestrator writes `ready` to the OLD path while gatekeeper writes `finishing` to the NEW path. The TUI watches the runtime path (where gatekeeper's `finishing` lives).

This explains why our QA Tier C harness saw `building 95%`: QA sets `FORGE_MOD_SOURCES_DIR` after orchestrator import. It also explains why the issue hadn't surfaced loudly before — under normal launch (TUI auto-starts orchestrator, env from `agents/.env`), the path is stable. **Production demo recording may be safe.** But under any path reconfiguration (worktrees, `FORGE_MOD_SOURCES_DIR` env override, the new pre-flight surfacing channel from Phase 3b) the divergence resurfaces.

**Phase 1.1 — Reproduce.**
- Launch orchestrator under controlled `FORGE_MOD_SOURCES_DIR` path matching the value of `STATUS_FILE` at import. Run a forge. Confirm root file ends at `ready`. (Should pass.)
- Launch under a divergent `FORGE_MOD_SOURCES_DIR` set after import (mimicking QA harness). Confirm root file ends at `building 95%`. (Should fail.)

**Phase 1.2 — Fix (preferred: make path resolution dynamic).**
- Replace the module-level `STATUS_FILE` constant in `agents/orchestrator.py:77` with a function `_status_file_path() -> Path` that calls `core.paths.mod_sources_root()` at each call site.
- Update `_write_status` (`orchestrator.py:101`) to call the function. All other module-level path constants that mirror this pattern (`WORKSHOP_STATUS_FILE`, `SESSION_SHELL_STATUS_FILE`) should get the same treatment for consistency, even if not currently bug-triggering.
- Add a unit test `tests/test_orchestrator_path_resolution.py` that monkeypatches `mod_sources_root` mid-test and asserts subsequent writes follow the new path.
- Also harden: `_set_ready` should perform a final `_write_status` even if `_sync_ready_workshop_session` raises, so the root file lands at `ready` regardless of downstream side-effect failures.

**Phase 1.3 — Verify.**
- Re-run QA Tier C harness; confirm `tier_c_NN_status.json` ends at `status: ready`.
- `pytest agents/` green.

### Fix 2 — `mechanics.shoot_projectile: null` for ranged sub_types (PRODUCT-BLOCKING if firing on camera)

**Symptom.** Codex's Tier B adversarial review found 4/10 architect manifests had `mechanics.shoot_projectile: null` despite ranged sub_types (Pistol #6, Shotgun #7, Bow #9, Staff #11). In Terraria, weapons that don't set `Item.shoot` simply do nothing when right-clicked / used. A generated gun would be a silent dud on camera.

**Suspected root cause(s).** Two layers, both need fixing:

- **Layer A — Architect prompts.** `agents/architect/weapon_prompt.py` and the structured-output schema for `Mechanics` allow `shoot_projectile: null`. The LLM has no strong instruction to populate it for ranged sub_types. For melee sub_types (Sword, Broadsword, Spear) leaving it null is correct.
- **Layer B — Forge Master snippets.** Codex flagged that `agents/forge_master/templates/snippets.py:19-35` and `:1687-1694` subtype maps lack entries for `Pistol`, `Shotgun`, `Rifle`. Even when the architect populates `shoot_projectile`, the C# template generator may not emit working `Item.shoot = ProjectileID.X` for these. Bow/Gun/Staff have working snippet examples (`snippets.py:123-127, 984-988`).

**Phase 2.1 — Verify the gap.**
- Read `agents/forge_master/templates/snippets.py` end-to-end. Confirm whether Pistol/Shotgun/Rifle are missing from subtype maps.
- Run a Tier C generation for `repeating crystal pistol` with the generated C# saved. Inspect the C# file: does it set `Item.shoot`? If yes, what `ProjectileID` value? If no, the gap is real.
- Check `agents/architect/models.py` `Mechanics` model — is `shoot_projectile` `Optional[str]` or required? If optional, the schema allows null without tripping validation.

**Phase 2.2 — Fix architect side.**
- In `agents/architect/weapon_prompt.py`, add a sub_type-conditional instruction block: when sub_type is in `{Pistol, Shotgun, Rifle, Bow, Repeater, Gun, Staff, Wand, Spellbook, Tome}`, the LLM MUST populate `mechanics.shoot_projectile` with a valid Terraria `ProjectileID.*` constant or a custom-projectile sentinel (`<CustomProjectile>`).
- Add a model validator in `agents/architect/models.py` `WeaponManifest` (or wherever the manifest is built) that raises if `mechanics.shoot_projectile is None` when sub_type ∈ ranged set. Fail-fast at architect output time so the bug surfaces in QA, not in-game.

**Phase 2.3 — Fix forge_master side.**
- Extend subtype maps in `agents/forge_master/templates/snippets.py` to include Pistol, Shotgun, Rifle. Pattern-match what Bow and Gun have at `snippets.py:123-127`. Each should template:
  - `Item.shoot = <ProjectileID>` from `mechanics.shoot_projectile`
  - `Item.useAmmo = AmmoID.Bullet` (Pistol/Shotgun/Rifle) or `AmmoID.Arrow` (Bow already covered)
  - Multi-shot pattern for Shotgun (3-pellet spread per `Item.NewProjectile` calls)
- Mirror the Forge Master tests in `agents/forge_master/test_*.py` to cover the new sub_types.

**Phase 2.4 — Verify.**
- Re-run QA Tier B with corpus prompts that exercise Pistol/Shotgun/Rifle/Staff. Assert manifests have non-null `shoot_projectile`.
- Re-run QA Tier C for the same prompts; inspect generated C# files; confirm `Item.shoot` is set.

### Fix 3 — Pickaxe routes to `content_type=Weapon` instead of `Tool`

**Symptom.** Prompt `obsidian pickaxe with magma cracks` produces a manifest with `content_type: "Weapon"`, `sub_type: "Pickaxe"`, `tool_stats: null`. The orchestrator's `_request_sub_type` correctly identifies Pickaxe, but the request still arrives with `content_type="Weapon"`. As a result, the pickaxe has weapon damage/use_time but no `pickaxePower` and can't actually mine in-game.

**Suspected root cause.** The orchestrator's content_type comes from the request payload, which the TUI defaults to `"Weapon"`. There is no logic that overrides content_type when the inferred sub_type clearly belongs to Tool. `agents/architect/prompts.py:13-19` already has the right routing: `DEFAULT_SUB_TYPES["Tool"] = "Pickaxe"` and a `Tool` prompt template at `agents/architect/tool_prompt.py:37` that takes `Pickaxe` as a default.

**Phase 3.1 — Add content_type override.**
- In `agents/orchestrator.py`, after `_request_sub_type` returns, add `_request_content_type_inferred(request)` that:
  - If the request already specifies a non-Weapon `content_type`, use it.
  - Else, if the inferred sub_type is in a `_TOOL_SUB_TYPES = {"Pickaxe", "Axe", "Hamaxe", "Hammer"}` set, override content_type to `"Tool"`.
  - Else, return the request's content_type (default `"Weapon"`).
- Both `run_pipeline` (line ~1250) and `run_instant_pipeline` (line ~1374) read content_type at the same site; route both through the new helper.

**Phase 3.2 — Verify Tool path produces a real pickaxe manifest.**
- Run architect with `content_type="Tool"`, `sub_type="Pickaxe"`, prompt `obsidian pickaxe with magma cracks`. Inspect manifest: should have `content_type="Tool"`, populated `tool_stats` (pickaxePower, axeDamage if hamaxe, etc.), and weapon-like damage fields can stay populated (pickaxes do also damage enemies on hit).
- Add a test case in `agents/qa/corpus.py` for this scenario, or extend Tier B to assert `manifest["content_type"] == "Tool"` for Pickaxe-inferred prompts.

**Phase 3.3 — Verify forge_master and gatekeeper accept Tool content_type.**
- Read `agents/forge_master/templates/snippets.py` Tool subtype map. Confirm Pickaxe/Axe/Hamaxe templates exist. If missing, add them. (Codex's earlier review didn't flag this — but worth verifying as a precondition.)
- Run QA Tier C on `obsidian pickaxe with magma cracks`. Inspect generated C#: should set `Item.pick`, not just `Item.damage`.

## Sequencing and order

The three fixes are independent. Recommended order by demo-impact:

1. **Fix 1 first** — confirmed demo-blocker if path divergence happens; small/safe change.
2. **Fix 2 second** — cross-cutting (architect + forge_master + tests), highest LOC. Defer if the demo cuts at the inventory-injection moment.
3. **Fix 3 last** — narrowest scope; only matters if pickaxe demos are in scope or if the user wants Pickaxe in the QA corpus to round out Tool content_type coverage.

Each phase is one or two commits on `main`, with a Codex adversarial review of the diff before commit. If a fix turns out to be larger than estimated, stop and escalate; do not muscle through.

## Critical files

- **Fix 1**: `agents/orchestrator.py:77,101,371-400`, `agents/gatekeeper/gatekeeper.py:175-183,342-351,376-384`, new `agents/tests/test_orchestrator_path_resolution.py`.
- **Fix 2**: `agents/architect/weapon_prompt.py`, `agents/architect/models.py` (Mechanics validator), `agents/forge_master/templates/snippets.py:19-35,123-127,984-988,1687-1694`, `agents/forge_master/test_*.py`.
- **Fix 3**: `agents/orchestrator.py` (new `_request_content_type_inferred` helper near line 773), `agents/architect/prompts.py:13-50`, `agents/architect/tool_prompt.py:37`.

## Verification per fix

- **Fix 1**: `pytest agents/` green, new path-resolution test passes, QA Tier C harness re-run shows `status: ready` final state.
- **Fix 2**: ranged-sub_type manifests have non-null `shoot_projectile`, generated C# has `Item.shoot = ProjectileID.X`, new architect/forge_master tests green.
- **Fix 3**: pickaxe prompt produces `content_type: "Tool"` with populated `tool_stats`; generated C# uses `Item.pick`.

## Out of scope

- Sprite-gate calibration for thin shapes (bow `occupancy` failure) — a separate sprite-gen workstream.
- Architect stat-block copy-paste between same-tier+same-sub_type items — product hygiene, deferable.
- Item-name encoding the sub_type word — naming heuristic, deferable.
- Expanding QA corpus to non-Weapon content types — already noted in the QA report.
