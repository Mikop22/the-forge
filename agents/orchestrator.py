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
import contextlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv(Path(__file__).parent / ".env")

from contracts.ipc import GenerationStatus, UserRequest
from contracts.session_shell import SessionShellState, SessionShellStatus
from contracts.workshop import BenchState, ShelfVariant, WorkshopRequest, WorkshopStatus

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ModuleNotFoundError:

    class FileSystemEventHandler:  # type: ignore[no-redef]
        pass

    Observer = None

from core.atomic_io import atomic_write_text as _atomic_write_text
from core.paths import mod_sources_root
from core.runtime_contracts import (
    HiddenLabRequest,
    build_hidden_lab_request,
    evaluate_behavior_contract,
    load_hidden_lab_request,
    load_hidden_lab_result,
    runtime_result_has_terminal_evidence,
)
from core.recovery_mode import fingerprint_thesis, next_recovery_mode
from core.workshop_director import build_variants
from core.workshop_session import WorkshopSessionStore
from core.weapon_lab_archive import RuntimeGateRecord, WeaponLabArchive
from core.weapon_lab_models import SearchBudget

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

_MOD_SOURCES = mod_sources_root()
REQUEST_FILE = _MOD_SOURCES / "user_request.json"
STATUS_FILE = _MOD_SOURCES / "generation_status.json"
WORKSHOP_REQUEST_FILE = _MOD_SOURCES / "workshop_request.json"
WORKSHOP_STATUS_FILE = _MOD_SOURCES / "workshop_status.json"
SESSION_SHELL_STATUS_FILE = _MOD_SOURCES / "session_shell_status.json"
WORKSHOP_SESSION_DIR = _MOD_SOURCES / ".forge_workshop_sessions"
HEARTBEAT_FILE = _MOD_SOURCES / "orchestrator_alive.json"
ORCHESTRATOR_LOCK_FILE = _MOD_SOURCES / ".forge_orchestrator.lock"
HIDDEN_LAB_REQUEST_FILE = _MOD_SOURCES / "forge_lab_hidden_request.json"
HIDDEN_LAB_RESULT_FILE = _MOD_SOURCES / "forge_lab_hidden_result.json"
HIDDEN_LAB_RUNTIME_TIMEOUT_S = 90.0

# Where Pixelsmith drops sprites and Forge Master drops code
_AGENTS_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = _AGENTS_ROOT / "output"
WORKSHOP_STORE = WorkshopSessionStore(WORKSHOP_SESSION_DIR)

# ---------------------------------------------------------------------------
# Status helpers (TUI handshake)
# ---------------------------------------------------------------------------


def _write_status(payload: dict) -> None:
    """Atomically write *payload* to ``generation_status.json``.

    Uses a uniquely named temp file in the same directory, fsync, then replace —
    avoids ENOENT from fixed ``generation_status.tmp`` races (cloud sync, AV, coalesced FS events).
    Retries if the ModSources tree is briefly missing.
    """
    text = json.dumps(payload, indent=2) + "\n"
    _atomic_write_text(STATUS_FILE, text)
    log.info("Status → %s", payload.get("status"))


def _write_workshop_status(payload: dict[str, Any]) -> None:
    """Atomically write workshop state for the TUI."""
    validated = WorkshopStatus.model_validate(payload)
    text = validated.model_dump_json(indent=2) + "\n"
    _atomic_write_text(WORKSHOP_STATUS_FILE, text)
    log.info("Workshop → %s", validated.last_action or "update")


def _write_session_shell_status(payload: dict[str, Any]) -> None:
    """Atomically write the minimal shell snapshot for the TUI."""
    validated = SessionShellStatus.model_validate(payload)
    text = validated.model_dump_json(indent=2) + "\n"
    _atomic_write_text(SESSION_SHELL_STATUS_FILE, text)
    log.info("Shell → %s", validated.session_id or "update")


