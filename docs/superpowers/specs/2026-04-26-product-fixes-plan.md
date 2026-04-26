# Plan: Three Product Fixes Surfaced by QA

**Context.** QA pass on 2026-04-26 surfaced three product issues that affect the demo or near-demo behavior. This plan groups them by independent root causes, scopes the fix per area, and bakes a Codex adversarial review into each phase.

> **Codex adversarial review v1 (folded in below).** Codex pushed back on all three fixes. Headline corrections:
> - Fix 1: original "import-time vs dynamic" diagnosis is **wrong** — `mod_sources_root()` re-resolves per call, but Gatekeeper also caches `self._mod_root` at `__init__` (`agents/gatekeeper/gatekeeper.py:124-132`), and write-ordering under happy path is actually correct. The real cause is unknown; do not implement before reproducing in production.
> - Fix 2: missed the combat-package lowering layer at `agents/architect/models.py:366-400`. Combat-package weapons set `Item.shoot` directly in C# templates so they "work" despite null `shoot_projectile`. The real gap is non-package ranged sub_types: Pistol, Shotgun, Rifle, Repeater, Wand, Tome, Spellbook, Launcher, Cannon — all missing from snippet subtype maps. Original plan only listed Pistol/Shotgun/Rifle.
> - Fix 3: not end-to-end. Forge Master has no Tool/Pickaxe codegen mappings, so routing `content_type="Tool"` produces a DIFFERENT failure (no template). Must scope Tool codegen first. Also: the TUI lets users explicitly select `content_type=Weapon`; an unconditional override is a silent intent-breaker. Need request-provenance threading (explicit vs defaulted) before any override is safe.

## The three fixes

### Fix 1 — `generation_status.json` final-state race (DEMO-BLOCKING if reproduces in production)

**Symptom.** After a successful pipeline, the on-disk `generation_status.json` at ModSources root remains `{"status": "building", "stage_label": "Compilation successful. Finalizing...", "stage_pct": 95}` instead of `"status": "ready"`. The TUI watches this file (`BubbleTeaTerminal/internal/ipc/ipc.go:121,137-140`); a stuck `building` keeps the forge screen polling forever (`screen_forge.go:80-102`).

**Root cause: UNKNOWN.** Codex's review (v1, see header) showed the original "path divergence between import-time orchestrator constant and dynamic gatekeeper path" theory is wrong. Both sides cache: `STATUS_FILE` at import (`agents/orchestrator.py:75-77`), `self._mod_root` at `Integrator.__init__` (`agents/gatekeeper/gatekeeper.py:124-132`). `mod_sources_root()` re-resolves but isn't the locus. Write ordering is correct on the happy path; atomic-write is unique-tmp + `os.replace` (`agents/core/atomic_io.py:38-50`).

**Therefore Phase 1 is mostly investigation, not implementation.** Do NOT fix anything until the bug is reproduced under production-realistic launch conditions.

