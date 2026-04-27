# Demo Dry-Run Checklist — LinkedIn Recording

Run this top-to-bottom **before** hitting record. Goal: prove the full forge → live-inject loop on a clean state. Marketing positioning: **"Claude Code for Terraria."**

## Pre-flight (do this once, ahead of recording)

- [ ] On `main`, working tree clean (`git status` empty).
- [ ] `cd BubbleTeaTerminal && go test ./...` → all green.
- [ ] `cd agents && python3 -m pytest` → 331 passed, 0 failed.
- [ ] `agents/.env` exists, has real `FAL_KEY` and `OPENAI_API_KEY` (verify with `head -5 agents/.env`).
- [ ] Pixelsmith weights present at `agents/pixelsmith/*.safetensors` (download via `python3 agents/pixelsmith/download_weights.py` if missing).
- [ ] Playwright Chromium installed (`playwright install chromium`).
- [ ] tModLoader installed, `ForgeConnector` mod copied to ModSources, built, and enabled.
- [ ] Test the loop once end-to-end with the Storm Brand prompt before recording. Recover from any surprise. **Do not hit record on a first attempt.**

## Recording session — terminal setup

- [ ] Terminal width: **110 cols or wider** (matches the staging-layout breakpoint).
- [ ] Font: monospace, 14–16pt for legibility on a recorded video.
- [ ] Color theme: dark background, high-contrast foreground.
- [ ] Hide irrelevant tabs/windows. Quit Slack/notifications.
- [ ] Screen recorder running. Mic level checked.

## The demo run

### 1. Launch Terraria + load a world
- [ ] Open tModLoader, load mods, select world, click **Play**, get into the world.
- [ ] In-game: open inventory once to confirm vanilla items visible. Close inventory.
- [ ] Leave Terraria visible on a second monitor (or split-screen) so the injection moment is on camera.

### 2. Launch The Forge TUI
- [ ] In the recording terminal: `cd BubbleTeaTerminal && go run .`
- [ ] **Watch for:** TUI welcome screen with prompt input. Orchestrator log line confirming heartbeat.
- [ ] **Recover if:** TUI shows a pre-flight error message in the forge screen (red text). The `message` field tells you what's missing — fix it (set the env var, install Chromium, etc.) and rerun.

### 3. Forge the demo item — Storm Brand
- [ ] Type:
  ```
  Storm Brand — a long sword wreathed in crackling cobalt lightning, with arcing electric runes along the blade
  ```
- [ ] Press Enter, choose `Auto`.
- [ ] **Watch for in TUI:** progress lines (`Architect…`, `Pixelsmith…`, `Forge Master…`), elapsed time ticking, no long silences.
- [ ] **Watch for in-game:** when injection lands, the item appears in inventory (or in cursor, depending on inject mode).

### 4. Workshop loop demo (optional, if recording is going well)
- [ ] On the staging screen, press `/` or `Tab` to open the director command bar.
- [ ] Run `/variants make it more icy` — watch shelf populate.
- [ ] `/bench 2` to swap a variant onto the bench.
- [ ] `/restore live` to reinject the live variant.
- [ ] Show the `/history` command listing items accepted this session.

### 5. End the recording cleanly
- [ ] Stop the recording on a stable frame.
- [ ] In TUI: `Ctrl+C` to quit.

## Known papercuts to be ready for

| Symptom | Cause | Recovery |
|---|---|---|
| Long pause with no feedback | FAL queue under load | Wait — orchestrator polls every 2s, timeout is 90 polls (~3 min). |
| `Sprite has background noise…` error | Sprite gate tripped | Pre-flight already showed Storm Brand passes; if a different prompt fails, retry with `r` from the failure screen. |
| `FAL_KEY missing` in TUI | `.env` not loaded | Confirm `agents/.env` exists with `FAL_KEY=…`; restart the TUI. |
| `OPENAI_API_KEY missing` | Same | Same. |
| ForgeConnector heartbeat dropping | Mod not enabled or world not loaded | Re-enable mod in tModLoader, load a world before forging. |
| `Unsupported command` for slash command | Command typed wrong | Reference the autocomplete drawer (`/` opens it). |

## Recording tips

- Lead with the hook on screen for 2–3 seconds: **"Claude Code for Terraria."**
- Cut to: prompt typed, then a few-second timelapse over the generation, then the in-game appearance moment in real time.
- Keep the TUI and the game both visible at the moment of injection — that's the wow.
- Voiceover (if any): explain what the agents do in one breath. Don't read the architecture.

## Backup demo prompts (if Storm Brand misbehaves on the day)

- `Thundering Broadsword of Dawn — a radiant storm-forged broadsword that crackles with morning lightning` (sword family, paired with Storm Brand on stats but visually distinct)
- `Frost Staff of the Glacier — a long ice-carved staff crowned with a faceted glacier crystal` (Tier C verified: passes gates, generates projectile sprite cleanly; on-camera safe as long as you don't right-click to cast — `shoot_projectile: null` would surface as a silent dud)
- `Shortsword of the Bog Wraith — a slim iron blade veined with peat and rot` (Tier1 melee, no projectile concern, sub_type passes Tier A cleanly)

**Banned from demo entirely:**
- ~~`Verdant Bow`~~ — measured 60% sprite-gate failure rate over 5 runs.
- ~~`Frostgun`~~ — ranged `shoot_projectile: null` = silent dud if fired on camera.
- ~~`Obsidian Pickaxe`~~ — manifest is `content_type: "Weapon", tool_stats: null`. The TUI's staging screen renders `contentType` in the meta line (`BubbleTeaTerminal/main.go:180,187`, `screen_staging.go:305-307`), so the mismatch is visible on camera. Per `2026-04-26-product-fixes-plan.md`, Tool codegen is unscoped and Fix 3 is deferred past the demo. **Do not let any Pickaxe item enter the workshop session before recording.**

**Pre-record corpus quarantine check.**
Before launching the TUI on recording day, run:

```bash
cd /Users/user/Desktop/the-forge
python3 agents/qa/quarantine_check.py
```

The script greps all planned demo prompts, this checklist, and any persisted workshop-session JSON for `sub_type: Pickaxe` paired with `content_type: Weapon`. Non-zero exit means stop and clear state before recording.

These are picked to maximize on-camera reliability, not breadth of sub_type coverage.
