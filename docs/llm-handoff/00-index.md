# LLM Handoff Index

## Purpose
Replace scattered plans/design notes with 3 AI-oriented entrypoints after repo minimization and architecture mapping.

## Canonical Docs
1. `docs/llm-handoff/00-index.md`: navigation, environment, reading order, deletion shortlist.
2. `docs/llm-handoff/01-architecture.md`: topology, contracts, execution paths, state files, coupling.
3. `docs/llm-handoff/02-current-state.md`: implemented reality, design drift, risks, next actions.

## Minimal Environment
- Target runtime: Terraria + tModLoader `1.4.4`.
- Go: `1.24+` for `BubbleTeaTerminal/`.
- Python: `3.12+` for `agents/`.
- Node: `18+` for `agents/pixelsmith/fal_flux2_runner.mjs`.
- Python deps: `agents/requirements.txt` plus `fal-client`, `playwright`, `scikit-learn`.
- Browser runtime: `playwright install chromium` for Architect reference lookup.
- External keys: `OPENAI_API_KEY`, `FAL_KEY`; optional `FAL_IMAGE_TO_IMAGE_ENABLED=true`.
- Pixelsmith local weight file: `agents/pixelsmith/terraria_weights.safetensors` via `agents/pixelsmith/download_weights.py`.
- tModLoader bridge mod: copy `mod/ForgeConnector/` into `ModSources`, build, enable.

## Working Assumptions
- Shared filesystem IPC through tModLoader `ModSources` is the system backbone.
- Python orchestrator is the source of truth for pipeline state and hidden-audition control flow.
- Go TUI is a client, not the orchestrator.
- `ForgeConnector` is a constrained runtime adapter, not a full generated-runtime host.
- Package-first combat exists, but live runtime support is intentionally tiny.

## Repo Topology
- `BubbleTeaTerminal/`: Bubble Tea UI, request writing, status polling, staging/inject UX.
- `agents/`: Python agent pipeline.
- `agents/architect/`: prompt-to-manifest + thesis tournament/finalist expansion.
- `agents/pixelsmith/`: sprite generation, sprite gates, hidden art audition.
- `agents/forge_master/`: manifest-to-C# generation + review.
- `agents/gatekeeper/`: stage/build/repair loop, mirrors status back to `ModSources` root.
- `agents/core/`: package registry, runtime contracts, archive models, consistency checks, path resolution.
- `agents/contracts/`: IPC file schemas between TUI and orchestrator.
- `mod/ForgeConnector/`: runtime injection, template slot pool, telemetry, texture loading.
- `docs/plans/`, `BubbleTeaTerminal/docs/plans/`, `ReferenceDesign.MD`: archived context, mostly superseded by this handoff set.

## Exact Reading Order For A New LLM
1. `docs/llm-handoff/01-architecture.md`
2. `docs/llm-handoff/02-current-state.md`
3. `agents/orchestrator.py`
4. `agents/contracts/ipc.py`
5. `agents/architect/architect.py`
6. `agents/architect/models.py`
7. `agents/core/combat_packages.py`
8. `agents/core/runtime_capabilities.py`
9. `agents/core/runtime_contracts.py`
10. `agents/core/runtime_lab_contract.py`
11. `agents/core/cross_consistency.py`
12. `agents/core/weapon_lab_archive.py`
13. `agents/pixelsmith/pixelsmith.py`
14. `agents/pixelsmith/models.py`
15. `agents/forge_master/forge_master.py`
16. `agents/gatekeeper/gatekeeper.py`
17. `mod/ForgeConnector/ForgeConnectorSystem.cs`
18. `mod/ForgeConnector/ForgeManifestStore.cs`
19. `mod/ForgeConnector/ForgeLabTelemetry.cs`
20. `mod/ForgeConnector/ForgeItemGlobal.cs`
21. `mod/ForgeConnector/ForgeProjectileGlobal.cs`
22. `BubbleTeaTerminal/screen_forge.go`
23. `BubbleTeaTerminal/screen_staging.go`

## Fast Verification Targets
- Python contracts/tests: `agents/tests/test_hidden_audition_pipeline.py`, `agents/tests/test_runtime_lab_contract.py`, `agents/tests/test_combat_package_pipeline.py`, `agents/tests/test_pixelsmith_hidden_audition.py`.
- Go/TUI integration: `BubbleTeaTerminal/main_test.go`.
- Connector behavior guardrails are asserted in Python tests by reading C# source, especially runtime gate semantics.

## Deletion Shortlist
Safe only after confirming this handoff set is accepted as the new entrypoint.

- `ReferenceDesign.MD`
- `docs/plans/2026-04-10-combat-package-v2.md`
- `docs/plans/2026-04-10-weapon-lab-hidden-audition-design.md`
- `docs/plans/2026-04-10-weapon-lab-hidden-audition-implementation.md`
- `docs/plans/2026-04-10-weapon-lab-system-diagram.md`
- `BubbleTeaTerminal/docs/plans/2026-02-18-arcane-forge-hud-design.md`
- `BubbleTeaTerminal/docs/plans/2026-02-18-arcane-forge-hud-implementation.md`
- `BubbleTeaTerminal/docs/plans/2026-02-27-forge-design-improvements.md`
- `.DS_Store`
- `/build.txt`
- `/description.txt`
- `/ForgeConnector.csproj`
- `/ForgeConnectorSystem.cs`

## Notes On The Shortlist
- Root-level `/build.txt`, `/description.txt`, `/ForgeConnector.csproj`, `/ForgeConnectorSystem.cs` appear to be stale duplicates/candidates from earlier layouts; active connector sources live under `mod/ForgeConnector/`.
- Do not delete anything in this pass.
