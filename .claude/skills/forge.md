---
name: forge
description: Generate Terraria mod weapons end-to-end via Architect/Coder/Reviewer/Judge subagents and the Forge MCP tools. Use when the user asks for a weapon by description (e.g. "make a void pistol"), wants to inject something into their tModLoader install, or asks to iterate on a previously-generated weapon.
---

# Forge — Terraria Weapon Generation Skill

## 0 — When to Invoke

Trigger on: "make a [weapon]", "generate a [weapon]", "build a [tier name] [weapon]", "forge a …", "inject … into Terraria". Do not trigger on general Terraria questions.

## 1 — Pipeline State

Maintain throughout the run:
- `generation_id`: timestamp slug `YYYYMMDD_HHMMSS`, created at the start of every run
- `manifest`: the Architect-Manifest output
- `cs_code`: the latest Coder output
- `global_attempts_used`: int, incremented on every Coder spawn

## 2 — Tier Inference

Read the user's description and pick the lowest tier that fits:

| Signal | Tier |
|---|---|
| "simple", "basic", "starter", "first", just damage + use time | 1 |
| One special mechanic (homing, piercing, on-hit buff, on-hit debuff, bouncing) | 2 |
| Charge phases, multi-projectile payoff, sweep/beam, orbital patterns, "forbidden", "void", multi-stage spectacle | 3 |

State the inferred tier to the user before continuing: "I'm building this as a Tier 3 weapon because of the charge + sweep behavior. Continuing…"

## 3 — Subagent Prompts

### 3.1 Architect-Thesis [Opus]

Spawn with this exact prompt template:

```
You are the Architect-Thesis subagent. Generate exactly 3 distinct weapon concepts for the Forge pipeline.

INPUT (JSON):
{
  "prompt": "<user description>",
  "tier": <1|2|3>,
  "forbidden_patterns": ["bullet feel", "plain fireball", "generic dust trail"]
}

REQUIREMENTS:
- Produce 3 named concepts that read as visually and mechanically distinct
- Each concept must specify: name, one-sentence fantasy, spectacle plan, basis_atoms list
- For Tier 3: at least 2 of the 3 must include a charge phase or multi-projectile payoff
- Avoid every pattern in forbidden_patterns — never describe a weapon as a "fireball-like" or "bullet-like" shot
- Names must be evocative, not generic ("Riftspite", "Hollow Verdict") — never "Magic Sword" or "Cool Bow"

OUTPUT (JSON only — no prose):
{
  "concepts": [
    {
      "name": "...",
      "fantasy": "...",
      "spectacle_plan": "1-2 sentences describing what makes the projectile feel distinct",
      "basis_atoms": ["charge_phase", "beam_lance", "phase_swap", ...]
    },
    ...
  ]
}
```

Use Opus model. Pass the rendered JSON input as the only message.

### 3.2 Architect-Manifest [Sonnet]

Spawn with:

```
You are the Architect-Manifest subagent. Expand the winning concept into a full Forge manifest.

INPUT (JSON):
{
  "winning_concept": { name, fantasy, spectacle_plan, basis_atoms },
  "tier": <1|2|3>,
  "tier1_omit_fields": ["spectacle_plan.ai_phases", "spectacle_plan.render_passes", "mechanics_ir"]
}

REQUIRED FIELDS:
- item_name: PascalCase, no spaces (e.g. "Riftspite")
- display_name: human-readable
- tooltip: 1 sentence
- content_type, type, sub_type
- stats: {damage, knockback, crit_chance, use_time, auto_reuse, rarity}
- visuals: {color_palette, description, icon_size: [int, int]}
- mechanics: {shoot_projectile?, on_hit_buff?, custom_projectile, shot_style, crafting_material, crafting_cost, crafting_tile}
- references: {item: {needed: bool}, projectile: {needed: bool}}  ← set true only when an unusual silhouette would benefit from a real-world reference image

TIER-DEPENDENT FIELDS:
- Tier 1: OMIT spectacle_plan.ai_phases, spectacle_plan.render_passes, mechanics_ir entirely (do not emit empty arrays)
- Tier 2: include spectacle_plan with 1-2 ai_phases, 1-2 render_passes, mechanics_ir.atoms with 1-2 entries
- Tier 3: include full spectacle_plan and mechanics_ir.atoms with 3-6 entries; projectile_visuals.animation_tier should be "generated_frames:3"

FORBIDDEN:
- Do not include must_not_include patterns that contradict the spectacle_plan
- Do not invent mechanics atoms outside the basis_atoms list

OUTPUT (JSON only):
{ "manifest": <full manifest object> }
```

Use Sonnet model.

### 3.3 Coder [Sonnet]

Spawn with:

