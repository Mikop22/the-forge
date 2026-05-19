## Claude Code plugin that generates, compiles, sprites, and live-injects custom Terraria weapons into tModLoader.

"a magic staff that shoots nyan cat for 0 mana"

https://github.com/user-attachments/assets/b6fb6588-1519-402b-8b05-2df8b91a65f8

## Install

Prerequisites:

- Terraria with **tModLoader** installed
- **Claude Code** with the `/plugin` command available
- **Python** `3.12+`
- **Node.js/npm**
- A fal.ai API key

Inside Claude Code:

```text
/plugin marketplace add Mikop22/the-forge
/plugin install tforge@tforge
```

the plugin will then prompt you for a FAL.ai API key. You need this key to access the diffusion model which generates sprites and animation frames.

Run setup and diagnostics:

```text
/tforge:setup
/tforge:doctor
```

`/tforge:setup` installs local Python and Node dependencies, downloads Pixelsmith weights, and copies `ForgeConnector` into your tModLoader `ModSources` directory when it can find it.

In tModLoader, build and enable `ForgeConnector`, enter a world, then run:

```text
/tforge:forge <describe item here>
```

For local development without installing from the marketplace:

```bash
git clone https://github.com/Mikop22/the-forge.git
cd the-forge
claude --plugin-dir .
```

## Technical Details

Architecture, MCP tools, supported item types, environment overrides, project layout, and troubleshooting live in [TECHNICAL.md](TECHNICAL.md).
