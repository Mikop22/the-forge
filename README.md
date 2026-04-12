# The Forge

Terraria item workshop for tModLoader.

Describe an item, and The Forge can design it, generate art, build the mod output, or inject it live into a running tModLoader session. The current UI is a workshop surface, not an IDE: one item on the bench, optional variants on the shelf, and fast reinject loops for live tuning.

![Go](https://img.shields.io/badge/TUI-Go%20%2F%20BubbleTea-00ADD8)
![Python](https://img.shields.io/badge/Pipeline-Python-3776AB)
![tModLoader](https://img.shields.io/badge/Target-tModLoader%201.4.4-green)

## What It Does

- Prompt-to-item generation through `Architect`, `Pixelsmith`, `Forge Master`, and `Gatekeeper`
- Instant live injection through `ForgeConnector`
- Bench/shelf workshop loop in the TUI
- Direct reinject and restore flows for runtime tuning
- Bounded hidden-audition and runtime-validation path for supported package/runtime slices

## Current Product Shape

The repo has three active flows:

1. **Normal compile path**
   - generate manifest, art, C# mod output, and staged build artifacts
2. **Instant inject path**
   - generate manifest + art and inject directly without a packaged build
3. **Workshop / Forge Director path**
   - keep one active item on the bench
   - generate shelf variants from natural-language direction
   - bench a variant and reinject it live

## Architecture Docs

The canonical architecture entrypoint is:

- [docs/architecture/00-index.md](docs/architecture/00-index.md)

Read these first if you are trying to understand or modify the system:

- [docs/architecture/01-architecture.md](docs/architecture/01-architecture.md)
- [docs/architecture/02-current-state.md](docs/architecture/02-current-state.md)
  
## Prerequisites

- Terraria with tModLoader installed
- Go `1.24+`
- Python `3.12+`
- Node `18+`
- Playwright runtime for Architect reference lookup

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Mikop22/the-forge.git
cd the-forge
```

### 2. API keys: *pending local mode for those of you with cool gpus*

Create `agents/.env`:

```env
OPENAI_API_KEY=your-openai-key
FAL_KEY=your-fal-key
FAL_IMAGE_TO_IMAGE_ENABLED=true
```

| Key | Use |
|-----|-----|
| `OPENAI_API_KEY` | Architect, Forge Master, orchestration |
| `FAL_KEY` | Pixelsmith image generation |
| `FAL_IMAGE_TO_IMAGE_ENABLED` | optional reference-aware art path |

### 3. Pixelsmith weights

Download the sprite model weights into `agents/pixelsmith/`:

```bash
cd agents/pixelsmith
python download_weights.py
```

See `agents/README.md` for the expected weights workflow.

### 4. Python environment

```bash
cd agents
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install fal-client playwright scikit-learn
playwright install chromium
```

### 5. Node dependency

```bash
cd agents/pixelsmith
npm install @fal-ai/client
```

### 6. Go dependencies

```bash
cd BubbleTeaTerminal
go mod download
```

### 7. Install `ForgeConnector`

`ForgeConnector` is the tModLoader bridge mod that enables live injection and runtime status.

1. Copy `mod/ForgeConnector/` into your tModLoader `ModSources` directory:
   - macOS: `~/Library/Application Support/Terraria/tModLoader/ModSources/`
   - Windows: `Documents/My Games/Terraria/tModLoader/ModSources/`
   - Linux: `~/.local/share/Terraria/tModLoader/ModSources/`
2. Build `ForgeConnector` from tModLoader's mod tools
3. Enable it in the mod list

## Running The Forge

From `BubbleTeaTerminal/`:

```bash
go run .
```

The TUI auto-starts the Python orchestrator.

## ModSources Resolution

All components resolve tModLoader `ModSources` in this order:

1. `FORGE_MOD_SOURCES_DIR`
2. `~/.config/theforge/config.toml` `mod_sources_dir`
3. OS default path

Only one orchestrator may run per `ModSources` tree. The lock file is:

```text
ModSources/.forge_orchestrator.lock
```

## Using The TUI

### Basic forge flow

1. Enter an item prompt
2. Choose `Auto` or use the manual wizard
3. Let the forge/build pipeline run
4. Review the result on the staging/workshop screen
5. Inject the item into a live tModLoader session

### Workshop flow

On the staging screen:

- `Enter` or `A`: inject the current bench item
- `/` or `Tab`: open the director command bar
- `C`: start another item
- `R`: reprompt art
- `S`: tweak stats

The workshop command bar supports the current V1 commands:

- `/variants <direction>`
- `/bench <variant-id-or-number>`
- `/try`
- `/restore baseline`
- `/restore live`

If you type plain natural language into the command bar instead of a slash command, it is treated as a variant-generation direction.

## Runtime Files

The most important live files under `ModSources` are:

- `generation_status.json`
- `workshop_request.json`
- `workshop_status.json`
- `forge_inject.json`
- `forge_connector_status.json`
- `forge_runtime_summary.json`
- `forge_connector_alive.json`

When debugging direct inject, these are also useful:

- `forge_last_inject.json`
- `forge_last_inject_debug.json`
- `ForgeConnectorInjectedAssets/`

## Power Tiers

| Tier | Damage | Examples |
|------|--------|----------|
| Starter | 8–15 | early-game, wood and iron |
| Dungeon | 25–40 | post-Skeletron |
| Hardmode | 45–65 | post-Wall of Flesh |
| Endgame | 150–300 | post-Moon Lord |

## Project Structure

```text
the-forge/
├── BubbleTeaTerminal/
│   ├── main.go
│   ├── screen_forge.go
│   ├── screen_staging.go
│   └── internal/
│       ├── ipc/
│       └── modsources/
├── agents/
│   ├── orchestrator.py
│   ├── contracts/
│   ├── core/
│   ├── architect/
│   ├── pixelsmith/
│   ├── forge_master/
│   └── gatekeeper/
├── mod/
│   └── ForgeConnector/
└── docs/
    ├── architecture/
    └── plans/
```

## Boundaries

- The TUI is a workshop client, not a general coding environment
- Runtime validation is intentionally bounded; do not assume every package/runtime combination is live-valid
- `ForgeConnector` is a constrained live-runtime bridge, not an arbitrary generated-runtime host

## Reference-Aware Generation

When a prompt references a known object, weapon, or character, the pipeline can fetch references and use them to guide sprite generation.
