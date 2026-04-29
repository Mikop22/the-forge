
# The Forge
## Describe an item, The Forge can conceptualize it, generate art, make novel animations, write the code and inject the item, *without reloading the game*.

*all in the terminal*

<p align="center">
  <img src="https://github.com/user-attachments/assets/5c2b3eab-8aeb-494f-8911-21628cff59c3" width="688" />
</p>

*see "a staff that shoots nyan-cat" below*


https://github.com/user-attachments/assets/b6fb6588-1519-402b-8b05-2df8b91a65f8


## Architecture (High Level)

### The whole thing — prompt to playable

```mermaid
flowchart LR
    P([“a frostbrand katana<br/>with rime-etched edge”])

    P --> ENGINE{{The Forge}}

    ENGINE --> D[A design]
    D --> A[A sprite]
    A --> C[Working code]
    C --> M[A compiled mod]
    M --> G([Swinging it<br/>in Terraria])

    style P fill:#1f2937,color:#fff,stroke:#111,stroke-width:2px
    style ENGINE fill:#1e3a8a,color:#fff,stroke:#0c1e4f,stroke-width:3px
    style D fill:#0f172a,color:#fff,stroke:#020617
    style A fill:#0f172a,color:#fff,stroke:#020617
    style C fill:#0f172a,color:#fff,stroke:#020617
    style M fill:#0f172a,color:#fff,stroke:#020617
    style G fill:#065f46,color:#fff,stroke:#022c22,stroke-width:2px
```

### The pipeline at a glance

```mermaid
flowchart LR
    USER([Player types a prompt])

    USER --> ROUTER{{How complex is this item?}}

    subgraph Full["Full build"]
        direction LR
        F1[Designer<br/>writes the spec] --> F2[Artist<br/>paints the sprite]
        F2 --> F3[Engineer<br/>writes the code]
        F3 --> F4[Inspector<br/>compiles the mod]
        F4 --> F5([Playable mod<br/>installed in Terraria])
    end

    subgraph Instant["Instant inject"]
        direction LR
        I1[Designer] --> I2[Artist]
        I2 --> I3([Live item dropped<br/>into the running game])
    end

    ROUTER -->|Best of 1| F1
    ROUTER -->|Try it now| I1
    ROUTER -->|Best-of-N audition| AUD[Hidden audition<br/>see below]

    style USER fill:#1f2937,color:#fff,stroke:#111
    style F5 fill:#065f46,color:#fff,stroke:#022c22
    style I3 fill:#065f46,color:#fff,stroke:#022c22
    style AUD fill:#7c2d12,color:#fff,stroke:#431407
```


### The hidden audition — how we pick winners

```mermaid
flowchart TD
    PROMPT([One player prompt]) --> THESES[Generate several<br/>creative directions]

    THESES --> NARROW[Narrow to the<br/>strongest finalists]

    NARROW --> ART[Paint every finalist<br/>and score the art]

    ART --> SURVIVE{Did the art<br/>pass review?}
    SURVIVE -->|No| REJECT[(Archive the reason<br/>it lost)]
    SURVIVE -->|Yes| PLAYTEST[Drop each survivor into<br/>a live game and watch it play]

    PLAYTEST --> EVIDENCE{Did it actually<br/>feel good in-game?}
    EVIDENCE -->|No| REJECT
    EVIDENCE -->|Yes| WINNER([Pick the best<br/>by art score])

    REJECT -.->|All candidates failed| LEARN[Learn from the failure<br/>and try new directions]
    LEARN --> THESES

    style PROMPT fill:#1f2937,color:#fff
    style WINNER fill:#065f46,color:#fff
    style REJECT fill:#7f1d1d,color:#fff
    style LEARN fill:#854d0e,color:#fff
```

We don't trust the model's first idea, and we don't trust the art alone, a candidate also has to survive a live playtest before it can win. If everything fails, the system learns why and retries with a different angle.

### Endgame items; when the system gets ambitious

