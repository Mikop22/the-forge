"""Tests for agents/atomic_io.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.atomic_io import atomic_write_text


class AtomicWriteTests(unittest.TestCase):
    def test_writes_content_and_leaves_no_tmp_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "nested" / "out.json"
            payload = '{"status": "ok"}\n'
            atomic_write_text(target, payload)
            self.assertEqual(target.read_text(encoding="utf-8"), payload)
            tmp_left = list(Path(tmpdir).rglob("*.tmp"))
            self.assertEqual(tmp_left, [], f"unexpected temp files: {tmp_left}")


if __name__ == "__main__":
    unittest.main()
