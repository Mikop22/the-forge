# Storm Brand Live Bug Handoff

## Problem Statement
- `StormBrandStaffLive` can be injected into a running tModLoader session.
- Item appears in inventory.
- Reported live behavior from user:
  - inventory icon blank
  - no visible projectile when used
  - staff mechanics still feel broken / not visibly doing what they claim

## Scope
- This is a live runtime/debugging issue, not a schema-generation issue.
- Hidden audition, package-first manifests, and runtime telemetry plumbing are already implemented.
- Immediate target is the direct/live injected `storm_brand` staff path.

## Current Code Reality

### Python side
- Hidden runtime request/winner path now preserves `projectile_sprite_path`:
  - `agents/orchestrator.py:616`
  - `agents/orchestrator.py:673-675`
  - `agents/orchestrator.py:734-735`
- Hidden Pixelsmith finalists now carry projectile art:
  - `agents/pixelsmith/models.py:171-177`
- Hidden runtime request contract includes sprite paths and package/runtime identity:
  - `agents/core/runtime_contracts.py`

### C# runtime side
- Runtime bridge reads both item and projectile sprite paths from inject payload:
  - `mod/ForgeConnector/ForgeConnectorSystem.cs:218`
- Telemetry context is package-aware and only enabled for `storm_brand` / `mark_cashout`:
  - `mod/ForgeConnector/ForgeLabTelemetry.cs:17-20`
- `storm_brand` now spawns a real visible 3rd-hit follow-up attack:
  - `mod/ForgeConnector/ForgeProjectileGlobal.cs:111-121`
  - `mod/ForgeConnector/ForgeProjectileGlobal.cs:134-154`
  - uses `ProjectileID.Starfury`

## What Has Already Been Tried

### Hidden-audition / pipeline fixes already made
- Implemented hidden thesis ranking, package-first finalist expansion, hidden art audition, cross-consistency gate, runtime telemetry, runtime contract handshake, winner-only reveal, recovery mode.
- Added dense AI handoff docs:
  - `docs/llm-handoff/00-index.md`
  - `docs/llm-handoff/01-architecture.md`
  - `docs/llm-handoff/02-current-state.md`

### Review-driven fixes already made
- Hidden-audition winner no longer drops `projectile_sprite_path`.
- One finalist timing out no longer aborts the whole hidden-audition batch.
- Runtime timing anchor moved away from the first cast in the run.

### Live-specific tuning already made
- Real hidden-audition art failures were investigated.
- Deterministic sprite gates were tuned twice:
  - ignore tiny detached noise in silhouette metric
  - allow tiny bounded edge contact for item sprites
- Hidden finalists now synthesize imageable package-aware visual briefs instead of feeding gameplay prose directly into Pixelsmith.
- Single-survivor art auditions no longer fabricate extreme scores, but do emit conservative nonzero structured evidence.

### Direct live inject path already tested
- Direct inject script generated:
  - item sprite
  - projectile sprite
  - `storm_brand` manifest
- Inject succeeded with:
  - `forge_connector_status.json.status = item_injected`
- User still reported:
  - blank inventory icon
  - no visible projectile/assets

### Runtime evidence already observed
- Hidden lab request consumption was confirmed once the player entered a world.
- Runtime telemetry showed `seed_triggered`, `escalate_triggered`, and `cashout_triggered` for `storm_brand`.
- That means gameplay hooks and projectile hit path are at least partially executing.

## Strongest Current Hypotheses

### H1. Texture path / asset load failure inside live `ForgeConnector`
Evidence:
- user sees blank icon and no projectile art
- direct inject carried sprite paths
- runtime telemetry still fires, implying mechanics path exists while visuals do not
Files to inspect first:
- `mod/ForgeConnector/ForgeConnectorSystem.cs`
- `mod/ForgeConnector/ForgeManifestStore.cs`
- any helper that loads sprite paths into `TextureAssets`

