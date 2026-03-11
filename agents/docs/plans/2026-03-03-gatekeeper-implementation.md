# Gatekeeper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Gatekeeper module — an `Integrator` class that stages Coder/Artist outputs into tModLoader's ModSources directory, runs headless tModLoader builds, and self-heals via LLM repair loops.

**Architecture:** Single `gatekeeper/gatekeeper.py` with an `Integrator` class. Pydantic models in `gatekeeper/models.py`. Layered on top of the existing `CompilationHarness` (which stays for fast pre-validation). Gatekeeper calls `CoderAgent.fix_code()` directly for the repair loop. TUI communication via `generation_status.json` in the mod root.

**Tech Stack:** Python 3.10+, subprocess, re, os/shutil, Pydantic v2, LangChain (via CoderAgent)

---

## Task 1: Create Pydantic models

**Files:**
- Create: `gatekeeper/__init__.py`
- Create: `gatekeeper/models.py`
- Create: `gatekeeper/test_gatekeeper.py`

**Step 1: Write the failing test**

In `gatekeeper/test_gatekeeper.py`:

```python
"""Unit tests for gatekeeper module — no LLM, no dotnet required."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import GatekeeperResult, RoslynError


class TestModels(unittest.TestCase):
    """Pydantic models validate and serialize correctly."""

    def test_roslyn_error_round_trip(self):
        err = RoslynError(code="CS0103", message="name does not exist", line=42, file="Foo.cs")
        d = err.model_dump()
        self.assertEqual(d["code"], "CS0103")
        self.assertEqual(d["line"], 42)

    def test_roslyn_error_optional_fields(self):
        err = RoslynError(code="CS0246", message="type not found")
        self.assertIsNone(err.line)
        self.assertIsNone(err.file)

    def test_gatekeeper_result_success(self):
        r = GatekeeperResult(status="success", item_name="FrostBlade", attempts=1)
        d = r.model_dump()
        self.assertEqual(d["status"], "success")
        self.assertIsNone(d["errors"])

    def test_gatekeeper_result_error(self):
        r = GatekeeperResult(
            status="error",
            item_name="FrostBlade",
            attempts=4,
            errors=[RoslynError(code="CS0103", message="x")],
            error_message="Critical Failure",
        )
        self.assertEqual(len(r.errors), 1)

    def test_gatekeeper_result_rejects_invalid_status(self):
        with self.assertRaises(Exception):
            GatekeeperResult(status="banana", item_name="X", attempts=1)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestModels -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models'`

**Step 3: Create the empty package and models**

Create `gatekeeper/__init__.py` (empty file).

Create `gatekeeper/models.py`:

```python
"""Pydantic models for the Gatekeeper module."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class RoslynError(BaseModel):
    """A single Roslyn compiler error extracted from build output."""

    code: str = Field(description="Compiler error code, e.g. 'CS0103'.")
    message: str = Field(description="Full error message text.")
    line: Optional[int] = None
    file: Optional[str] = None


class GatekeeperResult(BaseModel):
    """Final output of Integrator.build_and_verify()."""

    status: Literal["success", "error"]
    item_name: str
    attempts: int
    errors: Optional[list[RoslynError]] = None
    error_message: Optional[str] = None
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestModels -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add gatekeeper/__init__.py gatekeeper/models.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): add Pydantic models for RoslynError and GatekeeperResult"
```

---

## Task 2: Error parsing — extract Roslyn errors from build output

**Files:**
- Modify: `gatekeeper/test_gatekeeper.py` (add TestErrorParsing class)
- Create: `gatekeeper/gatekeeper.py` (start with just the parsing function)

**Step 1: Write the failing test**

Append to `gatekeeper/test_gatekeeper.py`:

```python
class TestErrorParsing(unittest.TestCase):
    """_parse_errors extracts structured RoslynError from compiler output."""

    def test_single_error(self):
        from gatekeeper import Integrator
        output = (
            "Content/Items/FrostBlade.cs(15,9): error CS0103: "
            "The name 'foo' does not exist in the current context"
        )
        errors = Integrator._parse_errors(output)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, "CS0103")
        self.assertEqual(errors[0].line, 15)
        self.assertEqual(errors[0].file, "Content/Items/FrostBlade.cs")
        self.assertIn("foo", errors[0].message)

    def test_multiple_errors(self):
        from gatekeeper import Integrator
        output = (
            "Foo.cs(1,1): error CS0103: x\n"
            "Foo.cs(5,2): error CS0246: y\n"
            "Build FAILED."
        )
        errors = Integrator._parse_errors(output)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0].code, "CS0103")
        self.assertEqual(errors[1].code, "CS0246")

    def test_no_errors(self):
        from gatekeeper import Integrator
        errors = Integrator._parse_errors("Build succeeded.\n0 Warnings.\n0 Errors.")
        self.assertEqual(errors, [])

    def test_warning_not_counted(self):
        from gatekeeper import Integrator
        output = "Foo.cs(1,1): warning CS0168: variable declared but never used"
        errors = Integrator._parse_errors(output)
        self.assertEqual(errors, [])
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestErrorParsing -v`
Expected: FAIL with ImportError

**Step 3: Implement Integrator skeleton with _parse_errors**

Create `gatekeeper/gatekeeper.py`:

```python
"""Gatekeeper — integration and compilation engine for The Forge."""

from __future__ import annotations

import re

from models import RoslynError

# Regex: filename(line,col): error CSxxxx: message
_ERROR_RE = re.compile(
    r"^(?P<file>[^\s(]+)\((?P<line>\d+),\d+\):\s+error\s+(?P<code>CS\d{4}):\s+(?P<message>.+)$",
    re.MULTILINE,
)


class Integrator:
    """Stages mod files, runs tModLoader builds, and self-heals via LLM repair."""

    @staticmethod
    def _parse_errors(output: str) -> list[RoslynError]:
        """Extract structured Roslyn errors from dotnet build output."""
        errors = []
        for m in _ERROR_RE.finditer(output):
            errors.append(RoslynError(
                code=m.group("code"),
                message=m.group("message"),
                line=int(m.group("line")),
                file=m.group("file"),
            ))
        return errors
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestErrorParsing -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add gatekeeper/gatekeeper.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): add Roslyn error parsing from build output"
```

---

## Task 3: Item name extraction from C# source

**Files:**
- Modify: `gatekeeper/test_gatekeeper.py` (add TestItemNameExtraction)
- Modify: `gatekeeper/gatekeeper.py` (add _extract_item_name)

**Step 1: Write the failing test**

```python
class TestItemNameExtraction(unittest.TestCase):
    """_extract_item_name pulls the ModItem class name from C# source."""

    def test_simple_class(self):
        from gatekeeper import Integrator
        code = "public class FrostBlade : ModItem { }"
        self.assertEqual(Integrator._extract_item_name(code), "FrostBlade")

    def test_class_with_namespace(self):
        from gatekeeper import Integrator
        code = "namespace ForgeGeneratedMod {\npublic class GelatinousBlade : ModItem {\n}\n}"
        self.assertEqual(Integrator._extract_item_name(code), "GelatinousBlade")

    def test_no_mod_item_returns_none(self):
        from gatekeeper import Integrator
        code = "public class Foo : MonoBehaviour { }"
        self.assertIsNone(Integrator._extract_item_name(code))

    def test_multiple_classes_returns_mod_item(self):
        from gatekeeper import Integrator
        code = (
            "public class MyProjectile : ModProjectile { }\n"
            "public class MyWeapon : ModItem { }"
        )
        self.assertEqual(Integrator._extract_item_name(code), "MyWeapon")
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestItemNameExtraction -v`
Expected: FAIL with AttributeError (no _extract_item_name)

**Step 3: Implement _extract_item_name**

Add to `gatekeeper/gatekeeper.py` inside `Integrator`:

```python
_ITEM_NAME_RE = re.compile(r"class\s+(\w+)\s*:\s*ModItem\b")

@staticmethod
def _extract_item_name(cs_code: str) -> str | None:
    """Extract the ModItem class name from C# source."""
    m = _ITEM_NAME_RE.search(cs_code)
    return m.group(1) if m else None
```

Move `_ITEM_NAME_RE` to module level alongside `_ERROR_RE`.

**Step 4: Run test to verify it passes**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestItemNameExtraction -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add gatekeeper/gatekeeper.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): add ModItem class name extraction from C# source"
```

---

## Task 4: HJSON merge logic

**Files:**
- Modify: `gatekeeper/test_gatekeeper.py` (add TestHjsonMerge)
- Modify: `gatekeeper/gatekeeper.py` (add _merge_hjson)

**Step 1: Write the failing test**

```python
import tempfile
import os

