# The Forge

Is an agentic item generator for Terraria. Describe any weapon you can imagine and The Forge will design it, write the mod code, generate pixel art, and inject it into your game all from the terminal interface.

<img width="1364" height="703" alt="Screenshot 2026-03-11 at 11 13 51 AM" src="https://github.com/user-attachments/assets/ee8874e7-dd91-4678-bc0e-2ba1f12ec945" />





![Go](https://img.shields.io/badge/TUI-Go%20%2F%20BubbleTea-00ADD8)
![Python](https://img.shields.io/badge/Pipeline-Python-3776AB)
![tModLoader](https://img.shields.io/badge/Target-tModLoader%201.4.4-green)

## How It Works

1. **You describe a weapon** — "A frost katana that shoots ice shards"
2. **The Architect Agent** designs a balanced item manifest (stats, crafting recipe, visuals)
3. **The Forge Master Agent** writes compilable C# mod code for tModLoader and tests it
4. **The Pixelsmith Agent** generates a pixel art sprite via AI image generation
5. **The Gatekeeper Agent** compiles the mod and stages it into your ModSources
6. **ForgeConnector** hot-reloads the mod into your running Terraria game and signals back to the TUI when the reload is complete

The entire pipeline runs from a single terminal UI. You pick your weapon idea, choose a power tier, and watch it get built in real time.

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

Create `agents/.env` with your keys:

```env
OPENAI_API_KEY=your-openai-key
FAL_KEY=your-fal-key
FAL_IMAGE_TO_IMAGE_ENABLED=true # This controls if the app will look for reference images of real objects
```

| Key | What it's for |
|-----|---------------|
| `OPENAI_API_KEY` | Powers the Architect (item design), Forge Master (code gen), and reference image approval |
| `FAL_KEY` | Powers the Pixelsmith sprite generator via fal-ai FLUX |

### 3. Model weights (Pixelsmith)

Download the sprite model weights (hosted on Google Drive) into `agents/pixelsmith/`:

```bash
cd agents/pixelsmith
# Edit download_weights.py and add your Google Drive file IDs, then:
python download_weights.py
```

See `agents/README.md` for how to get the file IDs from your share links.

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

### 7. ForgeConnector bridge mod (one-time)

This small tModLoader mod lets The Forge hot-reload items into your running game.

1. Copy the `mod/ForgeConnector/` folder into your tModLoader ModSources directory:
   - **macOS:** `~/Library/Application Support/Terraria/tModLoader/ModSources/`
   - **Windows:** `Documents/My Games/Terraria/tModLoader/ModSources/`
   - **Linux:** `~/.local/share/Terraria/tModLoader/ModSources/`

2. Open Terraria → Workshop → Develop Mods → Build ForgeConnector

3. Enable ForgeConnector in the Mod List

## Running The Forge

From the `BubbleTeaTerminal/` directory:

```bash
go run .
```

That's it. The TUI will auto-start the Python orchestrator in the background.

### Using the TUI

1. **Type your weapon idea** and press Enter
2. **Choose a path:**
   - **Auto** — The AI picks everything for you
   - **Manual** — Walk through a wizard to choose tier, damage class, weapon style, projectile, and crafting station
3. **Watch it build** — the heat bar tracks each pipeline stage in real time
4. **Staging screen** — your item is ready:
   - The sprite is rendered directly in the terminal alongside the item's stats
   - If Terraria is running with ForgeConnector, press **Enter** to inject the item live — the TUI waits for a confirmation signal from the game before marking the reload complete
   - Press **C** to craft another item without losing your inventory

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

Swords, broadswords, bows, guns, staves, wands, spears, yoyos, flails, whips, summon weapons, launchers, and more. If the user prompt describes a projectile, The Forge will generate a custom ModProjectile with its own sprite.

## Reference-Aware Generation

If your prompt references a known character or item ("a sword like the Master Sword", "Naruto's kunai"), the Architect will search for reference images using Playwright and use them to guide the sprite generation for higher fidelity.

