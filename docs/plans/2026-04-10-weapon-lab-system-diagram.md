# Weapon Lab System Diagram

Archived note for the hidden-lab flow.

## Flow Summary

1. Prompt enters the orchestrator.
2. Hidden thesis generation and ranking run first.
3. Finalists expand into manifests and art candidates.
4. Sprite gates, cross-consistency checks, and runtime validation run before reveal.
5. Only the winner reaches codegen, staging, and TUI reveal.

## Runtime Evidence Summary

- Orchestrator writes a hidden-lab request into `ModSources`.
- `ForgeConnector` records runtime events and a hidden-lab result.
- The orchestrator evaluates that evidence before selecting a winner.

## Related Areas

- `agents/orchestrator.py`
- `agents/architect/*`
- `agents/core/*weapon_lab*`
- `agents/pixelsmith/*`
- `mod/ForgeConnector/*`
