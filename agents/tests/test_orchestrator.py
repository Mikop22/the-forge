import asyncio
import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from watchdog.events import FileCreatedEvent, FileMovedEvent

from core import atomic_io
import orchestrator


class RunSafeValidationTests(unittest.TestCase):
    def test_invalid_mode_does_not_run_pipeline(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:

            async def run() -> None:
                with mock.patch.object(orchestrator, "run_pipeline") as rp:
                    with mock.patch.object(orchestrator, "run_instant_pipeline") as rip:
                        with mock.patch.object(orchestrator, "_set_error") as se:
                            await handler._run_safe(Path("/tmp/user_request.json"), {"prompt": "x", "mode": "bogus"})
                            rp.assert_not_called()
                            rip.assert_not_called()
                            se.assert_called_once()

            loop.run_until_complete(run())
        finally:
            loop.close()


class RequestHandlerEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.handler = orchestrator._RequestHandler(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_created_request_file_triggers_pipeline(self) -> None:
        with TemporaryDirectory() as tmpdir:
            request_file = (Path(tmpdir) / "user_request.json").resolve()
            request_file.write_text(json.dumps({"prompt": "Blade"}), encoding="utf-8")

            with mock.patch.object(orchestrator, "REQUEST_FILE", request_file), \
                 mock.patch.object(orchestrator.asyncio, "run_coroutine_threadsafe") as runner:
                key = str(request_file.resolve())
                self.handler._last_trigger = {key: time.monotonic() - 2.0}
                self.handler.on_created(FileCreatedEvent(str(request_file)))

            self.assertEqual(runner.call_count, 1)
            runner.call_args.args[0].close()

    def test_moved_request_file_triggers_pipeline(self) -> None:
        with TemporaryDirectory() as tmpdir:
            request_file = (Path(tmpdir) / "user_request.json").resolve()
            request_file.write_text(json.dumps({"prompt": "Blade"}), encoding="utf-8")
            tmp_request = request_file.with_suffix(".tmp")
            tmp_request.write_text(json.dumps({"prompt": "Blade"}), encoding="utf-8")

            with mock.patch.object(orchestrator, "REQUEST_FILE", request_file), \
                 mock.patch.object(orchestrator.asyncio, "run_coroutine_threadsafe") as runner:
                key = str(request_file.resolve())
                self.handler._last_trigger = {key: time.monotonic() - 2.0}
                self.handler.on_moved(FileMovedEvent(str(tmp_request), str(request_file)))

            self.assertEqual(runner.call_count, 1)
            runner.call_args.args[0].close()


class StatusWriterTests(unittest.TestCase):
    def test_write_status_retries_transient_replace_race(self) -> None:
        with TemporaryDirectory() as tmpdir:
            status_file = (Path(tmpdir) / "generation_status.json").resolve()
            original_os_replace = os.replace
            attempts = {"count": 0}

            def flaky_os_replace(src, dst):
                dst_s = os.path.realpath(os.fspath(dst))
                target_s = os.path.realpath(os.fspath(status_file))
                if dst_s == target_s and "generation_status." in os.fspath(src):
                    attempts["count"] += 1
                    if attempts["count"] < 4:
                        raise FileNotFoundError("simulated ModSources race")
                return original_os_replace(src, dst)

            with mock.patch.object(orchestrator, "STATUS_FILE", status_file), \
                 mock.patch.object(atomic_io.os, "replace", new=flaky_os_replace), \
                 mock.patch.object(atomic_io.time, "sleep", return_value=None):
                orchestrator._write_status({"status": "building"})

            self.assertEqual(attempts["count"], 4)
            payload = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "building")


class RequestSubTypeInferenceTests(unittest.TestCase):
    """Keyword inference for weapon sub_type when the TUI sends it empty."""

    def test_explicit_sub_type_passes_through_unchanged(self) -> None:
        req = {"prompt": "frostgun", "content_type": "Weapon", "sub_type": "Staff"}
        self.assertEqual(orchestrator._request_sub_type(req), "Staff")

    def test_frostgun_prompt_infers_gun(self) -> None:
        req = {"prompt": "frostgun", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Gun")

    def test_ice_bow_prompt_infers_bow(self) -> None:
        req = {"prompt": "icy elven bow", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Bow")

    def test_obsidian_pickaxe_prompt_infers_pickaxe(self) -> None:
        # "pickaxe" must win over the "axe" substring inside it.
        req = {"prompt": "obsidian pickaxe", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Pickaxe")

    def test_shotgun_prompt_infers_shotgun_not_gun(self) -> None:
        req = {"prompt": "blizzard shotgun", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Shotgun")

    def test_broadsword_prompt_infers_broadsword_not_sword(self) -> None:
        req = {"prompt": "ancient broadsword of dawn", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Broadsword")

    def test_case_insensitive(self) -> None:
        req = {"prompt": "FROSTGUN", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Gun")

    def test_ambiguous_prompt_falls_back_to_sword(self) -> None:
        # No recognizable weapon noun — preserve current default behavior.
        req = {"prompt": "radiant moonlight artifact", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Sword")

    def test_empty_prompt_falls_back_to_sword(self) -> None:
        req = {"prompt": "", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Sword")

    def test_multi_keyword_prompt_resolves_by_registry_order(self) -> None:
        # "bladed spear" contains both "blade" (→ Sword, low priority) and
        # "spear" (→ Spear, higher priority). Pins the ordering contract so
        # future edits to _WEAPON_SUBTYPE_KEYWORDS can't silently flip precedence.
        req = {"prompt": "bladed spear", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Spear")

    def test_inference_skipped_for_non_weapon_content_type(self) -> None:
        # Tool/Accessory/etc. have their own DEFAULT_SUB_TYPES downstream in
        # architect.prompts. Orchestrator must not stamp "Gun" on a Tool request
        # just because the prompt contains "gun".
        req = {"prompt": "frostgun", "content_type": "Tool"}
        self.assertEqual(orchestrator._request_sub_type(req), "")


if __name__ == "__main__":
    unittest.main()
