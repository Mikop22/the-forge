# Forge Master Test Suite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a fast unit test suite for `templates.py` and a real-LLM + `dotnet build` integration suite for `CoderAgent`, covering all 7 weapon sub-types.

**Architecture:** Three new files inline with source (matching `architect/` style): `compilation_harness.py` wraps `dotnet build` in a temp project; `test_templates.py` uses `unittest.TestCase` for pure-Python validation checks; `test_codegen_integration.py` uses pytest marks for real LLM + compile smoke tests.

**Tech Stack:** Python `unittest` + pytest 8.x, dotnet 8.0, tModLoader DLLs (via `TMODLOADER_PATH` env var or Steam path), langchain-openai.

---

## Prerequisite: fix allowed imports in `prompts.py`

The new templates use `using Terraria.DataStructures;` and `using Terraria.Audio;` but `prompts.py` has "Allowed Imports (ONLY these)" that omits them. Fix this before writing tests so the LLM produces compilable code.

**File:** `forge_master/prompts.py:24-28`

Replace the Allowed Imports block:
```
## Allowed Imports (use whichever are needed)
- `using Terraria;`
- `using Terraria.ID;`
- `using Terraria.ModLoader;`
- `using Microsoft.Xna.Framework;`
- `using Terraria.DataStructures;`   // EntitySource_ItemUse_WithAmmo, IEntitySource
- `using Terraria.Audio;`            // SoundEngine.PlaySound, SoundStyle
```

Also update rule 5 to note the projectile variant:
```
5. ModItem.OnHitNPC signature: `(Player player, NPC target, NPC.HitInfo hit, int damageDone)`.
   ModProjectile.OnHitNPC signature: `(NPC target, NPC.HitInfo hit, int damageDone)` — NO Player parameter.
```

**Run after:** No tests yet; just verify the file parses cleanly:
```bash
cd /Users/user/terraria/agents && python3 -c "from forge_master.prompts import build_codegen_prompt; print('ok')"
```
Expected: `ok`

**Commit:**
```bash
git add forge_master/prompts.py
git commit -m "fix: expand allowed imports and fix OnHitNPC rules in codegen prompt"
```

---

### Task 1: pytest `conftest.py` for the `integration` mark

**Files:**
- Create: `forge_master/conftest.py`

Without this file, `pytest -m integration` prints a warning about unknown marks.

**Step 1: Create the file**

```python
# forge_master/conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: real LLM calls + dotnet compilation (slow, requires TMODLOADER_PATH)",
    )
```

**Step 2: Verify pytest sees it**

```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/conftest.py --co -q 2>&1
```
Expected: `no tests ran` with no "unknown mark" warning.

**Step 3: Commit**
```bash
git add forge_master/conftest.py
git commit -m "test: add pytest conftest with integration mark for forge_master"
```

---

### Task 2: `compilation_harness.py` — DLL discovery

**Files:**
- Create: `forge_master/compilation_harness.py`

The harness must find two DLLs — `Terraria.dll` and `FNA.dll` — from a tModLoader installation. If they can't be found it raises `unittest.SkipTest` so tests are skipped cleanly rather than erroring.

**Step 1: Write the failing test first**

Create `forge_master/test_compilation_harness.py` temporarily:
```python
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

class TestDllDiscovery(unittest.TestCase):
    def test_find_tmod_dlls_returns_path_or_none(self):
        from compilation_harness import find_tmod_path
        result = find_tmod_path()
        # Either returns a Path with the DLLs or None — never raises
        self.assertIsInstance(result, (Path, type(None)))
```

