# Weapon Lab Hidden Audition Design

## Goal

Turn The Forge from a first-pass weapon generator into a hidden-audition weapon lab that invents, judges, repairs, and rejects candidates before a weapon is ever shown in the TUI or injected into Terraria.

The target is not conservative reliability. The target is surprising novelty with enough structure that the winning weapon still reads clearly, pays off quickly, looks distinct, and actually performs the loop it promises in-game.

## Research Basis

This design is informed by:

1. Current codebase behavior on the `combat-package-v2` branch
2. External research into community-loved modded Terraria weapons and weapon families
3. Expert review from a Terraria gameplay/art lens
4. Expert review from an AI/LLM systems lens

Research findings that drive this design:

- Memorable Terraria weapons are usually praised for hit feel, sound identity, and readable escalation before raw DPS.
- Short payoff loops win. Players respond best when a meaningful cash-out happens in roughly `1-3s` or within a few successful hits.
- Escalation must be visible. Marks, charges, satellites, sound pitch-up, glow changes, or timing windows make the loop readable.
- Reliable payoff matters. After the player completes setup, the reward should connect dependably instead of becoming another whiff-prone projectile.
- Novelty works best when attached to one strong verb: mark and condemn, charge and release, pogo and slam, parry and riposte, orbit and divebomb.

Reference patterns from community-loved weapons:

- `Murasama`: tight combo cadence and premium hit timing
- `Biome Blade`: readable attunements, movement hooks, charge/release, target-state play
- `Ark of the Cosmos`: combo stages, parry timing, escalating spectacle
- `Thorium Bard` instruments: visible timing windows and rhythmic payoff

## Current Problem

The current system still makes it too easy for valid but underwhelming outputs to survive:

- Architect can still emit legacy projectile-only manifests on the supported staff surface.
- Pixelsmith still returns a single accepted asset too often, especially outside reference-mode multi-variant selection.
- The TUI reveals the first acceptable result instead of the best candidate.
- Live validation currently proves injection and compilation, but not whether the weapon actually performs its intended loop.

This creates a common failure mode:

- nice prompt
- nice sprite
- valid projectile
- no real payoff loop
- no strong audiovisual identity

That feels like a projectile generator, not a weapon lab.

## Product Identity

The system should feel like a weapon lab:

- it experiments in secret
- it generates multiple combat toys
- it judges them ruthlessly
- it only reveals the winner
- when it fails, it searches farther into strange idea space instead of lowering standards

The user should never see a weak candidate merely because it was valid.

## Core Principles

1. Never reveal the first valid result.
2. Never lower the quality bar in recovery mode.
3. Prefer runtime-expressible novelty over purely textual cleverness.
4. Judge mechanics, art, and runtime behavior separately before choosing a winner.
5. Persist enough hidden-run evidence to understand why a candidate won or lost.

## Runtime Capability Envelope

The hidden lab can only claim “winner-only” behavior if candidate theses are constrained by what the current runtime can actually express.

The system must maintain a capability matrix covering at least:

- supported loop families
- supported state owners
- supported escalation signals
- supported finisher trigger classes
- supported sound and FX hooks
- supported telemetry events
- unsupported thesis primitives

Examples of capability-matrix questions:

- Can this thesis express target marks today?
- Can the instant inject runtime emit the seed/escalate/cashout events needed for validation?
- Can the runtime actually play a distinct finisher sound/FX ladder for this family?

If the runtime cannot express a thesis family yet, that thesis must not be eligible to win.

## System Overview

The hidden pipeline should become:

1. User prompt
2. Hidden weapon thesis batch
3. Hidden thesis tournament
4. Finalist manifest/package expansion
5. Hidden art thesis + art strategy generation
6. Hidden sprite audition
7. Cross-consistency review
8. Hidden in-game lab validation
9. Winner selection
10. `_set_ready(...)` only for the winner

Winner selection must happen only after all evidence-bearing gates have run.

## Weapon Thesis Layer

Before manifest generation, each candidate should be a compact weapon thesis rather than a full manifest.

Each thesis should define:

- `fantasy`
- `player_verb`
- `seed`
- `escalate`
- `cashout`
- `time_to_payoff`
- `reliability_aid`
- `movement_or_spacing_hook`
- `spectacle_ladder`
- `signature_sound`

