# Gatekeeper Module Design

**Date:** 2026-03-03
**Status:** Approved

## Overview

The Gatekeeper is the integration and compilation engine for The Forge. It takes outputs from the CoderAgent (C# code + HJSON) and ArtistAgent (PNG sprites), stages them into the tModLoader ModSources directory, runs a real tModLoader build, and self-heals via LLM repair if compilation fails.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Relationship to CompilationHarness | Separate (layered) | CompilationHarness stays for fast Roslyn pre-validation in forge_master. Gatekeeper sits downstream for real tModLoader builds. |
| Repair loop coupling | Direct call to CoderAgent | Gatekeeper imports CoderAgent.fix_code() directly. Simpler, owns the retry loop end-to-end. |
| HJSON append strategy | Regex/string merge | No extra dependency. HJSON structure is simple enough for regex-based key insertion. |
| Status file location | Mod root directory | generation_status.json lives inside ForgeGeneratedMod/. TUI watches the mod directory. |
| Module structure | Monolithic Integrator | Single gatekeeper.py with Integrator class. Matches spec and project conventions (one agent = one file). |

## Module Structure

```
gatekeeper/
├── __init__.py
├── gatekeeper.py          # Integrator class
├── models.py              # Pydantic input/output models
└── test_gatekeeper.py     # Tests
```

## Class API

```python
class Integrator:
    def __init__(self, coder: CoderAgent | None = None):
        """
        Reads MOD_SOURCE_PATH from env (default: ~/Documents/My Games/Terraria/
        tModLoader/ModSources/ForgeGeneratedMod/).
        Reads TMODLOADER_PATH from env for the tModLoader.dll location.
        Optionally accepts a CoderAgent for repair; creates one if not provided.
        """

    def build_and_verify(self, forge_output: dict, sprite_path: str | None = None) -> dict:
        """
        Main entry point. Returns a GatekeeperResult dict.
        """
```

### Internal Methods

- `_stage_files(cs_code, hjson_code, item_name, sprite_path)` -- writes to ModSources
- `_merge_hjson(hjson_code, item_name)` -- appends to existing en-US.hjson
- `_run_tmod_build() -> CompileResult` -- subprocess call
- `_parse_errors(output) -> list[RoslynError]` -- regex CS\d{4} extraction
- `_write_status(status_dict)` -- writes generation_status.json
- `_extract_item_name(cs_code)` -- regex for class name

## Data Flow

### Input

`build_and_verify()` receives:
- `forge_output: dict` from `CoderAgent.write_code()` containing `cs_code`, `hjson_code`, `status`
- `sprite_path: str | None` from ArtistAgent

### File Staging Rules

1. Extract `item_name` from CS code via regex (`class (\w+)\s*:\s*ModItem`)
2. Write `Content/Items/{ItemName}.cs` -- overwrite only if same class name exists
3. Copy sprite to `Content/Items/{ItemName}.png` -- only if sprite_path provided
4. Merge HJSON into `Localization/en-US.hjson` -- regex finds `Items: {` block, inserts new keys without duplicating
5. Ensure `build.txt` and `description.txt` exist at root (create with defaults if missing, never overwrite)

### Build Command

```
dotnet {TMODLOADER_PATH}/tModLoader.dll -build "ForgeGeneratedMod" -eac
```

Blocking subprocess, cwd = ModSources parent. Capture stdout + stderr.

## Self-Healing Loop

```
Attempt 1: build → parse errors → if CS errors:
    CoderAgent.fix_code(error_log, cs_code) → new cs_code → re-stage
Attempt 2: build → parse errors → if CS errors:
    CoderAgent.fix_code(error_log, cs_code) → new cs_code → re-stage
Attempt 3: build → parse errors → if CS errors:
    CoderAgent.fix_code(error_log, cs_code) → new cs_code → re-stage
Attempt 4: build → STILL failing? → ABORT
```

- Max 3 repair retries (4 total build attempts)
- Error parsing: regex `(CS\d{4})` + line/col from `filename.cs(line,col): error CSxxxx: message`
- Repair prompt includes: failed code, all error messages with line numbers, CS error codes
- On abort: write error status to generation_status.json

## TUI Status Protocol

### State 1 -- Building
```json
{"status": "building"}
```

### State 2 -- Success
```json
{
  "status": "ready",
  "message": "Compilation successful. Waiting for user..."
}
```

### State 3 -- Error (after 3 retries exhausted)
```json
{
  "status": "error",
  "error_code": "CS0103",
  "message": "Critical Failure: The compiler rejected the generated logic."
}
```

## Pydantic Models

```python
class GatekeeperInput(BaseModel):
    cs_code: str
    hjson_code: str
    item_name: str

class RoslynError(BaseModel):
    code: str       # e.g. "CS0103"
    message: str
    line: int | None
    file: str | None

class GatekeeperResult(BaseModel):
    status: Literal["success", "error"]
    item_name: str
    attempts: int
    errors: list[RoslynError] | None = None
    error_message: str | None = None
```

## Testing Strategy

- **Unit tests:** Mock subprocess, test file staging, HJSON merging, error parsing regex, status file writing
- **Integration tests:** (`@pytest.mark.integration`) Real tModLoader build with known-good CS, verify full loop
- Pattern: `unittest.TestCase` for pure logic, `pytest` markers for integration

## Configuration

| Env Var | Default | Description |
|---|---|---|
| `MOD_SOURCE_PATH` | `~/Documents/My Games/Terraria/tModLoader/ModSources/ForgeGeneratedMod/` | Root of the mod directory |
| `TMODLOADER_PATH` | Auto-discovered (same logic as CompilationHarness) | Path to tModLoader installation |