**Step 2: Run to verify it fails**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/test_compilation_harness.py -v
```
Expected: `ImportError: cannot import name 'find_tmod_path'`

**Step 3: Implement `find_tmod_path`**

Create `forge_master/compilation_harness.py`:
```python
"""Wraps dotnet build in a throwaway tModLoader mod project."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# DLL discovery
# ---------------------------------------------------------------------------

_STEAM_PATHS = [
    # macOS
    Path.home() / "Library/Application Support/Steam/steamapps/common/tModLoader",
    # Windows
    Path("C:/Program Files (x86)/Steam/steamapps/common/tModLoader"),
    Path("C:/Program Files/Steam/steamapps/common/tModLoader"),
    # Linux
    Path.home() / ".steam/steam/steamapps/common/tModLoader",
    Path.home() / ".local/share/Steam/steamapps/common/tModLoader",
]

_REQUIRED_DLLS = ["Terraria.dll", "FNA.dll"]


def find_tmod_path() -> Path | None:
    """Return a directory that contains the required tModLoader DLLs, or None."""
    # 1. Explicit env override
    env = os.environ.get("TMODLOADER_PATH")
    if env:
        candidate = Path(env)
        if _has_dlls(candidate):
            return candidate

    # 2. Common Steam paths
    for base in _STEAM_PATHS:
        if _has_dlls(base):
            return base
        # DLLs may live one level deeper (macOS app bundle, etc.)
        for sub in base.glob("*/"):
            if _has_dlls(sub):
                return sub

    return None


def _has_dlls(path: Path) -> bool:
    return path.is_dir() and all((path / dll).exists() for dll in _REQUIRED_DLLS)
```

**Step 4: Run test to verify it passes**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/test_compilation_harness.py::TestDllDiscovery::test_find_tmod_dlls_returns_path_or_none -v
```
Expected: `PASSED`

**Step 5: Commit**
```bash
git add forge_master/compilation_harness.py forge_master/test_compilation_harness.py
git commit -m "feat: add compilation_harness DLL discovery"
```

---

### Task 3: `compilation_harness.py` — project scaffolding and `dotnet build`

**Files:**
- Modify: `forge_master/compilation_harness.py`
- Modify: `forge_master/test_compilation_harness.py`

**Step 1: Add the failing test**

Append to `test_compilation_harness.py`:
```python
class TestCompilationHarness(unittest.TestCase):
    def test_valid_sword_compiles(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from compilation_harness import CompilationHarness, find_tmod_path
        if find_tmod_path() is None:
            self.skipTest("TMODLOADER_PATH not set and tModLoader not found via Steam")

        from templates import SWORD_TEMPLATE
        result = CompilationHarness().compile(SWORD_TEMPLATE, "ExampleSword")
        self.assertTrue(result.success, msg=result.output)

    def test_invalid_cs_fails(self):
        from compilation_harness import CompilationHarness, find_tmod_path
        if find_tmod_path() is None:
            self.skipTest("TMODLOADER_PATH not set and tModLoader not found via Steam")

        bad_code = "this is not valid C#"
        result = CompilationHarness().compile(bad_code, "BadItem")
        self.assertFalse(result.success)
        self.assertIn("error", result.output.lower())
```

**Step 2: Run to verify it fails**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/test_compilation_harness.py::TestCompilationHarness -v
```
Expected: `ImportError: cannot import name 'CompilationHarness'`

**Step 3: Implement `CompileResult` and `CompilationHarness`**

Append to `forge_master/compilation_harness.py`:
```python
# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class CompileResult:
    success: bool
    output: str  # combined stdout + stderr from dotnet build


# ---------------------------------------------------------------------------
# .csproj template
# ---------------------------------------------------------------------------

_CSPROJ_TEMPLATE = """\
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net6.0</TargetFramework>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>
    <Nullable>enable</Nullable>
    <NoWarn>CS1591;CS0436;CS8019;CS0162</NoWarn>
    <GenerateDocumentationFile>false</GenerateDocumentationFile>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="Terraria">
      <HintPath>{tmod_path}/Terraria.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="FNA">
      <HintPath>{tmod_path}/FNA.dll</HintPath>
      <Private>false</Private>
    </Reference>
  </ItemGroup>
