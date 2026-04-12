# Architecture Map

## System Shape
`BubbleTeaTerminal` writes file requests into tModLoader `ModSources`. `agents/orchestrator.py` watches those files, runs the Python pipeline, writes shared status files, and optionally asks `ForgeConnector` to perform runtime injection and hidden-lab telemetry collection inside a live tModLoader process.

## Topology
### TUI
- Entry: `BubbleTeaTerminal/main.go`.
- Request path: `screen_forge.go` -> `ipc.WriteUserRequest(...)` -> `user_request.json`.
- Ready/inject path: `screen_staging.go` -> `ipc.WriteInjectFile(...)` -> `forge_inject.json`.
- TUI only polls status/connector files and renders previews; it does not own generation logic.

### Python pipeline
- Entry/daemon: `agents/orchestrator.py`.
- Agent order, normal compile path: `ArchitectAgent` -> parallel `CoderAgent` + `ArtistAgent` -> `Gatekeeper Integrator`.
- Agent order, instant path: `ArchitectAgent` -> `ArtistAgent` -> `_set_ready(..., inject_mode=True)`; no Gatekeeper build.
- Hidden audition path is still orchestrator-owned end-to-end; winner reveal happens only after art review + runtime gate pass.

### Runtime bridge
- Active code: `mod/ForgeConnector/`.
- `ForgeConnectorSystem.cs`: watches IPC files, parses manifests, allocates template slots, loads textures, spawns items, writes bridge status, handles hidden-lab request/result handshake.
- `ForgeManifestStore.cs`: in-memory slot/type/texture registries for item/projectile/buff templates.
- `ForgeLabTelemetry.cs`: emits `forge_lab_runtime_events.jsonl` for supported hidden runtime checks.
- `ForgeItemGlobal.cs` and `ForgeProjectileGlobal.cs`: runtime behavior hooks that make template slots behave like the injected manifest.

## Core Contracts
### TUI <-> orchestrator
- `agents/contracts/ipc.py::UserRequest`
  - `prompt`, `tier`, `crafting_station`, `content_type`, `sub_type`, `mode`, `existing_manifest`, `art_feedback`.
  - Note: no explicit `hidden_audition` field in the typed contract; orchestrator still probes raw request dict for it.
- `agents/contracts/ipc.py::GenerationStatus`
  - root file for TUI polling.
  - `status in {building, ready, error}` plus stage metadata, manifest, sprite paths, `inject_mode`, `error_code`.

### Architect / manifest
- `agents/architect/models.py::ItemManifest`
  - validated source manifest for both codegen and art.
  - package-first mechanics live under `mechanics.combat_package`; resolved lowering lives under `resolved_combat`.
- `agents/core/combat_packages.py`
  - phase-1 bounded registry: `storm_brand`, `orbit_furnace`, `frost_shatter`.
  - deterministic lowering to modules + legacy projection.

### Hidden runtime gate
- `agents/core/runtime_contracts.py::HiddenLabRequest`
  - candidate identity, `run_id`, `package_key`, `loop_family`, manifest snapshot, sprite paths, bounded `BehaviorContract`.
  - enforces manifest/runtime identity alignment.
  - currently rejects anything outside `storm_brand` + `mark_cashout`.
- `agents/core/runtime_lab_contract.py::RuntimeLabResult`
  - normalized runtime evidence payload.
  - validates that each event matches candidate/run/package/loop identity.
- `agents/core/weapon_lab_archive.py::WeaponLabArchive`
  - prompt, theses, finalists, judge scores, rejection reasons, reroll ancestry, runtime gate records, winner rationale.

## File IPC Surface
All paths are under resolved tModLoader `ModSources` unless noted.

### Primary control/status
- `user_request.json`: Go TUI -> orchestrator.
- `generation_status.json`: orchestrator and Gatekeeper mirror status for TUI.
- `orchestrator_alive.json`: orchestrator heartbeat.
- `.forge_orchestrator.lock`: single-instance guard per `ModSources` tree.

### Instant inject / bridge
- `forge_inject.json`: TUI staging screen -> `ForgeConnector` instant injection.
- `forge_connector_status.json`: `ForgeConnector` -> TUI (`item_injected`, `item_pending`, `inject_failed`, etc.).
- `forge_connector_alive.json`: bridge heartbeat.

### Hidden audition runtime gate
- `forge_lab_hidden_request.json`: orchestrator -> `ForgeConnector` hidden runtime request.
- `forge_lab_hidden_result.json`: `ForgeConnector` -> orchestrator runtime result.
- `forge_lab_runtime_events.jsonl`: telemetry event stream written by `ForgeLabTelemetry`.

## Execution Paths
### 1. Normal compile path
1. TUI writes `user_request.json`.
2. Orchestrator validates request, writes `generation_status.json` building stages.
3. Architect produces `ItemManifest`.
4. Pixelsmith generates item/projectile sprites.
5. Forge Master generates C# + hjson.
6. Gatekeeper stages files into `ForgeGeneratedMod`, builds with tModLoader, may invoke repair loop.
7. Gatekeeper mirrors status back to root `generation_status.json`.
8. TUI reaches preview/staging screen.
9. User accepts; TUI writes `forge_inject.json`.
10. `ForgeConnector` injects into live game and writes `forge_connector_status.json`.