class TestHjsonMerge(unittest.TestCase):
    """_merge_hjson appends new item keys without overwriting existing ones."""

    def _make_tmpdir(self):
        d = tempfile.mkdtemp(prefix="gatekeeper_test_")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return Path(d)

    def test_creates_file_from_scratch(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        hjson_path = tmp / "Localization" / "en-US.hjson"

        hjson_block = (
            "Mods: {\n"
            "\tForgeGeneratedMod: {\n"
            "\t\tItems: {\n"
            "\t\t\tFrostBlade: {\n"
            "\t\t\t\tDisplayName: Frost Blade\n"
            "\t\t\t\tTooltip: A chilly sword\n"
            "\t\t\t}\n"
            "\t\t}\n"
            "\t}\n"
            "}"
        )
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._merge_hjson(hjson_block, "FrostBlade")

        self.assertTrue(hjson_path.exists())
        content = hjson_path.read_text()
        self.assertIn("FrostBlade", content)
        self.assertIn("Frost Blade", content)

    def test_appends_to_existing(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        loc_dir = tmp / "Localization"
        loc_dir.mkdir(parents=True)
        hjson_path = loc_dir / "en-US.hjson"

        existing = (
            "Mods: {\n"
            "\tForgeGeneratedMod: {\n"
            "\t\tItems: {\n"
            "\t\t\tFrostBlade: {\n"
            "\t\t\t\tDisplayName: Frost Blade\n"
            "\t\t\t\tTooltip: A chilly sword\n"
            "\t\t\t}\n"
            "\t\t}\n"
            "\t}\n"
            "}"
        )
        hjson_path.write_text(existing)

        new_block = (
            "Mods: {\n"
            "\tForgeGeneratedMod: {\n"
            "\t\tItems: {\n"
            "\t\t\tFireSword: {\n"
            "\t\t\t\tDisplayName: Fire Sword\n"
            "\t\t\t\tTooltip: A hot sword\n"
            "\t\t\t}\n"
            "\t\t}\n"
            "\t}\n"
            "}"
        )
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._merge_hjson(new_block, "FireSword")

        content = hjson_path.read_text()
        self.assertIn("FrostBlade", content)
        self.assertIn("FireSword", content)

    def test_does_not_duplicate_existing_item(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        loc_dir = tmp / "Localization"
        loc_dir.mkdir(parents=True)
        hjson_path = loc_dir / "en-US.hjson"

        existing = (
            "Mods: {\n"
            "\tForgeGeneratedMod: {\n"
            "\t\tItems: {\n"
            "\t\t\tFrostBlade: {\n"
            "\t\t\t\tDisplayName: Frost Blade\n"
            "\t\t\t\tTooltip: Old tooltip\n"
            "\t\t\t}\n"
            "\t\t}\n"
            "\t}\n"
            "}"
        )
        hjson_path.write_text(existing)

        # Same item name, updated tooltip
        new_block = (
            "Mods: {\n"
            "\tForgeGeneratedMod: {\n"
            "\t\tItems: {\n"
            "\t\t\tFrostBlade: {\n"
            "\t\t\t\tDisplayName: Frost Blade\n"
            "\t\t\t\tTooltip: New tooltip\n"
            "\t\t\t}\n"
            "\t\t}\n"
            "\t}\n"
            "}"
        )
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._merge_hjson(new_block, "FrostBlade")

        content = hjson_path.read_text()
        # Should have the new tooltip, not the old
        self.assertIn("New tooltip", content)
        # Should only have one FrostBlade entry
        self.assertEqual(content.count("FrostBlade:"), 1)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestHjsonMerge -v`
Expected: FAIL with AttributeError (no _merge_hjson)

**Step 3: Implement _merge_hjson**

Add to `gatekeeper/gatekeeper.py`:

```python
import os
from pathlib import Path

# Regex to extract the item block from CoderAgent's HJSON output
_ITEM_BLOCK_RE = re.compile(
    r"(\w+):\s*\{[^{}]*DisplayName:[^\n]*\n[^{}]*Tooltip:[^\n]*\n\s*\}",
    re.DOTALL,
)

class Integrator:
    # ... existing code ...

    def _merge_hjson(self, hjson_block: str, item_name: str) -> None:
        """Append or replace an item's HJSON block in en-US.hjson."""
        hjson_path = self._mod_root / "Localization" / "en-US.hjson"
        hjson_path.parent.mkdir(parents=True, exist_ok=True)

        if not hjson_path.exists():
            hjson_path.write_text(hjson_block, encoding="utf-8")
            return

        existing = hjson_path.read_text(encoding="utf-8")

        # Extract the new item's inner block (ItemName: { ... })
        new_item_re = re.compile(
            rf"({re.escape(item_name)}:\s*\{{[^{{}}]*\}})", re.DOTALL
        )
        new_match = new_item_re.search(hjson_block)
        if not new_match:
            # Fallback: just write the whole block
            hjson_path.write_text(hjson_block, encoding="utf-8")
            return

        new_item_block = new_match.group(1)

        # Check if this item already exists in the file
        existing_match = new_item_re.search(existing)
        if existing_match:
            # Replace the existing block with the new one
            updated = existing[:existing_match.start()] + new_item_block + existing[existing_match.end():]
            hjson_path.write_text(updated, encoding="utf-8")
        else:
            # Insert before the closing of the Items block
            # Find the last } before the file's final two closing braces
            # Pattern: insert before the "\t\t}\n" that closes Items
            items_close = re.search(r"(\n\t\t\})", existing)
            if items_close:
                insert_pos = items_close.start()
                indent = "\t\t\t"
                updated = existing[:insert_pos] + "\n" + indent + new_item_block + existing[insert_pos:]
                hjson_path.write_text(updated, encoding="utf-8")
            else:
                hjson_path.write_text(hjson_block, encoding="utf-8")
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestHjsonMerge -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add gatekeeper/gatekeeper.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): add HJSON merge logic for localization files"
```

---

## Task 5: File staging — write CS, PNG, build.txt, description.txt

**Files:**
- Modify: `gatekeeper/test_gatekeeper.py` (add TestFileStaging)
- Modify: `gatekeeper/gatekeeper.py` (add _stage_files, _ensure_build_files)

**Step 1: Write the failing test**

```python
class TestFileStaging(unittest.TestCase):
    """_stage_files writes CS and PNG to the correct locations."""

    def _make_tmpdir(self):
        d = tempfile.mkdtemp(prefix="gatekeeper_test_")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return Path(d)

    def test_stages_cs_file(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        code = "public class FrostBlade : ModItem { }"
        intg._stage_files(code, "", "FrostBlade", sprite_path=None)

        cs_path = tmp / "Content" / "Items" / "FrostBlade.cs"
        self.assertTrue(cs_path.exists())
        self.assertEqual(cs_path.read_text(), code)

    def test_stages_png_file(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp

        # Create a fake sprite
        sprite_dir = self._make_tmpdir()
        sprite = sprite_dir / "FrostBlade.png"
        sprite.write_bytes(b"\x89PNG_fake_data")

        intg._stage_files("class FrostBlade : ModItem {}", "", "FrostBlade", str(sprite))

        png_path = tmp / "Content" / "Items" / "FrostBlade.png"
        self.assertTrue(png_path.exists())
        self.assertEqual(png_path.read_bytes(), b"\x89PNG_fake_data")

    def test_creates_build_txt_if_missing(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._ensure_build_files()

        build_txt = tmp / "build.txt"
        desc_txt = tmp / "description.txt"
        self.assertTrue(build_txt.exists())
        self.assertTrue(desc_txt.exists())
        self.assertIn("ForgeGeneratedMod", build_txt.read_text())

    def test_does_not_overwrite_existing_build_txt(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        build_txt = tmp / "build.txt"
        build_txt.write_text("custom content")

        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._ensure_build_files()

        self.assertEqual(build_txt.read_text(), "custom content")

    def test_does_not_wipe_existing_items(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        items_dir = tmp / "Content" / "Items"
        items_dir.mkdir(parents=True)
        (items_dir / "OldWeapon.cs").write_text("old code")

        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._stage_files("class NewWeapon : ModItem {}", "", "NewWeapon", None)

        # Old file must still exist
        self.assertTrue((items_dir / "OldWeapon.cs").exists())
        self.assertTrue((items_dir / "NewWeapon.cs").exists())
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestFileStaging -v`
Expected: FAIL with AttributeError

**Step 3: Implement _stage_files and _ensure_build_files**

Add to `Integrator` class in `gatekeeper/gatekeeper.py`:

```python
import shutil

_DEFAULT_BUILD_TXT = """\
displayName = ForgeGeneratedMod
author = The Forge
version = 0.1
"""

_DEFAULT_DESCRIPTION_TXT = "A mod generated by The Forge.\n"


class Integrator:
    # ... existing code ...

    def _stage_files(
        self,
        cs_code: str,
        hjson_code: str,
        item_name: str,
        sprite_path: str | None,
    ) -> None:
        """Write CS and PNG to Content/Items/."""
        items_dir = self._mod_root / "Content" / "Items"
        items_dir.mkdir(parents=True, exist_ok=True)

        (items_dir / f"{item_name}.cs").write_text(cs_code, encoding="utf-8")

        if sprite_path and Path(sprite_path).exists():
            shutil.copy2(sprite_path, items_dir / f"{item_name}.png")

        if hjson_code:
            self._merge_hjson(hjson_code, item_name)

        self._ensure_build_files()

    def _ensure_build_files(self) -> None:
        """Create build.txt and description.txt if they don't exist."""
        build_txt = self._mod_root / "build.txt"
        desc_txt = self._mod_root / "description.txt"
        if not build_txt.exists():
            build_txt.write_text(_DEFAULT_BUILD_TXT, encoding="utf-8")
        if not desc_txt.exists():
            desc_txt.write_text(_DEFAULT_DESCRIPTION_TXT, encoding="utf-8")
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestFileStaging -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add gatekeeper/gatekeeper.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): add file staging for CS, PNG, build.txt, description.txt"
```

---

## Task 6: TUI status writer

**Files:**
- Modify: `gatekeeper/test_gatekeeper.py` (add TestStatusWriter)
- Modify: `gatekeeper/gatekeeper.py` (add _write_status)

**Step 1: Write the failing test**

```python
import json

class TestStatusWriter(unittest.TestCase):
    """_write_status writes generation_status.json to mod root."""

    def _make_tmpdir(self):
        d = tempfile.mkdtemp(prefix="gatekeeper_test_")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return Path(d)

    def test_writes_building_status(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._write_status({"status": "building"})

        status_file = tmp / "generation_status.json"
        self.assertTrue(status_file.exists())
        data = json.loads(status_file.read_text())
        self.assertEqual(data["status"], "building")

    def test_writes_ready_status(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._write_status({
            "status": "ready",
            "message": "Compilation successful. Waiting for user...",
        })

        data = json.loads((tmp / "generation_status.json").read_text())
        self.assertEqual(data["status"], "ready")

    def test_writes_error_status(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._write_status({
            "status": "error",
            "error_code": "CS0103",
            "message": "Critical Failure: The compiler rejected the generated logic.",
        })

        data = json.loads((tmp / "generation_status.json").read_text())
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_code"], "CS0103")
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestStatusWriter -v`
Expected: FAIL with AttributeError

**Step 3: Implement _write_status**

Add to `Integrator` class:

```python
import json as _json

def _write_status(self, status_dict: dict) -> None:
    """Write generation_status.json to the mod root directory."""
    self._mod_root.mkdir(parents=True, exist_ok=True)
    status_path = self._mod_root / "generation_status.json"
    status_path.write_text(
        _json.dumps(status_dict, indent=2) + "\n", encoding="utf-8"
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestStatusWriter -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add gatekeeper/gatekeeper.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): add TUI status writer for generation_status.json"
```

---

## Task 7: tModLoader build subprocess

**Files:**
- Modify: `gatekeeper/test_gatekeeper.py` (add TestBuildCommand)
- Modify: `gatekeeper/gatekeeper.py` (add _run_tmod_build)

**Step 1: Write the failing test**

```python
from unittest.mock import patch, MagicMock

class TestBuildCommand(unittest.TestCase):
    """_run_tmod_build invokes the correct subprocess command."""

    def _make_tmpdir(self):
        d = tempfile.mkdtemp(prefix="gatekeeper_test_")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return Path(d)

    @patch("gatekeeper.subprocess.run")
    def test_calls_dotnet_with_correct_args(self, mock_run):
        from gatekeeper import Integrator
        mock_run.return_value = MagicMock(returncode=0, stdout="Build succeeded.", stderr="")

        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp / "ModSources" / "ForgeGeneratedMod"
        intg._tmod_dll = Path("/fake/tModLoader.dll")

        result = intg._run_tmod_build()
        self.assertTrue(result.success)

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        self.assertEqual(cmd[0], "dotnet")
        self.assertIn("/fake/tModLoader.dll", cmd)
        self.assertIn("-build", cmd)
        self.assertIn("-eac", cmd)

    @patch("gatekeeper.subprocess.run")
    def test_captures_failure(self, mock_run):
        from gatekeeper import Integrator
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Foo.cs(1,1): error CS0103: x does not exist",
        )

        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp / "ModSources" / "ForgeGeneratedMod"
        intg._tmod_dll = Path("/fake/tModLoader.dll")

        result = intg._run_tmod_build()
        self.assertFalse(result.success)
        self.assertIn("CS0103", result.output)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestBuildCommand -v`
Expected: FAIL with AttributeError

**Step 3: Implement _run_tmod_build**

Add to `gatekeeper/gatekeeper.py`:

```python
import subprocess
from dataclasses import dataclass

@dataclass
class CompileResult:
    success: bool
    output: str

class Integrator:
    # ... existing code ...

    def _run_tmod_build(self) -> CompileResult:
        """Run the tModLoader headless build as a blocking subprocess."""
        mod_name = self._mod_root.name
        mod_sources_dir = self._mod_root.parent

        cmd = [
            "dotnet",
            str(self._tmod_dll),
            "-build",
            mod_name,
            "-eac",
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(mod_sources_dir),
        )
        output = proc.stdout + proc.stderr
        return CompileResult(success=proc.returncode == 0, output=output)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestBuildCommand -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add gatekeeper/gatekeeper.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): add tModLoader headless build subprocess invocation"
```

---

## Task 8: __init__ and build_and_verify — the main orchestration

**Files:**
- Modify: `gatekeeper/test_gatekeeper.py` (add TestBuildAndVerify)
- Modify: `gatekeeper/gatekeeper.py` (add __init__, build_and_verify)

**Step 1: Write the failing test**

```python
class TestBuildAndVerify(unittest.TestCase):
    """build_and_verify orchestrates staging, building, and self-healing."""

    def _make_tmpdir(self):
        d = tempfile.mkdtemp(prefix="gatekeeper_test_")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return Path(d)

    def _forge_output(self, cs_code="public class TestItem : ModItem {}"):
        return {
            "cs_code": cs_code,
            "hjson_code": "Mods: {\n\tForgeGeneratedMod: {\n\t\tItems: {\n\t\t\tTestItem: {\n\t\t\t\tDisplayName: Test\n\t\t\t\tTooltip: t\n\t\t\t}\n\t\t}\n\t}\n}",
            "status": "success",
        }

    @patch("gatekeeper.Integrator._run_tmod_build")
    def test_success_on_first_try(self, mock_build):
        from gatekeeper import Integrator
        from models import GatekeeperResult
        mock_build.return_value = CompileResult(success=True, output="Build succeeded.")

        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._tmod_dll = Path("/fake/tModLoader.dll")
        intg._coder = None
        intg._max_retries = 3

        result = intg.build_and_verify(self._forge_output())
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["attempts"], 1)

        # Check status file was written
        status = json.loads((tmp / "generation_status.json").read_text())
        self.assertEqual(status["status"], "ready")

    @patch("gatekeeper.Integrator._run_tmod_build")
    def test_retries_on_failure_then_succeeds(self, mock_build):
        from gatekeeper import Integrator

        fail_result = CompileResult(
            success=False,
            output="TestItem.cs(5,1): error CS0103: 'foo' does not exist",
        )
        success_result = CompileResult(success=True, output="Build succeeded.")
        mock_build.side_effect = [fail_result, success_result]

        mock_coder = MagicMock()
        mock_coder.fix_code.return_value = {
            "cs_code": "public class TestItem : ModItem { /* fixed */ }",
            "status": "success",
        }

        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._tmod_dll = Path("/fake/tModLoader.dll")
        intg._coder = mock_coder
        intg._max_retries = 3

        result = intg.build_and_verify(self._forge_output())
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["attempts"], 2)
        mock_coder.fix_code.assert_called_once()

    @patch("gatekeeper.Integrator._run_tmod_build")
    def test_aborts_after_max_retries(self, mock_build):
        from gatekeeper import Integrator

        fail_result = CompileResult(
            success=False,
            output="TestItem.cs(5,1): error CS0103: 'foo' does not exist",
        )
        mock_build.return_value = fail_result

        mock_coder = MagicMock()
        mock_coder.fix_code.return_value = {
            "cs_code": "public class TestItem : ModItem { /* still broken */ }",
            "status": "success",
        }

        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._tmod_dll = Path("/fake/tModLoader.dll")
        intg._coder = mock_coder
        intg._max_retries = 3

        result = intg.build_and_verify(self._forge_output())
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["attempts"], 4)  # 1 initial + 3 retries
        self.assertEqual(mock_coder.fix_code.call_count, 3)

        # Check error status file
        status = json.loads((tmp / "generation_status.json").read_text())
        self.assertEqual(status["status"], "error")
        self.assertIn("CS0103", status["error_code"])

    @patch("gatekeeper.Integrator._run_tmod_build")
    def test_aborts_if_coder_returns_error(self, mock_build):
        from gatekeeper import Integrator

        fail_result = CompileResult(
            success=False,
            output="TestItem.cs(5,1): error CS0103: 'foo' does not exist",
        )
        mock_build.return_value = fail_result

        mock_coder = MagicMock()
        mock_coder.fix_code.return_value = {
            "cs_code": "",
            "status": "error",
            "error": {"code": "VALIDATION", "message": "LLM gave up"},
        }

        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._tmod_dll = Path("/fake/tModLoader.dll")
        intg._coder = mock_coder
        intg._max_retries = 3

        result = intg.build_and_verify(self._forge_output())
        self.assertEqual(result["status"], "error")

    def test_rejects_error_forge_output(self):
        from gatekeeper import Integrator
        tmp = self._make_tmpdir()
        intg = Integrator.__new__(Integrator)
        intg._mod_root = tmp
        intg._tmod_dll = Path("/fake/tModLoader.dll")
        intg._coder = None
        intg._max_retries = 3

        result = intg.build_and_verify({"cs_code": "", "hjson_code": "", "status": "error"})
        self.assertEqual(result["status"], "error")
```

Note: import `CompileResult` at the top of the test file:
```python
from gatekeeper import Integrator, CompileResult
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestBuildAndVerify -v`
Expected: FAIL

**Step 3: Implement __init__ and build_and_verify**

Add to `gatekeeper/gatekeeper.py`:

```python
import os

# At module level, reuse find_tmod_path from compilation_harness
try:
    from forge_master.compilation_harness import find_tmod_path
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "forge_master"))
    from compilation_harness import find_tmod_path

_MAX_RETRIES = 3

_DEFAULT_MOD_SOURCE_PATH = (
    Path.home() / "Documents" / "My Games" / "Terraria"
    / "tModLoader" / "ModSources" / "ForgeGeneratedMod"
)


class Integrator:
    """Stages mod files, runs tModLoader builds, and self-heals via LLM repair."""

    def __init__(self, coder=None) -> None:
        mod_source = os.environ.get("MOD_SOURCE_PATH")
        self._mod_root = Path(mod_source) if mod_source else _DEFAULT_MOD_SOURCE_PATH

        tmod_path = find_tmod_path()
        self._tmod_dll = (tmod_path / "tModLoader.dll") if tmod_path else None

        self._coder = coder
        self._max_retries = _MAX_RETRIES

    def build_and_verify(self, forge_output: dict, sprite_path: str | None = None) -> dict:
        """Main entry point. Stage files, build, self-heal, return result."""
        # Reject error outputs from the Coder
        if forge_output.get("status") == "error":
            return GatekeeperResult(
                status="error",
                item_name="",
                attempts=0,
                error_message="Received error output from CoderAgent.",
            ).model_dump()

        cs_code = forge_output["cs_code"]
        hjson_code = forge_output.get("hjson_code", "")
        item_name = self._extract_item_name(cs_code)

        if not item_name:
            return GatekeeperResult(
                status="error",
                item_name="",
                attempts=0,
                error_message="Could not extract ModItem class name from C# source.",
            ).model_dump()

        # 1. Write "building" status
        self._write_status({"status": "building"})

        # 2. Stage files
        self._stage_files(cs_code, hjson_code, item_name, sprite_path)

        # 3. Build + retry loop
        for attempt in range(1, self._max_retries + 2):  # 1 initial + max_retries
            result = self._run_tmod_build()

            if result.success:
                self._write_status({
                    "status": "ready",
                    "message": "Compilation successful. Waiting for user...",
                })
                return GatekeeperResult(
                    status="success",
                    item_name=item_name,
                    attempts=attempt,
                ).model_dump()

            errors = self._parse_errors(result.output)

            # Last attempt — no more retries
            if attempt > self._max_retries:
                error_code = errors[0].code if errors else "UNKNOWN"
                self._write_status({
                    "status": "error",
                    "error_code": error_code,
                    "message": "Critical Failure: The compiler rejected the generated logic.",
                })
                return GatekeeperResult(
                    status="error",
                    item_name=item_name,
                    attempts=attempt,
                    errors=errors,
                    error_message=f"Build failed after {self._max_retries} retries.",
                ).model_dump()

            # Attempt repair via CoderAgent
            if not self._coder:
                # Lazy-init CoderAgent
                try:
                    from forge_master.forge_master import CoderAgent
                except ImportError:
                    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "forge_master"))
                    from forge_master import CoderAgent
                self._coder = CoderAgent()

            repair_result = self._coder.fix_code(
                error_log=result.output,
                original_code=cs_code,
            )

            if repair_result.get("status") == "error":
                error_code = errors[0].code if errors else "UNKNOWN"
                self._write_status({
                    "status": "error",
                    "error_code": error_code,
                    "message": "Critical Failure: The compiler rejected the generated logic.",
                })
                return GatekeeperResult(
                    status="error",
                    item_name=item_name,
                    attempts=attempt + 1,
                    errors=errors,
                    error_message="CoderAgent repair failed.",
                ).model_dump()

            cs_code = repair_result["cs_code"]
            self._stage_files(cs_code, hjson_code, item_name, sprite_path=None)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestBuildAndVerify -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add gatekeeper/gatekeeper.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): implement build_and_verify orchestration with self-healing loop"