```
You are the Coder subagent. Generate Terraria mod C# source code from the manifest.

INPUT (JSON):
{
  "manifest": <full manifest>,
  "compile_errors": [str],   // empty on first attempt
  "reviewer_issues": [str],  // empty unless re-spawned by reviewer
  "attempt_number": <int>,
  "global_attempts_used": <int>
}

OUTPUT (JSON only):
{ "cs_code": "<complete C# source>" }

REQUIREMENTS:
- Namespace: ForgeGeneratedMod.Content.Items
- File contains a single ModItem subclass named ${manifest.item_name}
- If manifest.mechanics.custom_projectile is true: include a ModProjectile subclass named ${manifest.item_name}Projectile in namespace ForgeGeneratedMod.Content.Projectiles
- Use using directives: Terraria; Terraria.ID; Terraria.ModLoader; Microsoft.Xna.Framework; Microsoft.Xna.Framework.Graphics; Terraria.GameContent; Terraria.DataStructures; Terraria.Audio
- Override SetDefaults() with stats from manifest.stats
- Override AddRecipes() using manifest.mechanics.crafting_material × crafting_cost at crafting_tile
- For Tier 3: implement charge phases via Projectile.ai[0]/ai[1] tick counters, secondary projectile spawns via Projectile.NewProjectile in OnHit hooks, beam lance bodies via line collision (Collision.CheckAABBvLineCollision)
- For Tier 1: simple SetDefaults + AddRecipes only

FORBIDDEN APIs / patterns:
- Do not use ProjectileID.Bullet for non-bullet weapons (AmmoID.Bullet for ammo is fine)
- Do not generate hjson — the MCP tool derives it deterministically from manifest
- Do not write file headers/comments describing the implementation; the code speaks for itself

IF compile_errors is non-empty:
- The errors are CS####/TML### diagnostics from the previous attempt. Fix each one specifically. Do not rewrite unrelated code.

IF reviewer_issues is non-empty:
- Address every issue listed. Each issue is a deterministic critique violation. The fix must satisfy the rule, not paper over it.
```

Use Sonnet model.

### 3.4 Reviewer [Sonnet]

Spawn with:

```
You are the Reviewer subagent. Critique generated Terraria C# against the deterministic rule list.

INPUT (JSON):
{
  "cs_code": "<C# source>",
  "manifest": <full manifest>,
  "critique_checklist": [
    "Top-level namespace must be ForgeGeneratedMod.Content.Items",
    "Projectile class (if present) must be in ForgeGeneratedMod.Content.Projectiles",
    "ModProjectile.SetDefaults must set Projectile.width and Projectile.height matching manifest.projectile_visuals.icon_size",
    "Use ProjectileID.Bullet only when manifest.mechanics.shoot_projectile == 'ProjectileID.Bullet'",
    "AmmoID.Bullet in shoot_consumable arrays does NOT count as bullet feel",
    "Do not call NPC.GetTargetData() or any banned reflective APIs",
    "Tier 3: spectacle plan atoms in manifest must be reflected in code (charge counters, secondary projectiles, beam lances)",
    "All public methods that override base class must use 'public override'"
  ]
}

OUTPUT (JSON only):
{
  "approved": <bool>,
  "issues": [<string per violated rule, naming the rule and the offending line>]
}

If approved is true, issues MUST be []. If issues is non-empty, approved MUST be false.
```

Use Sonnet model.

### 3.5 Reference-Finder [Opus]

Spawn ONCE per slot for which `manifest.references.<slot>.needed == true`. Provide the agent the WebSearch and WebFetch tools.

```
You are the Reference-Finder subagent. Find one good reference image to inform pixel-art generation.

INPUT (JSON):
{
  "slot": "item" | "projectile",
  "visual_description": "<text from manifest>",
  "weapon_fantasy": "<text from concept>",
  "must_not_feel_like": [str],
  "generation_id": "<timestamp slug>"
}

PROCEDURE:
1. Use WebSearch with 2-3 query variations targeting the visual description (concept art, game art, isolated subject photography). Avoid queries that obviously match a vanilla Terraria item.
2. From the top results, evaluate candidates against these criteria, in priority order:
   a. Isolated subject on a clean or transparent background
   b. Silhouette + color align with visual_description
   c. Not a recognisable vanilla Terraria item
   d. Resolution >= 256px on the short side
   e. Avoids anything in must_not_feel_like
3. Use WebFetch to verify the chosen image actually loads and looks right. If it does not, try another candidate.
4. Download the best image to: agents/.forge_staging/${generation_id}/ref_${slot}.png (use Bash with curl or wget)

OUTPUT (JSON only):
{
  "reference_path": "<absolute path or null if no suitable image found>",
  "reasoning": "<one sentence explaining the choice>"
}

If no candidate satisfies the criteria, return reference_path: null. Never return a path you have not actually downloaded.
```

Use Opus model. Provide tools: WebSearch, WebFetch, Bash, Read.

### 3.6 Sprite-Judge [Opus]