### 2. Instant path
1. Same request ingress.
2. Orchestrator runs Architect + Pixelsmith only.
3. Orchestrator returns `ready` with `inject_mode=true` and preview manifest/sprites.
4. TUI still uses `forge_inject.json` for actual runtime appearance.
5. No Gatekeeper compile/build occurs.

### 3. Hidden audition path
1. Orchestrator sees raw request `hidden_audition=true`.
2. Architect thesis tournament generates multiple theses, ranks finalists, expands finalists into manifests.
3. Pixelsmith hidden audition generates multiple art variants per finalist, applies deterministic sprite gates, judges survivors, archives losers.
4. `core.cross_consistency` filters finalists whose prompt/thesis/manifest/art signals drift.
5. Orchestrator converts each surviving finalist into `HiddenLabRequest` and writes `forge_lab_hidden_request.json` one candidate at a time.
6. `ForgeConnector` injects candidate context and writes telemetry/result files.
7. Orchestrator waits for terminal evidence (`cashout_triggered` or `candidate_completed`), evaluates `BehaviorContract`, archives outcome.
8. Only finalists passing runtime gate are eligible.
9. Winner is selected from runtime passers by art sort key.
10. Only the winner manifest/sprites move to normal reveal.

## Hidden-Audition Internal Logic
### Thesis/finalist side
- `ArchitectAgent.generate_thesis_finalists(...)`: returns ranked finalists without choosing winner.
- `ArchitectAgent.expand_thesis_finalist_to_manifest(...)`: package-first when runtime surface supports the loop; otherwise legacy fallback with explicit `fallback_reason`.
- Runtime support is checked through `RuntimeCapabilityMatrix`.

### Art side
- `ArtistAgent.generate_hidden_audition_finalists(...)`:
  - validates each finalist via `PixelsmithInput`.
  - derives bounded art-direction strategy.
  - generates `>=2` variants for hidden audition.
  - runs deterministic sprite gates.
  - judges surviving variants for `motif_strength` and `family_coherence`.
  - writes winner sprite for that finalist; archives loser reasons.

### Runtime side
- `build_hidden_lab_request(...)` rejects unsupported runtime identities and legacy fallback finalists.
- `run_hidden_lab_runtime_gate(...)` writes request file, waits for result file, requires terminal evidence, evaluates hit/time budgets.
- `ForgeLabTelemetry` only emits for `storm_brand` / `mark_cashout` contexts.

## Status Ownership
- Orchestrator writes root `generation_status.json` during pipeline phases and final ready/error states.
- Gatekeeper writes mod-local `ForgeGeneratedMod/generation_status.json` and mirrors a TUI-compatible version back to root `generation_status.json`.
- TUI reads root status; connector status is separate and only used after staging accept.

## Environment Resolution
- ModSources resolution order from README: `FORGE_MOD_SOURCES_DIR` -> `~/.config/theforge/config.toml` `mod_sources_dir` -> OS default.
- Only one orchestrator may run per `ModSources` tree; enforced by `.forge_orchestrator.lock`.

## Highest-Risk Coupling Points
### 1. Identity drift across manifest/package/runtime
- `package_key` and `loop_family` may exist in root finalist fields, `mechanics`, and `resolved_combat`.
- Hidden runtime gate assumes these stay aligned; mismatches are intentionally fatal.

### 2. Hidden-lab support matrix is tiny
- Package registry has 3 packages.
- `RuntimeCapabilityMatrix.default()` supports only `Weapon/Staff/mark_cashout`.
- `HiddenLabRequest` currently allows only `storm_brand` runtime telemetry.
- Any design discussion that implies multi-package runtime validation is ahead of implementation.

### 3. Contract mismatch between typed request and orchestrator behavior
- `UserRequest` omits `hidden_audition`, `thesis_count`, `finalist_count`.
- Orchestrator reads those from raw dict anyway.
- This is soft-compatible because Pydantic ignores extras, but typed docs/tests can lag behavior.

### 4. Template-slot reuse and ephemeral runtime state
- `ForgeManifestStore` uses round-robin slot reuse (`50` item, `25` projectile, `25` buff templates).
- Injected content is live-session state, not durable compiled code.
- Incorrect assumptions about slot persistence cause hard-to-debug runtime bleed.

### 5. Reflection-based texture injection
- `ForgeConnectorSystem` mutates `TextureAssets` via reflection-backed helpers.
- Runtime texture success can diverge from manifest registration success.

### 6. Terminal evidence semantics
- Runtime gate does not accept any telemetry; it waits for terminal evidence before judging.
- If connector emits partial events without `cashout_triggered` or `candidate_completed`, orchestrator can time out.

### 7. Legacy fallback contamination
- Hidden runtime requests reject legacy fallback finalists for correctness.
- Normal compile flow still tolerates legacy projection/lowering.
- Mixing those assumptions causes false confidence about runtime-validated winners.