```

---

## Task 9: Integrator.__init__ with env config and conftest

**Files:**
- Create: `gatekeeper/conftest.py`
- Modify: `gatekeeper/test_gatekeeper.py` (add TestInit)

**Step 1: Write the failing test**

Add `conftest.py`:

```python
import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: real tModLoader build (slow, requires TMODLOADER_PATH)",
    )
```

Add test:

```python
class TestInit(unittest.TestCase):
    """Integrator reads configuration from environment."""

    @patch.dict(os.environ, {"MOD_SOURCE_PATH": "/custom/path/MyMod"}, clear=False)
    def test_custom_mod_source_path(self):
        from gatekeeper import Integrator
        intg = Integrator.__new__(Integrator)
        intg.__init__()
        self.assertEqual(intg._mod_root, Path("/custom/path/MyMod"))

    @patch.dict(os.environ, {}, clear=False)
    def test_default_mod_source_path(self):
        from gatekeeper import Integrator
        # Remove MOD_SOURCE_PATH if set
        os.environ.pop("MOD_SOURCE_PATH", None)
        intg = Integrator.__new__(Integrator)
        intg.__init__()
        self.assertIn("ForgeGeneratedMod", str(intg._mod_root))
```

**Step 2: Run test to verify it passes** (this should already work from Task 8)

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py::TestInit -v`
Expected: PASS