def _read_text_snapshot(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _restore_text_snapshot(path: Path, previous_text: str | None) -> None:
    if previous_text is None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
        return
    _atomic_write_text(path, previous_text)


def _restore_workshop_session_snapshot(
    store: WorkshopSessionStore,
    session_id: str,
    previous_session: dict[str, Any] | None,
) -> None:
    session_path = store._session_path(session_id)
    if previous_session is None:
        with contextlib.suppress(FileNotFoundError):
            session_path.unlink()
        with contextlib.suppress(FileNotFoundError):
            store._active_path.unlink()
        return
    store.save(previous_session)


def _status_snapshot_id(path: Path) -> int | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return int(payload.get("snapshot_id"))
    except (TypeError, ValueError):
        return None


def _reconcile_workshop_mirrors(
    session: dict[str, Any],
    *,
    persist_session: bool = False,
    store: WorkshopSessionStore | None = None,
) -> None:
    session_id = str(session.get("session_id", "")).strip()
    snapshot_id = int(session.get("snapshot_id") or 0)
    if not session_id or snapshot_id <= 0:
        return

    current_workshop_snapshot = _status_snapshot_id(WORKSHOP_STATUS_FILE)
    current_shell_snapshot = _status_snapshot_id(SESSION_SHELL_STATUS_FILE)
    if (
        current_workshop_snapshot == snapshot_id
        and current_shell_snapshot == snapshot_id
    ):
        return

    shell = _session_shell_snapshot(session).model_copy(update={"snapshot_id": snapshot_id})
    shell_payload = shell.model_dump(exclude_none=True)
    workshop_payload = {
        "session_id": session_id,
        "snapshot_id": snapshot_id,
        "bench": session.get("bench", {}),
        "shelf": session.get("shelf", []),
        "last_action": "reconciled",
    }
    active_store = store or WORKSHOP_STORE
    previous_session = active_store.load(session_id) if persist_session else None
    previous_shell_status = _read_text_snapshot(SESSION_SHELL_STATUS_FILE)
    previous_workshop_status = _read_text_snapshot(WORKSHOP_STATUS_FILE)
    try:
        if persist_session:
            active_store.save(session)
        _write_session_shell_status(shell_payload)
        _write_workshop_status(workshop_payload)
    except Exception:
        if persist_session:
            with contextlib.suppress(Exception):
                _restore_workshop_session_snapshot(
                    active_store, session_id, previous_session
                )
        with contextlib.suppress(Exception):
            _restore_text_snapshot(SESSION_SHELL_STATUS_FILE, previous_shell_status)
        with contextlib.suppress(Exception):
            _restore_text_snapshot(WORKSHOP_STATUS_FILE, previous_workshop_status)
        raise


def _validation_error_message(exc: ValidationError) -> str:
    first_error = exc.errors()[0] if exc.errors() else None
    if first_error is None:
        return str(exc)
    message = str(first_error.get("msg") or str(exc))
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message


def _write_heartbeat() -> None:
    body = (
        json.dumps(
            {
                "status": "listening",
                "pid": os.getpid(),
                "timestamp": time.time(),
                "mod_sources_root": str(_MOD_SOURCES.resolve()),
            },
            indent=2,
        )
        + "\n"
    )
    _atomic_write_text(HEARTBEAT_FILE, body)


def _clear_heartbeat() -> None:
    try:
        HEARTBEAT_FILE.unlink()
    except FileNotFoundError:
        pass


def _release_lock() -> None:
    try:
        ORCHESTRATOR_LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _acquire_single_instance_lock() -> None:
    """Refuse to start if another orchestrator holds the lock (same ModSources)."""
    ORCHESTRATOR_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    if ORCHESTRATOR_LOCK_FILE.exists():
        try:
            old_raw = ORCHESTRATOR_LOCK_FILE.read_text(encoding="utf-8").strip()
            old_pid = int(old_raw.splitlines()[0])
        except (OSError, ValueError):
            old_pid = -1
        if _pid_alive(old_pid):
            log.error(
                "Another orchestrator is already running (PID %s, lock %s). Exiting.",
                old_pid,
                ORCHESTRATOR_LOCK_FILE,
            )
            sys.exit(1)
        try:
            ORCHESTRATOR_LOCK_FILE.unlink()
        except OSError:
            pass

    try:
        fd = os.open(
            ORCHESTRATOR_LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{pid}\n")
    except FileExistsError:
        log.error(
            "Lock race on %s — retry or remove stale lock.", ORCHESTRATOR_LOCK_FILE
        )
        sys.exit(1)


def _set_stage(label: str, pct: int) -> None:
    _write_status({"status": "building", "stage_label": label, "stage_pct": pct})


def _set_ready(
    item_name: str,
    manifest: dict | None = None,
    sprite_path: str = "",
    projectile_sprite_path: str = "",
    inject_mode: bool = False,
) -> None:
    _write_status(
        {
            "status": "ready",
            "stage_pct": 100,
            "batch_list": [item_name],
            "message": "Ready for injection."
            if inject_mode
            else "Compilation successful. Waiting for user...",
            "manifest": manifest or {},
            "sprite_path": sprite_path,
            "projectile_sprite_path": projectile_sprite_path,
            "inject_mode": inject_mode,
        }
    )
    _sync_ready_workshop_session(
        item_name=item_name,
        manifest=manifest or {},
        sprite_path=sprite_path,
        projectile_sprite_path=projectile_sprite_path,
    )


def _set_error(message: str) -> None:
    _write_status(
        {
            "status": "error",
            "error_code": "PIPELINE_FAIL",
            "message": f"The pipeline collapsed: {message}",
        }
    )


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "bench-item"


def _bench_snapshot(
    *,
    item_name: str,
    manifest: dict[str, Any] | None,
    sprite_path: str,
    projectile_sprite_path: str,
) -> dict[str, Any]:
    return BenchState(
        item_id=_slugify(item_name),
        label=item_name,
        manifest=manifest or {},
        sprite_path=sprite_path or None,
        projectile_sprite_path=projectile_sprite_path or None,
    ).model_dump(exclude_none=True)


def _next_snapshot_id(session: dict[str, Any]) -> int:
    current = session.get("snapshot_id", 0)
    try:
        current_id = int(current)
    except (TypeError, ValueError):
        current_id = 0
    snapshot_id = current_id + 1
    session["snapshot_id"] = snapshot_id
    return snapshot_id


def _session_shell_snapshot(session: dict[str, Any] | None) -> SessionShellState:
    session = session or {}
    session_id = str(session.get("session_id", "")).strip()
    snapshot_id = session.get("snapshot_id", 0)
    raw_shell = session.get("session_shell")
    if isinstance(raw_shell, dict):
        shell = SessionShellState.model_validate(raw_shell)
        if session_id and not shell.session_id:
            shell = shell.model_copy(update={"session_id": session_id})
        if snapshot_id and not shell.snapshot_id:
            shell = shell.model_copy(update={"snapshot_id": int(snapshot_id)})
        return shell
    return SessionShellState(session_id=session_id, snapshot_id=int(snapshot_id or 0))


def _emit_workshop_snapshot(
    *,
    session: dict[str, Any],
    bench: dict[str, Any] | None = None,
    shelf: list[dict[str, Any]] | None = None,
    last_action: str,
    error: str | None = None,
    persist: bool = True,
) -> None:
    snapshot_id = _next_snapshot_id(session)
    shell = _session_shell_snapshot(session).model_copy(update={"snapshot_id": snapshot_id})
    shell_payload = shell.model_dump(exclude_none=True)
    session["session_shell"] = shell_payload
    session_id = str(session.get("session_id", "")).strip()
    previous_session = WORKSHOP_STORE.load(session_id) if persist and session_id else None
    previous_shell_status = _read_text_snapshot(SESSION_SHELL_STATUS_FILE)
    previous_workshop_status = _read_text_snapshot(WORKSHOP_STATUS_FILE)
    try:
        if persist and session_id:
            WORKSHOP_STORE.save(session)
        _write_session_shell_status(shell_payload)
        _write_workshop_status(
            {
                "session_id": session_id,
                "snapshot_id": snapshot_id,
                "bench": bench if bench is not None else session.get("bench", {}),
                "shelf": shelf if shelf is not None else session.get("shelf", []),
                "last_action": last_action,
                "error": error,
            }
        )
    except Exception:
        if persist and session_id:
            with contextlib.suppress(Exception):
                _restore_workshop_session_snapshot(
                    WORKSHOP_STORE, session_id, previous_session
                )
        with contextlib.suppress(Exception):
            _restore_text_snapshot(SESSION_SHELL_STATUS_FILE, previous_shell_status)
        with contextlib.suppress(Exception):
            _restore_text_snapshot(WORKSHOP_STATUS_FILE, previous_workshop_status)
        raise


def _sync_ready_workshop_session(
    *,
    item_name: str,
    manifest: dict[str, Any],
    sprite_path: str,
    projectile_sprite_path: str,
) -> None:
    if not item_name.strip():
        return
    bench = _bench_snapshot(
        item_name=item_name,
        manifest=manifest,
        sprite_path=sprite_path,
        projectile_sprite_path=projectile_sprite_path,
    )
    session_id = f"bench-{bench['item_id']}"
    session = {
        "session_id": session_id,
        "bench": bench,
        "baseline": bench,
        "last_live": bench,
        "shelf": [],
        "session_shell": SessionShellState(session_id=session_id).model_dump(
            mode="json", exclude_none=True
        ),
    }
    _emit_workshop_snapshot(
        session=session,
        bench=bench,
        shelf=[],
        last_action="ready",
    )


def _load_ready_bench_snapshot() -> dict[str, Any] | None:
    if not STATUS_FILE.exists():
        return None
    try:
        payload = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        ready = GenerationStatus.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError):
        return None
    if ready.status != "ready":
        return None
    item_name = (ready.batch_list or [""])[0]
    if not item_name:
        return None
    return _bench_snapshot(
        item_name=item_name,
        manifest=ready.manifest or {},
        sprite_path=ready.sprite_path or "",
        projectile_sprite_path=ready.projectile_sprite_path or "",
    )


def _load_existing_workshop_session(session_id: str, store: WorkshopSessionStore | None = None) -> dict[str, Any]:
    active_store = store or WORKSHOP_STORE
    cleaned = session_id.strip()
    if cleaned:
        return active_store.load(cleaned)
    return active_store.load_active()


def _load_validation_workshop_session(
    request: WorkshopRequest,
    store: WorkshopSessionStore | None = None,
) -> dict[str, Any]:
    active_store = store or WORKSHOP_STORE
    session_id = request.session_id.strip()
    if session_id:
        session = active_store.load(session_id)
        if not session:
            session = active_store.load_active()
    else:
        session = active_store.load_active()
    if session:
        _reconcile_workshop_mirrors(session, store=active_store)
    return session


def _load_or_bootstrap_workshop_session(
    request: WorkshopRequest,
    *,
    store: WorkshopSessionStore | None = None,
    allow_bootstrap: bool = True,
) -> dict[str, Any]:
    active_store = store or WORKSHOP_STORE
    session_id = request.session_id.strip()
    if session_id:
        session = active_store.load(session_id)
        if not session:
            session = active_store.load_active()
    else:
        active = active_store.load_active()
        if active:
            session = active
        else:
            session = {}

    if session:
        _reconcile_workshop_mirrors(session, store=active_store)
        return session

    if not allow_bootstrap:
        raise RuntimeError("No existing workshop session")

    bench = None
    if request.bench is not None:
        bench = request.bench.model_dump(exclude_none=True)
    if not bench:
        bench = _load_ready_bench_snapshot()
    if not bench:
        raise RuntimeError("No ready bench item is available to start a workshop session")

    item_id = str(bench.get("item_id") or "").strip()
    if not item_id:
        item_id = _slugify(str(bench.get("label") or "bench-item"))
        bench["item_id"] = item_id
    session_id = session_id or f"bench-{item_id}"
    session = {
        "session_id": session_id,
        "bench": bench,
        "baseline": bench,
        "last_live": bench,
        "shelf": [],
        "session_shell": SessionShellState(session_id=session_id).model_dump(
            mode="json", exclude_none=True
        ),
    }
    active_store.save(session)
    return session


def _build_shelf_variants(session: dict[str, Any], directive: str) -> list[dict[str, Any]]:
    bench = dict(session.get("bench") or {})
    variants = build_variants(
        bench_manifest=dict(bench.get("manifest") or {}),
        directive=directive,
        session_id=str(session["session_id"]),
        sprite_path=bench.get("sprite_path"),
        projectile_sprite_path=bench.get("projectile_sprite_path"),
    )
    shelf: list[dict[str, Any]] = []
    for variant in variants:
        shelf.append(ShelfVariant.model_validate(variant).model_dump(exclude_none=True))
    return shelf


def _write_workshop_error(message: str, session: dict[str, Any] | None = None, session_id: str = "") -> None:
    session = session or {}
    persist = bool(session)
    if session_id and not session.get("session_id"):
        session["session_id"] = session_id
    _emit_workshop_snapshot(
        session=session,
        bench=session.get("bench", {}),
        shelf=session.get("shelf", []),
        last_action="error",
        error=message,
        persist=persist,
    )


def _handle_workshop_request(
    request: WorkshopRequest,
    *,
    store: WorkshopSessionStore | None = None,
) -> None:
    active_store = store or WORKSHOP_STORE
    allow_bootstrap = request.action == "variants"
    validation_session = _load_validation_workshop_session(request, active_store)
    current_snapshot_id = int(validation_session.get("snapshot_id") or 0)
    requested_snapshot_id = int(getattr(request, "snapshot_id", 0) or 0)
    if current_snapshot_id > 0:
        if requested_snapshot_id <= 0:
            raise RuntimeError(
                "stale workshop action missing snapshot_id "
                f"(current: {current_snapshot_id})"
            )
        if requested_snapshot_id != current_snapshot_id:
            raise RuntimeError(
                "stale workshop action for snapshot "
                f"{requested_snapshot_id} (current: {current_snapshot_id})"
            )
    current_bench_id = str((validation_session.get("bench") or {}).get("item_id") or "").strip()
    requested_bench_id = str(request.bench_item_id or "").strip()
    if requested_bench_id and current_bench_id and requested_bench_id != current_bench_id:
        raise RuntimeError(
            f"stale workshop action for bench item {requested_bench_id} (current: {current_bench_id})"
        )
    if requested_bench_id and not current_bench_id:
        raise RuntimeError(
            f"stale workshop action for bench item {requested_bench_id} (no active workshop session)"
        )

    session = _load_or_bootstrap_workshop_session(request, store=active_store, allow_bootstrap=allow_bootstrap)
    action = request.action

    if action == "variants":
        directive = (request.directive or "").strip()
        session["shelf"] = _build_shelf_variants(session, directive)
    elif action == "bench":
        variant_id = (request.variant_id or "").strip()
        variant = next(
            (candidate for candidate in session.get("shelf", []) if candidate.get("variant_id") == variant_id),
            None,
        )
        if variant is None:
            raise RuntimeError(f"Unknown variant_id: {variant_id or '<empty>'}")
        session["bench"] = {
            "item_id": str(session["bench"].get("item_id", "")),
            "label": str(variant.get("label") or session["bench"].get("label") or ""),
            "manifest": variant.get("manifest"),
            "sprite_path": variant.get("sprite_path"),
            "projectile_sprite_path": variant.get("projectile_sprite_path"),
        }
    elif action == "restore":
        target = request.restore_target or "baseline"
        snapshot = session.get(target)
        if not snapshot:
            raise RuntimeError(f"No stored snapshot for restore target: {target}")
        session["bench"] = snapshot
    elif action == "try":
        session["last_live"] = dict(session.get("bench") or {})

    _emit_workshop_snapshot(
        session=session,
        bench=session.get("bench", {}),
        shelf=session.get("shelf", []),
        last_action=action,
    )


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


def _import_instant_agents():
    """Lazily import only the agents needed for the instant inject path."""
    sys.path.insert(0, str(_AGENTS_ROOT))

    from architect.architect import ArchitectAgent
    from pixelsmith.pixelsmith import ArtistAgent

    return ArchitectAgent, ArtistAgent


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _request_content_type(request: dict[str, Any]) -> str:
    return str(request.get("content_type") or "Weapon")


def _request_sub_type(request: dict[str, Any]) -> str:
    return str(request.get("sub_type") or "Sword")


def _request_uses_hidden_audition(request: dict[str, Any]) -> bool:
    return bool(request.get("hidden_audition"))


def _build_hidden_audition_finalists(
    *,
    architect: Any,
    prompt: str,
    tier: str,
    content_type: str,
    sub_type: str,
    crafting_station: str | None,
    thesis_count: int,
    finalist_count: int,
) -> list[dict[str, Any]]:
    """Expand architect thesis finalists into manifest finalists for judging."""

    finalist_bundle = architect.generate_thesis_finalists(
        prompt=prompt,
        thesis_count=thesis_count,
        finalist_count=finalist_count,
        selected_tier=tier,
        content_type=content_type,
        sub_type=sub_type,
    )
    return [
        architect.expand_thesis_finalist_to_manifest(
            finalist=finalist,
            prompt=prompt,
            tier=tier,
            content_type=content_type,
            sub_type=sub_type,
            crafting_station=crafting_station,
        )
        for finalist in finalist_bundle.finalists
    ]


def _prepare_preview_manifest(request: dict[str, Any]) -> dict[str, Any] | None:
    existing_manifest = request.get("existing_manifest")
    if not isinstance(existing_manifest, dict):
        return None

    manifest = json.loads(json.dumps(existing_manifest))
    art_feedback = str(request.get("art_feedback") or "").strip()
    if art_feedback:
        visuals = dict(manifest.get("visuals") or {})
        description = str(visuals.get("description") or "").strip()
        feedback_line = f"Art feedback: {art_feedback}"
        visuals["description"] = (
            f"{description} {feedback_line}".strip() if description else feedback_line
        )
        manifest["visuals"] = visuals
    return manifest


def build_hidden_batch_recovery_plan(
    *,
    candidate_archive: WeaponLabArchive | dict[str, Any],
    failed_batches: int,
    quality_threshold: float,
    search_budget: SearchBudget | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan the next reroll for a failed hidden batch without lowering the bar."""

    from architect.thesis_generator import (
        ThesisFinalist,
        build_recovery_thesis_policies,
    )

    archive = WeaponLabArchive.model_validate(candidate_archive)
    explicit_search_budget = (
        SearchBudget.model_validate(search_budget)
        if search_budget is not None
        else None
    )
    recovery_mode = next_recovery_mode(
        failed_batches=failed_batches,
        base_budget=explicit_search_budget,
        quality_threshold=quality_threshold,
    )
    if explicit_search_budget is not None:
        recovery_mode = recovery_mode.model_copy(
            update={"search_budget": explicit_search_budget}
        )

    scored_finalists = _score_hidden_batch_finalists(archive)
    deduped_by_fingerprint: dict[str, tuple[int, str, float]] = {}
    for candidate_id, score in scored_finalists:
        thesis = archive.theses.get(candidate_id)
        if thesis is None:
            continue
        fingerprint = fingerprint_thesis(thesis)
        current = deduped_by_fingerprint.get(fingerprint)
        if current is None or score > current[2]:
            deduped_by_fingerprint[fingerprint] = (
                archive.finalists.index(candidate_id),
                candidate_id,
                score,
            )

    deduped_finalists = [
        (candidate_id, score)
        for _, candidate_id, score in sorted(
            deduped_by_fingerprint.values(), key=lambda item: item[0]
        )
    ]

    near_miss_floor = quality_threshold - 1.0
    best_score = max((score for _, score in deduped_finalists), default=0.0)
    discard_batch = best_score < near_miss_floor

    near_misses = [
        ThesisFinalist(
            candidate_id=candidate_id,
            thesis=archive.theses[candidate_id],
            total_score=score,
        )
        for candidate_id, score in deduped_finalists
        if score >= near_miss_floor
    ]

    recovery_candidates = []
    ancestry = dict(archive.reroll_ancestry)
    if not discard_batch:
        recovery_candidates = build_recovery_thesis_policies(
            finalists=near_misses,
            recovery_mode=recovery_mode,
        )
        ancestry.update(
            {
                candidate.candidate_id: list(candidate.source_candidate_ids)
                for candidate in recovery_candidates
            }
        )

    updated_archive = archive.model_copy(update={"reroll_ancestry": ancestry})
    return {
        "discard_batch": discard_batch,
        "recovery_mode": recovery_mode,
        "search_budget": recovery_mode.search_budget.model_dump(),
        "deduped_candidate_ids": [
            candidate_id for candidate_id, _ in deduped_finalists
        ],
        "recovery_candidates": [
            candidate.model_dump(mode="python") for candidate in recovery_candidates
        ],
        "candidate_archive": updated_archive,
    }


def _score_hidden_batch_finalists(archive: WeaponLabArchive) -> list[tuple[str, float]]:
    scored: list[tuple[str, float]] = []
    for candidate_id in archive.finalists:
        judge_scores = archive.judge_scores.get(candidate_id, [])
        if not judge_scores:
            scored.append((candidate_id, 0.0))
            continue
        total = sum(score.score for score in judge_scores)
        scored.append((candidate_id, round(total / len(judge_scores), 2)))
    return scored


def _hidden_audition_art_sort_key(art_finalist: Any) -> tuple[float, float, str, str]:
    scores = art_finalist.winner_art_scores
    return (
        -float(scores.motif_strength),
        -float(scores.family_coherence),
        str(art_finalist.item_name).lower(),
        str(art_finalist.finalist_id),
    )


def run_hidden_pixelsmith_audition(
    *,
    finalists: list[dict[str, Any]],
    prompt: str,
    output_dir: str | Path | None = None,
    artist: Any | None = None,
) -> dict[str, Any]:
    """Run the hidden Pixelsmith art audition for thesis finalists."""
    if artist is None:
        _, ArtistAgent = _import_instant_agents()
        artist = ArtistAgent(output_dir=str(output_dir or OUTPUT_DIR))
    from core.cross_consistency import apply_hidden_audition_consistency_gate

    art_audition = artist.generate_hidden_audition_finalists(
        finalists=finalists,
        prompt=prompt,
    )
    reviewed = apply_hidden_audition_consistency_gate(
        prompt=prompt,
        finalists=finalists,
        art_audition=art_audition,
    )
    return reviewed.model_dump()


async def run_hidden_lab_runtime_gate(
    *,
    finalist: HiddenLabRequest | dict[str, Any],
    timeout_s: float = 15.0,
    poll_interval_s: float = 0.1,
) -> dict[str, Any]:
    """Write a hidden lab request and wait for runtime evidence."""
    request = (
        finalist
        if isinstance(finalist, HiddenLabRequest)
        else build_hidden_lab_request(finalist=finalist)
    )

    try:
        HIDDEN_LAB_RESULT_FILE.unlink()
    except FileNotFoundError:
        pass

    _atomic_write_text(
        HIDDEN_LAB_REQUEST_FILE,
        json.dumps(request.model_dump(mode="json"), indent=2) + "\n",
    )

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if HIDDEN_LAB_RESULT_FILE.exists():
            payload = json.loads(HIDDEN_LAB_RESULT_FILE.read_text(encoding="utf-8"))
            result = load_hidden_lab_result(payload)
            if (
                result.candidate_id == request.candidate_id
                and result.run_id == request.run_id
            ):
                if not runtime_result_has_terminal_evidence(result):
                    await asyncio.sleep(poll_interval_s)
                    continue
                evaluation = evaluate_behavior_contract(
                    request.behavior_contract, result
                )
                return {
                    "candidate_id": request.candidate_id,
                    "passed_runtime_gate": evaluation.passed,
                    "runtime_gate_reason": evaluation.fail_reason,
                    "observed_hits_to_cashout": evaluation.observed_hits_to_cashout,
                    "observed_time_to_cashout_ms": (
                        evaluation.observed_time_to_cashout_ms
                    ),
                    "runtime_result": result.model_dump(mode="json"),
                }
        await asyncio.sleep(poll_interval_s)

    raise TimeoutError(
        f"Timed out waiting for runtime evidence for {request.candidate_id}"
    )


def _archive_hidden_audition_result(
    *,
    candidate_archive: WeaponLabArchive | dict[str, Any],
    finalist_id: str,
    runtime_result: dict[str, Any],
    final_winner_rationale: str | None = None,
) -> WeaponLabArchive:
    """Record runtime gate evidence without exposing loser details to the TUI."""

    archive = WeaponLabArchive.model_validate(candidate_archive)
    candidate_id = str(runtime_result.get("candidate_id") or finalist_id)
    passed = bool(runtime_result.get("passed_runtime_gate"))
    reason = runtime_result.get("runtime_gate_reason")

    runtime_gate_records = dict(archive.runtime_gate_records)
    runtime_gate_records[candidate_id] = RuntimeGateRecord(
        candidate_id=candidate_id,
        passed=passed,
        reason=str(reason) if reason else None,
        observed_hits_to_cashout=runtime_result.get("observed_hits_to_cashout"),
        observed_time_to_cashout_ms=runtime_result.get("observed_time_to_cashout_ms"),
    )

    rejection_reasons = dict(archive.rejection_reasons)
    update: dict[str, Any] = {"runtime_gate_records": runtime_gate_records}
    if passed:
        update["winning_finalist_id"] = finalist_id
        if final_winner_rationale:
            update["final_winner_rationale"] = final_winner_rationale
    else:
        rejection_reasons[finalist_id] = str(reason or "failed runtime gate")
        update["rejection_reasons"] = rejection_reasons

    return archive.model_copy(update=update)


async def run_hidden_audition_pipeline(
    *,
    finalists: list[dict[str, Any]],
    prompt: str,
    output_dir: str | Path | None = None,
    artist: Any | None = None,
) -> dict[str, Any]:
    """Select one winner only after art review and runtime evidence both pass."""

    from pixelsmith.models import PixelsmithReviewedHiddenAuditionOutput

    reviewed = run_hidden_pixelsmith_audition(
        finalists=finalists,
        prompt=prompt,
        output_dir=output_dir,
        artist=artist,
    )
    audition = PixelsmithReviewedHiddenAuditionOutput.model_validate(reviewed)
    if audition.status == "error":
        error = audition.error
        if error is not None:
            raise RuntimeError(
                f"Hidden Pixelsmith audition failed [{error.code}]: {error.message}"
            )
        raise RuntimeError("Hidden Pixelsmith audition failed")

    finalists_by_id = {
        str(finalist.get("candidate_id") or finalist.get("item_name") or ""): finalist
        for finalist in finalists
    }
    finalists_by_name = {
        str(finalist.get("item_name") or ""): finalist for finalist in finalists
    }

    candidate_archive = audition.candidate_archive
    runtime_passing_finalists: list[tuple[Any, dict[str, Any], dict[str, Any]]] = []
    for art_finalist in audition.art_scored_finalists:
        finalist = finalists_by_id.get(
            art_finalist.finalist_id
        ) or finalists_by_name.get(art_finalist.item_name)
        if finalist is None:
            raise RuntimeError(
                "Unable to map art finalist "
                f"{art_finalist.finalist_id!r}/{art_finalist.item_name!r} "
                "back to a manifest finalist"
            )

        try:
            runtime_request = build_hidden_lab_request(
                finalist=finalist,
                candidate_id=art_finalist.finalist_id,
                sprite_path=art_finalist.item_sprite_path,
                projectile_sprite_path=art_finalist.projectile_sprite_path,
            )
        except ValidationError as exc:
            candidate_archive = candidate_archive.model_copy(
                update={
                    "rejection_reasons": {
                        **candidate_archive.rejection_reasons,
                        art_finalist.finalist_id: _validation_error_message(exc),
                    }
                }
            )
            continue

        runtime_payload = runtime_request.model_dump(mode="json")

        try:
            runtime_result = await run_hidden_lab_runtime_gate(
                finalist=runtime_payload,
                timeout_s=HIDDEN_LAB_RUNTIME_TIMEOUT_S,
            )
        except TimeoutError:
            candidate_archive = candidate_archive.model_copy(
                update={
                    "rejection_reasons": {
                        **candidate_archive.rejection_reasons,
                        art_finalist.finalist_id: "runtime gate timeout",
                    }
                }
            )
            continue
        if runtime_result.get("passed_runtime_gate"):
            runtime_passing_finalists.append(
                (art_finalist, runtime_payload, runtime_result)
            )
            candidate_archive = _archive_hidden_audition_result(
                candidate_archive=candidate_archive,
                finalist_id=art_finalist.finalist_id,
                runtime_result=runtime_result,
            )
            continue

        candidate_archive = _archive_hidden_audition_result(
            candidate_archive=candidate_archive,
            finalist_id=art_finalist.finalist_id,
            runtime_result=runtime_result,
        )

    if runtime_passing_finalists:
        winning_art_finalist, runtime_payload, _ = min(
            runtime_passing_finalists,
            key=lambda entry: _hidden_audition_art_sort_key(entry[0]),
        )
        winner = {
            "candidate_id": winning_art_finalist.finalist_id,
            "item_name": winning_art_finalist.item_name,
            "manifest": runtime_payload["manifest"],
            "item_sprite_path": winning_art_finalist.item_sprite_path,
            "projectile_sprite_path": str(
                runtime_payload.get("projectile_sprite_path") or ""
            ),
        }
        candidate_archive = candidate_archive.model_copy(
            update={
                "winning_finalist_id": winning_art_finalist.finalist_id,
                "final_winner_rationale": (
                    f"{winning_art_finalist.finalist_id} cleared art review and runtime evidence."
                ),
            }
        )
        return {"winner": winner, "candidate_archive": candidate_archive}

    raise RuntimeError("No hidden audition finalist passed the runtime gate")


async def run_pipeline(request: dict[str, Any]) -> None:
    """Execute the full Architect → (Coder ∥ Artist) → Integrator DAG."""

    ArchitectAgent, CoderAgent, ArtistAgent, Integrator = _import_agents()

    prompt: str = request.get("prompt", "")
    tier: str = request.get("tier", "Tier1_Starter")
    crafting_station: str | None = request.get("crafting_station")
    content_type: str = _request_content_type(request)
    sub_type: str = _request_sub_type(request)

    if not prompt:
        raise ValueError("Request payload missing 'prompt' field.")

    # --- Step A: signal the TUI ----------------------------------------
    _set_stage("Kindling the Forge...", 5)

    # --- Step B: Architect (sequential) --------------------------------
    log.info("▸ Architect — generating manifest for: %s", prompt[:80])
    _set_stage("Architect — Designing item...", 15)
    architect = ArchitectAgent()
    art_result: dict[str, Any] | None = None
    if _request_uses_hidden_audition(request):
        artist = ArtistAgent(output_dir=str(OUTPUT_DIR))
        finalists = _build_hidden_audition_finalists(
            architect=architect,
            prompt=prompt,
            tier=tier,
            content_type=content_type,
            sub_type=sub_type,
            crafting_station=crafting_station,
            thesis_count=int(request.get("thesis_count", 3)),
            finalist_count=int(request.get("finalist_count", 2)),
        )
        hidden_result = await run_hidden_audition_pipeline(
            finalists=finalists,
            prompt=prompt,
            output_dir=OUTPUT_DIR,
            artist=artist,
        )
        manifest = dict(hidden_result["winner"]["manifest"])
        art_result = {
            "status": "success",
            "item_sprite_path": hidden_result["winner"].get("item_sprite_path", ""),
            "projectile_sprite_path": hidden_result["winner"].get(
                "projectile_sprite_path", ""
            ),
        }
    else:
        manifest = architect.generate_manifest(
            prompt=prompt,
            tier=tier,
            content_type=content_type,
            sub_type=sub_type,
            crafting_station=crafting_station,
        )
    item_name: str = manifest["item_name"]
    log.info("✓ Architect complete — item: %s", item_name)

    # --- Step C: Coder ∥ Artist (parallel) -----------------------------
    log.info("▸ Starting parallel production — Coder + Artist")
    _set_stage("Smithing code and art...", 40)

    loop = asyncio.get_running_loop()

    coder = CoderAgent()
    if art_result is None:
        artist = ArtistAgent(output_dir=str(OUTPUT_DIR))
        coder_future = loop.run_in_executor(None, coder.write_code, manifest)
        artist_future = loop.run_in_executor(None, artist.generate_asset, manifest)
        code_result, art_result = await asyncio.gather(coder_future, artist_future)
    else:
        code_result = await loop.run_in_executor(None, coder.write_code, manifest)

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
        projectile_sprite_path=str(art_result.get("projectile_sprite_path") or ""),
    )
    log.info("★ Pipeline complete for %s", item_name)


# ---------------------------------------------------------------------------
# Instant Inject Pipeline (Architect → Artist → forge_inject.json)
# ---------------------------------------------------------------------------


async def run_instant_pipeline(request: dict[str, Any]) -> None:
    """Execute the instant inject DAG: Architect → Artist only.

    Skips Coder and Gatekeeper entirely.  Instead of compiling a .tmod,
    writes ``forge_inject.json`` for the ForgeConnector template pool
    to pick up at runtime.
    """
    ArchitectAgent, ArtistAgent = _import_instant_agents()

    prompt: str = request.get("prompt", "")
    tier: str = request.get("tier", "Tier1_Starter")
    crafting_station: str | None = request.get("crafting_station")
    content_type: str = _request_content_type(request)
    sub_type: str = _request_sub_type(request)
    preview_manifest = _prepare_preview_manifest(request)

    if preview_manifest is None and not prompt:
        raise ValueError("Request payload missing 'prompt' field.")

    # --- Step A: signal the TUI ----------------------------------------
    _set_stage("Kindling the Forge...", 5)

    # --- Step B: Architect (sequential) --------------------------------
    if preview_manifest is not None:
        manifest = preview_manifest
        log.info(
            "▸ Reusing existing manifest for preview regeneration: %s",
            manifest.get("item_name", "unknown"),
        )
    else:
        log.info("▸ Architect — generating manifest for: %s", prompt[:80])
        _set_stage("Architect — Designing item...", 15)
        architect = ArchitectAgent()
        manifest = architect.generate_manifest(
            prompt=prompt,
            tier=tier,
            content_type=content_type,
            sub_type=sub_type,
            crafting_station=crafting_station,
        )
    item_name: str = manifest["item_name"]
    log.info("✓ Architect complete — item: %s", item_name)

    # --- Step C: Artist (sequential — no Coder needed) -----------------
    log.info("▸ Artist — generating sprite")
    _set_stage("Pixelsmith — Forging sprite...", 40)

    loop = asyncio.get_running_loop()
    artist = ArtistAgent(output_dir=str(OUTPUT_DIR))
    art_result = await loop.run_in_executor(None, artist.generate_asset, manifest)

    if art_result.get("status") != "success":
        err = art_result.get("error", {})
        raise RuntimeError(
            f"ArtistAgent failed [{err.get('code', '?')}]: {err.get('message', 'unknown')}"
        )
    log.info("✓ Artist complete")

    # --- Step D: Signal success (TUI writes forge_inject.json on confirm) -
    _set_stage("Preparing injection...", 80)
    _set_ready(
        item_name,
        manifest=manifest,
        sprite_path=str(art_result.get("item_sprite_path", "")),
        projectile_sprite_path=str(art_result.get("projectile_sprite_path") or ""),
        inject_mode=True,
    )
    log.info("★ Instant pipeline complete for %s", item_name)


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

_DEBOUNCE_SECONDS = 1.0


class _RequestHandler(FileSystemEventHandler):
    """Fires the pipeline when ``user_request.json`` changes."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._last_trigger: dict[str, float] = {}
        self._loop = loop
        self._lock = asyncio.Lock()

    def _handle_request_event(self, path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return

        watched: Path | None = None
        if resolved == REQUEST_FILE.resolve():
            watched = REQUEST_FILE
        elif resolved == WORKSHOP_REQUEST_FILE.resolve():
            watched = WORKSHOP_REQUEST_FILE
        if watched is None:
            return
        if not watched.exists():
            return

        now = time.monotonic()
        key = str(watched.resolve())
        if now - self._last_trigger.get(key, 0.0) < _DEBOUNCE_SECONDS:
            log.debug("Debounced duplicate event")
            return

        log.info("Detected change → %s", watched.name)

        try:
            payload = json.loads(watched.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self._last_trigger.pop(key, None)
            log.error("Failed to read request file: %s", exc)
            if watched == REQUEST_FILE:
                _set_error(str(exc))
            else:
                _write_workshop_error(str(exc))
            return

        self._last_trigger[key] = now

        # Schedule on the main event loop from this watchdog thread.
        asyncio.run_coroutine_threadsafe(self._run_safe(watched, payload), self._loop)

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

    async def _run_safe(self, source_file: Path, request: dict) -> None:
        """Execute the pipeline with top-level error handling."""
        async with self._lock:  # serialise concurrent requests
            if source_file == WORKSHOP_REQUEST_FILE:
                session: dict[str, Any] | None = None
                try:
                    try:
                        validated = WorkshopRequest.model_validate(request)
                    except ValidationError as exc:
                        log.error("Invalid workshop_request.json: %s", exc)
                        session = _load_existing_workshop_session(
                            str(request.get("session_id", "")),
                            WORKSHOP_STORE,
                        )
                        _write_workshop_error(
                            f"Invalid workshop request: {_validation_error_message(exc)}",
                            session=session,
                            session_id=str(request.get("session_id", "")),
                        )
                        return
                    session = _load_existing_workshop_session(validated.session_id, WORKSHOP_STORE)
                    _handle_workshop_request(validated, store=WORKSHOP_STORE)
                except Exception as exc:
                    log.exception("Workshop request failed")
                    if not session:
                        session = _load_existing_workshop_session(str(request.get("session_id", "")), WORKSHOP_STORE)
                    _write_workshop_error(
                        str(exc),
                        session=session,
                        session_id=str(request.get("session_id", "")),
                    )
                return

            try:
                try:
                    validated = UserRequest.model_validate(request)
                except ValidationError as exc:
                    log.error("Invalid user_request.json: %s", exc)
                    _set_error(f"Invalid request: {exc}")
                    return
                # Merge so Pydantic coercion applies to known fields while unknown keys are kept.
                merged: dict[str, Any] = {**request, **validated.model_dump()}
                mode = merged.get("mode", "compile")
                if mode == "instant":
                    log.info("Mode: instant inject (template pool)")
                    await run_instant_pipeline(merged)
                else:
                    log.info("Mode: full compile")
                    await run_pipeline(merged)
            except Exception as exc:
                log.exception("Pipeline failed")
                _set_error(str(exc))


# ---------------------------------------------------------------------------
# Main — run as a daemon
# ---------------------------------------------------------------------------


def main() -> None:
    if Observer is None:
        raise ModuleNotFoundError("watchdog is required to run the orchestrator daemon")

    log.info("The Forge Orchestrator starting up")
    log.info("ModSources: %s", _MOD_SOURCES.resolve())
    log.info("Watching: %s", REQUEST_FILE)
    log.info("Status:   %s", STATUS_FILE)
    log.info("Workshop request: %s", WORKSHOP_REQUEST_FILE)
    log.info("Workshop status:  %s", WORKSHOP_STATUS_FILE)
    log.info("Heartbeat: %s", HEARTBEAT_FILE)

    # Ensure the watched directory exists.
    REQUEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    _acquire_single_instance_lock()
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
        _release_lock()
        loop.close()
        log.info("Orchestrator stopped.")


if __name__ == "__main__":
    main()