</Project>
"""


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class CompilationHarness:
    """Compile a C# snippet against tModLoader DLLs using dotnet build.

    Raises ``unittest.SkipTest`` if tModLoader DLLs cannot be located.
    """

    def compile(self, cs_code: str, item_name: str) -> CompileResult:
        tmod_path = find_tmod_path()
        if tmod_path is None:
            raise unittest.SkipTest(
                "tModLoader DLLs not found. Set TMODLOADER_PATH to the tModLoader "
                "installation directory (must contain Terraria.dll and FNA.dll)."
            )

        tmp = tempfile.mkdtemp(prefix="forge_compile_")
        try:
            return self._build(cs_code, item_name, Path(tmp), tmod_path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _build(
        self, cs_code: str, item_name: str, tmp: Path, tmod_path: Path
    ) -> CompileResult:
        # Write .csproj
        csproj = tmp / "ForgeTestMod.csproj"
        csproj.write_text(
            _CSPROJ_TEMPLATE.format(tmod_path=tmod_path), encoding="utf-8"
        )

        # Write .cs source
        cs_dir = tmp / "Content" / "Items" / "Weapons"
        cs_dir.mkdir(parents=True)
        (cs_dir / f"{item_name}.cs").write_text(cs_code, encoding="utf-8")

        # Run dotnet build
        proc = subprocess.run(
            ["dotnet", "build", str(csproj), "--no-incremental", "-v", "minimal"],
            capture_output=True,
            text=True,
        )
        output = proc.stdout + proc.stderr
        return CompileResult(success=proc.returncode == 0, output=output)
```

**Step 4: Run tests**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/test_compilation_harness.py -v
```
Expected: Both tests PASS (or SKIP if tModLoader not installed — that's correct behaviour).

**Step 5: Commit**
```bash
git add forge_master/compilation_harness.py forge_master/test_compilation_harness.py
git commit -m "feat: implement CompilationHarness with dotnet build scaffolding"
```

---

### Task 4: `test_templates.py` — banned pattern tests

**Files:**
- Create: `forge_master/test_templates.py`

**Step 1: Write the tests**

```python
"""Unit tests for forge_master/templates.py — no LLM, no dotnet required."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from templates import validate_cs


class TestBannedPatterns(unittest.TestCase):
    """Each banned pattern must fire on the exact hallucination it targets."""

    def _assert_banned(self, code: str, fragment: str):
        violations = validate_cs(code)
        self.assertTrue(
            any(fragment in v for v in violations),
            msg=f"Expected violation containing '{fragment}', got: {violations}",
        )

    def _minimal_valid(self) -> str:
        return (
            "using Terraria;\nusing Terraria.ID;\nusing Terraria.ModLoader;\n"
            "namespace X { public class A : ModItem { public override void SetDefaults() {} } }"
        )

    def test_system_drawing_banned(self):
        code = self._minimal_valid().replace(
            "using Terraria;", "using Terraria;\nusing System.Drawing;"
        )
        self._assert_banned(code, "System.Drawing")

    def test_mod_recipe_banned(self):
        code = self._minimal_valid() + "\n// new ModRecipe(this);"
        self._assert_banned(code, "ModRecipe")

    def test_item_melee_banned(self):
        code = self._minimal_valid() + "\n// item.melee = true;"
        self._assert_banned(code, "item.melee")

    def test_item_ranged_banned(self):
        code = self._minimal_valid() + "\n// item.ranged = true;"
        self._assert_banned(code, "item.ranged")

    def test_item_magic_banned(self):
        code = self._minimal_valid() + "\n// item.magic = true;"
        self._assert_banned(code, "item.magic")

    def test_item_summon_banned(self):
        code = self._minimal_valid() + "\n// item.summon = true;"
        self._assert_banned(code, "item.summon")

    def test_old_on_hit_npc_signature_banned(self):
        # Old 1.3 signature: (Player player, NPC target, int damage, float knockBack, bool crit)
        code = self._minimal_valid() + (
            "\npublic override void OnHitNPC(Player player, NPC target, int damage, "
            "float knockBack, bool crit) {}"
        )
        self._assert_banned(code, "OnHitNPC")

    def test_get_mod_item_banned(self):
        code = self._minimal_valid() + "\n// mod.GetItem<Foo>();"
        self._assert_banned(code, "mod.GetItem")

    def test_get_mod_item_generic_banned(self):
        code = self._minimal_valid() + "\n// x.GetModItem<Foo>();"
        self._assert_banned(code, "GetModItem")

    def test_minion_positive_penetrate_banned(self):
        code = self._minimal_valid() + (
            "\nProjectile.minion = true;\n"
            "Projectile.penetrate = 1;\n"
        )
        self._assert_banned(code, "Minion projectiles must use")

    def test_minion_negative_penetrate_allowed(self):
        # penetrate = -1 is CORRECT and must NOT trigger the ban
        code = self._minimal_valid() + (
            "\nProjectile.minion = true;\n"
            "Projectile.penetrate = -1;\n"
        )
        violations = validate_cs(code)
        penetrate_violations = [v for v in violations if "penetrate" in v.lower()]
        self.assertEqual(penetrate_violations, [])

    def test_mod_projectile_on_hit_npc_with_player_banned(self):
        # A ModProjectile subclass with Player parameter is wrong
        code = (
            "using Terraria;\nusing Terraria.ID;\nusing Terraria.ModLoader;\n"
            "namespace X {\n"
            "  public class A : ModItem { public override void SetDefaults() {} }\n"
            "  public class B : ModProjectile {\n"
            "    public override void SetDefaults() {}\n"
            "    public override void OnHitNPC(Player player, NPC target, NPC.HitInfo hit, int d) {}\n"
            "  }\n"
            "}"
        )
        self._assert_banned(code, "ModProjectile.OnHitNPC")

    def test_mod_item_on_hit_npc_with_player_allowed(self):
        # ModItem correctly uses Player parameter — must NOT trigger the projectile ban
        code = (
            "using Terraria;\nusing Terraria.ID;\nusing Terraria.ModLoader;\n"
            "namespace X {\n"
            "  public class A : ModItem {\n"
            "    public override void SetDefaults() {}\n"
            "    public override void OnHitNPC(Player player, NPC target, NPC.HitInfo hit, int d) {}\n"
            "  }\n"
            "}"
        )
        violations = validate_cs(code)
        proj_violations = [v for v in violations if "ModProjectile.OnHitNPC" in v]
        self.assertEqual(proj_violations, [])