### H2. Live mod instance still not fully aligned with repo code or asset paths
Evidence:
- source sync + mod reload were required mid-debug
- live behavior diverged from what the branch code appeared to support
Files/areas:
- live `ModSources/ForgeConnector` vs repo `mod/ForgeConnector`
- tModLoader logs
- `forge_connector_alive.json`, `forge_connector_status.json`

### H3. Item/projectile art generation succeeded on disk but resulting images are transparent / effectively blank
Evidence:
- injected paths existed
- user still saw blank icon
Files/areas:
- generated images under `agents/output/`
- Pixelsmith background removal/downscale path:
  - `agents/pixelsmith/pixelsmith.py`
  - `agents/pixelsmith/sprite_gates.py`

### H4. Projectile exists mechanically but visual draw path falls back incorrectly
Evidence:
- telemetry comes from `ForgeProjectileGlobal.OnHitNPC(...)`
- user sees no projectile
Files/areas:
- `mod/ForgeConnector/ForgeProjectileGlobal.cs`
- `PreDraw(...)`
- projectile texture assignment in manifest store/runtime load path

## What Is Probably Not The Main Root Cause
- Architect package selection alone. The direct injected manifest already forced `storm_brand`.
- Hidden runtime contract plumbing alone. Telemetry did occur.
- Lack of a cashout mechanic. `SpawnStormCashout(...)` exists now.

## Critical Files For Next Agent

### Read first
- `docs/llm-handoff/01-architecture.md`
- `docs/llm-handoff/02-current-state.md`

### Then inspect
- `agents/orchestrator.py`
- `agents/pixelsmith/pixelsmith.py`
- `agents/pixelsmith/models.py`
- `mod/ForgeConnector/ForgeConnectorSystem.cs`
- `mod/ForgeConnector/ForgeManifestStore.cs`
- `mod/ForgeConnector/ForgeItemGlobal.cs`
- `mod/ForgeConnector/ForgeProjectileGlobal.cs`
- `mod/ForgeConnector/ForgeLabTelemetry.cs`
- `agents/tests/test_pixelsmith_hidden_audition.py`
- `agents/tests/test_runtime_lab_contract.py`
- `agents/tests/test_hidden_audition_pipeline.py`

## Necessary Background Knowledge
- Python orchestrator owns generation and writes file-based IPC into tModLoader `ModSources`.
- Go TUI is a client only.
- `ForgeConnector` is a constrained runtime bridge that injects template-backed items and textures.
- Hidden runtime validation only truly supports:
  - `storm_brand`
  - `mark_cashout`
- The current bug is likely in the live asset/render path, not the manifest schema.

## Useful Live Files
- `/Users/user/Library/Application Support/Terraria/tModLoader/ModSources/forge_inject.json`
- `/Users/user/Library/Application Support/Terraria/tModLoader/ModSources/forge_connector_status.json`
- `/Users/user/Library/Application Support/Terraria/tModLoader/ModSources/forge_connector_alive.json`
- `/Users/user/Library/Application Support/Terraria/tModLoader/ModSources/forge_lab_hidden_request.json`
- `/Users/user/Library/Application Support/Terraria/tModLoader/ModSources/forge_lab_hidden_result.json`
- `/Users/user/Library/Application Support/Terraria/tModLoader/ModSources/forge_lab_runtime_events.jsonl`

## Current Test State
- Focused bug-area regression slice:
  - `34 passed`
- Hidden-audition/projectile regression slice:
  - `40 passed`
- Full hidden-lab suite earlier reached:
  - `250 passed`

## Immediate Next Step Recommendation
1. Prove whether the injected item and projectile textures are actually loaded in `ForgeConnectorSystem` / `ForgeManifestStore`.
2. Compare the on-disk generated PNGs with what the live mod thinks it loaded.
3. If textures are loaded correctly, inspect `PreDraw` and item icon assignment paths.
4. If textures are not loaded, fix asset path / image generation / alpha handling at the source.