**Step 3: Commit**

```bash
git add gatekeeper/conftest.py gatekeeper/test_gatekeeper.py
git commit -m "feat(gatekeeper): add conftest.py and Integrator init tests"
```

---

## Task 10: Run full test suite and final cleanup

**Files:**
- Modify: `gatekeeper/gatekeeper.py` (ensure dual-import guard, add `__all__`)
- Modify: `gatekeeper/__init__.py` (add convenience imports)

**Step 1: Add dual-import guard to gatekeeper.py**

At the top of `gatekeeper/gatekeeper.py`, ensure the import pattern matches the project convention:

```python
try:
    from gatekeeper.models import GatekeeperResult, RoslynError
except ImportError:
    from models import GatekeeperResult, RoslynError
```

**Step 2: Add convenience imports to __init__.py**

```python
from gatekeeper.gatekeeper import CompileResult, Integrator
from gatekeeper.models import GatekeeperResult, RoslynError

__all__ = ["Integrator", "CompileResult", "GatekeeperResult", "RoslynError"]
```

**Step 3: Run entire test suite**

Run: `cd /Users/user/terraria/agents && python -m pytest gatekeeper/test_gatekeeper.py -v`
Expected: All tests PASS (approximately 25+ tests)

Also run existing tests to ensure no regressions:

Run: `cd /Users/user/terraria/agents && python -m pytest forge_master/test_templates.py -v`
Expected: All existing tests still PASS

**Step 4: Commit**

```bash
git add gatekeeper/__init__.py gatekeeper/gatekeeper.py
git commit -m "feat(gatekeeper): finalize module with dual-import guards and public API"
```
