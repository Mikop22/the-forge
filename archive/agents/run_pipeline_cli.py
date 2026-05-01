#!/usr/bin/env python3
"""Run the Forge pipeline without the TUI or orchestrator daemon.

Loads a request (same shape as ``user_request.json``), runs ``run_pipeline`` or
``run_instant_pipeline``, then optionally writes ``forge_inject.json`` so the
in-game ForgeConnector can inject the item (same contract as
``BubbleTeaTerminal/internal/ipc.WriteInjectFile``).
"""

from __future__ import annotations

_EPILOG = """examples:
  cd agents && python3 run_pipeline_cli.py --request path/to/user_request.json
  python3 run_pipeline_cli.py -r request.json
  python3 run_pipeline_cli.py -r request.json --mode instant
  python3 run_pipeline_cli.py --prompt "A storm brand staff" --no-inject

environment:
  FORGE_MOD_SOURCES_DIR   Override ModSources root (see core.paths.mod_sources_root).
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make ``agents/`` importable when run as ``python3 run_pipeline_cli.py`` from agents/.
_AGENTS_DIR = Path(__file__).resolve().parent
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_AGENTS_DIR / ".env")

import orchestrator  # noqa: E402
from core.atomic_io import atomic_write_text  # noqa: E402
from core.paths import mod_sources_root  # noqa: E402


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def _status_ready_payload() -> dict[str, Any]:
    path = orchestrator.STATUS_FILE
    if not path.is_file():
        raise FileNotFoundError(f"Missing status file after pipeline: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("generation_status.json must be a JSON object")
    if raw.get("status") != "ready":
        msg = raw.get("message", "unknown")
        err = raw.get("error_code", "")
        raise RuntimeError(
            f"Pipeline did not succeed (status={raw.get('status')!r} {err}): {msg}"
        )
    return raw


def write_forge_inject(
    mod_sources: Path,
    *,
    item_name: str,
    manifest: dict[str, Any],
    sprite_path: str,
    projectile_sprite_path: str,
) -> Path:
    """Write ModSources/forge_inject.json (matches Go ``WriteInjectFile``)."""
    payload: dict[str, Any] = {
        "action": "inject",
        "item_name": item_name,
        "manifest": manifest,
        "sprite_path": sprite_path,
        "projectile_sprite_path": projectile_sprite_path,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if not item_name:
        raise ValueError("item_name is empty; cannot write forge_inject.json")
    out = mod_sources / "forge_inject.json"
    text = json.dumps(payload, indent=2) + "\n"
    atomic_write_text(out, text)
    return out


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.strip(),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "-r",
        "--request",
        type=Path,
        help="JSON file with a user_request-shaped payload (prompt, tier, mode, …)",
    )
    p.add_argument(
        "--mode",
        choices=("compile", "instant"),
        help="Override request mode (default: from file or compile)",
    )
    p.add_argument(
        "--prompt",
        type=str,
        default="",
        help="Shorthand when --request is omitted",
    )
    p.add_argument(
        "--tier",
        type=str,
        default="Tier1_Starter",
        help="Shorthand tier when --request is omitted",
    )
    p.add_argument(
        "--no-inject",
        action="store_true",
        help="Do not write forge_inject.json after success",
    )
    return p.parse_args()


def _build_request(ns: argparse.Namespace) -> dict[str, Any]:
    if ns.request is not None:
        req = _read_json(ns.request)
    else:
        if not ns.prompt.strip():
            raise SystemExit("Provide --request FILE or --prompt …")
        req = {
            "prompt": ns.prompt,
            "tier": ns.tier,
            "mode": "compile",
        }
    if ns.mode is not None:
        req["mode"] = ns.mode
    return req


async def _amain() -> int:
    ns = _parse_args()
    request = _build_request(ns)
    mode = str(request.get("mode") or "compile")

    mod_root = mod_sources_root()
    if mode == "instant":
        await orchestrator.run_instant_pipeline(request)
    else:
        await orchestrator.run_pipeline(request)

    if ns.no_inject:
        print("OK — pipeline complete (skipped forge_inject.json).", file=sys.stderr)
        return 0

    st = _status_ready_payload()
    names = st.get("batch_list") or []
    item_name = str(names[0]) if names else ""
    if not item_name:
        m = st.get("manifest") or {}
        if isinstance(m, dict) and m.get("item_name"):
            item_name = str(m["item_name"])
    if not item_name.strip():
        raise RuntimeError(
            "Could not determine item_name from generation_status (batch_list / manifest)"
        )

    out = write_forge_inject(
        mod_root,
        item_name=item_name,
        manifest=dict(st.get("manifest") or {}),
        sprite_path=str(st.get("sprite_path") or ""),
        projectile_sprite_path=str(st.get("projectile_sprite_path") or ""),
    )
    print(f"OK — wrote {out}", file=sys.stderr)
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(_amain()))
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
