# This is are some things to remember from a tricky bug

## Status
Resolved on `main`.

## Original Symptom
- `StormBrandStaffLive` injected successfully
- item appeared in inventory
- inventory icon was blank
- projectile visuals were missing or effectively invisible
- gameplay hooks could still fire, which made the bug look mechanical when it was mostly visual/runtime-asset related

## Root Cause
This was not one single issue.

1. Direct inject depended on external sprite file paths surviving long enough for `ForgeConnector` to consume them.
2. The direct-inject art path could pass through sprites that were technically valid but visually too weak/sparse.
3. Runtime evidence was hard to inspect because the live inject payload and resolved asset state were not preserved.

## Fixes Landed

### Runtime / connector
- direct-inject sprites are staged into a runtime-owned directory before load
- last inject payload/debug artifacts are preserved
- runtime summary state was hardened so failure states and menu/world state are clearer

### Art / pipeline
- deterministic sprite gates were applied to the normal direct-inject path, not just hidden audition

### Validation
- focused regression coverage was added around:
  - direct inject asset guards
  - runtime summary behavior
  - live workshop/runtime transport semantics

## Lessons
- A successful inject status does not prove visible runtime presentation
- Manifest correctness, runtime slot registration, and texture readability are separate concerns
- Live-runtime debugging benefits from preserving raw inject payloads and resolved asset paths
- Runtime support should stay bounded and explicit instead of pretending arbitrary generated content is equally live-valid

## Still Relevant Files
- `agents/pixelsmith/pixelsmith.py`
- `agents/tests/test_direct_inject_asset_guards.py`
- `mod/ForgeConnector/ForgeConnectorSystem.cs`
- `mod/ForgeConnector/ForgeManifestStore.cs`
- `mod/ForgeConnector/ForgeItemGlobal.cs`
- `mod/ForgeConnector/ForgeProjectileGlobal.cs`

## Why Keep This Note
This incident is resolved, but it remains the clearest compact example of how the live inject/render path can fail even when gameplay hooks and inject status appear healthy.
