# Agents runtime notes

This directory is the **active** Python stack for The Forge. The default integration is **`mcp_server.py`** (MCP tools); the old file-driven orchestrator lives only under **`../archive/agents/`**.

## Model weights

Pixelsmith uses the `terraria_weights.safetensors` model file, which is not in the repo. Download it once after cloning:

```bash
cd agents/pixelsmith
python download_weights.py
```

Before running, edit `download_weights.py` and set the Google Drive file IDs for each weight file (from the share links you get after uploading). The script will download them into `agents/pixelsmith/`.

## Reference-aware generation configuration

Reference lookup for sprites uses Bing Images via Playwright (no API key needed).
Requires `playwright install chromium` to be run once.

Pixelsmith generation mode configuration:

- `FAL_KEY` or `FAL_API_KEY`: required for all generations.
- `FAL_IMAGE_TO_IMAGE_ENABLED`: set `true` to allow `image_to_image` requests.
- `FAL_IMAGE_TO_IMAGE_ENDPOINT`: optional endpoint override for image-to-image mode.

Fallback behavior:

- Any reference lookup or approval failure falls back to `text_to_image`.
- `image_to_image` requests without a reference URL or with capability disabled fall back to `text_to_image`.

## MCP server

Run from **`agents/`** (working directory required for imports):

```bash
source .venv/bin/activate   # after pip install -r requirements.txt
python mcp_server.py
```

Register this command with your MCP client (stdio). See the root **README.md** → [MCP tools](../README.md#mcp-tools) for the four exposed tools.

## Automated tests (recommended smoke)

End-to-end MCP tool wiring is covered by pytest (uses isolated ModSources via `FORGE_MOD_SOURCES_DIR` in `conftest.py`):

```bash
cd agents
source .venv/bin/activate
pytest tests/mcp/test_smoke_tier1.py -v
```

Broader suite:

```bash
pytest tests/ -v
```

Test layout: **`tests/core/`**, **`tests/pixelsmith/`**, **`tests/gatekeeper/`**, **`tests/contracts/`** (mirror packages); **`tests/mcp/`** (MCP tools + tier‑1 smoke); **`tests/workshop/`** (session, director, contracts); **`tests/stress/`**, **`tests/fixtures/`**.

## Legacy orchestrator smoke (archive only)

The historical **`orchestrator_smoke.py`** — subprocess test that drove **`user_request.json`** / **`generation_status.json`** against the monolithic orchestrator — lives under **`../archive/agents/orchestrator_smoke.py`**. It is **not** part of the MCP-first workflow; use the pytest commands above unless you are reviving the archived stack.
