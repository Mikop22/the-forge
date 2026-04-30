# The Forge — MCP + Skill Redesign

**Date:** 2026-04-30  
**Status:** Approved for planning

---

## Overview

Migrate The Forge from a standalone Python orchestration pipeline (OpenAI + Go TUI) to a Claude Code skill backed by a thin local MCP server. All LLM reasoning moves to Claude subagents. Python becomes pure execution — compile, FAL.ai sprite gen, file inject. FAL.ai stays for image generation.

---

## Goals

- Replace all OpenAI API calls with Claude subagents
- Keep FAL.ai FLUX.2 for sprite generation (quality is proven, audition pipeline stays)
- The conversation in Claude Code IS the interface — no separate TUI required
- Tier inference from natural language description — user never specifies a tier
- Model-per-stage selection to balance quality vs cost
- Archive the Go TUI and Python orchestrator — preserve code, disconnect from active pipeline

---

## Architecture

```
the-forge/
  .claude/
    skills/
      forge.md              ← skill: workflow, tier rules, all subagent prompts
    settings.json           ← registers local MCP server

  agents/
    mcp_server.py           ← 4 execution tools
    pixelsmith/             ← unchanged (FAL.ai Node.js runner stays)
    gatekeeper/             ← LLM calls removed, compile/inject logic stays
    core/                   ← paths, atomic IO, unchanged

  archive/
    BubbleTeaTerminal/      ← Go TUI (preserved, disconnected)
    orchestrator.py         ← old Python orchestrator
    architect/              ← old LLM agent code
    forge_master/           ← old LLM agent code
    run_pipeline_cli.py     ← old CLI entry point
```

---

## Generation Flow

**Rules:** MCP tools are only callable from the main Claude session — subagents return data, main Claude calls tools. `generation_id` is created by main Claude as a timestamp slug (`YYYYMMDD_HHMMSS`) at pipeline start, before any tool calls. It is passed explicitly to every tool and subagent that needs it.

```
User: "make a void pistol"

Main Claude
  │
  ├─ Infers tier → states it to user
  ├─ Creates generation_id = "20260430_214500"  ← timestamp slug, owned by main session
  │
  ├─ Spawns Architect-Thesis [Opus]
  │   In:  {prompt, tier, forbidden_patterns}
  │   Out: {concepts: [{name, fantasy, spectacle_plan, basis_atoms}] × 3}
  │   → Present to user; wait for pick
  │
  ├─ Spawns Architect-Manifest [Sonnet]
  │   In:  {winning_concept, tier, manifest_schema, tier1_omit_fields}
  │   Out: {manifest}   ← includes references.item.needed + references.projectile.needed
  │
  ├─ COMPILE LOOP  (global_attempts_used tracked by main session, max 6)
  │   ├─ Spawns Coder [Sonnet]
  │   │   In:  {manifest, compile_errors: [str], reviewer_issues: [str],
  │   │          attempt_number, global_attempts_used}
  │   │   Out: {cs_code}
  │   │
  │   ├─ Main calls forge_compile(cs_code, manifest, generation_id)
  │   │   Out: {status, errors: [str], artifact_path}
  │   │   → staging dir: agents/.forge_staging/<generation_id>/
  │   │   → on error + budget remaining: re-spawn Coder with compile_errors
  │   │   → on budget exhausted: surface to user
  │   │
  │   ├─ Spawns Reviewer [Sonnet]
  │   │   In:  {cs_code, manifest, critique_checklist}
  │   │   Out: {approved: bool, issues: [str]}
  │   │   → on fail + budget remaining: re-spawn Coder with reviewer_issues
  │   │   → on approve: exit loop
  │
  ├─ Reference-Finder [Opus] × 2  (only if manifest.references.<slot>.needed == true)
  │   In:  {slot, visual_description, weapon_fantasy, must_not_feel_like, generation_id}
  │   → WebSearch + WebFetch; downloads to agents/.forge_staging/<generation_id>/ref_<slot>.png
  │   Out: {reference_path: str|null, reasoning}
  │   → null if no suitable image found → text-to-image mode
  │
  ├─ Main calls forge_generate_sprite(description, size, animation_frames, kind,
  │                                    reference_path, generation_id) × 2
  │   → item:  description=manifest.visuals.description,      size=manifest.visuals.icon_size
  │   → proj:  description=manifest.projectile_visuals.description, size=manifest.projectile_visuals.icon_size,
  │             animation_frames parsed from manifest.projectile_visuals.animation_tier
  │   → Tool uploads reference_path to FAL storage before img2img call (via existing _upload_ref.mjs)
  │   Out: {status, candidate_paths: [3 local paths]}
  │
  ├─ Spawns Sprite-Judge [Opus]
  │   In:  {item_candidates: [path×3], projectile_candidates: [path×3], weapon_description}
  │   → Uses Read tool to view each image
  │   Out: {item_sprite: path, projectile_sprite: path, reasoning}
  │
  ├─ Main calls forge_status()
  │   → tModLoader not running → block inject, tell user
  │   → ForgeConnector offline → warn, ask user to confirm
  │
  └─ Main calls forge_inject(item_name, cs_code, manifest, item_sprite_path,
                              projectile_sprite_path, generation_id)
       → Atomically moves agents/.forge_staging/<generation_id>/ → ForgeGeneratedMod/Content/
       → Re-derives hjson from manifest; writes forge_inject.json
       → Deletes staging dir on success
       Out: {status, error_message, reload_required: true}
       → Tell user: item name, crafting recipe, "reload mods in tModLoader to spawn it"
```

