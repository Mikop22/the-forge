"""orchestrator.py — The Forge's central nervous system.

A long-running daemon that:
  1. Watches ``user_request.json`` for changes from the Go TUI.
  2. Executes a DAG of AI agents:
       Architect → (Coder ∥ Artist) → Integrator
  3. Reports pipeline status back via ``generation_status.json``.

Run:
    python orchestrator.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Paths — all relative to the tModLoader ModSources directory
# ---------------------------------------------------------------------------

_HOME = Path.home()
_MOD_SOURCES = _HOME / "Library" / "Application Support" / "Terraria" / "tModLoader" / "ModSources"
REQUEST_FILE = _MOD_SOURCES / "user_request.json"
STATUS_FILE = _MOD_SOURCES / "generation_status.json"
HEARTBEAT_FILE = _MOD_SOURCES / "orchestrator_alive.json"

# Where Pixelsmith drops sprites and Forge Master drops code
_AGENTS_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = _AGENTS_ROOT / "output"

# ---------------------------------------------------------------------------
# Status helpers (TUI handshake)
# ---------------------------------------------------------------------------

def _write_status(payload: dict) -> None:
    """Atomically write *payload* to ``generation_status.json``."""
    tmp = STATUS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(STATUS_FILE)
    log.info("Status → %s", payload.get("status"))


def _write_heartbeat() -> None:
    HEARTBEAT_FILE.write_text(
        json.dumps({
            "status": "listening",
            "pid": os.getpid(),
            "timestamp": time.time(),
        }, indent=2),
        encoding="utf-8",
    )


def _clear_heartbeat() -> None:
    try:
        HEARTBEAT_FILE.unlink()
    except FileNotFoundError:
        pass


def _set_stage(label: str, pct: int) -> None:
    _write_status({"status": "building", "stage_label": label, "stage_pct": pct})


def _set_ready(item_name: str, manifest: dict | None = None, sprite_path: str = "") -> None:
    _write_status({
        "status": "ready",
        "stage_pct": 100,
        "batch_list": [item_name],
        "message": "Compilation successful. Waiting for user...",
        "manifest": manifest or {},
        "sprite_path": sprite_path,
    })


def _set_error(message: str) -> None:
    _write_status({
        "status": "error",
        "error_code": "PIPELINE_FAIL",
        "message": f"The pipeline collapsed: {message}",
    })


# ---------------------------------------------------------------------------
# Agent imports (deferred so the module loads even if agents aren't installed)
# ---------------------------------------------------------------------------

def _import_agents():
    """Lazily import the three specialist agents and the Gatekeeper Integrator."""
    # Ensure the agent packages are importable.
    sys.path.insert(0, str(_AGENTS_ROOT))

    from architect.architect import ArchitectAgent
    from forge_master.forge_master import CoderAgent
    from pixelsmith.pixelsmith import ArtistAgent
    from gatekeeper.gatekeeper import Integrator

    return ArchitectAgent, CoderAgent, ArtistAgent, Integrator


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(request: dict[str, Any]) -> None:
    """Execute the full Architect → (Coder ∥ Artist) → Integrator DAG."""

    ArchitectAgent, CoderAgent, ArtistAgent, Integrator = _import_agents()

    prompt: str = request.get("prompt", "")
    tier: str = request.get("tier", "Tier1_Starter")
    crafting_station: str | None = request.get("crafting_station")

    if not prompt:
        raise ValueError("Request payload missing 'prompt' field.")

    # --- Step A: signal the TUI ----------------------------------------
    _set_stage("Kindling the Forge...", 5)

    # --- Step B: Architect (sequential) --------------------------------
    log.info("▸ Architect — generating manifest for: %s", prompt[:80])
    _set_stage("Architect — Designing item...", 15)
    architect = ArchitectAgent()
    manifest: dict = architect.generate_manifest(prompt=prompt, tier=tier, crafting_station=crafting_station)
    item_name: str = manifest["item_name"]
    log.info("✓ Architect complete — item: %s", item_name)

    # --- Step C: Coder ∥ Artist (parallel) -----------------------------
    log.info("▸ Starting parallel production — Coder + Artist")
    _set_stage("Smithing code and art...", 40)

    loop = asyncio.get_running_loop()

    coder = CoderAgent()
    artist = ArtistAgent(output_dir=str(OUTPUT_DIR))

    coder_future = loop.run_in_executor(None, coder.write_code, manifest)
    artist_future = loop.run_in_executor(None, artist.generate_asset, manifest)

    code_result, art_result = await asyncio.gather(coder_future, artist_future)

    # Validate Coder output
    if code_result.get("status") != "success":
        err = code_result.get("error", {})
        raise RuntimeError(
            f"CoderAgent failed [{err.get('code', '?')}]: {err.get('message', 'unknown')}"
        )
    log.info("✓ Coder complete")

    # Validate Artist output
    if art_result.get("status") != "success":
        err = art_result.get("error", {})
        raise RuntimeError(
            f"ArtistAgent failed [{err.get('code', '?')}]: {err.get('message', 'unknown')}"
        )
    log.info("✓ Artist complete")

    # --- Step D: Gatekeeper (sequential) --------------------------------
    log.info("▸ Gatekeeper — staging & verifying build")
    _set_stage("Gatekeeper — Compiling mod...", 80)
    integrator = Integrator(coder=coder)
    gate_result = integrator.build_and_verify(
        forge_output=code_result,
        sprite_path=art_result.get("item_sprite_path"),
        projectile_sprite_path=art_result.get("projectile_sprite_path"),
    )

    if gate_result.get("status") != "success":
        raise RuntimeError(
            f"Gatekeeper failed: {gate_result.get('error_message', 'unknown')}"
        )

    # --- Step E: signal success ----------------------------------------
    _set_ready(
        gate_result.get("item_name", item_name),
        manifest=manifest,
        sprite_path=str(art_result.get("item_sprite_path", "")),
    )
    log.info("★ Pipeline complete for %s", item_name)


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

_DEBOUNCE_SECONDS = 1.0


class _RequestHandler(FileSystemEventHandler):
    """Fires the pipeline when ``user_request.json`` changes."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._last_trigger: float = 0.0
        self._loop = loop
        self._lock = asyncio.Lock()

    def _handle_request_event(self, path: Path) -> None:
        if path.resolve() != REQUEST_FILE.resolve():
            return
        if not REQUEST_FILE.exists():
            return

        now = time.monotonic()
        if now - self._last_trigger < _DEBOUNCE_SECONDS:
            log.debug("Debounced duplicate event")
            return
        self._last_trigger = now

        log.info("Detected change → %s", REQUEST_FILE.name)

        try:
            payload = json.loads(REQUEST_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Failed to read request file: %s", exc)
            _set_error(str(exc))
            return

        # Schedule on the main event loop from this watchdog thread.
        asyncio.run_coroutine_threadsafe(self._run_safe(payload), self._loop)

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._handle_request_event(Path(event.src_path))

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._handle_request_event(Path(event.src_path))

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        self._handle_request_event(Path(event.dest_path))

    async def _run_safe(self, request: dict) -> None:
        """Execute the pipeline with top-level error handling."""
        async with self._lock:  # serialise concurrent requests
            try:
                await run_pipeline(request)
            except Exception as exc:
                log.exception("Pipeline failed")
                _set_error(str(exc))


# ---------------------------------------------------------------------------
# Main — run as a daemon
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("The Forge Orchestrator starting up")
    log.info("Watching: %s", REQUEST_FILE)
    log.info("Status:   %s", STATUS_FILE)
    log.info("Heartbeat: %s", HEARTBEAT_FILE)

    # Ensure the watched directory exists.
    REQUEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    _write_heartbeat()

    # Keep the asyncio event loop alive so pipeline tasks can run.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    handler = _RequestHandler(loop)
    observer = Observer()
    observer.schedule(handler, str(REQUEST_FILE.parent), recursive=False)
    observer.start()

    log.info("Watchdog active — waiting for requests…")

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("Shutting down…")
    finally:
        observer.stop()
        observer.join()
        _clear_heartbeat()
        loop.close()
        log.info("Orchestrator stopped.")


if __name__ == "__main__":
    main()
