from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import orchestrator


JsonPredicate = Callable[[dict[str, Any]], bool]


def build_smoke_request(*, hidden_audition: bool = False) -> dict[str, Any]:
    if not hidden_audition:
        return {"prompt": "Smoke Blade", "tier": "Tier1_Starter"}

    return {
        "prompt": "forge a hidden audition storm weapon",
        "tier": "Tier1_Starter",
        "content_type": "Weapon",
        "sub_type": "Staff",
        "hidden_audition": True,
    }


def write_request(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def wait_for_json(
    path: Path,
    predicate: JsonPredicate,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(poll_interval)
            continue

        if predicate(payload):
            return payload

        time.sleep(poll_interval)

    raise TimeoutError(f"Timed out waiting for {path}") from last_error


async def fake_run_pipeline(request: dict[str, Any]) -> None:
    prompt = request.get("prompt", "").strip()
    item_name = f"Smoke: {prompt}" if prompt else "Smoke Item"
    manifest = request.get("existing_manifest")
    if not isinstance(manifest, dict):
        manifest = None
    orchestrator._set_stage("Smoke test - handling request", 25)
    await asyncio.sleep(0.01)
    orchestrator._set_ready(item_name, manifest=manifest)


def wait_for_absent(
    path: Path, timeout: float = 5.0, poll_interval: float = 0.05
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not path.exists():
            return
        time.sleep(poll_interval)
    raise TimeoutError(f"Timed out waiting for {path} to be removed")


def mod_sources_dir(home: Path) -> Path:
    return (
        home
        / "Library"
        / "Application Support"
        / "Terraria"
        / "tModLoader"
        / "ModSources"
    )


def serve_smoke_orchestrator() -> int:
    from watchdog.observers.polling import PollingObserver

    orchestrator.Observer = PollingObserver
    orchestrator.run_pipeline = fake_run_pipeline
    orchestrator.main()
    return 0


def _tail_log(path: Path) -> str:
    if not path.exists():
        return "<no log output>"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-20:]) if lines else "<no log output>"


def _shutdown_process(proc: subprocess.Popen[str], heartbeat_file: Path) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)
    wait_for_absent(heartbeat_file)


def run_smoke(
    timeout: float = 10.0, request_payload: dict[str, Any] | None = None
) -> int:
    script_path = Path(__file__).resolve()
    agents_dir = script_path.parent

    with tempfile.TemporaryDirectory(prefix="theforge-smoke-home.") as home_dir:
        home = Path(home_dir)
        mod_sources = mod_sources_dir(home)
        request_file = mod_sources / "user_request.json"
        status_file = mod_sources / "generation_status.json"
        heartbeat_file = mod_sources / "orchestrator_alive.json"
        log_file = home / "orchestrator-smoke.log"

        env = os.environ.copy()
        env["HOME"] = str(home)

        with log_file.open("w", encoding="utf-8") as log_handle:
            proc = subprocess.Popen(
                [sys.executable, str(script_path), "--serve"],
                cwd=agents_dir,
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )

        try:
            heartbeat = wait_for_json(
                heartbeat_file,
                lambda data: data.get("status") == "listening" and "pid" in data,
                timeout=timeout,
            )
            write_request(
                request_file,
                request_payload or build_smoke_request(),
            )
            status = wait_for_json(
                status_file,
                lambda data: data.get("status") == "ready" and data.get("batch_list"),
                timeout=timeout,
            )
            print(
                "Smoke PASS: "
                f"heartbeat pid={heartbeat['pid']} "
                f"item={status['batch_list'][0]}"
            )
            return 0
        except Exception as exc:
            log_tail = _tail_log(log_file)
            print(f"Smoke FAIL: {exc}", file=sys.stderr)
            print(log_tail, file=sys.stderr)
            return 1
        finally:
            try:
                _shutdown_process(proc, heartbeat_file)
            except Exception as exc:
                print(f"Smoke shutdown warning: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manual smoke harness for orchestrator file watching."
    )
    parser.add_argument(
        "--serve", action="store_true", help="internal mode for the smoke subprocess"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="seconds to wait for heartbeat and status files",
    )
    parser.add_argument(
        "--hidden-audition",
        action="store_true",
        help="send a hidden-audition-style request through the smoke harness",
    )
    args = parser.parse_args(argv)

    if args.serve:
        return serve_smoke_orchestrator()
    return run_smoke(
        timeout=args.timeout,
        request_payload=build_smoke_request(hidden_audition=args.hidden_audition),
    )


if __name__ == "__main__":
    raise SystemExit(main())