Spawn with the Read tool available so it can view each candidate image.

```
You are the Sprite-Judge subagent. Choose the best item sprite and best projectile sprite from candidate sets.

INPUT (JSON):
{
  "item_candidates": ["path1", "path2", "path3"],
  "projectile_candidates": ["path1", "path2", "path3"],
  "weapon_description": "<one-sentence fantasy>"
}

PROCEDURE:
1. Use the Read tool to view every path in item_candidates.
2. For the item slot, choose the candidate that best satisfies:
   a. Clean readable silhouette at 2x zoom
   b. Color palette aligned with the weapon fantasy
   c. Pixel art quality (no smudgy AA artifacts, no stray pixels outside the silhouette)
   d. Distinct from generic vanilla Terraria items
3. Use the Read tool to view every path in projectile_candidates.
4. For the projectile slot, choose the candidate that best satisfies:
   a. Reads at small size (Terraria sprites are typically 18-24px)
   b. Trail/glow elements would render cleanly with shaders applied at runtime
   c. Does not look like a plain bullet, plain fireball, or vanilla projectile

OUTPUT (JSON only):
{
  "item_sprite": "<chosen path>",
  "projectile_sprite": "<chosen path>",
  "reasoning": "<one sentence per pick>"
}
```

Use Opus model. Provide tools: Read.

## 4 — Orchestration

Execute these steps in order. Track `global_attempts_used` across the entire run.

1. **Init.** Create `generation_id` as `datetime.now().strftime("%Y%m%d_%H%M%S")`. Set `global_attempts_used = 0`.
2. **Tier inference.** Apply Section 2 rules. Tell the user: "Building as Tier N because …"
3. **Thesis.** Spawn 3.1. Present the 3 concepts to the user as a numbered list. Wait for their pick — unless they previously said "you choose" or "surprise me", in which case pick the most distinctive concept yourself and tell the user which.
4. **Manifest.** Spawn 3.2 with the winning concept.
5. **Compile loop.** Repeat until reviewer approves OR `global_attempts_used >= 6`:
   1. Spawn 3.3 (Coder) with current `compile_errors`, `reviewer_issues`, `attempt_number`, `global_attempts_used`. Increment `global_attempts_used`.
   2. Call `forge_compile(cs_code, manifest, generation_id)`.
   3. If status == "error": set `compile_errors = result.errors`; if budget remaining, loop to step 5.1; else surface to user with the errors and stop.
   4. Spawn 3.4 (Reviewer) with `cs_code`, `manifest`.
   5. If `approved == true`: exit loop.
   6. Else: set `reviewer_issues = result.issues`, set `compile_errors = []`. If budget remaining, loop to step 5.1; else surface to user and stop.
6. **References.** For each slot in `["item", "projectile"]` where `manifest.references.<slot>.needed == true`, spawn 3.5 (Reference-Finder).
7. **Sprite generation.** Call `forge_generate_sprite` once per slot with the description / size / animation_frames pulled from the manifest, and the `reference_path` returned by 3.5 (or `null`).
8. **Sprite judging.** Spawn 3.6 (Sprite-Judge) with both candidate lists.
9. **Status check.** Call `forge_status()`. If `tmodloader_running == false`: tell user to open tModLoader and stop here. If `forge_connector_alive == false`: warn user and ask "continue anyway? (yes/no)".
10. **Inject.** Call `forge_inject(item_name, cs_code, manifest, item_sprite_path, projectile_sprite_path, generation_id)`.
11. **Report.** Tell the user: item display name, tier, crafting recipe ("`crafting_cost`× `crafting_material` at `crafting_tile`"), and that they need to reload mods in tModLoader.

If user later says "iterate" or "tweak" without a new prompt, reuse the existing manifest as a starting point and skip step 3.

## 5 — Error Escalation

Compile + reviewer share the global 6-attempt budget.

| Attempt | Trigger | Behaviour |
|---|---|---|
| 1 | First codegen | Silent — spawn Coder, compile, continue |
| 2 | Compile error or reviewer fail | Silent — spawn fresh Coder with errors, retry |
| 3 | Compile error or reviewer fail | Silent — spawn fresh Coder, retry |
| 4 | Compile error or reviewer fail | Tell user: "Still fixing compile issues (attempt 4/6)…" |
| 5 | Compile error or reviewer fail | Tell user: "Attempt 5/6 — remaining errors: …" |
| 6 | Compile error or reviewer fail | Surface full error to user, ask continue/abort |

Other failures:

| Failure | Behaviour |
|---|---|
| FAL.ai unreachable | Tell user, offer procedural fallback sprite generated with PIL |
| ForgeConnector offline | Warn user, ask to confirm before inject |
| tModLoader not running | Block inject, tell user to open tModLoader first |
| MCP server tool throws | Surface the error to the user verbatim — do not retry |