```

**Step 2: Run to verify it passes**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/test_templates.py::TestBannedPatterns -v
```
Expected: All 12 tests PASS.

**Step 3: Commit**
```bash
git add forge_master/test_templates.py
git commit -m "test: add TestBannedPatterns for templates.py validate_cs()"
```

---

### Task 5: `test_templates.py` — required patterns, template validation, mappings

**Files:**
- Modify: `forge_master/test_templates.py`

**Step 1: Append the remaining test classes**

```python
class TestRequiredPatterns(unittest.TestCase):
    """Each required pattern must fire when absent."""

    def _base(self) -> str:
        return (
            "using Terraria;\nusing Terraria.ID;\nusing Terraria.ModLoader;\n"
            "namespace X { public class A : ModItem { public override void SetDefaults() {} } }"
        )

    def test_missing_terraria_import(self):
        code = self._base().replace("using Terraria;\n", "")
        violations = validate_cs(code)
        self.assertTrue(any("using Terraria;" in v for v in violations))

    def test_missing_terraria_id_import(self):
        code = self._base().replace("using Terraria.ID;\n", "")
        violations = validate_cs(code)
        self.assertTrue(any("using Terraria.ID;" in v for v in violations))

    def test_missing_modloader_import(self):
        code = self._base().replace("using Terraria.ModLoader;\n", "")
        violations = validate_cs(code)
        self.assertTrue(any("using Terraria.ModLoader;" in v for v in violations))

    def test_missing_mod_item_inheritance(self):
        code = self._base().replace(": ModItem", ": SomeOtherClass")
        violations = validate_cs(code)
        self.assertTrue(any("ModItem" in v for v in violations))

    def test_missing_set_defaults(self):
        code = self._base().replace("public override void SetDefaults() {}", "")
        violations = validate_cs(code)
        self.assertTrue(any("SetDefaults" in v for v in violations))


class TestAllTemplatesPassValidation(unittest.TestCase):
    """Every built-in template must produce zero validate_cs() violations."""

    def _check(self, sub_type: str, custom_projectile: bool = False):
        from templates import get_reference_snippet
        code = get_reference_snippet(sub_type, custom_projectile=custom_projectile)
        violations = validate_cs(code)
        self.assertEqual(violations, [], msg=f"{sub_type} violations: {violations}")

    def test_sword_template(self):       self._check("Sword")
    def test_gun_template(self):         self._check("Gun")
    def test_staff_template(self):       self._check("Staff")
    def test_bow_template(self):         self._check("Bow")
    def test_summon_template(self):      self._check("Summon")
    def test_whip_template(self):        self._check("Whip")
    def test_custom_projectile_template(self): self._check("Gun", custom_projectile=True)


class TestSubTypeMappings(unittest.TestCase):
    """DAMAGE_CLASS_MAP and USE_STYLE_MAP cover all 6 sub-types."""

    def setUp(self):
        from templates import DAMAGE_CLASS_MAP, USE_STYLE_MAP
        self.dc = DAMAGE_CLASS_MAP
        self.us = USE_STYLE_MAP

    def test_damage_class_sword(self):   self.assertEqual(self.dc["Sword"],  "DamageClass.Melee")
    def test_damage_class_gun(self):     self.assertEqual(self.dc["Gun"],    "DamageClass.Ranged")
    def test_damage_class_bow(self):     self.assertEqual(self.dc["Bow"],    "DamageClass.Ranged")
    def test_damage_class_staff(self):   self.assertEqual(self.dc["Staff"],  "DamageClass.Magic")
    def test_damage_class_summon(self):  self.assertEqual(self.dc["Summon"], "DamageClass.Summon")
    def test_damage_class_whip(self):    self.assertIn("Whip", self.dc)

    def test_use_style_sword(self):  self.assertEqual(self.us["Sword"],  "ItemUseStyleID.Swing")
    def test_use_style_gun(self):    self.assertEqual(self.us["Gun"],    "ItemUseStyleID.Shoot")
    def test_use_style_bow(self):    self.assertEqual(self.us["Bow"],    "ItemUseStyleID.Shoot")
    def test_use_style_staff(self):  self.assertEqual(self.us["Staff"],  "ItemUseStyleID.Shoot")
    def test_use_style_summon(self): self.assertEqual(self.us["Summon"], "ItemUseStyleID.Swing")
    def test_use_style_whip(self):   self.assertIn("Whip", self.us)


class TestGetReferenceSnippet(unittest.TestCase):
    def test_known_sub_types_return_correct_template(self):
        from templates import REFERENCE_SNIPPETS, get_reference_snippet
        for sub_type, expected in REFERENCE_SNIPPETS.items():
            with self.subTest(sub_type=sub_type):
                self.assertEqual(get_reference_snippet(sub_type), expected)

    def test_unknown_falls_back_to_sword(self):
        from templates import SWORD_TEMPLATE, get_reference_snippet
        self.assertEqual(get_reference_snippet("Axe"), SWORD_TEMPLATE)

    def test_custom_projectile_flag_returns_custom_template(self):
        from templates import CUSTOM_PROJECTILE_TEMPLATE, get_reference_snippet
        result = get_reference_snippet("Gun", custom_projectile=True)
        self.assertEqual(result, CUSTOM_PROJECTILE_TEMPLATE)

    def test_custom_projectile_flag_overrides_sub_type(self):
        from templates import CUSTOM_PROJECTILE_TEMPLATE, get_reference_snippet
        # Even if sub_type is Sword, custom_projectile=True should return the projectile template
        self.assertEqual(
            get_reference_snippet("Sword", custom_projectile=True),
            CUSTOM_PROJECTILE_TEMPLATE,
        )


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run the full test_templates.py suite**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/test_templates.py -v
```
Expected: All tests PASS.