## Stage Handoff Contracts

Canonical. Every section of this spec must match these exactly.

| Stage boundary | Payload |
|---|---|
| → Architect-Thesis | `{prompt, tier, forbidden_patterns: [str]}` |
| Architect-Thesis → Main | `{concepts: [{name, fantasy, spectacle_plan, basis_atoms}] × 3}` |
| → Architect-Manifest | `{winning_concept, tier, manifest_schema, tier1_omit_fields: [str]}` |
| Architect-Manifest → Main | `{manifest}` — includes `references.item.needed`, `references.projectile.needed` |
| → Coder | `{manifest, compile_errors: [str], reviewer_issues: [str], attempt_number, global_attempts_used}` |
| Coder → Main | `{cs_code}` |
| Main → forge_compile | `(cs_code, manifest, generation_id)` |
| forge_compile → Main | `{status, errors: [str], artifact_path}` |
| → Reviewer | `{cs_code, manifest, critique_checklist: [str]}` |
| Reviewer → Main | `{approved: bool, issues: [str]}` |
| → Reference-Finder | `{slot: "item"\|"projectile", visual_description, weapon_fantasy, must_not_feel_like: [str], generation_id}` |
| Reference-Finder → Main | `{reference_path: str\|null, reasoning}` |
| Main → forge_generate_sprite | `(description, size: [int,int], animation_frames: int, kind, reference_path: str\|null, generation_id)` |
| forge_generate_sprite → Main | `{status, candidate_paths: [str × 3]}` |
| → Sprite-Judge | `{item_candidates: [str × 3], projectile_candidates: [str × 3], weapon_description}` |
| Sprite-Judge → Main | `{item_sprite: str, projectile_sprite: str, reasoning}` |
| Main → forge_inject | `(item_name, cs_code, manifest, item_sprite_path, projectile_sprite_path, generation_id)` |
| forge_inject → Main | `{status, error_message, reload_required: true}` |

---

## MCP Tools (`agents/mcp_server.py`)

Four tools. All thin — no reasoning, no LLM calls. Signatures are canonical and match the Stage Handoff Contracts table exactly.

### `forge_compile(cs_code: str, manifest: dict, generation_id: str) → dict`
- Creates `agents/.forge_staging/<generation_id>/` if it does not exist
- Derives hjson deterministically from `manifest.item_name`, `manifest.display_name`, `manifest.tooltip` — the only place hjson is generated
- Writes cs_code + hjson to staging dir, triggers tModLoader build against staging
- Deletes staging directories older than 24h on each call (stale cleanup)
- Returns `{status: "success"|"error", errors: [str], artifact_path: str}`

### `forge_generate_sprite(description: str, size: list[int], animation_frames: int, kind: str, reference_path: str|None, generation_id: str) → dict`
- `kind`: `"item"` or `"projectile"`
- If `reference_path` is not None: uploads local file to FAL storage via `_upload_ref.mjs` before calling img2img endpoint
- If `reference_path` is None: calls text-to-image endpoint
- Pixelsmith internals (FAL Node.js runner, audition logic) unchanged
- Returns `{status: "success"|"error", candidate_paths: [str × 3]}`

### `forge_inject(item_name: str, cs_code: str, manifest: dict, item_sprite_path: str, projectile_sprite_path: str, generation_id: str) → dict`
- The ONLY tool that mutates live `ForgeGeneratedMod`
- Re-derives hjson from manifest (same logic as forge_compile — no drift between compile and inject)
- Atomically moves `agents/.forge_staging/<generation_id>/` contents into `ForgeGeneratedMod/Content/`
- Copies sprite files into `ForgeGeneratedMod/Content/Items/` and `Content/Projectiles/`
- Writes `forge_inject.json` to trigger ForgeConnector watcher
- Deletes staging dir on success
- Returns `{status: "success"|"error", error_message: str|None, reload_required: true}`

