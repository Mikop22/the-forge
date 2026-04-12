# Current State

## Reality Snapshot
- Non-destructive minimization already happened before this pass.
- Architecture-critical code for package-first combat and hidden audition exists in repo, with tests.
- Archived plan/design docs were compressed but not deleted.
- Handoff docs here are intended to become the new high-signal entrypoint.

## Implemented Reality Vs Design Intent
### Implemented now
- Go TUI can write requests, poll build status, preview generated outputs, reprompt art, tweak some stats, and perform instant inject via `forge_inject.json`.
- Orchestrator supports:
  - normal compile path,
  - instant path,
  - hidden audition path.
- Architect supports thesis tournaments, finalist expansion, bounded package-first manifests, and explicit legacy fallback reasons.
- Pixelsmith supports deterministic sprite gates and hidden art audition with per-finalist winner selection.
- Cross-consistency gate exists and filters art finalists using heuristic signal matching plus structured art scores.
- Runtime request/result contracts exist and are tested.
- ForgeConnector can inject live items/projectiles/buffs, load textures, and emit hidden-lab telemetry.
- Runtime gate winner-only selection is implemented in orchestrator logic.

### Still bounded / intentionally incomplete
- Hidden runtime validation is effectively single-package: `storm_brand` + `mark_cashout` only.
- Runtime capability matrix supports only `Weapon/Staff/mark_cashout`.
- Cross-consistency is text/metadata heuristic, not image-native evaluation.
- TUI does not appear to expose hidden-audition controls directly in the core typed request contract.
- Request extras such as `hidden_audition`, `thesis_count`, `finalist_count` are raw-dict behavior, not first-class typed fields.
- Package registry names exceed live runtime telemetry coverage; `orbit_furnace` and `frost_shatter` are architecturally present but not hidden-runtime-valid.

### Design intent from archived docs that is not fully true yet
- "Winner-only hidden lab" is only true on the supported runtime slice.
- "Research-informed evidence layer" is not a first-class persistent subsystem in the critical path described here.
- Runtime validation is not a general weapon sandbox; it is a bounded contract check against minimal telemetry.
- Art consistency is not image-aware beyond proxy signals and judged summaries.

## Practical Mental Model
- Treat the system as `package-first authoring + legacy-compatible compile path + narrow runtime-validated hidden lab prototype`.
- Do not treat hidden audition as generally available for all packages/subtypes.
- Do not assume Go/TUI owns workflow truth; it mostly packages user intent and reflects pipeline state.
- Do not assume ForgeConnector can safely host arbitrary generated mechanics; it hosts a constrained template/slot runtime.

## Known Sharp Edges
### IPC / state
- Two writers touch root-ish generation state: orchestrator and Gatekeeper. Root mirroring is deliberate but easy to misunderstand.
- TUI clears some files optimistically (`generation_status.json`, `forge_connector_status.json`, `forge_inject.json`), so race reasoning must include client cleanup behavior.

### Hidden audition
- Runtime request creation fails fast for legacy fallbacks and unsupported package/runtime combinations.
- Hidden-audition winner selection currently uses art-score ordering among runtime passers, not a more explicit global multi-axis scalar.
- `run_hidden_audition_pipeline()` maps art finalists back to manifests by `candidate_id` or `item_name`; name collisions would be dangerous.

### ForgeConnector
- Manifest parsing still contains multiple fallback and normalization branches for legacy fields.
- Projectile, buff, and texture behavior depend on slot allocation plus runtime hooks, not compiled item-specific classes.
- Reflection-backed texture loading and static-ID resolution are fragile integration seams.

### Gatekeeper
- Build repair loop only handles compile-time issues after Forge Master output; it cannot fix packaging/environment failures.
- Staging/build files are created if missing under `ForgeGeneratedMod`, which can hide missing-repo-context assumptions.

## Suggested Next Steps
### Highest-value cleanup
1. Make hidden-audition request fields first-class in `agents/contracts/ipc.py::UserRequest` and in TUI request-writing helpers if the feature is meant to be operator-accessible.
2. Add a single canonical `docs/llm-handoff/` link from `README.md` once this set is accepted.
3. Delete archived docs from the shortlist only after confirming no active workflow still deep-links them.

### Highest-value engineering hardening
1. Unify identity sourcing for hidden runtime requests so `candidate_id`, `package_key`, and `loop_family` have one canonical origin in finalist data.
2. Expand or explicitly fence the runtime support matrix. Current ambiguity invites incorrect assumptions that all packages are runtime-valid.
3. Add explicit tests for finalist mapping collisions (`candidate_id` missing, duplicate `item_name`, mixed fallback/package finalists).
4. Add a compact operator-visible signal for hidden-audition mode in TUI if the path is intended for actual use, or mark it internal-only in docs/tests.
5. Decide whether root `generation_status.json` is the sole public status contract; if yes, document mod-local status as internal and keep all clients off it.

### If continuing hidden-lab work specifically
1. Extend runtime telemetry and `RuntimeCapabilityMatrix` package-by-package, starting with one additional package instead of generalizing all at once.
2. Promote cross-consistency from text-proxy heuristics toward stronger image-derived checks only if the extra cost is justified by eval wins.
3. Persist hidden-audition archives to disk for offline eval; current archive objects are typed but not described here as a durable on-disk artifact.

## Exact Read Targets By Goal
### Goal: modify request/UI behavior
- `BubbleTeaTerminal/screen_forge.go`
- `BubbleTeaTerminal/screen_staging.go`
- `BubbleTeaTerminal/main.go`
- `agents/contracts/ipc.py`

### Goal: modify normal generation
- `agents/orchestrator.py`
- `agents/architect/architect.py`
- `agents/architect/models.py`
- `agents/pixelsmith/pixelsmith.py`
- `agents/forge_master/forge_master.py`
- `agents/gatekeeper/gatekeeper.py`

### Goal: modify hidden audition
- `agents/orchestrator.py`
- `agents/core/runtime_capabilities.py`
- `agents/core/runtime_contracts.py`
- `agents/core/runtime_lab_contract.py`
- `agents/core/cross_consistency.py`
- `agents/core/weapon_lab_archive.py`
- `agents/pixelsmith/pixelsmith.py`
- `mod/ForgeConnector/ForgeLabTelemetry.cs`
- `mod/ForgeConnector/ForgeConnectorSystem.cs`
- `mod/ForgeConnector/ForgeProjectileGlobal.cs`

### Goal: modify runtime injection
- `mod/ForgeConnector/ForgeConnectorSystem.cs`
- `mod/ForgeConnector/ForgeManifestStore.cs`
- `mod/ForgeConnector/ForgeItemGlobal.cs`
- `mod/ForgeConnector/ForgeProjectileGlobal.cs`

## Residual Verbose/Redundant Docs
Still mostly superseded by this handoff set:

- `ReferenceDesign.MD`
- `docs/plans/2026-04-10-combat-package-v2.md`
- `docs/plans/2026-04-10-weapon-lab-hidden-audition-design.md`
- `docs/plans/2026-04-10-weapon-lab-hidden-audition-implementation.md`
- `docs/plans/2026-04-10-weapon-lab-system-diagram.md`
- `BubbleTeaTerminal/docs/plans/2026-02-18-arcane-forge-hud-design.md`
- `BubbleTeaTerminal/docs/plans/2026-02-18-arcane-forge-hud-implementation.md`
- `BubbleTeaTerminal/docs/plans/2026-02-27-forge-design-improvements.md`

Potentially still useful but not minimized into this handoff set:

- `agents/docs/pipeline-flow.md`: useful as a lower-level trace doc, but no longer the best entrypoint for a new LLM.
