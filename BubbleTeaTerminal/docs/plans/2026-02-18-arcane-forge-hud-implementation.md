# Arcane Forge HUD Implementation Plan

Archived implementation summary for the Bubble Tea HUD refresh.

## Goal

Add a forge-themed shell and lightweight animation state without changing navigation.

## Implementation Summary

1. Extend the model with animation/layout state.
2. Route screens through a shared shell renderer.
3. Add compact-mode handling for small terminals.
4. Add bounded forge heat and staged reveal behavior.
5. Verify with `go test ./...`.
