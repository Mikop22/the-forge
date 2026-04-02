# The Polished Forge — Design Spec

**Date:** 2026-04-02
**Status:** Approved for implementation

## Vision

Transform The Forge from a single-item weapon generator into an interactive content playground. Users generate weapons, accessories, summons, consumables, and tools, preview them with ASCII animations in the TUI, iterate on sprites and stats before injecting, and test everything in-game.

The experience target: **30 minutes of fun** — generate a loadout, tweak it, inject it, go fight.

## What's NOT in scope

- Armor sets (head/body/legs with set bonuses) — requires cross-item linking
- Bosses and biomes — deferred to a future "Arena" expansion
- Browser-based preview — staying terminal-only
- Template pool scaling — existing 50 item / 25 projectile slots are sufficient for now

## Approved Scope

### New Content Types

- Accessories: wings, shields, movement modifiers, stat boosts, passive-defense items
- Summon weapons: minion staves with persistent follower minions
- Consumables: healing, mana, buffs, thrown weapons, ammo
- Tools: grappling hooks and fishing rods for v1

### Architect Changes

- Replace the monolithic architect prompt with a prompt router
- Add specialized prompts and models for weapon, accessory, summon, consumable, and tool manifests
- Validate BuffID and AmmoID values against whitelists before they reach runtime

### TUI Changes

- Add a content-type-first wizard
- Add a preview screen with ASCII sprite rendering and simple use-style animation
- Add preview actions for sprite reprompt, stat tweak, accept/inject, and discard

### Runtime Changes

- Expand the template-pool manifest store for richer item/projectile behavior
- Add a buff template pool for summon staves
- Expand item/projectile globals for accessories, summons, consumables, hooks, and fishing rods
- Add AI mode dispatch including a minion follower loop and vanilla hook aiStyle support

## Success Criteria

1. User can generate and inject at least 5 content types (weapons, accessories, summons, consumables, hooks)
2. ASCII preview renders the sprite recognizably in the terminal
3. Swing/shoot animation plays in the preview
4. User can reprompt the sprite and tweak stats before injecting
5. Summon minions follow the player and attack enemies in-game
6. No game crashes from injected content
7. Specialized prompts outperform the current monolithic prompt
