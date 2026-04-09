import asyncio
import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import orchestrator_smoke


class OrchestratorSmokeHelperTests(unittest.TestCase):
    def test_write_request_replaces_final_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            request_file = Path(tmpdir) / "user_request.json"
            request_file.write_text('{"prompt":"old"}', encoding="utf-8")

            orchestrator_smoke.write_request(request_file, {"prompt": "new", "tier": "Tier1_Starter"})

            self.assertEqual(
                json.loads(request_file.read_text(encoding="utf-8")),
                {"prompt": "new", "tier": "Tier1_Starter"},
            )
            self.assertFalse(request_file.with_suffix(".json.tmp").exists())

    def test_wait_for_json_reads_matching_payload(self) -> None:
        with TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "generation_status.json"

            def delayed_write() -> None:
                time.sleep(0.05)
                status_file.write_text(json.dumps({"status": "ready"}), encoding="utf-8")

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
        with TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "generation_status.json"
            with mock.patch.object(orchestrator_smoke.orchestrator, "STATUS_FILE", status_file):
                asyncio.run(orchestrator_smoke.fake_run_pipeline({"prompt": "Starfury"}))

            payload = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["batch_list"], ["Smoke: Starfury"])


if __name__ == "__main__":
    unittest.main()
