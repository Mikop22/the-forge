import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from forge_master import compilation_harness


class FindTmodPathTests(unittest.TestCase):
    def test_finds_tmodloader_root_with_nested_fna_layout(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "tModLoader"
            (root / "Libraries" / "FNA" / "1.0.0").mkdir(parents=True)
            (root / "tModLoader.dll").write_text("", encoding="utf-8")
            (root / "Libraries" / "FNA" / "1.0.0" / "FNA.dll").write_text("", encoding="utf-8")

            with mock.patch.dict(os.environ, {"TMODLOADER_PATH": ""}, clear=False), \
                 mock.patch.object(compilation_harness, "_STEAM_PATHS", [root]):
                self.assertEqual(compilation_harness.find_tmod_path(), root)


if __name__ == "__main__":
    unittest.main()
