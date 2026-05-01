import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import orchestrator
from contracts.session_shell import SessionEvent, SessionShellState
from contracts.workshop import WorkshopRequest
from core.workshop_session import WorkshopSessionStore


class WorkshopTransportTests(unittest.TestCase):
    def test_set_ready_bootstraps_workshop_status(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            status_file = root / "generation_status.json"
            workshop_status = root / "workshop_status.json"
            session_shell_status = root / "session_shell_status.json"
            store = WorkshopSessionStore(root / ".forge_workshop_sessions")

            with (
                mock.patch.object(orchestrator, "STATUS_FILE", status_file),
                mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
            ):
                orchestrator._set_ready(
                    "Storm Brand",
                    manifest={"item_name": "Storm Brand"},
                    sprite_path="/tmp/item.png",
                    projectile_sprite_path="/tmp/projectile.png",
                    inject_mode=True,
                )

            payload = json.loads(workshop_status.read_text(encoding="utf-8"))
            self.assertEqual(payload["bench"]["item_id"], "storm-brand")
            self.assertEqual(payload["last_action"], "ready")
            self.assertIn("snapshot_id", payload)
            shell_payload = json.loads(session_shell_status.read_text(encoding="utf-8"))
            self.assertEqual(payload["snapshot_id"], shell_payload["snapshot_id"])
            self.assertEqual(store.load(payload["session_id"])["bench"]["label"], "Storm Brand")

    def test_set_ready_shares_snapshot_id_with_session_shell_status(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            status_file = root / "generation_status.json"
            workshop_status = root / "workshop_status.json"
            session_shell_status = root / "session_shell_status.json"
            store = WorkshopSessionStore(root / ".forge_workshop_sessions")

            with (
                mock.patch.object(orchestrator, "STATUS_FILE", status_file),
                mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
            ):
                orchestrator._set_ready(
                    "Storm Brand",
                    manifest={"item_name": "Storm Brand"},
                    sprite_path="/tmp/item.png",
                    projectile_sprite_path="/tmp/projectile.png",
                    inject_mode=True,
                )

            workshop_payload = json.loads(workshop_status.read_text(encoding="utf-8"))
            shell_payload = json.loads(session_shell_status.read_text(encoding="utf-8"))
            self.assertEqual(workshop_payload["snapshot_id"], shell_payload["snapshot_id"])
            self.assertEqual(workshop_payload["snapshot_id"], 1)
            self.assertEqual(store.load(workshop_payload["session_id"])["snapshot_id"], 1)

    def test_emit_workshop_snapshot_rolls_back_on_status_write_failure(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workshop_status = root / "workshop_status.json"
            session_shell_status = root / "session_shell_status.json"
            store = WorkshopSessionStore(root / ".forge_workshop_sessions")
            store.save(
                {
                    "session_id": "sess-1",
                    "snapshot_id": 3,
                    "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                    "baseline": {"item_id": "storm-brand", "label": "Storm Brand"},
                    "last_live": {"item_id": "storm-brand", "label": "Storm Brand"},
                    "shelf": [],
                    "session_shell": {
                        "session_id": "sess-1",
                        "snapshot_id": 3,
                        "recent_events": [{"kind": "feed", "message": "old feed"}],
                        "pinned_notes": ["keep the cashout"],
                    },
                }
            )
            workshop_status.write_text(
                json.dumps(
                    {
                        "session_id": "sess-1",
                        "snapshot_id": 3,
                        "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "shelf": [],
                        "last_action": "ready",
                    }
                ),
                encoding="utf-8",
            )
            session_shell_status.write_text(
                json.dumps(
                    {
                        "session_id": "sess-1",
                        "snapshot_id": 3,
                        "recent_events": [{"kind": "feed", "message": "old feed"}],
                        "pinned_notes": ["keep the cashout"],
                    }
                ),
                encoding="utf-8",
            )

            session = store.load("sess-1")
            with (
                mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
                mock.patch.object(
                    orchestrator,
                    "_write_workshop_status",
                    side_effect=RuntimeError("boom"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    orchestrator._emit_workshop_snapshot(
                        session=session,
                        bench=session["bench"],
                        shelf=session["shelf"],
                        last_action="ready",
                    )

            self.assertEqual(
                json.loads(workshop_status.read_text(encoding="utf-8"))["snapshot_id"],
                3,
            )
            self.assertEqual(
                json.loads(session_shell_status.read_text(encoding="utf-8"))["snapshot_id"],
                3,
            )
            self.assertEqual(store.load("sess-1")["snapshot_id"], 3)

    def test_workshop_variants_request_writes_shelf(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                workshop_status = root / "workshop_status.json"
                session_shell_status = root / "session_shell_status.json"
                store = WorkshopSessionStore(root / ".forge_workshop_sessions")

                with (
                    mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                    mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                    mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
                ):
                    loop.run_until_complete(
                        handler._run_safe(
                            orchestrator.WORKSHOP_REQUEST_FILE,
                            {
                                "action": "variants",
                                "session_id": "sess-1",
                                "directive": "make the projectile feel heavier",
                                "bench": {
                                    "item_id": "storm-brand",
                                    "label": "Storm Brand",
                                    "manifest": {"item_name": "Storm Brand"},
                                    "sprite_path": "/tmp/item.png",
                                    "projectile_sprite_path": "/tmp/projectile.png",
                                },
                            },
                        )
                    )

                payload = json.loads(workshop_status.read_text(encoding="utf-8"))
                self.assertEqual(payload["session_id"], "sess-1")
                self.assertEqual(payload["last_action"], "variants")
                self.assertEqual(len(payload["shelf"]), 3)
                self.assertEqual(payload["shelf"][0]["label"], "Heavier Shot")
        finally:
            loop.close()

    def test_workshop_error_preserves_loaded_session_snapshot(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                workshop_status = root / "workshop_status.json"
                session_shell_status = root / "session_shell_status.json"
                store = WorkshopSessionStore(root / ".forge_workshop_sessions")
                store.save(
                    {
                        "session_id": "sess-1",
                        "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "baseline": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "last_live": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "shelf": [],
                        "session_shell": SessionShellState(
                            session_id="sess-1",
                            recent_events=[
                                SessionEvent(kind="feed", message="forged manifest"),
                                SessionEvent(kind="memory", message="keep the cashout"),
                            ],
                            pinned_notes=["keep the cashout"],
                        ).model_dump(),
                    }
                )

                with (
                    mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                    mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                    mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
                ):
                    loop.run_until_complete(
                        handler._run_safe(
                            orchestrator.WORKSHOP_REQUEST_FILE,
                            {
                                "action": "bench",
                                "session_id": "sess-1",
                                "variant_id": "missing",
                            },
                        )
                    )

                payload = json.loads(workshop_status.read_text(encoding="utf-8"))
                self.assertEqual(payload["last_action"], "error")
                self.assertEqual(payload["bench"]["item_id"], "storm-brand")
                shell_payload = json.loads(
                    session_shell_status.read_text(encoding="utf-8")
                )
                self.assertEqual(shell_payload["session_id"], "sess-1")
                self.assertEqual(
                    [event["message"] for event in shell_payload["recent_events"]],
                    ["forged manifest", "keep the cashout"],
                )
                self.assertEqual(shell_payload["pinned_notes"], ["keep the cashout"])
                self.assertEqual(payload["snapshot_id"], shell_payload["snapshot_id"])
        finally:
            loop.close()

    def test_workshop_request_rejects_stale_bench_item_id(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                workshop_status = root / "workshop_status.json"
                session_shell_status = root / "session_shell_status.json"
                store = WorkshopSessionStore(root / ".forge_workshop_sessions")
                store.save(
                    {
                        "session_id": "sess-1",
                        "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "baseline": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "last_live": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "shelf": [],
                        "session_shell": {
                            "session_id": "sess-1",
                            "recent_events": [],
                            "pinned_notes": ["keep the cashout"],
                        },
                    }
                )

                with (
                    mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                    mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                    mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
                ):
                    loop.run_until_complete(
                        handler._run_safe(
                            orchestrator.WORKSHOP_REQUEST_FILE,
                            {
                                "action": "bench",
                                "session_id": "sess-1",
                                "bench_item_id": "orbit-furnace",
                                "variant_id": "v1",
                            },
                        )
                    )

                payload = json.loads(workshop_status.read_text(encoding="utf-8"))
                shell_payload = json.loads(session_shell_status.read_text(encoding="utf-8"))
                self.assertEqual(payload["last_action"], "error")
                self.assertIn("stale workshop action", payload["error"])
                self.assertEqual(payload["snapshot_id"], shell_payload["snapshot_id"])
                self.assertEqual(store.active_session_id(), "sess-1")
                self.assertEqual(store.load_active()["session_id"], "sess-1")
        finally:
            loop.close()

    def test_workshop_request_rejects_stale_snapshot_id_even_for_same_bench(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                workshop_status = root / "workshop_status.json"
                session_shell_status = root / "session_shell_status.json"
                store = WorkshopSessionStore(root / ".forge_workshop_sessions")
                store.save(
                    {
                        "session_id": "sess-1",
                        "snapshot_id": 7,
                        "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "baseline": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "last_live": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "shelf": [{"variant_id": "v1", "label": "Heavier Shot"}],
                        "session_shell": {
                            "session_id": "sess-1",
                            "snapshot_id": 7,
                            "recent_events": [],
                            "pinned_notes": ["keep the cashout"],
                        },
                    }
                )

                with (
                    mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                    mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                    mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
                ):
                    loop.run_until_complete(
                        handler._run_safe(
                            orchestrator.WORKSHOP_REQUEST_FILE,
                            {
                                "action": "bench",
                                "session_id": "sess-1",
                                "snapshot_id": 2,
                                "bench_item_id": "storm-brand",
                                "variant_id": "v1",
                            },
                        )
                    )

                payload = json.loads(workshop_status.read_text(encoding="utf-8"))
                shell_payload = json.loads(session_shell_status.read_text(encoding="utf-8"))
                self.assertEqual(payload["last_action"], "error")
                self.assertIn("stale workshop action", payload["error"])
                self.assertEqual(payload["snapshot_id"], shell_payload["snapshot_id"])
                self.assertEqual(payload["snapshot_id"], 8)
                self.assertEqual(store.load("sess-1")["snapshot_id"], 8)
        finally:
            loop.close()

    def test_workshop_request_rejects_missing_snapshot_id_for_active_session(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                workshop_status = root / "workshop_status.json"
                session_shell_status = root / "session_shell_status.json"
                store = WorkshopSessionStore(root / ".forge_workshop_sessions")
                store.save(
                    {
                        "session_id": "sess-1",
                        "snapshot_id": 7,
                        "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "baseline": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "last_live": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "shelf": [{"variant_id": "v1", "label": "Heavier Shot"}],
                        "session_shell": {
                            "session_id": "sess-1",
                            "snapshot_id": 7,
                            "recent_events": [],
                            "pinned_notes": ["keep the cashout"],
                        },
                    }
                )

                with (
                    mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                    mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                    mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
                ):
                    loop.run_until_complete(
                        handler._run_safe(
                            orchestrator.WORKSHOP_REQUEST_FILE,
                            {
                                "action": "bench",
                                "session_id": "sess-1",
                                "bench_item_id": "storm-brand",
                                "variant_id": "v1",
                            },
                        )
                    )

                payload = json.loads(workshop_status.read_text(encoding="utf-8"))
                shell_payload = json.loads(session_shell_status.read_text(encoding="utf-8"))
                self.assertEqual(payload["last_action"], "error")
                self.assertIn("missing snapshot", payload["error"])
                self.assertEqual(payload["snapshot_id"], shell_payload["snapshot_id"])
                self.assertEqual(payload["snapshot_id"], 8)
                self.assertEqual(store.load("sess-1")["snapshot_id"], 8)
        finally:
            loop.close()

    def test_stale_request_without_active_session_does_not_create_one(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                workshop_status = root / "workshop_status.json"
                session_shell_status = root / "session_shell_status.json"
                store = WorkshopSessionStore(root / ".forge_workshop_sessions")

                with (
                    mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                    mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                    mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
                ):
                    loop.run_until_complete(
                        handler._run_safe(
                            orchestrator.WORKSHOP_REQUEST_FILE,
                            {
                                "action": "variants",
                                "session_id": "sess-stale",
                                "bench_item_id": "orbit-furnace",
                                "bench": {
                                    "item_id": "storm-brand",
                                    "label": "Storm Brand",
                                    "manifest": {"item_name": "Storm Brand"},
                                },
                                "directive": "make the projectile feel heavier",
                            },
                        )
                    )

                payload = json.loads(workshop_status.read_text(encoding="utf-8"))
                self.assertEqual(payload["last_action"], "error")
                self.assertIn("stale workshop action", payload["error"])
                self.assertIsNone(store.active_session_id())
                self.assertEqual(store.load_active(), {})
                self.assertFalse(any(store._root.glob("*.json")))
        finally:
            loop.close()

    def test_load_path_reconciles_missing_mirrors_from_persisted_session(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workshop_status = root / "workshop_status.json"
            session_shell_status = root / "session_shell_status.json"
            store = WorkshopSessionStore(root / ".forge_workshop_sessions")
            store.save(
                {
                    "session_id": "sess-1",
                    "snapshot_id": 4,
                    "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                    "shelf": [{"variant_id": "v1", "label": "Heavier Shot"}],
                    "session_shell": {
                        "session_id": "sess-1",
                        "snapshot_id": 4,
                        "recent_events": [{"kind": "feed", "message": "old feed"}],
                        "pinned_notes": ["keep the cashout"],
                    },
                }
            )

            with (
                mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
            ):
                session = orchestrator._load_validation_workshop_session(
                    WorkshopRequest.model_validate(
                        {"action": "bench", "session_id": "sess-1", "variant_id": "v1"}
                    ),
                    store,
                )

            self.assertEqual(session["snapshot_id"], 4)
            self.assertEqual(
                json.loads(workshop_status.read_text(encoding="utf-8"))["snapshot_id"], 4
            )
            self.assertEqual(
                json.loads(session_shell_status.read_text(encoding="utf-8"))["snapshot_id"],
                4,
            )

    def test_load_path_reconciles_mismatched_snapshot_id_from_persisted_session(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workshop_status = root / "workshop_status.json"
            session_shell_status = root / "session_shell_status.json"
            store = WorkshopSessionStore(root / ".forge_workshop_sessions")
            store.save(
                {
                    "session_id": "sess-1",
                    "snapshot_id": 7,
                    "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                    "shelf": [],
                    "session_shell": {
                        "session_id": "sess-1",
                        "snapshot_id": 7,
                        "recent_events": [{"kind": "feed", "message": "old feed"}],
                        "pinned_notes": ["keep the cashout"],
                    },
                }
            )
            workshop_status.write_text(
                json.dumps(
                    {
                        "session_id": "sess-1",
                        "snapshot_id": 2,
                        "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
                        "shelf": [],
                        "last_action": "ready",
                    }
                ),
                encoding="utf-8",
            )
            session_shell_status.write_text(
                json.dumps(
                    {
                        "session_id": "sess-1",
                        "snapshot_id": 2,
                        "recent_events": [{"kind": "feed", "message": "wrong feed"}],
                        "pinned_notes": ["wrong"],
                    }
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                mock.patch.object(orchestrator, "WORKSHOP_STORE", store),
            ):
                session = orchestrator._load_validation_workshop_session(
                    WorkshopRequest.model_validate(
                        {"action": "bench", "session_id": "sess-1", "variant_id": "v1"}
                    ),
                    store,
                )

            self.assertEqual(session["snapshot_id"], 7)
            self.assertEqual(
                json.loads(workshop_status.read_text(encoding="utf-8"))["snapshot_id"], 7
            )
            self.assertEqual(
                json.loads(session_shell_status.read_text(encoding="utf-8"))["snapshot_id"],
                7,
            )

    def test_read_failure_does_not_advance_debounce_clock(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:
            with TemporaryDirectory() as tmpdir:
                request_file = (Path(tmpdir) / "workshop_request.json").resolve()
                request_file.write_text('{"action":"variants"}', encoding="utf-8")
                workshop_status = Path(tmpdir) / "workshop_status.json"
                session_shell_status = Path(tmpdir) / "session_shell_status.json"

                with (
                    mock.patch.object(orchestrator, "WORKSHOP_REQUEST_FILE", request_file),
                    mock.patch.object(orchestrator, "WORKSHOP_STATUS_FILE", workshop_status),
                    mock.patch.object(orchestrator, "SESSION_SHELL_STATUS_FILE", session_shell_status),
                    mock.patch.object(orchestrator.asyncio, "run_coroutine_threadsafe") as runner,
                    mock.patch.object(Path, "read_text", side_effect=OSError("busy")),
                ):
                    handler._last_trigger[str(request_file)] = 0.0
                    handler._handle_request_event(request_file)

                self.assertNotIn(str(request_file), handler._last_trigger)
                self.assertEqual(runner.call_count, 0)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
