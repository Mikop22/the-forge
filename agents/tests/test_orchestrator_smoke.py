import asyncio
import builtins
import importlib
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


_TEST_FILE = Path(__file__).resolve()
_AGENTS_DIR = _TEST_FILE.parents[1]
_REPO_ROOT = _TEST_FILE.parents[2]


def _import_orchestrator_smoke(*, missing_watchdog: bool = False):
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if missing_watchdog and (name == "watchdog" or name.startswith("watchdog.")):
            raise ModuleNotFoundError("No module named 'watchdog'")
        return original_import(name, globals, locals, fromlist, level)

    with mock.patch("builtins.__import__", side_effect=guarded_import):
        for import_root in (str(_REPO_ROOT), str(_AGENTS_DIR)):
            if import_root not in sys.path:
                sys.path.insert(0, import_root)
        sys.modules.pop("orchestrator_smoke", None)
        sys.modules.pop("agents.orchestrator_smoke", None)
        sys.modules.pop("orchestrator", None)
        sys.modules.pop("agents.orchestrator", None)
        sys.modules.pop("watchdog", None)
        sys.modules.pop("watchdog.events", None)
        sys.modules.pop("watchdog.observers", None)
        sys.modules.pop("watchdog.observers.polling", None)
        try:
            return importlib.import_module("agents.orchestrator_smoke")
        except ModuleNotFoundError:
            return importlib.import_module("orchestrator_smoke")