### `forge_status()`
- Reads `generation_status.json` and `forge_connector_alive.json`
- Returns `{pipeline_stage, forge_connector_alive: bool, tmodloader_running: bool}`
- Main Claude calls this before injecting
- Three offline states each produce a distinct user message:
  - MCP server unavailable: Claude Code surfaces a tool error — user must restart the server
  - tModLoader not running: warn user, inject is blocked until tModLoader is open
  - ForgeConnector offline (tModLoader open but mod disabled): warn user, ask to confirm before injecting

---

## Skill File (`forge.md`)

### Section 1 — Tier Inference

| Signal in description | Tier |
|---|---|
| "simple", "basic", "starter", no special mechanics | Tier 1 |
| Single special mechanic (homing, piercing, on-hit effect, on-hit buff) | Tier 2 |
| Charge phases, multi-projectile payoff, sweep/beam, orbital patterns, "forbidden" language | Tier 3 |

Claude infers tier and states it to the user before proceeding.

**Tier differences in the Architect-Manifest prompt:**

| Field | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| `mechanics_ir.atoms` | 1 atom max | 1-2 atoms | 3-6 atoms |
| `spectacle_plan.ai_phases` | omitted | 2 phases | 3-6 phases |
| `projectile_visuals.animation_tier` | `vanilla_frames` | `vanilla_frames` or `generated_frames:1` | `generated_frames:3` |
| `spectacle_plan.render_passes` | omitted | 1-2 passes | 3+ passes |

The manifest schema embedded in the Architect-Manifest prompt marks Tier 3-only fields as optional with a `// tier3 only` annotation so the subagent knows to omit them for Tier 1/2.

### Section 2 — Subagent Prompts

Each prompt is self-contained — no assumed context from the main session.

**Architect-Thesis [Opus]**
- Full Terraria weapon design context
- Forbidden patterns: no plain fireball feel, no bullet-feel projectiles, no generic dust trail
- Must produce exactly 3 named concepts, each with: name, one-sentence fantasy, spectacle plan, basis atoms

**Architect-Manifest [Sonnet]**
- Receives: winning concept + tier + manifest_schema + tier1_omit_fields list
- Produces: full manifest JSON including `references.item.needed: bool` and `references.projectile.needed: bool` — set true only when the visual description is unusual enough that a real-world reference image would meaningfully help (e.g. a specific blade shape, unusual silhouette, real object being stylized)
- Schema is embedded in the prompt with `// tier3 only` annotations on optional fields
- For Tier 1: prompt explicitly instructs to omit `spectacle_plan.ai_phases`, `spectacle_plan.render_passes`, and `mechanics_ir` entirely — do not supply empty arrays or stub values

**Coder [Sonnet]**
- Receives: manifest JSON, reviewer_issues (empty on first attempt), attempt_number, global_attempts_used
- Terraria modding rules, forbidden API calls, namespace requirements
- Generates cs_code only (ModItem + ModProjectile) — hjson is derived deterministically by forge_compile from manifest, NOT generated by Coder
- Returns {cs_code} — main Claude calls forge_compile, passes errors back in next Coder spawn
- Global compile budget: 6 attempts across all reviewer loops (tracks via global_attempts_used field in prompt)

**Reviewer [Sonnet]**
- Receives: cs_code + manifest
- Deterministic checklist: namespace match, no banned APIs, hitbox validity, projectile spawn patterns, AmmoID vs ProjectileID rules
- Returns: approved or list of specific issues

**Reference-Finder [Opus]**
- Receives: slot ("item" or "projectile"), visual_description, weapon_fantasy, must_not_feel_like list
- Uses WebSearch + WebFetch — searches for real-world concept art, game art, or object photography that best matches the weapon's visual intent
- Selection criteria (in priority order):
  1. Isolated subject on a clean or transparent background
  2. Silhouette and color palette aligns with the visual description
  3. Not a recognisable vanilla Terraria item or common reskin
  4. High enough resolution that shape and color read clearly
  5. Avoids anything on the must_not_feel_like list
- Downloads chosen image to `agents/.forge_staging/<generation_id>/ref_<slot>.png`
- Returns `{reference_path: str|null, reasoning: str}` — null if no suitable image found (Pixelsmith falls back to text-to-image)
- Never returns a reference image it cannot actually download and verify

**Sprite-Judge [Opus]**
- Receives: all candidate image paths (item + projectile candidates)
- Uses the Read tool to view each image before judging
- Pixel art quality criteria: clean silhouette, readable at 2x, Terraria palette feel
- Must not feel like: generic fireball, plain bullet, vanilla item reskin
- Returns: selected item_path + projectile_path with brief reasoning per pick

### Section 3 — Orchestration Rules

