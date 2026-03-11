# Forge Master — Code Generation & Compilation Test Design

**Date:** 2026-02-27
**Status:** Approved

---

## Context

`forge_master/` contains a `CoderAgent` that converts an Architect manifest into compilable tModLoader 1.4.4 C#. It has no tests. The `architect/` module provides the style reference: test files live inline with source (e.g. `architect/test_reference_finder.py`).

dotnet 8.0.418 is installed. No `.csproj` or tModLoader project exists yet.

---

## Chosen Approach: Two test files + shared compilation harness

```
forge_master/
  compilation_harness.py      ← NEW
  test_templates.py           ← NEW
  test_codegen_integration.py ← NEW
```

---

## Component 1: `compilation_harness.py`

Creates a throwaway tModLoader mod project, writes a `.cs` file, runs `dotnet build`, returns the result.

### tModLoader DLL discovery (tried in order)

1. `TMODLOADER_PATH` env var
2. macOS Steam path: `~/Library/Application Support/Steam/steamapps/common/tModLoader/`
3. NuGet fallback: `.csproj` referencing the `tModLoader` NuGet package

### Temp project layout

```
/tmp/forge_compile_XXXX/
  ForgeTestMod.csproj
  Content/Items/Weapons/<ItemName>.cs
```

Created fresh per call, always cleaned up (even on failure).

### Interface

```python
@dataclass
class CompileResult:
    success: bool
    output: str   # full dotnet stdout+stderr

class CompilationHarness:
    def compile(self, cs_code: str, item_name: str) -> CompileResult
```

---

## Component 2: `test_templates.py`

Pure-Python, no network, no dotnet. Always runs as part of the default `pytest` suite.

| Test class | Coverage |
|---|---|
| `TestAllTemplatesPassValidation` | All 7 templates (Sword, Gun, Staff, Bow, Summon, Whip, CustomProjectile) return zero violations from `validate_cs()` |
| `TestBannedPatterns` | Each banned pattern fires on crafted bad code |
| `TestRequiredPatterns` | Each required pattern fires when absent |
| `TestProjectileOnHitNPCContextCheck` | Context-sensitive check fires on ModProjectile but not ModItem |
| `TestSubTypeMappings` | All 6 sub-types in `DAMAGE_CLASS_MAP` and `USE_STYLE_MAP`, including Whip |
| `TestGetReferenceSnippet` | Known types, unknown fallback, `custom_projectile=True` |

---

## Component 3: `test_codegen_integration.py`

Real LLM calls + `dotnet build`. Skipped by default; opt in with `pytest -m integration`.

### Sub-types under test

| Sub-type | Key stress point |
|---|---|
| Sword | `on_hit_buff`, melee damage class |
| Gun | `useAmmo: AmmoID.Bullet`, placeholder shoot |
| Staff | `Item.staff[Type] = true`, mana cost |
| Bow | `useAmmo: AmmoID.Arrow`, multi-arrow Shoot override |
| Summon | `DamageClass.Summon`, buff type, minion penetrate = -1 |
| Whip | `channel: true`, `DefaultToWhip`, `MeleePrefix()` |
| CustomProjectile | `custom_projectile: true`, both ModItem + ModProjectile in one file |

### Per-test assertions

1. `result["status"] == "success"`
2. `validate_cs(result["cs_code"])` returns no violations
3. `result["hjson_code"]` contains the item name
4. `CompilationHarness().compile(cs_code, item_name).success is True`
   — on failure, the full `dotnet` output is shown as the assertion message

---

## Running the tests

```bash
# Fast suite only (no LLM, no dotnet)
pytest forge_master/test_templates.py

# Full suite including LLM + compilation
pytest -m integration forge_master/test_codegen_integration.py
```