**Step 3: Commit**
```bash
git add forge_master/test_templates.py
git commit -m "test: complete test_templates.py — banned/required patterns, all templates, mappings"
```

---

### Task 6: `test_codegen_integration.py` — real LLM + compile smoke tests

**Files:**
- Create: `forge_master/test_codegen_integration.py`

These tests actually call gpt-5-nano and then `dotnet build`. They're marked `integration` and skipped by default.

**Step 1: Write the test file**

```python
"""Integration smoke tests: real LLM generation + dotnet compilation.

Run with:
    pytest forge_master/test_codegen_integration.py -m integration -v

Requires:
- OPENAI_API_KEY environment variable
- TMODLOADER_PATH pointing to a directory containing Terraria.dll and FNA.dll
  (or tModLoader installed via Steam in a standard path)
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


# ---------------------------------------------------------------------------
# Minimal manifests — one per sub-type, stressing the template's key features
# ---------------------------------------------------------------------------

MANIFESTS = {
    "Sword": {
        "item_name": "TestSword",
        "display_name": "Test Sword",
        "tooltip": "A test sword.",
        "type": "Weapon",
        "sub_type": "Sword",
        "stats": {
            "damage": 30, "knockback": 5.0, "crit_chance": 4,
            "use_time": 20, "auto_reuse": True, "rarity": "ItemRarityID.Green",
        },
        "mechanics": {
            "on_hit_buff": "BuffID.OnFire",
            "custom_projectile": False,
            "crafting_material": "ItemID.IronBar",
            "crafting_cost": 5,
            "crafting_tile": "TileID.Anvils",
        },
    },
    "Gun": {
        "item_name": "TestGun",
        "display_name": "Test Gun",
        "tooltip": "A test gun.",
        "type": "Weapon",
        "sub_type": "Gun",
        "stats": {
            "damage": 20, "knockback": 3.0, "crit_chance": 4,
            "use_time": 10, "auto_reuse": True, "rarity": "ItemRarityID.Green",
        },
        "mechanics": {
            "shoot_projectile": "ProjectileID.PurificationPowder",
            "custom_projectile": False,
            "crafting_material": "ItemID.IronBar",
            "crafting_cost": 8,
            "crafting_tile": "TileID.Anvils",
        },
    },
    "Staff": {
        "item_name": "TestStaff",
        "display_name": "Test Staff",
        "tooltip": "A magic staff.",
        "type": "Weapon",
        "sub_type": "Staff",
        "stats": {
            "damage": 25, "knockback": 4.0, "crit_chance": 4,
            "use_time": 25, "auto_reuse": True, "rarity": "ItemRarityID.Green",
        },
        "mechanics": {
            "shoot_projectile": "ProjectileID.MagicMissile",
            "custom_projectile": False,
            "crafting_material": "ItemID.FallenStar",
            "crafting_cost": 10,
            "crafting_tile": "TileID.Anvils",
        },
    },
    "Bow": {
        "item_name": "TestBow",
        "display_name": "Test Bow",
        "tooltip": "A ranged bow.",
        "type": "Weapon",
        "sub_type": "Bow",
        "stats": {
            "damage": 22, "knockback": 3.0, "crit_chance": 4,
            "use_time": 24, "auto_reuse": False, "rarity": "ItemRarityID.Green",
        },
        "mechanics": {
            "custom_projectile": False,
            "crafting_material": "ItemID.Wood",
            "crafting_cost": 15,
            "crafting_tile": "TileID.WorkBenches",
        },
    },
    "Summon": {
        "item_name": "TestSummon",
        "display_name": "Test Minion Staff",
        "tooltip": "Summons a test minion.",
        "type": "Weapon",
        "sub_type": "Summon",
        "stats": {
            "damage": 20, "knockback": 2.0, "crit_chance": 0,
            "use_time": 36, "auto_reuse": True, "rarity": "ItemRarityID.Cyan",
        },
        "mechanics": {
            "custom_projectile": False,
            "crafting_material": "ItemID.Silk",
            "crafting_cost": 10,
            "crafting_tile": "TileID.Loom",
        },
    },
    "Whip": {
        "item_name": "TestWhip",
        "display_name": "Test Whip",
        "tooltip": "A summoner whip.",
        "type": "Weapon",
        "sub_type": "Whip",
        "stats": {
            "damage": 18, "knockback": 2.0, "crit_chance": 0,
            "use_time": 28, "auto_reuse": False, "rarity": "ItemRarityID.Green",
        },
        "mechanics": {
            "custom_projectile": False,
            "crafting_material": "ItemID.Leather",
            "crafting_cost": 8,
            "crafting_tile": "TileID.WorkBenches",
        },
    },
    "CustomProjectile": {
        "item_name": "TestCustomGun",
        "display_name": "Test Custom Gun",
        "tooltip": "Fires a bouncing projectile.",
        "type": "Weapon",
        "sub_type": "Gun",
        "stats": {
            "damage": 35, "knockback": 5.0, "crit_chance": 4,
            "use_time": 12, "auto_reuse": True, "rarity": "ItemRarityID.Orange",
        },
        "mechanics": {
            "custom_projectile": True,
            "crafting_material": "ItemID.HellstoneBar",
            "crafting_cost": 15,
            "crafting_tile": "TileID.Anvils",
        },
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.parametrize("sub_type", list(MANIFESTS.keys()))
def test_codegen_compiles(sub_type: str):
    """Generate C# for sub_type, validate it, then compile it with dotnet."""
    from compilation_harness import CompilationHarness, find_tmod_path
    from forge_master import CoderAgent
    from templates import validate_cs

    if find_tmod_path() is None:
        pytest.skip(
            "tModLoader DLLs not found. Set TMODLOADER_PATH to your tModLoader "
            "installation directory."
        )

    manifest = MANIFESTS[sub_type]
    agent = CoderAgent()
    result = agent.write_code(manifest)

    # 1. Agent must report success
    assert result["status"] == "success", (
        f"CoderAgent returned error: {result.get('error')}"
    )

    cs_code = result["cs_code"]
    item_name = manifest["item_name"]

    # 2. validate_cs must pass (catches 1.3 hallucinations)
    violations = validate_cs(cs_code)
    assert violations == [], f"validate_cs violations: {violations}\n\nCode:\n{cs_code}"

    # 3. hjson must reference the item name
    hjson = result["hjson_code"]
    assert item_name in hjson, f"hjson missing item_name '{item_name}':\n{hjson}"

    # 4. dotnet build must succeed
    compile_result = CompilationHarness().compile(cs_code, item_name)
    assert compile_result.success, (
        f"dotnet build failed for {sub_type}:\n{compile_result.output}\n\nCode:\n{cs_code}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-m", "integration", "-v"])
```

