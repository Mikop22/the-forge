# The Forge

Agentic Terraria item generator. Describe an item, then The Forge designs it, writes the mod code, generates sprite art, and stages or injects it from the terminal UI.

<img width="1364" height="703" alt="Screenshot 2026-03-11 at 11 13 51 AM" src="https://github.com/user-attachments/assets/ee8874e7-dd91-4678-bc0e-2ba1f12ec945" />





![Go](https://img.shields.io/badge/TUI-Go%20%2F%20BubbleTea-00ADD8)
![Python](https://img.shields.io/badge/Pipeline-Python-3776AB)
![tModLoader](https://img.shields.io/badge/Target-tModLoader%201.4.4-green)

## How It Works

1. Enter an item prompt.
2. `Architect` creates the manifest.
3. `Forge Master` generates C# mod code.
4. `Pixelsmith` generates item and projectile art.
5. `Gatekeeper` builds and stages the mod.
6. `ForgeConnector` can inject it into a running tModLoader session.

## Prerequisites

- **Terraria** with **tModLoader** installed via Steam
- **Go 1.24+**
- **Python 3.12+**
- **Node.js 18+**
- **Playwright** (for reference image search)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/mikop22/the-forge.git
cd the-forge
```

### 2. API Keys

Create `agents/.env`:

```env
OPENAI_API_KEY=your-openai-key
FAL_KEY=your-fal-key
FAL_IMAGE_TO_IMAGE_ENABLED=true # This controls if the app will look for reference images of real objects
```

| Key | Use |
|-----|-----|
| `OPENAI_API_KEY` | Architect, Forge Master, reference approval |
| `FAL_KEY` | Pixelsmith generation |

### 3. Model weights

Download the sprite model weights into `agents/pixelsmith/`:

```bash
cd agents/pixelsmith
# Edit download_weights.py and add your Google Drive file IDs, then:
python download_weights.py
```

See `agents/README.md` for the file IDs workflow.

### 4. Python environment

```bash
cd agents
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install fal-client playwright scikit-learn
playwright install chromium
```

### 5. Node dependencies

```bash
cd agents/pixelsmith
npm install @fal-ai/client
```

### 6. Go dependencies

```bash
cd BubbleTeaTerminal
go mod download
```

### 7. ForgeConnector bridge mod

This tModLoader mod enables live injection.

1. Copy the `mod/ForgeConnector/` folder into your tModLoader ModSources directory:
   - **macOS:** `~/Library/Application Support/Terraria/tModLoader/ModSources/`
   - **Windows:** `Documents/My Games/Terraria/tModLoader/ModSources/`
   - **Linux:** `~/.local/share/Terraria/tModLoader/ModSources/`

2. Build `ForgeConnector` from Terraria's mod tools.
3. Enable it in the mod list.

## Running The Forge

From the `BubbleTeaTerminal/` directory:

```bash
go run .
```

The TUI auto-starts the Python orchestrator.

### ModSources resolution

All components resolve `ModSources` in this order:

1. `FORGE_MOD_SOURCES_DIR`
2. `~/.config/theforge/config.toml` `mod_sources_dir`
3. OS default path

Only one orchestrator may run per `ModSources` tree. The lock file is `ModSources/.forge_orchestrator.lock`.

### Using the TUI

1. Enter an item prompt.
2. Choose `Auto` or walk the manual wizard.
3. Watch the forge/build stages.
4. On the staging screen, review the item and press `Enter` to inject or `C` to craft again.

### Power Tiers

| Tier | Damage | Examples |
|------|--------|----------|
| Starter | 8–15 | Early-game, wood and iron |
| Dungeon | 25–40 | Post-Skeletron |
| Hardmode | 45–65 | Post-Wall of Flesh |
| Endgame | 150–300 | Post-Moon Lord |

## Project Structure

```
the-forge/
├── BubbleTeaTerminal/     # Go TUI (BubbleTea)
│   ├── main.go            # Full TUI + orchestrator launcher
│   └── styles.go          # UI styling
├── agents/                # Python AI pipeline
│   ├── orchestrator.py    # Daemon — watches for requests, runs the pipeline
│   ├── architect/         # Designs item manifests (stats, visuals, mechanics)
│   ├── forge_master/      # Generates C# tModLoader code
│   ├── pixelsmith/        # Generates pixel art sprites
│   └── gatekeeper/        # Compiles and stages the mod
└── mod/
    └── ForgeConnector/    # tModLoader bridge mod for live injection
```

## Supported Weapon Types

Includes swords, bows, guns, staves, spears, summon weapons, launchers, and related variants. Prompts that imply projectile behavior can generate a custom `ModProjectile` and sprite.

## Reference-Aware Generation

When the prompt references a known character or item, the pipeline can fetch reference images and use them to guide sprite generation.