class OrchestratorSmokeHelperTests(unittest.TestCase):
    def test_orchestrator_smoke_imports_without_watchdog_dependency(self) -> None:
        module = _import_orchestrator_smoke(missing_watchdog=True)

        self.assertTrue(callable(module.write_request))
        self.assertTrue(callable(module.fake_run_pipeline))

    def test_write_request_replaces_final_file(self) -> None:
        orchestrator_smoke = _import_orchestrator_smoke()

        with TemporaryDirectory() as tmpdir:
            request_file = Path(tmpdir) / "user_request.json"
            request_file.write_text('{"prompt":"old"}', encoding="utf-8")

            orchestrator_smoke.write_request(
                request_file, {"prompt": "new", "tier": "Tier1_Starter"}
            )

            self.assertEqual(
                json.loads(request_file.read_text(encoding="utf-8")),
                {"prompt": "new", "tier": "Tier1_Starter"},
            )
            self.assertFalse(request_file.with_suffix(".json.tmp").exists())

    def test_wait_for_json_reads_matching_payload(self) -> None:
        orchestrator_smoke = _import_orchestrator_smoke()

        with TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "generation_status.json"

            def delayed_write() -> None:
                time.sleep(0.05)
                status_file.write_text(
                    json.dumps({"status": "ready"}), encoding="utf-8"
                )

            writer = threading.Thread(target=delayed_write)
            writer.start()
            try:
                payload = orchestrator_smoke.wait_for_json(
                    status_file,
                    lambda data: data.get("status") == "ready",
                    timeout=1.0,
                    poll_interval=0.01,
                )
            finally:
                writer.join()

            self.assertEqual(payload["status"], "ready")

    def test_fake_run_pipeline_sets_ready_status(self) -> None:
        orchestrator_smoke = _import_orchestrator_smoke()

        with TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "generation_status.json"
            with mock.patch.object(
                orchestrator_smoke.orchestrator, "STATUS_FILE", status_file
            ):
                asyncio.run(
                    orchestrator_smoke.fake_run_pipeline({"prompt": "Starfury"})
                )

            payload = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["batch_list"], ["Smoke: Starfury"])

    def test_fake_run_pipeline_preserves_existing_staff_manifest(self) -> None:
        orchestrator_smoke = _import_orchestrator_smoke()

        with TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "generation_status.json"
            manifest = {
                "item_name": "Storm Verdict",
                "type": "Weapon",
                "sub_type": "Staff",
                "mechanics": {
                    "combat_package": "storm_brand",
                    "delivery_style": "direct",
                    "payoff_rate": "fast",
                },
                "resolved_combat": {"package_key": "storm_brand"},
            }
            with mock.patch.object(
                orchestrator_smoke.orchestrator, "STATUS_FILE", status_file
            ):
                asyncio.run(
                    orchestrator_smoke.fake_run_pipeline(
                        {"prompt": "Storm Verdict", "existing_manifest": manifest}
                    )
                )

            payload = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["manifest"], manifest)
            self.assertEqual(
                payload["manifest"]["mechanics"]["combat_package"], "storm_brand"
            )
            self.assertNotIn("shot_style", payload["manifest"]["mechanics"])

    def test_main_hidden_audition_flag_drives_file_based_smoke_flow(
        self,
    ) -> None:
        orchestrator_smoke = _import_orchestrator_smoke()

        class FakeProc:
            def poll(self):
                return None

            def send_signal(self, _signal):
                return None

            def wait(self, timeout=None):
                return 0

        hidden_manifest = {
            "item_name": "Star Verdict",
            "candidate_id": "candidate-002",
            "type": "Weapon",
            "sub_type": "Staff",
            "mechanics": {
                "combat_package": "storm_brand",
                "delivery_style": "direct",
                "payoff_rate": "fast",
            },
            "resolved_combat": {"package_key": "storm_brand"},
        }
        with TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)

            class _FixedTempDir:
                def __enter__(self_nonlocal):
                    return str(home)

                def __exit__(self_nonlocal, exc_type, exc, tb):
                    return False

            def fake_wait_for_json(path, predicate, timeout=10.0, poll_interval=0.05):
                del timeout, poll_interval
                if path.name == "orchestrator_alive.json":
                    payload = {"status": "listening", "pid": 123}
                    assert predicate(payload)
                    return payload

                request_file = path.parent / "user_request.json"
                written_request = json.loads(request_file.read_text(encoding="utf-8"))
                self.assertTrue(written_request["hidden_audition"])
                self.assertEqual(
                    written_request["prompt"],
                    "forge a hidden audition storm weapon",
                )
                self.assertEqual(written_request["sub_type"], "Staff")
                ready_payload = {
                    "status": "ready",
                    "batch_list": [hidden_manifest["item_name"]],
                    "manifest": hidden_manifest,
                }
                assert predicate(ready_payload)
                return ready_payload

            with (
                mock.patch.object(
                    orchestrator_smoke.tempfile,
                    "TemporaryDirectory",
                    return_value=_FixedTempDir(),
                ),
                mock.patch.object(
                    orchestrator_smoke.subprocess, "Popen", return_value=FakeProc()
                ),
                mock.patch.object(
                    orchestrator_smoke, "wait_for_json", side_effect=fake_wait_for_json
                ),
                mock.patch.object(orchestrator_smoke, "_shutdown_process"),
            ):
                result = orchestrator_smoke.main(
                    ["--timeout", "1", "--hidden-audition"]
                )

            self.assertEqual(result, 0)

    def test_run_pipeline_uses_hidden_audition_winner_for_only_ready_status(
        self,
    ) -> None:
        orchestrator_smoke = _import_orchestrator_smoke()

        class FakeFinalist:
            def __init__(self, candidate_id: str) -> None:
                self.candidate_id = candidate_id

        class FakeArchitect:
            def generate_thesis_finalists(self, **_: object):
                return type(
                    "FinalistBundle",
                    (),
                    {
                        "finalists": [
                            FakeFinalist("candidate-001"),
                            FakeFinalist("candidate-002"),
                        ]
                    },
                )()

            def expand_thesis_finalist_to_manifest(self, *, finalist, **_: object):
                item_name = (
                    "Storm Brand"
                    if finalist.candidate_id == "candidate-001"
                    else "Star Verdict"
                )
                return {
                    "candidate_id": finalist.candidate_id,
                    "item_name": item_name,
                    "type": "Weapon",
                    "sub_type": "Staff",
                    "weapon_thesis": {
                        "fantasy": item_name,
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                }

        class FakeCoder:
            def write_code(self, manifest):
                return {
                    "status": "success",
                    "item_name": manifest["item_name"],
                    "cs_code": "",
                    "hjson_code": "",
                }

        class FakeArtist:
            def __init__(self, output_dir):
                self.output_dir = output_dir

        class FakeIntegrator:
            def __init__(self, coder):
                self.coder = coder

            def build_and_verify(self, **kwargs):
                return {
                    "status": "success",
                    "item_name": kwargs["forge_output"]["item_name"],
                }

        hidden_result = {
            "winner": {
                "candidate_id": "candidate-002",
                "item_name": "Star Verdict",
                "manifest": {
                    "item_name": "Star Verdict",
                    "candidate_id": "candidate-002",
                    "type": "Weapon",
                    "sub_type": "Staff",
                    "mechanics": {
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                    },
                    "resolved_combat": {"package_key": "storm_brand"},
                },
                "item_sprite_path": "/tmp/star-verdict.png",
                "projectile_sprite_path": "",
            },
            "candidate_archive": {
                "prompt": "forge a hidden audition storm weapon",
                "theses": {
                    "candidate-001": {
                        "fantasy": "Storm Brand",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                    "candidate-002": {
                        "fantasy": "Star Verdict",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                },
                "finalists": ["candidate-001", "candidate-002"],
                "rejection_reasons": {"candidate-001": "missing cashout event"},
                "winning_finalist_id": "candidate-002",
            },
        }

        async def run() -> None:
            with (
                mock.patch.object(
                    orchestrator_smoke.orchestrator,
                    "_import_agents",
                    return_value=(FakeArchitect, FakeCoder, FakeArtist, FakeIntegrator),
                ),
                mock.patch.object(
                    orchestrator_smoke.orchestrator,
                    "run_hidden_audition_pipeline",
                    new=mock.AsyncMock(return_value=hidden_result),
                ) as hidden_pipeline,
                mock.patch.object(
                    orchestrator_smoke.orchestrator, "_set_ready"
                ) as set_ready,
            ):
                await orchestrator_smoke.orchestrator.run_pipeline(
                    {
                        "prompt": "forge a hidden audition storm weapon",
                        "tier": "Tier1_Starter",
                        "content_type": "Weapon",
                        "sub_type": "Staff",
                        "hidden_audition": True,
                    }
                )

            hidden_pipeline.assert_awaited_once()
            set_ready.assert_called_once_with(
                "Star Verdict",
                manifest={
                    "item_name": "Star Verdict",
                    "candidate_id": "candidate-002",
                    "type": "Weapon",
                    "sub_type": "Staff",
                    "mechanics": {
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                    },
                    "resolved_combat": {"package_key": "storm_brand"},
                },
                sprite_path="/tmp/star-verdict.png",
                projectile_sprite_path="",
            )

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
