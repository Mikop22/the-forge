# The Forge — Complete Agent Pipeline Flow

> A detailed walkthrough of every agent, data contract, retry loop, and external call
> in the AI-powered Terraria mod generation pipeline.

---

## Table of Contents

1. [High-Level DAG](#1-high-level-dag)
2. [Entry Point: Go TUI + Watchdog Daemon](#2-entry-point-go-tui--watchdog-daemon)
3. [Step A: Status Handshake — "building"](#3-step-a-status-handshake--building)
4. [Step B: Architect Agent (Sequential)](#4-step-b-architect-agent-sequential)
5. [Step C: Coder + Artist (Parallel)](#5-step-c-coder--artist-parallel)
6. [Step D: Gatekeeper Integrator (Sequential)](#6-step-d-gatekeeper-integrator-sequential)
7. [Step E: Status Handshake — "ready" / "error"](#7-step-e-status-handshake--ready--error)
8. [Data Contracts Between Agents](#8-data-contracts-between-agents)
9. [Retry and Self-Healing Summary](#9-retry-and-self-healing-summary)
10. [External Service Calls](#10-external-service-calls)
11. [Environment Variables](#11-environment-variables)
12. [File System Outputs](#12-file-system-outputs)
13. [Known Gaps and Eval Considerations](#13-known-gaps-and-eval-considerations)

---

## 1. High-Level DAG

```
Go TUI (Bubble Tea)
  │  writes user_request.json
  ▼
orchestrator.py  (watchdog daemon, asyncio loop)
  │
  ├── Step A: _set_building()  →  generation_status.json {"status":"building"}
  │
  ├── Step B: ArchitectAgent.generate_manifest(prompt, tier)
  │             → ItemManifest dict  (the universal contract)
  │
  ├── Step C: [parallel via asyncio.gather]
  │   ├── CoderAgent.write_code(manifest)   → ForgeOutput dict (cs_code, hjson_code)
  │   └── ArtistAgent.generate_asset(manifest) → PixelsmithOutput dict (sprite paths)
  │
  ├── Step D: Integrator.build_and_verify(forge_output, sprite_path)
  │             → stages files → tModLoader build → self-heal loop
  │
  └── Step E: _set_ready(item_name)  →  generation_status.json {"status":"ready"}
```

**Key architectural properties:**
- Agents communicate exclusively via `dict` (Pydantic `.model_dump()` on send, `.model_validate()` on receive).
- Steps B, C, D are sequential boundaries; only the Coder and Artist within Step C run in parallel.
- Every `RuntimeError` raised by any agent is caught by the orchestrator and reported to the TUI as `{"status":"error"}`.

---

## 2. Entry Point: Go TUI + Watchdog Daemon

**File:** `orchestrator.py`

### How it starts

```
python orchestrator.py
```

This creates a `watchdog.Observer` watching the tModLoader ModSources directory for file modifications.

### What triggers a pipeline run

1. The Go TUI writes `user_request.json` to `~/Documents/My Games/Terraria/tModLoader/ModSources/`.
2. The `_RequestHandler.on_modified()` callback fires.
3. A 1.0-second debounce prevents duplicate triggers (common with file save events).
4. The request JSON is parsed:
   ```json
   { "prompt": "A sword that shoots fireballs", "tier": "Tier1_Starter" }
   ```
5. `run_pipeline(request)` is scheduled on the asyncio event loop via `loop.create_task()`.

### Concurrency model

- An `asyncio.Lock` serializes pipeline runs — only one request processes at a time.
- If a second write arrives while a pipeline is running, it queues behind the lock.

### Error handling at this level

- JSON parse failures → `_set_error()` immediately.
- Missing `prompt` field → `ValueError` → caught by `_run_safe()` → `_set_error()`.
- Any agent `RuntimeError` → caught by `_run_safe()` → `_set_error()`.

---

## 3. Step A: Status Handshake — "building"

**File:** `orchestrator.py:62-63`

```python
def _set_building():
    _write_status({"status": "building"})
```

Written atomically (`.tmp` → `.replace()`) to `generation_status.json` in the ModSources directory. The Go TUI polls this file and displays a spinner.

---

## 4. Step B: Architect Agent (Sequential)

**Files:** `architect/architect.py`, `architect/models.py`, `architect/prompts.py`, `architect/reference_finder.py`, `architect/reference_policy.py`

### Purpose

Convert a natural-language prompt + tier into a fully balanced, validated `ItemManifest` — the universal contract consumed by all downstream agents.

### Internal flow

```
generate_manifest(prompt, tier)
  │
  ├── 1. resolve_crafting(prompt, tier)         [deterministic, no LLM]
  │     Scans THEME_MATERIAL_MAP for keyword matches (fire→HellstoneBar, etc.)
  │     Falls back to tier default materials
  │     Returns: { crafting_material, crafting_cost, crafting_tile }
  │
  ├── 2. LCEL chain invocation                   [LLM call #1]
  │     ChatPromptTemplate → ChatOpenAI.with_structured_output(LLMItemOutput)
  │     Model: gpt-5-nano-2025-08-07
  │     Template vars: user_prompt, selected_tier, damage_min/max, use_time_min/max
  │     Returns: LLMItemOutput (unclamped Pydantic model)
  │
  ├── 3. Merge LLM output + deterministic crafting
  │     data["mechanics"].update(crafting)
  │
  ├── 4. ReferencePolicy.resolve()               [0-2 LLM calls + 0-2 Bing searches]
  │     If reference_needed or prompt implies reference:
  │       BrowserReferenceFinder.find_candidates() → Bing Images via Playwright
  │       HybridReferenceApprover.approve() → LLM picks best image or rejects all
  │       Up to 2 search+approve attempts (max_retries=1)
  │     Returns: { generation_mode, reference_image_url, reference_attempts, reference_notes }
  │
  ├── 5. _enforce_reference_fidelity_prompting()  [deterministic]
  │     If generation_mode == "image_to_image":
  │       Appends fidelity clause to visuals.description
  │       Appends consistency clause to projectile_visuals.description
  │
  └── 6. ItemManifest.model_validate(data, context={"tier": tier})
        Clamps damage to tier range (e.g. Tier1: 8-15)
        Clamps use_time to tier range (e.g. Tier1: 20-30)
        Forces rarity to tier-defined value
        Sanitizes item_name to PascalCase
        Normalizes reference fields (clears URL if reference_needed=False)
        Returns: ItemManifest.model_dump() → dict
```

### Tier balance table

| Tier | Damage | Use Time | Rarity | Crafting Tile |
|------|--------|----------|--------|---------------|
| Tier1_Starter  | 8–15   | 20–30 | White  | WorkBenches |
| Tier2_Dungeon  | 25–40  | 18–25 | Orange | Anvils |
| Tier3_Hardmode | 45–65  | 15–22 | Pink   | Anvils |
| Tier4_Endgame  | 150–300| 8–15  | Red    | Anvils |

### Reference image pipeline (optional path)

```
LLM decides reference_needed=True, reference_subject="Master Sword"
  │
  ├── BrowserReferenceFinder._search("Master Sword pixel art sprite")
  │     → Bing Images via Playwright browser
  │     → Score each result: pixel art +30, sprite +24, plain bg +18, clutter -15
  │     → Return top 3 ReferenceCandidate objects
  │
  └── HybridReferenceApprover.approve(candidates)
        → LLM (with_structured_output) picks best or rejects all
        → Fallback if LLM unavailable: accept top if score >= 20
        → If rejected: retry with different search query (up to max_retries+1 attempts)
        → If all rejected: generation_mode falls back to "text_to_image"
```

### Error modes

| Failure | Outcome |
|---------|---------|
| Invalid tier | `ValueError` raised → orchestrator catches → `_set_error()` |
| LLM chain fails | Exception bubbles → orchestrator catches |
| Browser search fails | `find_candidates()` returns `[]` → falls back to text_to_image |
| LLM approver fails | Falls back to top candidate if score >= 20, else text_to_image |
| LLM returns out-of-range stats | Clamped silently by `Stats.clamp_to_tier()` |

---

## 5. Step C: Coder + Artist (Parallel)

Both agents receive the same `ItemManifest` dict and run simultaneously via `asyncio.gather`.

```python
coder_future = loop.run_in_executor(None, coder.write_code, manifest)
artist_future = loop.run_in_executor(None, artist.generate_asset, manifest)
code_result, art_result = await asyncio.gather(coder_future, artist_future)
```

### 5a. CoderAgent (Forge Master)

**Files:** `forge_master/forge_master.py`, `forge_master/templates.py`, `forge_master/prompts.py`, `forge_master/models.py`

#### Purpose

Generate compilable tModLoader 1.4.4 C# source code and HJSON localization from the manifest.

#### Internal flow

```
write_code(manifest)
  │
  ├── 1. ForgeManifest.model_validate(manifest)
  │
  ├── 2. Look up sub_type mappings
  │     DAMAGE_CLASS_MAP: Sword→DamageClass.Melee, Gun→DamageClass.Ranged, etc.
  │     USE_STYLE_MAP: Sword→ItemUseStyleID.Swing, Gun→ItemUseStyleID.Shoot, etc.
  │
  ├── 3. get_reference_snippet(sub_type, custom_projectile)
  │     Returns a complete, correct C# template for the weapon type
  │     6 base templates: Sword, Gun, Staff, Bow, Summon, Whip
  │     + CUSTOM_PROJECTILE_TEMPLATE appended when custom_projectile=True
  │
  ├── 4. LCEL gen chain invocation                [LLM call]
  │     build_codegen_prompt() → ChatOpenAI.with_structured_output(CSharpOutput)
  │     Model: gpt-5.2-2025-12-11
  │     Template vars: manifest_json, damage_class, use_style, reference_snippet
  │     System prompt includes 5 absolute rules + allowed imports list
  │
  ├── 5. _strip_markdown_fences(code)              [deterministic]
  │
  ├── 6. validate_cs(cs_code)                      [deterministic]
  │     BANNED_PATTERNS (10 rules):
  │       - ModRecipe (1.3 API)
  │       - item.melee/ranged/magic/summon (1.3 API)
  │       - System.Drawing (crashes tML)
  │       - Old OnHitNPC(NPC, int, float, bool) signature
  │       - mod.GetItem<T> (1.3 API)
  │       - Minion penetrate > 0 (must be -1)
  │       - etc.
  │     REQUIRED_PATTERNS (5 rules):
  │       - using Terraria
  │       - using Terraria.ID
  │       - using Terraria.ModLoader
  │       - : ModItem
  │       - SetDefaults()
  │     Context-sensitive checks:
  │       - ModProjectile OnHitNPC must not have Player parameter
  │       - ModContent.BuffType<T>() requires T defined in same file
  │
  ├── 7. Repair loop (up to 3 attempts)            [0-3 LLM calls]
  │     while violations and attempt < 3:
  │       repair_chain.invoke(original_code, "VALIDATION ERRORS:\n" + violations)
  │       _strip_markdown_fences()
  │       validate_cs() again
  │
  ├── 8. If still invalid after 3 attempts:
  │     Return ForgeOutput(status="error", error=ForgeError("VALIDATION", ...))
  │
  └── 9. _generate_hjson(item_name, display_name, tooltip)  [deterministic]
        Produces localization block:
        Mods: { ForgeGeneratedMod: { Items: { ItemName: { DisplayName: ... Tooltip: ... } } } }
        Return ForgeOutput(cs_code, hjson_code, status="success")
```

#### fix_code() — used by Gatekeeper's self-heal loop

```
fix_code(error_log, original_code)
  │
  └── Same repair chain, up to 3 attempts
      On success: ForgeOutput(cs_code=repaired, status="success")
      On failure: ForgeOutput(status="error", error=ForgeError(code, message))
```

#### Error modes

| Failure | Outcome |
|---------|---------|
| LLM generates 1.3 API code | Caught by `validate_cs()` → repair loop |
| Repair loop exhausts 3 attempts | Returns `status="error"` (no exception) |
| LLM returns markdown-wrapped code | Stripped by `_strip_markdown_fences()` |

### 5b. ArtistAgent (Pixelsmith)

**Files:** `pixelsmith/pixelsmith.py`, `pixelsmith/image_processing.py`, `pixelsmith/armor_compositor.py`, `pixelsmith/models.py`, `pixelsmith/fal_flux2_runner.mjs`

#### Purpose

Generate game-ready pixel art sprite PNGs from the manifest's visual specification.

#### Internal flow

```
generate_asset(manifest)
  │
  ├── 1. PixelsmithInput.model_validate(manifest)
  │     Extracts: item_name, type, visuals, projectile_visuals,
  │               generation_mode, reference_image_url
  │
  ├── 2. _resolve_generation_mode()
  │     image_to_image requested + URL present + env flag enabled → use img2img
  │     Otherwise → fall back to text_to_image (silent, no error)
  │
  ├── 3. Branch by item type:
  │
  │   ┌─ type == "Armor":
  │   │   _generate_armor(parsed)
  │   │     build_prompt(visuals.description)
  │   │     _run_pipeline(prompt, mode, ref_url, endpoint)    [fal-ai API call]
  │   │     remove_background(raw_image)                       [rembg U²-Net]
  │   │     downscale(texture, 40×56)                          [nearest-neighbor]
  │   │     composite_armor(texture) → 40×1120 px 20-frame sheet
  │   │     Save: output/{ItemName}_Body.png
  │   │
  │   └─ type != "Armor":
  │       _generate_standard_item(parsed)
  │         build_prompt(visuals.description)
  │         _run_pipeline(prompt, mode, ref_url, endpoint)    [fal-ai API call]
  │         remove_background(raw_image)                       [rembg U²-Net]
  │         downscale(processed, icon_size e.g. 32×32)        [nearest-neighbor]
  │         Save: output/{ItemName}.png
  │
  ├── 4. If projectile_visuals is present:
  │     _generate_projectile(parsed, raw_manifest)
  │       build_prompt(projectile_visuals.description)
  │       _run_pipeline(prompt, mode, ref_url, endpoint)      [fal-ai API call]
  │       remove_background → downscale(proj_icon_size e.g. 16×16)
  │       Extract projectile name from manifest.mechanics.shoot_projectile
  │         regex: ModContent.ProjectileType<(\w+)>
  │         fallback: {item_name}Projectile
  │       Save: output/{ProjectileName}.png
  │
  └── 5. Return PixelsmithOutput(item_sprite_path, projectile_sprite_path, status)
```

#### _run_pipeline() — the fal-ai bridge

```
_run_pipeline(prompt, generation_mode, reference_image_url, endpoint)
  │
  ├── 1. Build fal input payload:
  │     { prompt, guidance_scale: 5, num_inference_steps: 28,
  │       image_size: {512, 512}, num_images: 1, ... }
  │     If img2img: add image_url + strength: 0.45
  │
  ├── 2. Write payload to tempfile as JSON
  │
  ├── 3. subprocess.run(["node", "fal_flux2_runner.mjs", payload.json])
  │     Environment: FAL_KEY injected
  │
  └── 4. fal_flux2_runner.mjs:
        fal.subscribe(endpoint, { input })  →  polls fal-ai cloud
        Downloads result image URL → writes to output_path
        Python reads the PNG → returns PIL Image (RGBA)
```

#### Prompt construction

```python
POSITIVE_TEMPLATE = (
    "pixel art sprite, {description}, plain white background, centered, "
    "hard edges, terraria game style, 2D, no anti-aliasing, "
    "clean silhouette, high contrast{lora_trigger}"
)
# {lora_trigger} = ", aziib" if local LoRA is loaded, else ""
```

#### Error modes

| Failure | Outcome |
|---------|---------|
| Manifest validation fails | Returns `PixelsmithOutput(status="error", error=("VALIDATION", ...))` |
| FAL_KEY missing | `RuntimeError` in `__init__` → orchestrator catches |
| Node.js subprocess fails | `RuntimeError("fal runner failed: ...")` → caught → status="error" |
| No output file after subprocess | `RuntimeError` → caught → status="error" |
| img2img without URL or disabled | Silent fallback to text_to_image |

---

## 6. Step D: Gatekeeper Integrator (Sequential)

**Files:** `gatekeeper/gatekeeper.py`, `gatekeeper/models.py`

### Purpose

Stage all generated files into the tModLoader ModSources directory, run the real headless build, and self-heal via the CoderAgent if compilation fails.

### Prerequisites check

The orchestrator validates both Coder and Artist succeeded before calling the Gatekeeper:

```python
if code_result.get("status") != "success":
    raise RuntimeError(f"CoderAgent failed [{err}]")
if art_result.get("status") != "success":
    raise RuntimeError(f"ArtistAgent failed [{err}]")
```

The orchestrator passes the same `CoderAgent` instance to the Integrator (for repair calls):

```python
integrator = Integrator(coder=coder)
gate_result = integrator.build_and_verify(
    forge_output=code_result,
    sprite_path=art_result.get("item_sprite_path"),
)
```

### Internal flow

```
build_and_verify(forge_output, sprite_path)
  │
  ├── 1. Validate forge_output is not status="error"
  │     If error: return GatekeeperResult(status="error") immediately
  │
  ├── 2. _extract_item_name(cs_code)
  │     Regex: class (\w+)\s*:\s*ModItem
  │     If not found: return error immediately
  │
  ├── 3. _write_status({"status": "building"})
  │     Writes generation_status.json in mod root (ForgeGeneratedMod/)
  │
  ├── 4. _stage_files(cs_code, hjson_code, item_name, sprite_path)
  │     ├── Write Content/Items/{ItemName}.cs
  │     ├── Copy sprite to Content/Items/{ItemName}.png (if provided)
  │     ├── _merge_hjson(hjson_code, item_name)
  │     │     ├── If en-US.hjson doesn't exist: create it
  │     │     ├── If item block exists in file: replace it (regex)
  │     │     └── If item block is new: insert before Items closing brace
  │     └── _ensure_build_files()
  │           ├── Create build.txt if missing (never overwrite)
  │           └── Create description.txt if missing (never overwrite)
  │
  ├── 5. Build + self-heal loop
  │     for attempt in range(1, _MAX_RETRIES + 2):  # attempts 1..4
  │       │
  │       ├── _run_tmod_build()
  │       │     subprocess.run(["dotnet", tModLoader.dll, "-build", "ForgeGeneratedMod", "-eac"])
  │       │     cwd = ModSources parent directory
  │       │     Returns CompileResult(success, output)
  │       │
  │       ├── If success:
  │       │     _write_status({"status": "ready", ...})
  │       │     Return GatekeeperResult(status="success", item_name, attempts)
  │       │
  │       ├── If failure:
  │       │     _parse_errors(output) → list[RoslynError]
  │       │       Regex: file(line,col): error CSxxxx: message
  │       │
  │       │     If attempt > _MAX_RETRIES (i.e. attempt 4):
  │       │       _write_status({"status": "error", "error_code": ..., ...})
  │       │       Return GatekeeperResult(status="error", errors, error_message)
  │       │
  │       │     coder.fix_code(error_log=output, original_code=cs_code)  [LLM calls]
  │       │
  │       │     If fix_code returns error:
  │       │       Return GatekeeperResult(status="error", "CoderAgent repair failed.")
  │       │
  │       └──   cs_code = repaired code
  │             _stage_files(cs_code, hjson_code, item_name, sprite_path=None)
  │             → loop back to build
  │
  └── Note: Lazy-loads CoderAgent if none was passed to __init__
```

### Total possible build attempts

- 1 initial build + up to 3 retries = **4 total tModLoader builds**
- Each retry involves the CoderAgent's `fix_code()` which itself does up to 3 LLM repair attempts
- **Worst case:** 4 builds × (1 + 3 LLM repairs per retry) = 4 builds + 9 LLM calls

### Error modes

| Failure | Outcome |
|---------|---------|
| forge_output has status="error" | Return error immediately (0 builds) |
| No ModItem class in C# | Return error immediately (0 builds) |
| Build fails, repair succeeds | Continue loop (retry build) |
| Build fails, repair fails | Return error (abort loop) |
| 4 builds all fail | Return error with last Roslyn errors |
| tModLoader DLL not found | `_tmod_dll` is None → subprocess will fail → error |

---

## 7. Step E: Status Handshake — "ready" / "error"

**File:** `orchestrator.py:66-79`

### On success

```python
_set_ready(item_name)
# Writes: {"status": "ready", "batch_list": ["ItemName"], "message": "Compilation successful..."}
```

### On any failure

```python
_set_error(str(exc))
# Writes: {"status": "error", "error_code": "PIPELINE_FAIL", "message": "The pipeline collapsed: ..."}
```

### Status file locations

There are **two** places status is written (potential eval concern):

1. **Orchestrator** writes to `~/Documents/.../ModSources/generation_status.json` (root of ModSources)
2. **Gatekeeper** writes to `~/Documents/.../ModSources/ForgeGeneratedMod/generation_status.json` (inside the mod)

The orchestrator writes atomically (`.tmp` → `.replace()`). The Gatekeeper writes directly (non-atomic). The TUI presumably reads one of these — verify which.

---

## 8. Data Contracts Between Agents

### user_request.json → Orchestrator

```json
{ "prompt": "A fire sword that shoots meteors", "tier": "Tier2_Dungeon" }
```

### Orchestrator → Architect

```python
architect.generate_manifest(prompt="A fire sword...", tier="Tier2_Dungeon")
```

### Architect → Coder + Artist (ItemManifest dict)

```json
{
  "item_name": "MeteorBlade",
  "display_name": "Meteor Blade",
  "tooltip": "Calls down the fury of the heavens.",
  "type": "Weapon",
  "sub_type": "Sword",
  "stats": {
    "damage": 32,
    "knockback": 5.5,
    "crit_chance": 4,
    "use_time": 22,
    "auto_reuse": true,
    "rarity": "ItemRarityID.Orange"
  },
  "visuals": {
    "color_palette": ["#FF4500", "#FFD700"],
    "description": "A blazing sword wreathed in flame, trailing embers.",
    "icon_size": [32, 32]
  },
  "mechanics": {
    "shoot_projectile": "ProjectileID.MeteorShot",
    "on_hit_buff": "BuffID.OnFire",
    "custom_projectile": false,
    "crafting_material": "ItemID.HellstoneBar",
    "crafting_cost": 15,
    "crafting_tile": "TileID.Anvils"
  },
  "projectile_visuals": null,
  "generation_mode": "text_to_image",
  "reference_image_url": null,
  "reference_needed": false,
  "reference_subject": null,
  "reference_attempts": 0,
  "reference_notes": "reference_not_requested"
}
```

### Coder → Gatekeeper (ForgeOutput dict)

```json
{
  "cs_code": "using Terraria;\nusing Terraria.ID;\n...",
  "hjson_code": "Mods: {\n\tForgeGeneratedMod: {...}\n}",
  "status": "success",
  "error": null
}
```

### Artist → Orchestrator (PixelsmithOutput dict)

```json
{
  "item_sprite_path": "/Users/.../agents/output/MeteorBlade.png",
  "projectile_sprite_path": null,
  "status": "success",
  "error": null
}
```

### Gatekeeper → Orchestrator (GatekeeperResult dict)

```json
{
  "status": "success",
  "item_name": "MeteorBlade",
  "attempts": 1,
  "errors": null,
  "error_message": null
}
```

---

## 9. Retry and Self-Healing Summary

| Stage | What can fail | Retry mechanism | Max attempts | Fallback |
|-------|--------------|-----------------|--------------|----------|
| Architect: reference search | Browser search fails / no good images | Retry with different query | 2 (max_retries=1) | Fall back to text_to_image |
| Architect: reference approval | LLM rejects all candidates | Retry search+approve loop | 2 | Fall back to text_to_image |
| Coder: code generation | LLM hallucinates 1.3 API | `validate_cs()` → repair chain | 3 | Return status="error" |
| Coder: fix_code (Gatekeeper repair) | Repair still has violations | Repair chain loop | 3 | Return status="error" |
| Gatekeeper: tModLoader build | Roslyn compilation error | Call coder.fix_code() → re-stage → rebuild | 3 retries (4 total builds) | Return status="error" |
| Artist: image generation | fal-ai fails | None — no retry | 1 | Return status="error" |
| Artist: img2img mode | URL missing or flag disabled | None | 1 | Silent fallback to text_to_image |

### Worst-case LLM calls per pipeline run

| Agent | Scenario | LLM calls |
|-------|----------|-----------|
| Architect | Manifest generation | 1 |
| Architect | Reference approval (2 attempts) | 2 |
| Coder | Code generation | 1 |
| Coder | validate_cs repair loop (3 attempts) | 3 |
| Gatekeeper | 3 retries × fix_code (3 attempts each) | 9 |
| **Total worst case** | | **16 LLM calls** |

---

## 10. External Service Calls

| Service | Protocol | Agent | When | Rate-limiting? |
|---------|----------|-------|------|----------------|
| OpenAI API (GPT-5-nano) | HTTPS via LangChain | Architect | Manifest generation, reference approval | Per OpenAI account limits |
| OpenAI API (GPT-5.2) | HTTPS via LangChain | Coder | Code gen, repair | Per OpenAI account limits |
| Bing Images | HTTPS via Playwright | Architect | Reference image search | N/A (browser scraping) |
| fal-ai FLUX.2 Klein | HTTPS via Node.js | Artist | Image generation | Per fal-ai plan |
| dotnet (tModLoader) | Local subprocess | Gatekeeper | Mod compilation | N/A (local) |
| dotnet (standalone) | Local subprocess | CompilationHarness (tests) | Fast pre-validation | N/A (local) |

---

## 11. Environment Variables

| Variable | Required | Default | Used By |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes | — | Architect, CoderAgent |
| `FAL_KEY` or `FAL_API_KEY` | Yes | — | ArtistAgent, fal_flux2_runner.mjs |
| `FAL_IMAGE_TO_IMAGE_ENABLED` | No | `false` | ArtistAgent |
| `FAL_IMAGE_TO_IMAGE_ENDPOINT` | No | same as base endpoint | ArtistAgent |
| `TMODLOADER_PATH` | No | Auto-detected via Steam paths | CompilationHarness, Integrator |
| `MOD_SOURCE_PATH` | No | `~/Documents/.../ModSources/ForgeGeneratedMod/` | Integrator |

---

## 12. File System Outputs

### Generated artifacts (output/ directory)

```
agents/output/
├── {ItemName}.png                  # Item sprite (32×32 default)
├── {ProjectileName}.png            # Projectile sprite (16×16 default, if custom)
└── {ItemName}_Body.png             # Armor sheet (40×1120, if type=Armor)
```

### Staged mod files (tModLoader ModSources)

```
~/Documents/My Games/Terraria/tModLoader/ModSources/ForgeGeneratedMod/
├── build.txt                       # Created once, never overwritten
├── description.txt                 # Created once, never overwritten
├── generation_status.json          # Written by Gatekeeper
├── Content/
│   └── Items/
│       ├── {ItemName}.cs           # C# source
│       └── {ItemName}.png          # Sprite (copied from output/)
└── Localization/
    └── en-US.hjson                 # Merged localization
```

### Status file (ModSources root)

```
~/Documents/My Games/Terraria/tModLoader/ModSources/
├── user_request.json               # Written by Go TUI, read by orchestrator
└── generation_status.json          # Written by orchestrator (atomic)
```

---

## 13. Known Gaps and Eval Considerations

### Potential issues to verify

1. **Dual status file writes.** Both the orchestrator (`ModSources/generation_status.json`) and the Gatekeeper (`ForgeGeneratedMod/generation_status.json`) write status files. If the TUI reads from the wrong location, it could miss updates. Verify which path the Go TUI actually watches.

2. **Artist has no retry logic.** If fal-ai returns a bad image (e.g., wrong style, text artifacts), there's no quality check or retry. The pipeline trusts the first result.

3. **Gatekeeper only extracts `ModItem` class names.** The `_ITEM_NAME_RE` regex (`class (\w+)\s*:\s*ModItem`) won't match a file that only contains a `ModProjectile` class without a `ModItem`. This means pure-projectile files would cause `_extract_item_name()` to return `None` → immediate error. Verify that every generated `.cs` file always contains a `ModItem` class.

4. **HJSON merge is regex-based.** The `_merge_hjson()` method uses `re.compile(rf"({re.escape(item_name)}:\s*\{{[^{{}}]*\}}")` which doesn't handle nested braces. If the HJSON block contains nested `{}` (which it shouldn't in the current `_generate_hjson()` template), the merge would break.

5. **No projectile sprite staging.** The Gatekeeper only stages `item_sprite_path` — the orchestrator passes `art_result.get("item_sprite_path")` but never passes `projectile_sprite_path`. If a custom projectile sprite was generated, it stays in `output/` but isn't copied to `Content/Items/`. tModLoader may or may not auto-discover it.

6. **No parallel failure handling.** If the Coder succeeds but the Artist fails (or vice versa), the successful agent's work is wasted. The orchestrator raises a RuntimeError for the failure but doesn't cache or reuse the successful result.

7. **`_run_tmod_build` success check.** The Gatekeeper determines build success solely by `proc.returncode == 0`. If tModLoader writes warnings to stderr but exits 0, those warnings are silently ignored (this is correct behavior, just worth knowing).

8. **Coder's `fix_code()` vs `write_code()` repair.** Both methods use the same repair chain, but `fix_code()` receives raw compiler errors while `write_code()` receives `validate_cs()` violations. The repair prompt is identical — the LLM sees different error formats and must handle both.

### Eval dimensions

| Dimension | What to measure | How |
|-----------|----------------|-----|
| **Architect accuracy** | Does the manifest match the user's intent? Are stats within tier bounds? | Compare manifest fields against prompt; check stat clamping |
| **Code correctness** | Does generated C# compile? Does it use 1.4.4 API only? | Run tModLoader build; run `validate_cs()` on output |
| **Repair effectiveness** | How often does the repair loop succeed? How many attempts? | Log `attempts` field in GatekeeperResult |
| **Sprite quality** | Does the sprite look like pixel art? Is the background clean? | Visual inspection; measure alpha channel coverage |
| **E2E success rate** | What percentage of prompts produce a working mod? | Run N prompts, count `status="success"` |
| **Latency** | How long does each stage take? Total pipeline time? | Instrument each agent call with timers |
| **Cost** | How many LLM calls per pipeline run? Total tokens? | Log LLM calls per run; track token usage |
| **Reference fidelity** | When img2img is used, does the output resemble the reference? | Compare reference URL to final sprite (CLIP similarity) |
| **Balance adherence** | Are stats always within tier bounds after clamping? | Assert on model_validate output |
| **Determinism** | Same prompt → same manifest (excluding LLM variation)? | Run same prompt N times, compare crafting fields (should be identical) |