Example:

- fantasy: celestial execution staff
- player_verb: brand targets and condemn them
- seed: a bolt applies a star sigil
- escalate: sigil intensifies from 1 to 3
- cashout: a star-spear ruptures the target
- reliability_aid: slight finisher homing on marked targets
- spectacle_ladder: chime -> crackle -> thunder tear

This is the main novelty surface. The system should generate `5-8` theses per prompt.

## Ranking Specification

The hidden thesis tournament must not be an uncalibrated prose contest.

The ranking layer should define:

- deterministic hard rejects
- pairwise or listwise ranking policy
- anchor examples of known-good and known-bad theses
- judge diversity and independence rules
- disagreement resolution policy
- tie-break rules
- rank-stability checks across repeated runs

The ranking layer should prefer:

- readable loops
- fast payoff
- distinctive player verbs
- runtime-expressible novelty

and explicitly penalize:

- “just shoot a projectile” behavior
- hidden buildup
- slow or missable payoff without reliability aid
- spectacle language unsupported by runtime hooks

## Thesis Tournament

Each thesis goes through two filters.

### Deterministic Hard Gates

Reject theses that lack:

- a clear `seed -> escalate -> cashout`
- payoff within `~1-3s`, unless the prompt explicitly asks for a long windup/charge concept
- visible escalation
- finisher escalation in sound/flash/impact
- a changed player behavior beyond “fire another projectile”
- a mapping to the current runtime capability envelope

### Model Judges

Score surviving theses on:

- novelty
- loop clarity
- payoff speed
- audiovisual punch
- Terraria combat fit
- reliability after setup
- keep-using-it score

Only the top `2-3` theses advance.

## Manifest And Package Expansion

Only finalists become manifests.

On the currently supported package surface, the system should behave as package-first and treat legacy projectile-only manifests as a losing outcome unless the prompt explicitly asks for:

- a homage weapon
- a simple vanilla-like projectile staff
- or some other intentionally non-package result

The expanded manifest should preserve a tight connection to the thesis:

- the package/loop must implement the thesis promise
- the presentation profile must reflect the spectacle ladder
- the legacy path should be heavily penalized on the eligible surface

The goal is to stop the lab from feeling like “pick one of three package skins.” Over time the supported runtime loop catalog must grow alongside the thesis search space.

## Art Thesis And Art Strategy

Each finalist should derive a `sprite_thesis` and `art_direction`.

### Sprite Thesis

- `hero_shape`
- `motif`
- `readability_goal`
- `spectacle_goal`
- `projectile_family`

### Art Direction

High-level controls only at first:

- `sprite_strategy`
- `detail_level`
- `contrast_profile`
- `reference_strength`
- `variant_budget`

The LLM should not control raw FAL parameters directly. It should choose a bounded art strategy, and the runtime should map that strategy to real generation settings.

## Hidden Sprite Audition

Pixelsmith should run its own hidden tournament.

For each finalist:

- generate multiple item sprite variants
- generate multiple projectile sprite variants if needed
- score them on silhouette readability, motif clarity, contrast, Terraria-scale punch, and item/projectile family coherence
- reject weak batches
- reroll if necessary

Only the winning art for the finalist continues.

## Deterministic Sprite Gates

The art path cannot rely on prose-only or caption-only judging.

Add deterministic gates for Terraria-scale readability such as:

- 1x silhouette readability
- sprite occupancy bounds
- handle/head or haft/crown separation where applicable
- projectile readability at Terraria-relevant size
- palette/value contrast floor
- off-center and background cleanup checks
- high-frequency noise and mushiness checks

Where practical, prefer image-derived gates or in-engine screenshots over text summaries.

## Cross-Consistency Gate

Before runtime validation, compare:

- user prompt
- weapon thesis
- final manifest
- item sprite
- projectile sprite

Reject finalists where the mechanic fantasy and the visual fantasy drift apart.

This gate should not be a prose-consistency check only. It should use image-aware checks where possible.

## Runtime Telemetry Contract

The hidden lab cannot validate behavior without first-class telemetry.

Define an explicit event schema with fields such as:

- `candidate_id`
- `package_key`
- `event_type`
- `timestamp_ms`
- `target_id`
- `stack_count`
- `seed_fired`
- `cashout_fired`
- `finisher_connected`
- `fx_marker`
- `audio_marker`
- `context_tag`

This schema must exist before the lab can truthfully claim that only winners are revealed.

## Hidden In-Game Lab Validation

The system should validate not only whether the weapon looks interesting, but whether it actually performs its promised loop.

Each finalist should carry a behavior contract derived from the thesis:

- `seed_event`
- `escalate_event`
- `cashout_event`
- `max_hits_to_cashout`
- `max_time_to_cashout_ms`
- `expected_fx_ladder`
- `expected_reliability_aid`

The runtime lab should then verify:

- did seed happen
- did escalation happen
- did cashout happen
- did it happen fast enough
- did finisher FX/audio trigger
- did the runtime behavior match the contract

Until runtime event telemetry exists, the hidden lab should be described as a prototype validation loop rather than a full winner-only gate.

## Research Evidence Layer

Research-informed prompting should be auditable, not merely intuitive.

Maintain a research evidence layer containing:

- source provenance
- distilled rules
- affected prompt fields
- affected judge fields
- anti-pattern mappings

Prompt revisions and judge-rule revisions should be treated as eval-triggering changes.

## Candidate Archive And Offline Eval

Persist hidden-run data for analysis and future offline evaluation.

Archive at least:

- prompt
- candidate theses
- manifest finalists
- art strategies
- judge scores
- rejection reasons
- reroll ancestry
- final winner rationale
- runtime contract results

Use this archive to build offline evals for:

- judge drift
- rank stability
- recovery-mode effectiveness
- cost per accepted winner
- future human-preference labeling

## Search Budgets And Stop Conditions

The hidden lab needs explicit search-budget rules.

Define per-run limits for:

- thesis batch count
- finalist count
- art variant count
- reroll depth
- mutation/crossbreed depth
- token budget
- image budget
- time budget

Also define:

- cache keys
- duplicate-candidate fingerprints
- early-stop rules
- when to widen search
- when to abort a run cleanly

Recovery mode should widen search diversity, not lower thresholds.

## Recovery Mode

When all candidates in a hidden batch are weak, the system should never lower standards.

Instead, recovery mode should:

- widen the search
- favor stranger player verbs
- favor rarer interaction patterns
- combine near-miss ideas
- mutate the best failed theses toward more surprising novelty

Recovery mode should increase novelty, not vagueness.

It should not excuse:

- unreadable chaos
- long opaque setup
- fake spectacle with no behavior change

## Prompt Writing Implications

Prompt writing should become research-informed and stage-specific.

### Weapon Thesis Prompting

Prompt text should explicitly bias toward:

- distinct player verbs
- readable escalation
- quick cash-out
- audiovisual signature
- movement or target-state interaction

### Manifest Expansion Prompting

Prompt text should preserve the chosen thesis rather than inventing a new combat identity downstream.

### Art Prompting

Prompt text should describe the sprite as a payoff-aware combat object, not only as a static fantasy prop. The prompt should know what the finisher fantasy is supposed to look and feel like.

## Evaluation Stack

The next iteration should use a layered evaluation stack:

1. deterministic thesis and manifest lints
2. calibrated model-based novelty and wow-factor judges
3. deterministic sprite-readability gates
4. hidden sprite audition judges
5. runtime behavior contract checks
6. human playtest only after the system already filtered weak candidates

## Non-Goals

This design does not require the first iteration to include:

- full free-form LLM-authored runtime code
- unrestricted raw FAL parameter control
- a production-safe guarantee that every generated weapon is balanced

The target is a stronger experimental lab, not a conservative shipping pipeline.

## Implementation Direction

The recommended implementation order is:

1. runtime capability matrix and telemetry event schema
2. candidate archive and ranking specification
3. research-informed thesis prompting
4. hidden thesis generation and calibrated judging
5. package-first finalist expansion
6. deterministic sprite-readability gates and hidden art audition
7. runtime behavior contract plumbing
8. pre-TUI winner selection only after all prior evidence exists
9. wild recovery mode, budgets, and offline evals

That sequence fixes the biggest current failure first: the system is still too willing to show the first valid but bland answer, and it does not yet have enough evidence to prove a candidate is truly a winner.