The QA Tier C "building 95%" snapshot may itself be a harness artifact (QA sets `FORGE_MOD_SOURCES_DIR` after `import orchestrator`, which is a setup we don't see in production). Possible real causes still open:

- Two `Integrator` instances built at different ModSources roots in the same process.
- `_sync_ready_workshop_session` raising mid-`_set_ready`, preventing the ready write from completing (the function in `_set_ready` is called AFTER the status write — verify call order at `orchestrator.py:382-400`).
- A subsequent write from a heartbeat / status writer thread that we haven't found.
- Genuinely no production race; QA artifact only.

**Phase 1.1 — Reproduce (production-realistic).**
- Launch the TUI normally (`cd BubbleTeaTerminal && go run .`) which auto-starts orchestrator with `agents/.env`, against a real ModSources path.
- Run a known-good forge (e.g. Storm Brand). After `Pipeline complete` log line, immediately `cat <ModSources>/generation_status.json`. Record the `status` and `stage_pct`.
- Repeat 3 times. If all 3 end at `ready`, the QA-only-artifact hypothesis is confirmed; close Fix 1 as "QA-harness-only" with a small note in `qa/run_qa.py` that documents the limitation. **No production code change needed.**
- If any of the 3 runs ends stuck at `building`, capture the orchestrator log + the offending file's mtimes. Then proceed to Phase 1.2 with a real diagnosis from the captured evidence.

**Phase 1.2 — Diagnose using captured evidence.**
Only enter this phase if Phase 1.1 reproduces a stuck `building` state in production. Trace the writes via:
- File mtime sequence at the stuck moment.
- Orchestrator log with `Status →` lines (already present at line 110).
- Gatekeeper log with `_write_status` calls.
- Whether `_sync_ready_workshop_session` raised an exception that ate the `_set_ready` finalization.

The fix shape (dynamic path resolution, ordering harden, exception-shielded `_set_ready`) depends on what the evidence shows. Do not pre-commit to a fix shape.

**Phase 1.3 — Verify.**
- If a fix lands: re-run the production reproduction from Phase 1.1; all 3 runs end at `ready`. Plus `pytest agents/` green plus any new regression test that targets the actual root cause.
- If no fix lands: leave a short note in the QA report explaining the QA-only origin of the symptom.

### Fix 2 — `mechanics.shoot_projectile: null` for ranged sub_types (PRODUCT-BLOCKING if firing on camera)

**Symptom.** Codex's Tier B adversarial review found 4/10 architect manifests had `mechanics.shoot_projectile: null` despite ranged sub_types (Pistol #6, Shotgun #7, Bow #9, Staff #11). In Terraria, weapons that don't set `Item.shoot` simply do nothing when right-clicked / used. A generated gun would be a silent dud on camera.

**Suspected root cause(s).** Three layers, two need fixing.

- **Layer A — Architect prompts and schema.** `agents/architect/weapon_prompt.py` and the structured-output Mechanics schema allow `shoot_projectile: null` and the LLM has no strong instruction to populate it for ranged sub_types. For melee sub_types (Sword, Broadsword, Spear) leaving it null is correct.
- **Layer B — Combat-package lowering (do NOT change).** Per Codex review v1: when `mechanics.combat_package` is set, `_lower_combat_package_fields` (`agents/architect/models.py:366-400`) overwrites `shoot_projectile` from `resolved_combat.legacy_projection`. All current packages project `shoot_projectile=None` (`agents/core/combat_packages.py:48-78`). This null is **not fatal** because package C# templates set `Item.shoot` directly (e.g. `frost_shatter` at `agents/forge_master/templates/snippets.py:1678-1679`). Combat-package weapons work despite the null. **This layer is fine — leave it alone.**
- **Layer C — Forge Master snippets for non-package ranged sub_types.** This is the real gap. Snippet subtype maps cover Gun/Bow/Staff (`agents/forge_master/templates/snippets.py:123-127, 984-988`) but are missing the full set: **Pistol, Shotgun, Rifle, Repeater, Wand, Tome, Spellbook, Launcher, Cannon** are absent from `snippets.py:19-35, 1687-1694`. Any of these without a combat package will produce C# that doesn't set `Item.shoot`.

**Phase 2.1 — Verify the gap and the package-vs-non-package split.**
- Read `agents/forge_master/templates/snippets.py` end-to-end. Confirm the missing sub_types vs. those with snippet support.
- Read `agents/core/combat_packages.py` and `_lower_combat_package_fields` at `agents/architect/models.py:366-400`. Confirm package weapons are unaffected by the null-`shoot_projectile` symptom.
- Run a Tier C generation for `repeating crystal pistol` and `arcane spellbook of thunder` (both should hit non-package ranged paths). Save the generated C#. Inspect: do they set `Item.shoot`?
- Check `agents/architect/models.py` `Mechanics` model: confirm `shoot_projectile` is `Optional[str]`.

**Phase 2.2 — Fix architect side (only for non-package paths).**
- In `agents/architect/weapon_prompt.py`, add a sub_type-conditional instruction block: when sub_type is in `RANGED_SUBTYPES = {Pistol, Shotgun, Rifle, Bow, Repeater, Gun, Staff, Wand, Spellbook, Tome, Launcher, Cannon}` AND no combat_package is selected, the LLM MUST populate `mechanics.shoot_projectile`.
- Add a model validator in `agents/architect/models.py` (after combat-package lowering at line ~400) that raises if `mechanics.shoot_projectile is None` AND sub_type ∈ RANGED_SUBTYPES AND no combat_package. The validator must run AFTER the package lowering so package weapons (which legitimately project null) are not flagged.

**Phase 2.3 — Fix forge_master side (full coverage).**
- Extend subtype maps in `agents/forge_master/templates/snippets.py` to include the full missing set: **Pistol, Shotgun, Rifle, Repeater, Wand, Tome, Spellbook, Launcher, Cannon**. Pattern-match what Bow/Gun/Staff have. Each should template:
  - `Item.shoot = <ProjectileID>` from `mechanics.shoot_projectile`
  - Ammo selection: `AmmoID.Bullet` (Pistol/Shotgun/Rifle/Repeater); none for magic (Wand/Tome/Spellbook/Staff already-covered) which use `Item.mana`; `AmmoID.Rocket` (Launcher); custom for Cannon.
  - Multi-shot patterns where appropriate: Shotgun (3-pellet spread), Repeater (rapid fire).
- Mirror the Forge Master tests to cover all newly-mapped sub_types.

**Phase 2.4 — Verify.**
- Re-run QA Tier B for the full ranged-sub_type set; assert manifests have non-null `shoot_projectile` for non-package items.
- Re-run QA Tier C for at least one prompt per newly-mapped sub_type; inspect generated C#; confirm `Item.shoot` is set and ammo/mana wiring is correct.

### Fix 3 — Pickaxe routes to `content_type=Weapon` instead of `Tool`

**Symptom.** Prompt `obsidian pickaxe with magma cracks` produces a manifest with `content_type: "Weapon"`, `sub_type: "Pickaxe"`, `tool_stats: null`. The orchestrator's `_request_sub_type` correctly identifies Pickaxe, but the request still arrives with `content_type="Weapon"`. As a result, the pickaxe has weapon damage/use_time but no `pickaxePower` and can't actually mine in-game.

**Suspected root cause.** Two layers:

- **Layer A — Routing.** Orchestrator's content_type comes from the request payload. The TUI lets users explicitly select content_type (`BubbleTeaTerminal/model.go:92-98`, written into `user_request.json` at `BubbleTeaTerminal/screen_forge.go:173-191`, IPC at `BubbleTeaTerminal/internal/ipc/ipc.go:314-329`). The current Weapon subtype list excludes Pickaxe/Axe/Hammer/Hamaxe (`BubbleTeaTerminal/model.go:107-115`), but the field is still reachable via API/JSON request and via ambiguous user input.
- **Layer B — Tool codegen (NEW SCOPE per codex review).** Codex flagged that `agents/forge_master/templates/snippets.py:19-35,1687-1694` has no Tool/Pickaxe codegen mappings. **Routing to `content_type="Tool"` without adding Forge Master Tool templates produces a different failure (no template, build error), not a working pickaxe.** The plan must include Tool codegen support before any routing override ships.

**Phase 3.0 — Decide whether to ship.**
Pickaxe is explicitly out of the demo's hero/backup prompt set. Fix 3 is **only worth doing if** the user wants Tool content_type to actually work end-to-end (for breadth of "Claude Code for Terraria" coverage). If not, document Pickaxe as unsupported in `docs/superpowers/specs/2026-04-26-product-fixes-plan.md` and ban it from the corpus. **Recommend deferring Fix 3 entirely until post-demo.**

If shipping:

**Phase 3.1 — Thread request provenance from TUI to orchestrator.**
Codex requirement: never silently override an explicit user selection.
- TUI (`BubbleTeaTerminal/`): when a user explicitly selects content_type via the wizard, write `content_type_explicit: true` alongside `content_type` into `user_request.json`. When defaulted (no wizard step taken / API caller omitted the field), write `content_type_explicit: false` (or omit the field entirely).
- IPC schema (`agents/contracts/ipc.py` `UserRequest`): add `content_type_explicit: Optional[bool] = None`.
- Orchestrator (`agents/orchestrator.py`): wire the new field through; only invoke the inference override when `content_type_explicit` is False or absent.

**Phase 3.2 — Add content_type override (gated on provenance).**
- New helper `_request_content_type_inferred(request)`:
  - If `content_type_explicit` is True, return the request's content_type unchanged. Period.
  - Else, if the inferred sub_type is in `_TOOL_SUB_TYPES = {Pickaxe, Axe, Hamaxe, Hammer}`, return `"Tool"`.
  - Else return request's content_type (default `"Weapon"`).
- Both `run_pipeline` (~line 1250) and `run_instant_pipeline` (~line 1374) route through it.

**Phase 3.3 — Add Tool codegen templates in Forge Master.**
- Extend `agents/forge_master/templates/snippets.py` subtype maps with Pickaxe, Axe, Hamaxe, Hammer entries. Each should template:
  - `Item.pick = <power>` (Pickaxe)
  - `Item.axe = <power>` (Axe; `5×` factor in tModLoader convention)
  - `Item.hammer = <power>` (Hammer)
  - Hamaxe combines hammer + axe.
  - Damage fields stay populated — tools also hit enemies.
- Mirror Forge Master tests for the new templates.

**Phase 3.4 — Verify Tool path produces a real pickaxe.**
- Architect with `content_type="Tool"`, `sub_type="Pickaxe"`, prompt `obsidian pickaxe with magma cracks`. Manifest should have `content_type="Tool"`, populated `tool_stats`, plus weapon-like damage.
- QA Tier C for the same prompt. Generated C# should set `Item.pick`. Ideally test in-game by mining a block.

**Phase 3.5 — Verify the explicit-Weapon escape hatch.**
- Manually craft a request with `content_type: "Weapon"`, `content_type_explicit: true`, `prompt: "weaponized pickaxe of war"`. Confirm orchestrator does NOT override to Tool. Confirm the architect produces a Weapon manifest with sub_type fallback.

## Sequencing and order (revised after codex review)

1. **Fix 1 first** — but Phase 1.1 is investigation, not implementation. If 3 production runs land cleanly at `ready`, close as QA-harness-only and move on. If not, diagnose with real evidence.
2. **Fix 2 second** — only if firing on camera. Scope is now **9 missing sub_types** (Pistol/Shotgun/Rifle/Repeater/Wand/Tome/Spellbook/Launcher/Cannon), not 3. Larger than original estimate; budget accordingly.
3. **Fix 3 — defer past the demo.** Codex showed the original scope was incomplete (missing Tool codegen, missing provenance threading). Ship surface area is significant. Pickaxe is out of demo prompts; banning it from the corpus and shipping Fix 3 post-demo is the right call. Document the Pickaxe-as-Weapon limitation in the README's known issues if needed.

Each phase is one or two commits on `main`, with a Codex adversarial review of the diff before commit. If a fix turns out to be larger than estimated, stop and escalate; do not muscle through.

**Hard stop for Fix 3:** if the user wants to ship Pickaxe support, treat it as a separate post-demo plan with its own brainstorming/spec/codex-review cycle. Do not try to land it in this batch.

## Critical files

- **Fix 1 (investigation):** `agents/orchestrator.py:75-77,101,371-400`, `agents/gatekeeper/gatekeeper.py:124-132,175-183,342-351,376-384`, `agents/core/atomic_io.py:38-50`, `agents/core/paths.py:67-75`. New regression test only if Phase 1.1 reproduces.
- **Fix 2:** `agents/architect/weapon_prompt.py`, `agents/architect/models.py:366-400` (lowering — DO NOT change) and validator after lowering, `agents/forge_master/templates/snippets.py:19-35,123-127,984-988,1687-1694`, `agents/core/combat_packages.py:48-78` (read-only confirmation), Forge Master tests.
- **Fix 3 (deferred):** `BubbleTeaTerminal/model.go:92-98,107-115`, `BubbleTeaTerminal/screen_forge.go:173-191`, `BubbleTeaTerminal/internal/ipc/ipc.go:314-329`, `agents/contracts/ipc.py` UserRequest, `agents/orchestrator.py` (~line 773 helper, callers at ~1250 and ~1374), `agents/forge_master/templates/snippets.py` (Tool subtype maps).

## Verification per fix

- **Fix 1**: `pytest agents/` green, new path-resolution test passes, QA Tier C harness re-run shows `status: ready` final state.
- **Fix 2**: ranged-sub_type manifests have non-null `shoot_projectile`, generated C# has `Item.shoot = ProjectileID.X`, new architect/forge_master tests green.
- **Fix 3**: pickaxe prompt produces `content_type: "Tool"` with populated `tool_stats`; generated C# uses `Item.pick`.

## Out of scope

- Sprite-gate calibration for thin shapes (bow `occupancy` failure) — a separate sprite-gen workstream.
- Architect stat-block copy-paste between same-tier+same-sub_type items — product hygiene, deferable.
- Item-name encoding the sub_type word — naming heuristic, deferable.
- Expanding QA corpus to non-Weapon content types — already noted in the QA report.