```mermaid
flowchart TD
    PROMPT([Endgame-tier prompt]) --> DESIGNER[Designer realizes<br/>this needs spectacle]

    DESIGNER --> SPLIT{{Designer produces two things}}

    SPLIT --> FANTASY[Visual fantasy<br/>for the artist]
    SPLIT --> CONTRACT[Creative contract<br/>for the engineer:<br/><br/>• What it should feel like<br/>• Mechanics it can compose from<br/>• Things it must NOT feel like<br/>• Things it must NOT include]

    FANTASY --> ART[Artist paints<br/>the fantasy]
    CONTRACT --> CODE[Engineer implements<br/>the mechanics]

    CODE --> JUDGE{Does the code<br/>honor the contract?}
    JUDGE -->|Forbidden mechanic snuck in| REWRITE[Send it back]
    JUDGE -->|Feels too generic| REWRITE
    JUDGE -->|Honors every clause| SHIP([Endgame weapon ships])
    REWRITE --> CODE

    ART --> SHIP

    style PROMPT fill:#1f2937,color:#fff
    style CONTRACT fill:#1e3a8a,color:#fff
    style FANTASY fill:#1e3a8a,color:#fff
    style SHIP fill:#065f46,color:#fff
    style REWRITE fill:#7f1d1d,color:#fff
```

At the high end, the designer stops describing "a weapon" and starts producing a **creative contract** — a list of must-haves and must-not-haves. The reviewer enforces that contract literally on the code side, which is what stops endgame items from collapsing into generic weapon thats use stock projectiles.

### Where the data goes

```mermaid
flowchart LR
    SPEC[Spec from Designer<br/>name, stats, fantasy] --> A1

    subgraph ART[Art generation]
        A1[Enrich the description<br/>with visual detail] --> A2[Generate sprite<br/>with custom-tuned model]
        A2 --> A3[Measure the sprite<br/>find the actual hitbox]
    end

    A3 --> SPEC2[Spec, now enriched<br/>with real hitboxes]

    SPEC2 --> CODE[Engineer writes code<br/>against the enriched spec]
    A2 --> ASSETS[(Sprite files)]

    CODE --> BUILD[Inspector stages everything<br/>and compiles]
    ASSETS --> BUILD

    BUILD --> OUT([Installed mod,<br/>ready to play])

    style SPEC fill:#1f2937,color:#fff
    style SPEC2 fill:#1e3a8a,color:#fff
    style OUT fill:#065f46,color:#fff
```

The spec isn't a static document, it gets richer as it travels. The artist hands back real hitbox measurements before the engineer writes a line of code, which is why the resulting weapon feels physically correct in-game.

## Prerequisites

- Terraria with tModLoader installed
- Go `1.24+`
- Python `3.12+`
- Node `18+`
- Playwright runtime for reference image lookup

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Mikop22/the-forge.git
cd the-forge
```

### 2. API keys: *pending local mode for those of you with beefy gpus*

Copy the template and fill in your keys:

```bash
cp agents/.env.example agents/.env
# then edit agents/.env in your editor
```

Required keys:

```env
OPENAI_API_KEY=your-openai-key
FAL_KEY=your-fal-key
```

| Key | Use |
|-----|-----|
| `OPENAI_API_KEY` | Architect, Forge Master, orchestration |
| `FAL_KEY` | Pixelsmith image generation |

### 3. Pixelsmith weights (must have for terraria compatible sprites)

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

`ForgeConnector` is the tModLoader mod that enables live injection and runtime status.

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
```


## Supported Item Types

The orchestrator infers `sub_type` from prompt keywords (with substring-trap precedence — `pickaxe` beats `axe`, `broadsword` beats `sword`, `shotgun` beats `gun`).

| Class | Sub-types |
|---|---|
| Melee | Sword, Broadsword, Shortsword, Spear, Lance |
| Firearms | Pistol, Shotgun, Rifle, Repeater (uses bullets) |
| Bows | Bow, Repeater (also crossbow) |
| Magic | Staff, Wand, Tome, Spellbook (use mana) |
| Heavy ranged | Launcher (rockets), Cannon (custom) |
| Tools | Pickaxe, Axe, Hamaxe, Hammer (also deal melee damage) |

All ranged sub-types emit working `Item.shoot` and ammo/mana wiring; tools emit `Item.pick` / `Item.axe` / `Item.hammer` and route through `content_type=Tool` automatically.

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
└── mod/
    └── ForgeConnector/
```

## Reference-Aware Generation

When a prompt references a known object, weapon, or character, the pipeline can fetch references and use them to guide sprite generation.