- Always state inferred tier to user before starting
- Present thesis concepts as a numbered list, wait for user pick unless they said "you choose"
- Compile loop and reviewer loop are silent — only surface to user on final failure
- After inject: report item name, crafting recipe (material × cost at tile), and one-line description of what to expect in-game
- If `forge_status` shows ForgeConnector offline: warn before injecting, don't block

### Section 4 — Error Escalation

**Global compile budget: 6 attempts total** — shared across compile errors and reviewer-triggered re-codes.

| Attempt | Trigger | Behaviour |
|---|---|---|
| 1 | First codegen | Silent — spawn Coder, compile, continue |
| 2 | Compile error | Silent — spawn fresh Coder with compile_errors, retry |
| 3 | Compile error or reviewer fail | Silent — spawn fresh Coder with errors, retry |
| 4 | Compile error or reviewer fail | Notify user: "Still fixing compile issues (attempt 4/6)…" — continue |
| 5 | Compile error or reviewer fail | Notify user: "Attempt 5/6 — here are the remaining errors: …" — continue |
| 6 | Compile error or reviewer fail | Surface full error to user, ask continue/abort |

**Other failures:**

| Failure | Behaviour |
|---|---|
| FAL.ai failure | Tell user, offer procedural fallback sprite |
| ForgeConnector offline | Warn user, ask to confirm before inject |
| tModLoader not running | Block inject, tell user to open tModLoader first |

---

## Model Assignment

| Stage | Model | Reason |
|---|---|---|
| Architect-Thesis | `opus` | Creative concept generation, weapon distinctiveness |
| Architect-Manifest | `sonnet` | Structured JSON expansion |
| Coder | `sonnet` | Strong code generation, fast iteration |
| Reviewer | `sonnet` | Rule-checking against known list |
| Reference-Finder | `opus` | Best web search reasoning + visual judgment for reference selection |
| Sprite-Judge | `opus` | Improved vision for pixel art quality comparison |

---

## What Gets Archived

Before archiving, the following must be extracted into active modules to avoid breaking `gatekeeper.py` at import time:

| Extract from | Extract to | What |
|---|---|---|
| `forge_master/compilation_harness.py` | `core/compilation_harness.py` | tModLoader build invocation |
| `forge_master/forge_master.py` (hjson gen) | `core/hjson_gen.py` | Deterministic HJSON generation |
| `forge_master/critique.py` (rule list) | `core/critique_rules.py` | Deterministic critique checklist as plain data |
| `architect/models.py` (shared types) | `core/manifest_models.py` | Pydantic models used by gatekeeper |

Once extracted and gatekeeper imports updated, archive:

- `BubbleTeaTerminal/` → `archive/BubbleTeaTerminal/`
- `agents/orchestrator.py` → `archive/`
- `agents/architect/` → `archive/architect/`
- `agents/forge_master/` → `archive/forge_master/`
- `agents/run_pipeline_cli.py` → `archive/`
- `agents/stress_tier3_*.py` → `archive/`

Kept active: `agents/pixelsmith/`, `agents/gatekeeper/`, `agents/core/`, `agents/mcp_server.py`

---

## What Does NOT Change

- ForgeConnector C# mod — watcher pattern stays identical
- FAL.ai FLUX.2 runner and audition pipeline
- Deterministic critique rules (move from `critique.py` into the Reviewer prompt)
- tModLoader build system and file layout
- `forge_inject.json` contract between Python and ForgeConnector

---

## MCP Server Lifecycle

**Startup:** `mcp_server.py` is registered in `.claude/settings.json` under `mcpServers`. Claude Code starts it automatically when a session opens in this project directory. No manual start required.

**Health:** The server exposes a no-op `forge_status()` call that always responds — if it fails, Claude Code surfaces a tool error with the message "Forge MCP server is not running. Restart Claude Code or run `python agents/mcp_server.py` manually."

**Graceful failures by offline state:**

| State | Tool response | Claude behaviour |
|---|---|---|
| MCP server process dead | Tool call throws | Claude tells user to restart Claude Code |
| tModLoader not running | `{tmodloader_running: false}` | Claude blocks inject, tells user to open tModLoader |
| ForgeConnector disabled | `{forge_connector_alive: false}` | Claude warns, asks user to confirm before injecting |
| FAL.ai unreachable | `forge_generate_sprite` returns error | Claude tells user, offers procedural fallback sprite |

**Shutdown:** Server exits automatically when the Claude Code session closes. No cleanup needed — it holds no state beyond in-flight tool calls.

---

## Success Criteria

- `forge.md` skill + `mcp_server.py` replaces the full Python orchestration pipeline
- Zero OpenAI API calls in the active codebase
- A Tier 3 weapon generates end-to-end from a natural language description in Claude Code
- Compile errors surface and are fixed without user intervention (within retry budget)
- Sprite audition produces a judge-selected result via Opus vision
- ForgeConnector injection works identically to today
