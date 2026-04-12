# Weapon Lab Hidden Audition Design

Archived design summary for a winner-only weapon lab.

## Goal

Generate multiple hidden candidates, score them, validate them, and reveal only the winner.

## Core Ideas

- Do not reveal the first valid result.
- Favor readable payoff loops over generic projectile output.
- Judge mechanics, art, and runtime behavior separately.
- Keep enough evidence to explain why a candidate won or failed.

## Proposed Pipeline

1. Prompt enters the hidden lab.
2. Generate several compact weapon theses.
3. Hard-gate and rank those theses.
4. Expand finalists into manifests/packages.
5. Run hidden art generation and sprite gates.
6. Run cross-consistency and runtime validation.
7. Reveal only the winner.

## Thesis Requirements

Each thesis should capture:

- `fantasy`
- `player_verb`
- `seed`
- `escalate`
- `cashout`
- `time_to_payoff`
- `reliability_aid`
- `spectacle_ladder`
- `signature_sound`

## Ranking Rules

Prefer:

- clear `seed -> escalate -> cashout`
- visible escalation
- payoff in roughly `1-3s`
- runtime-supported novelty

Penalize:

- plain projectile spam
- hidden buildup
- unreliable payoff
- effects unsupported by the runtime

## Why This Was Compressed

The original file was useful as exploration, but most of its value was the handful of constraints above.
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