**Step 2: Run without the integration mark to verify tests are skipped**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/test_codegen_integration.py -v
```
Expected: All 7 tests DESELECTED (not collected), no failures.

**Step 3: Run with the integration mark (requires OPENAI_API_KEY + tModLoader)**

Set your TMODLOADER_PATH first, then:
```bash
cd /Users/user/terraria/agents && TMODLOADER_PATH=/path/to/tModLoader \
  python3 -m pytest forge_master/test_codegen_integration.py -m integration -v
```
Expected: All 7 tests PASSED (or SKIPPED if DLLs not found).

**Step 4: Commit**
```bash
git add forge_master/test_codegen_integration.py
git commit -m "test: add integration smoke tests for all 7 sub-types (real LLM + dotnet compile)"
```

---

### Task 7: Clean up temp harness test file and run full suite

The `test_compilation_harness.py` file was scaffolding — its tests are now covered by the integration suite. Remove it to avoid duplication.

**Step 1: Delete the scaffolding test file**
```bash
rm /Users/user/terraria/agents/forge_master/test_compilation_harness.py
```

**Step 2: Run the full fast suite**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/test_templates.py -v
```
Expected: All tests PASS with no warnings.

**Step 3: Verify integration tests are skipped by default**
```bash
cd /Users/user/terraria/agents && python3 -m pytest forge_master/ -v
```
Expected: `test_templates.py` tests PASS, integration tests not collected.

**Step 4: Final commit**
```bash
git add -A forge_master/
git commit -m "test: finalize forge_master test suite — remove scaffolding, verify clean run"
```

---

## Quick Reference

```bash
# Fast suite (always safe to run, no API keys needed)
python3 -m pytest forge_master/test_templates.py -v

# Integration suite (needs OPENAI_API_KEY + TMODLOADER_PATH)
TMODLOADER_PATH=/path/to/tModLoader \
  python3 -m pytest forge_master/ -m integration -v

# All forge_master tests except integration
python3 -m pytest forge_master/ -v
```

## Setting `TMODLOADER_PATH`

Point it at the directory containing `Terraria.dll` and `FNA.dll`. Common locations:
- **macOS Steam:** `~/Library/Application Support/Steam/steamapps/common/tModLoader`
- **Windows Steam:** `C:\Program Files (x86)\Steam\steamapps\common\tModLoader`
- **Linux Steam:** `~/.steam/steam/steamapps/common/tModLoader`
