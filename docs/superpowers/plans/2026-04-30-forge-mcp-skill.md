# Forge MCP + Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate The Forge from a Python+OpenAI orchestration pipeline to a Claude Code skill backed by a thin local MCP server. All LLM reasoning moves to Claude subagents. FAL.ai stays for sprite generation.

**Architecture:** Five phases — (1) extract reusable Python from `forge_master`/`architect` into `core/`, (2) build a 4-tool MCP server, (3) write the skill file with subagent prompts, (4) wire up and smoke test, (5) archive the old pipeline. Codex subagents handle the mechanical extraction and archive moves; Claude main session handles MCP server design and prompt engineering.

**Tech Stack:** Python 3.9+ (existing), `mcp` Python SDK (FastMCP), pydantic, pytest, FAL.ai (existing), Claude Code skill system, Claude Code subagents.

**Reference spec:** `docs/superpowers/specs/2026-04-30-forge-mcp-skill-design.md`

**Codex delegation:** Tasks marked **[CODEX]** should be delegated to a Codex subagent via the `codex:codex-rescue` agent. They are mechanical (extraction, refactoring, mass moves) and benefit from Codex's strong refactoring ability. Tasks without that marker are Claude main-session work (design, prompt engineering, integration).

---

## Phase 1 — Extract Dependencies into `core/`

`gatekeeper.py` currently imports from `forge_master/` and `architect/`. Before archiving those, the imports must be moved into `core/`. All changes preserve the existing pipeline working until Phase 5 archives it.

### Task 1: Extract `find_tmod_path` to `core/compilation_harness.py` **[CODEX]**

**Files:**
- Create: `agents/core/compilation_harness.py`
- Create: `agents/core/test_compilation_harness.py`
- Modify: `agents/gatekeeper/gatekeeper.py:32` (update import)

- [ ] **Step 1: Write the failing test**

Create `agents/core/test_compilation_harness.py`:
```python
"""Tests for core.compilation_harness."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from core.compilation_harness import find_tmod_path


def test_find_tmod_path_respects_env_override(tmp_path: Path) -> None:
    fake_root = tmp_path / "tmod"
    fake_root.mkdir()
    (fake_root / "tModLoader.dll").write_text("")

    with patch.dict(os.environ, {"TMODLOADER_PATH": str(fake_root)}):
        result = find_tmod_path()

    assert result == fake_root


def test_find_tmod_path_returns_none_when_env_invalid(tmp_path: Path) -> None:
    bad_root = tmp_path / "missing"
    with patch.dict(os.environ, {"TMODLOADER_PATH": str(bad_root)}):
        result = find_tmod_path()
    assert result is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd agents && python -m pytest core/test_compilation_harness.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'core.compilation_harness'`

- [ ] **Step 3: Copy the source file verbatim**

```bash
cp agents/forge_master/compilation_harness.py agents/core/compilation_harness.py
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd agents && python -m pytest core/test_compilation_harness.py -v
```
Expected: PASS — both tests green.

- [ ] **Step 5: Update gatekeeper import**

Modify `agents/gatekeeper/gatekeeper.py` lines 30-37:
```python
try:
    from core.compilation_harness import find_tmod_path
except ImportError:
    from compilation_harness import find_tmod_path  # type: ignore
```

- [ ] **Step 6: Run the full gatekeeper test suite**

```bash
cd agents && python -m pytest gatekeeper/ -v
```
Expected: PASS — gatekeeper still works through the new import path.

- [ ] **Step 7: Commit**

```bash
git add agents/core/compilation_harness.py agents/core/test_compilation_harness.py agents/gatekeeper/gatekeeper.py
git commit -m "refactor: extract compilation_harness to core for MCP migration"
```

---

### Task 2: Extract HJSON generation to `core/hjson_gen.py` **[CODEX]**

**Files:**
- Create: `agents/core/hjson_gen.py`
- Create: `agents/core/test_hjson_gen.py`

- [ ] **Step 1: Write the failing test**

Create `agents/core/test_hjson_gen.py`:
```python
"""Tests for deterministic hjson generation."""
from __future__ import annotations

from core.hjson_gen import generate_hjson


def test_generate_hjson_emits_valid_structure() -> None:
    result = generate_hjson(
        item_name="VoidPistol",
        display_name="Void Pistol",
        tooltip="Fires void seeds",
    )
    assert "Mods: {" in result
    assert "ForgeGeneratedMod: {" in result
    assert "VoidPistol: {" in result
    assert '"Void Pistol"' in result
    assert '"Fires void seeds"' in result


def test_generate_hjson_escapes_special_characters() -> None:
    result = generate_hjson(
        item_name="QuoteWand",
        display_name='Wand "with" quotes',
        tooltip="Has\nnewlines and {braces}",
    )
    assert r'\"with\"' in result
    assert r"\n" in result
    assert "{braces}" in result


def test_generate_hjson_supports_custom_mod_name() -> None:
    result = generate_hjson(
        item_name="Foo",
        display_name="Foo",
        tooltip="",
        mod_name="OtherMod",
    )
    assert "OtherMod: {" in result
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd agents && python -m pytest core/test_hjson_gen.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `agents/core/hjson_gen.py`**

```python
"""Deterministic Terraria localization (hjson) generation."""
from __future__ import annotations

import json
import textwrap


def generate_hjson(
    item_name: str,
    display_name: str,
    tooltip: str,
    mod_name: str = "ForgeGeneratedMod",
) -> str:
    """Produce a Terraria mod localization hjson file.

    DisplayName and Tooltip are emitted as JSON string literals so newlines,
    closing braces, and Terraria markup like ``[c/rrggbb:...]`` cannot break
    the hjson structure.
    """
    quoted_display = json.dumps(display_name, ensure_ascii=False)
    quoted_tooltip = json.dumps(tooltip, ensure_ascii=False)
    return textwrap.dedent(f"""\
        Mods: {{
        \t{mod_name}: {{
        \t\tItems: {{
        \t\t\t{item_name}: {{
        \t\t\t\tDisplayName: {quoted_display}
        \t\t\t\tTooltip: {quoted_tooltip}
        \t\t\t}}
        \t\t}}
        \t}}
        }}""")
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd agents && python -m pytest core/test_hjson_gen.py -v
```
Expected: PASS — all three tests green.

- [ ] **Step 5: Commit**

```bash
git add agents/core/hjson_gen.py agents/core/test_hjson_gen.py
git commit -m "feat: extract deterministic hjson generation into core"
```

---

### Task 3: Extract critique rules to `core/critique_rules.py` **[CODEX]**

**Files:**
- Create: `agents/core/critique_rules.py`
- Create: `agents/core/test_critique_rules.py`

The existing `_critique_violations` and `_validate_projectile_hitbox_contract` in `agents/forge_master/forge_master.py` (lines 59 and 110) are pure functions. Move them into `core/critique_rules.py` unchanged.

- [ ] **Step 1: Write the failing test**

Create `agents/core/test_critique_rules.py`:
```python
"""Tests for core.critique_rules."""
from __future__ import annotations

from core.critique_rules import critique_violations, validate_projectile_hitbox_contract


def test_critique_violations_returns_list() -> None:
    manifest = {"item_name": "Test", "display_name": "Test"}
    cs_code = "namespace ForgeGeneratedMod.Content.Items { class Test {} }"
    result = critique_violations(manifest, cs_code)
    assert isinstance(result, list)


def test_validate_projectile_hitbox_contract_returns_list() -> None:
    manifest = {"projectile_visuals": {"icon_size": [18, 18]}}
    cs_code = ""
    result = validate_projectile_hitbox_contract(manifest, cs_code)
    assert isinstance(result, list)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd agents && python -m pytest core/test_critique_rules.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Delegate to Codex**

Use the `codex:codex-rescue` agent with this prompt:

> Move the function `_critique_violations` (line 59) and `_validate_projectile_hitbox_contract` (line 110) from `agents/forge_master/forge_master.py` into a new file `agents/core/critique_rules.py`. Rename them by removing the leading underscore (`_critique_violations` → `critique_violations`). Preserve all behavior, all imports the functions need, and any helper functions they call inside `forge_master.py` (such as `_strip_csharp_comments`, `_balanced_block`, `_first_modprojectile_setdefaults_body`). The helpers may keep underscore names. The new file must be self-contained — no imports from `forge_master` or `architect`. After moving, run `cd agents && python -m pytest core/test_critique_rules.py -v` and confirm both tests pass. Report the final file contents.

- [ ] **Step 4: Verify**

```bash
cd agents && python -m pytest core/test_critique_rules.py -v
```
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add agents/core/critique_rules.py agents/core/test_critique_rules.py
git commit -m "feat: extract critique rules into core for MCP server reuse"
```

---

### Task 4: Update gatekeeper to use core/critique_rules

**Files:**
- Modify: `agents/gatekeeper/gatekeeper.py:353-368`

- [ ] **Step 1: Replace the imports inside `_manifest_contract_errors`**

Modify `agents/gatekeeper/gatekeeper.py` `_manifest_contract_errors` method:
```python
@staticmethod
def _manifest_contract_errors(manifest: dict | None, cs_code: str) -> list[str]:
    if not isinstance(manifest, dict) or not manifest:
        return []
    from core.critique_rules import critique_violations, validate_projectile_hitbox_contract
    return validate_projectile_hitbox_contract(manifest, cs_code) + critique_violations(
        manifest, cs_code
    )
```

- [ ] **Step 2: Run the gatekeeper test suite**

```bash
cd agents && python -m pytest gatekeeper/ -v
```
Expected: PASS — gatekeeper still works through the new core imports.

- [ ] **Step 3: Commit**

```bash
git add agents/gatekeeper/gatekeeper.py
git commit -m "refactor: gatekeeper uses core.critique_rules instead of forge_master"
```

---

## Phase 2 — Build the MCP Server

The MCP server lives at `agents/mcp_server.py` and exposes 4 tools. It is the only Python entry point in the new pipeline.

### Task 5: Add `mcp` SDK to dependencies

**Files:**
- Modify: `agents/requirements.txt` (or create if absent)

- [ ] **Step 1: Check current dependencies**

```bash
cat agents/requirements.txt 2>/dev/null || echo "no requirements file"
```

- [ ] **Step 2: Add `mcp` to requirements**

Append to `agents/requirements.txt`:
```
mcp>=1.0.0
```

- [ ] **Step 3: Install**

```bash
cd agents && pip install -r requirements.txt
```
Expected: `mcp` installs without error.

- [ ] **Step 4: Verify import works**

```bash
cd agents && python -c "from mcp.server.fastmcp import FastMCP; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add agents/requirements.txt
git commit -m "chore: add mcp SDK dependency"
```

---

### Task 6: Create staging directory module `core/staging.py`

**Files:**
- Create: `agents/core/staging.py`
- Create: `agents/core/test_staging.py`

- [ ] **Step 1: Write the failing test**

Create `agents/core/test_staging.py`:
```python
"""Tests for staging directory lifecycle."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from core.staging import (
    STAGING_ROOT,
    create_staging_dir,
    cleanup_stale_staging,
    staging_path_for,
)


def test_create_staging_dir_creates_directory(tmp_path: Path) -> None:
    with patch("core.staging.STAGING_ROOT", tmp_path):
        path = create_staging_dir("20260430_120000")
    assert path.exists()
    assert path.name == "20260430_120000"


def test_staging_path_for_returns_expected_path(tmp_path: Path) -> None:
    with patch("core.staging.STAGING_ROOT", tmp_path):
        path = staging_path_for("20260430_120000")
    assert path == tmp_path / "20260430_120000"


def test_cleanup_stale_staging_removes_old_dirs(tmp_path: Path) -> None:
    old = tmp_path / "old"
    old.mkdir()
    (old / "marker").write_text("")
    fresh = tmp_path / "fresh"
    fresh.mkdir()

    old_time = time.time() - (25 * 3600)
    import os
    os.utime(old, (old_time, old_time))

    with patch("core.staging.STAGING_ROOT", tmp_path):
        cleanup_stale_staging(max_age_hours=24)

    assert not old.exists()
    assert fresh.exists()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd agents && python -m pytest core/test_staging.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `agents/core/staging.py`**

```python
"""Staging directory management for the Forge MCP pipeline."""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

STAGING_ROOT = Path(__file__).resolve().parents[1] / ".forge_staging"


def new_generation_id() -> str:
    """Return a fresh timestamp slug usable as a staging directory name."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def staging_path_for(generation_id: str) -> Path:
    """Resolve the staging directory path for the given generation ID."""
    return STAGING_ROOT / generation_id


def create_staging_dir(generation_id: str) -> Path:
    """Create the staging directory and return its path."""
    path = staging_path_for(generation_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_stale_staging(max_age_hours: int = 24) -> None:
    """Delete staging directories older than ``max_age_hours``."""
    if not STAGING_ROOT.exists():
        return
    cutoff = time.time() - (max_age_hours * 3600)
    for entry in STAGING_ROOT.iterdir():
        if not entry.is_dir():
            continue
        if entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd agents && python -m pytest core/test_staging.py -v
```
Expected: PASS — three tests green.

- [ ] **Step 5: Commit**

```bash
git add agents/core/staging.py agents/core/test_staging.py
git commit -m "feat: add core.staging for per-generation directory lifecycle"
```

---

### Task 7: Create MCP server skeleton with `forge_status` tool

**Files:**
- Create: `agents/mcp_server.py`
- Create: `agents/tests/test_mcp_server_status.py`

- [ ] **Step 1: Write the failing test**

Create `agents/tests/test_mcp_server_status.py`:
```python
"""Tests for forge_status MCP tool."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from mcp_server import forge_status


def test_forge_status_returns_offline_when_no_files(tmp_path: Path) -> None:
    with patch("mcp_server._mod_sources_root", return_value=tmp_path):
        result = forge_status()
    assert result["forge_connector_alive"] is False
    assert result["tmodloader_running"] is False


def test_forge_status_reports_alive_when_heartbeat_recent(tmp_path: Path) -> None:
    alive_path = tmp_path / "forge_connector_alive.json"
    alive_path.write_text(json.dumps({"timestamp_unix": __import__("time").time()}))
    with patch("mcp_server._mod_sources_root", return_value=tmp_path):
        result = forge_status()
    assert result["forge_connector_alive"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd agents && python -m pytest tests/test_mcp_server_status.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `agents/mcp_server.py` with `forge_status`**

```python
"""The Forge MCP server — exposes 4 execution tools to Claude Code."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from core.paths import mod_sources_root as _mod_sources_root_default

mcp = FastMCP("forge")


def _mod_sources_root() -> Path:
    return _mod_sources_root_default()


def _read_json_or_none(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@mcp.tool()
def forge_status() -> dict[str, Any]:
    """Return current Forge pipeline state.

    Returns:
        {
            pipeline_stage: str,
            forge_connector_alive: bool,
            tmodloader_running: bool,
        }
    """
    root = _mod_sources_root()

    alive_payload = _read_json_or_none(root / "forge_connector_alive.json")
    forge_connector_alive = False
    if alive_payload:
        ts = alive_payload.get("timestamp_unix", 0)
        forge_connector_alive = (time.time() - ts) < 30  # heartbeat within 30s

    status_payload = _read_json_or_none(root / "generation_status.json")
    pipeline_stage = (status_payload or {}).get("status", "idle")

    return {
        "pipeline_stage": pipeline_stage,
        "forge_connector_alive": forge_connector_alive,
        "tmodloader_running": forge_connector_alive,
    }


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd agents && python -m pytest tests/test_mcp_server_status.py -v
```
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add agents/mcp_server.py agents/tests/test_mcp_server_status.py
git commit -m "feat: add forge_status MCP tool with heartbeat-based liveness check"
```

---

### Task 8: Implement `forge_compile` tool

**Files:**
- Modify: `agents/mcp_server.py` (add `forge_compile`)
- Create: `agents/tests/test_mcp_server_compile.py`

- [ ] **Step 1: Write the failing test**

Create `agents/tests/test_mcp_server_compile.py`:
```python
"""Tests for forge_compile MCP tool."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mcp_server import forge_compile


def test_forge_compile_creates_staging_dir_with_generation_id(tmp_path: Path) -> None:
    cs_code = "namespace ForgeGeneratedMod.Content.Items { class Foo {} }"
    manifest = {
        "item_name": "Foo",
        "display_name": "Foo Item",
        "tooltip": "A simple foo",
    }

    with patch("mcp_server.STAGING_ROOT", tmp_path), \
         patch("mcp_server._invoke_tmodloader_build") as mock_build:
        mock_build.return_value = MagicMock(returncode=0, stdout="Build success", stderr="")
        result = forge_compile(cs_code, manifest, "20260430_120000")

    assert result["status"] == "success"
    staged = tmp_path / "20260430_120000"
    assert staged.exists()
    assert (staged / "Content" / "Items" / "Foo.cs").exists()
    assert (staged / "Localization" / "en-US.hjson").exists()


def test_forge_compile_returns_errors_on_build_failure(tmp_path: Path) -> None:
    cs_code = "broken c# code"
    manifest = {"item_name": "Bad", "display_name": "Bad", "tooltip": ""}

    with patch("mcp_server.STAGING_ROOT", tmp_path), \
         patch("mcp_server._invoke_tmodloader_build") as mock_build:
        mock_build.return_value = MagicMock(
            returncode=1,
            stdout="error CS1002: ; expected",
            stderr="",
        )
        result = forge_compile(cs_code, manifest, "20260430_120001")

    assert result["status"] == "error"
    assert any("CS1002" in err for err in result["errors"])
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd agents && python -m pytest tests/test_mcp_server_compile.py -v
```
Expected: FAIL — `forge_compile` not defined.

- [ ] **Step 3: Add `forge_compile` to `agents/mcp_server.py`**

Add these imports at the top of `agents/mcp_server.py`:
```python
import re
import subprocess
from core.compilation_harness import find_tmod_path
from core.hjson_gen import generate_hjson
from core.staging import STAGING_ROOT, create_staging_dir, cleanup_stale_staging
```

Add the tool below `forge_status`:
```python
_ERROR_RE = re.compile(r"(error\s+(?:CS\d+|TML\d+):\s+[^\n]+)")


def _invoke_tmodloader_build(staging_dir: Path) -> subprocess.CompletedProcess:
    """Invoke tModLoader build. Subprocess shape isolated for testability."""
    tmod_root = find_tmod_path()
    if tmod_root is None:
        raise RuntimeError("tModLoader installation not found. Set TMODLOADER_PATH.")
    return subprocess.run(
        ["dotnet", str(tmod_root / "tModLoader.dll"), "-build", str(staging_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


@mcp.tool()
def forge_compile(cs_code: str, manifest: dict, generation_id: str) -> dict:
    """Compile generated C# in an isolated staging directory.

    Args:
        cs_code: C# source for the ModItem (and any ModProjectile).
        manifest: Architect manifest. ``item_name``, ``display_name``, and
            ``tooltip`` are read for hjson generation.
        generation_id: Timestamp slug created by the main session at pipeline
            start. Used to locate the staging directory across compile/inject.

    Returns:
        {status, errors, artifact_path}
    """
    cleanup_stale_staging(max_age_hours=24)
    staging = create_staging_dir(generation_id)

    item_name = manifest["item_name"]
    items_dir = staging / "Content" / "Items"
    items_dir.mkdir(parents=True, exist_ok=True)
    (items_dir / f"{item_name}.cs").write_text(cs_code, encoding="utf-8")

    hjson = generate_hjson(
        item_name=item_name,
        display_name=manifest["display_name"],
        tooltip=manifest.get("tooltip", ""),
    )
    loc_dir = staging / "Localization"
    loc_dir.mkdir(parents=True, exist_ok=True)
    (loc_dir / "en-US.hjson").write_text(hjson, encoding="utf-8")

    proc = _invoke_tmodloader_build(staging)
    if proc.returncode == 0:
        return {
            "status": "success",
            "errors": [],
            "artifact_path": str(staging / f"{item_name}.tmod"),
        }
    errors = [m.group(1) for m in _ERROR_RE.finditer(proc.stdout + "\n" + proc.stderr)]
    if not errors:
        errors = [(proc.stderr or proc.stdout).strip().splitlines()[-1] if (proc.stderr or proc.stdout).strip() else "unknown build error"]
    return {"status": "error", "errors": errors, "artifact_path": ""}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd agents && python -m pytest tests/test_mcp_server_compile.py -v
```
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add agents/mcp_server.py agents/tests/test_mcp_server_compile.py
git commit -m "feat: add forge_compile MCP tool with staged builds"
```

---

### Task 9: Implement `forge_generate_sprite` tool

**Files:**
- Modify: `agents/mcp_server.py` (add `forge_generate_sprite`)
- Create: `agents/tests/test_mcp_server_sprite.py`

- [ ] **Step 1: Write the failing test**

Create `agents/tests/test_mcp_server_sprite.py`:
```python
"""Tests for forge_generate_sprite MCP tool."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

from mcp_server import forge_generate_sprite


def test_forge_generate_sprite_returns_three_candidates(tmp_path: Path) -> None:
    fake_paths = [tmp_path / f"cand_{i}.png" for i in range(3)]
    for p in fake_paths:
        p.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch("mcp_server._run_pixelsmith_audition") as mock_run:
        mock_run.return_value = [str(p) for p in fake_paths]
        result = forge_generate_sprite(
            description="silver wand with crescent",
            size=[40, 40],
            animation_frames=1,
            kind="item",
            reference_path=None,
            generation_id="20260430_120000",
        )

    assert result["status"] == "success"
    assert len(result["candidate_paths"]) == 3


def test_forge_generate_sprite_passes_reference_when_supplied(tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake_paths = [tmp_path / f"cand_{i}.png" for i in range(3)]
    for p in fake_paths:
        p.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch("mcp_server._run_pixelsmith_audition") as mock_run:
        mock_run.return_value = [str(p) for p in fake_paths]
        forge_generate_sprite(
            description="moon beam projectile",
            size=[18, 18],
            animation_frames=3,
            kind="projectile",
            reference_path=str(ref),
            generation_id="20260430_120001",
        )

    args, kwargs = mock_run.call_args
    assert kwargs["reference_path"] == str(ref) or args[-1] == str(ref) or kwargs.get("reference_path")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd agents && python -m pytest tests/test_mcp_server_sprite.py -v
```
Expected: FAIL — `forge_generate_sprite` not defined.

- [ ] **Step 3: Add `forge_generate_sprite` to `agents/mcp_server.py`**

```python
def _run_pixelsmith_audition(
    *,
    description: str,
    size: list[int],
    animation_frames: int,
    kind: str,
    reference_path: str | None,
    generation_id: str,
) -> list[str]:
    """Bridge into the existing pixelsmith audition pipeline.

    Wraps ``ArtistAgent.generate_scoped_asset`` so that the MCP tool stays a
    thin layer. The artist returns the chosen sprite path; we surface all
    audition candidates instead so the Sprite-Judge subagent can pick.
    """
    from pixelsmith.pixelsmith import ArtistAgent
    output_dir = STAGING_ROOT / generation_id / "sprites"
    output_dir.mkdir(parents=True, exist_ok=True)

    agent = ArtistAgent(output_dir=output_dir)
    result = agent.generate_audition_candidates(
        description=description,
        size=tuple(size),
        animation_frames=animation_frames,
        kind=kind,
        reference_path=reference_path,
    )
    return [str(p) for p in result["candidate_paths"]]


@mcp.tool()
def forge_generate_sprite(
    description: str,
    size: list[int],
    animation_frames: int,
    kind: str,
    reference_path: str | None,
    generation_id: str,
) -> dict:
    """Generate sprite candidates for the Sprite-Judge subagent to choose from.

    Args:
        description: Visual description from the manifest.
        size: ``[width, height]`` in pixels.
        animation_frames: 1 for static, N for animated sheets.
        kind: ``"item"`` or ``"projectile"``.
        reference_path: Local image path. If provided, FAL img2img mode is used.
            If ``None``, FAL text-to-image mode is used.
        generation_id: Pipeline ID; sprites are written under the staging dir.
    """
    if kind not in ("item", "projectile"):
        return {"status": "error", "candidate_paths": [], "error_message": f"invalid kind: {kind}"}

    try:
        candidate_paths = _run_pixelsmith_audition(
            description=description,
            size=size,
            animation_frames=animation_frames,
            kind=kind,
            reference_path=reference_path,
            generation_id=generation_id,
        )
    except Exception as exc:
        return {"status": "error", "candidate_paths": [], "error_message": str(exc)}

    return {"status": "success", "candidate_paths": candidate_paths}
```

- [ ] **Step 4: Add `generate_audition_candidates` shim to `pixelsmith/pixelsmith.py`**

This shim exposes the audition list without picking a winner. Add to `ArtistAgent`:

```python
def generate_audition_candidates(
    self,
    *,
    description: str,
    size: tuple[int, int],
    animation_frames: int,
    kind: str,
    reference_path: str | None,
) -> dict:
    """Return all audition candidates without selecting a winner.

    The MCP layer surfaces these to a Sprite-Judge subagent which picks.
    """
    # Build a minimal manifest the existing audition logic understands.
    manifest = self._minimal_audition_manifest(
        description=description,
        size=size,
        animation_frames=animation_frames,
        kind=kind,
        reference_path=reference_path,
    )
    candidate_paths = self._generate_audition_only(manifest, kind)
    return {"status": "success", "candidate_paths": candidate_paths}
```

(The `_minimal_audition_manifest` and `_generate_audition_only` helpers should be added — they reuse the existing `_generate_with_variants` plumbing but skip the variant-selector LLM call. **[CODEX]** Delegate this part: tell Codex "expose the existing audition logic in `pixelsmith.py` as a method that returns the candidate list without calling `select_best_variant` or `judge_surviving_candidates`. Preserve all sprite gates and post-processing.")

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd agents && python -m pytest tests/test_mcp_server_sprite.py -v
```
Expected: PASS — both tests green.

- [ ] **Step 6: Commit**

```bash
git add agents/mcp_server.py agents/pixelsmith/pixelsmith.py agents/tests/test_mcp_server_sprite.py
git commit -m "feat: add forge_generate_sprite MCP tool with audition surfacing"
```

---

### Task 10: Implement `forge_inject` tool

**Files:**
- Modify: `agents/mcp_server.py` (add `forge_inject`)
- Create: `agents/tests/test_mcp_server_inject.py`

- [ ] **Step 1: Write the failing test**

Create `agents/tests/test_mcp_server_inject.py`:
```python
"""Tests for forge_inject MCP tool."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from mcp_server import forge_inject


def test_forge_inject_writes_files_and_inject_json(tmp_path: Path) -> None:
    staging = tmp_path / "staging" / "20260430_120000"
    (staging / "Content" / "Items").mkdir(parents=True)
    (staging / "Content" / "Items" / "Foo.cs").write_text("// generated")
    (staging / "Localization").mkdir(parents=True)
    (staging / "Localization" / "en-US.hjson").write_text("Mods: {}")

    item_sprite = tmp_path / "item.png"
    item_sprite.write_bytes(b"\x89PNG\r\n\x1a\n")
    proj_sprite = tmp_path / "proj.png"
    proj_sprite.write_bytes(b"\x89PNG\r\n\x1a\n")

    mod_sources = tmp_path / "ModSources"
    mod_dest = mod_sources / "ForgeGeneratedMod"
    mod_dest.mkdir(parents=True)

    with patch("mcp_server.STAGING_ROOT", tmp_path / "staging"), \
         patch("mcp_server._mod_sources_root", return_value=mod_sources):
        result = forge_inject(
            item_name="Foo",
            cs_code="// generated",
            manifest={"item_name": "Foo", "display_name": "Foo", "tooltip": ""},
            item_sprite_path=str(item_sprite),
            projectile_sprite_path=str(proj_sprite),
            generation_id="20260430_120000",
        )

    assert result["status"] == "success"
    assert result["reload_required"] is True
    assert (mod_dest / "Content" / "Items" / "Foo.cs").exists()
    inject_payload = json.loads((mod_sources / "forge_inject.json").read_text())
    assert inject_payload["item_name"] == "Foo"


def test_forge_inject_rejects_unknown_generation_id(tmp_path: Path) -> None:
    with patch("mcp_server.STAGING_ROOT", tmp_path / "staging"), \
         patch("mcp_server._mod_sources_root", return_value=tmp_path / "ModSources"):
        result = forge_inject(
            item_name="Foo",
            cs_code="// x",
            manifest={"item_name": "Foo", "display_name": "Foo", "tooltip": ""},
            item_sprite_path="/nonexistent.png",
            projectile_sprite_path="/nonexistent.png",
            generation_id="does_not_exist",
        )
    assert result["status"] == "error"
    assert "staging" in result["error_message"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd agents && python -m pytest tests/test_mcp_server_inject.py -v
```
Expected: FAIL — `forge_inject` not defined.

- [ ] **Step 3: Add `forge_inject` to `agents/mcp_server.py`**

```python
import shutil


@mcp.tool()
def forge_inject(
    item_name: str,
    cs_code: str,
    manifest: dict,
    item_sprite_path: str,
    projectile_sprite_path: str,
    generation_id: str,
) -> dict:
    """Atomically promote a successfully compiled artifact into ForgeGeneratedMod.

    Args:
        item_name: ModItem class name.
        cs_code: Final C# source. Used as a checksum input — must match what
            forge_compile last accepted.
        manifest: Used to re-derive hjson (must match forge_compile).
        item_sprite_path: Path returned by Sprite-Judge for the item icon.
        projectile_sprite_path: Path returned by Sprite-Judge for the projectile.
        generation_id: Locates the staging directory.

    Returns:
        {status, error_message, reload_required}
    """
    from core.staging import staging_path_for

    staging = staging_path_for(generation_id)
    if not staging.exists():
        return {
            "status": "error",
            "error_message": f"staging directory not found for generation_id={generation_id}",
            "reload_required": False,
        }

    mod_root = _mod_sources_root() / "ForgeGeneratedMod"
    items_dir = mod_root / "Content" / "Items"
    proj_dir = mod_root / "Content" / "Projectiles"
    loc_dir = mod_root / "Localization"
    items_dir.mkdir(parents=True, exist_ok=True)
    proj_dir.mkdir(parents=True, exist_ok=True)
    loc_dir.mkdir(parents=True, exist_ok=True)

    (items_dir / f"{item_name}.cs").write_text(cs_code, encoding="utf-8")

    hjson = generate_hjson(
        item_name=item_name,
        display_name=manifest["display_name"],
        tooltip=manifest.get("tooltip", ""),
    )
    (loc_dir / "en-US.hjson").write_text(hjson, encoding="utf-8")

    item_sprite = Path(item_sprite_path)
    if item_sprite.exists():
        shutil.copy2(item_sprite, items_dir / f"{item_name}.png")
    proj_sprite = Path(projectile_sprite_path) if projectile_sprite_path else None
    if proj_sprite and proj_sprite.exists():
        shutil.copy2(proj_sprite, proj_dir / f"{item_name}Projectile.png")

    inject_payload = {
        "item_name": item_name,
        "manifest": manifest,
        "sprite_path": str(items_dir / f"{item_name}.png"),
        "projectile_sprite_path": str(proj_dir / f"{item_name}Projectile.png"),
    }
    (_mod_sources_root() / "forge_inject.json").write_text(
        json.dumps(inject_payload, indent=2), encoding="utf-8"
    )

    shutil.rmtree(staging, ignore_errors=True)
    return {"status": "success", "error_message": None, "reload_required": True}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd agents && python -m pytest tests/test_mcp_server_inject.py -v
```
Expected: PASS — both tests green.

- [ ] **Step 5: Run the full MCP server test suite**

```bash
cd agents && python -m pytest tests/test_mcp_server_*.py -v
```
Expected: PASS — all MCP server tests green.

- [ ] **Step 6: Commit**

```bash
git add agents/mcp_server.py agents/tests/test_mcp_server_inject.py
git commit -m "feat: add forge_inject MCP tool with atomic staging promotion"
```

---

## Phase 3 — Write the Skill File

The skill file at `.claude/skills/forge.md` is the workflow brain. It contains tier inference, all subagent prompts, orchestration rules, and error escalation policy.

### Task 11: Create `.claude/skills/forge.md` skeleton

**Files:**
- Create: `.claude/skills/forge.md`

- [ ] **Step 1: Create the file with frontmatter and section anchors**

```markdown
---
name: forge
description: Generate Terraria mod weapons end-to-end via Architect/Coder/Reviewer/Judge subagents and the Forge MCP tools. Use when the user asks for a weapon by description (e.g. "make a void pistol"), wants to inject something into their tModLoader install, or asks to iterate on a previously-generated weapon.
---

# Forge — Terraria Weapon Generation Skill

## 0 — When to Invoke

Trigger on: "make a [weapon]", "generate a [weapon]", "build a [tier name] [weapon]", "forge a …", "inject … into Terraria". Do not trigger on general Terraria questions.

## 1 — Pipeline State

Maintain throughout the run:
- `generation_id`: timestamp slug `YYYYMMDD_HHMMSS`, created at the start of every run
- `manifest`: the Architect-Manifest output
- `cs_code`: the latest Coder output
- `global_attempts_used`: int, incremented on every Coder spawn

## 2 — Tier Inference

(Filled in Task 12.)

## 3 — Subagent Prompts

(Filled in Tasks 13-18.)

## 4 — Orchestration

(Filled in Task 19.)

## 5 — Error Escalation

(Filled in Task 20.)
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat: add forge skill skeleton"
```

---

### Task 12: Add tier inference rules

**Files:**
- Modify: `.claude/skills/forge.md` (replace `## 2 — Tier Inference` placeholder)

- [ ] **Step 1: Replace the section**

```markdown
## 2 — Tier Inference

Read the user's description and pick the lowest tier that fits:

| Signal | Tier |
|---|---|
| "simple", "basic", "starter", "first", just damage + use time | 1 |
| One special mechanic (homing, piercing, on-hit buff, on-hit debuff, bouncing) | 2 |
| Charge phases, multi-projectile payoff, sweep/beam, orbital patterns, "forbidden", "void", multi-stage spectacle | 3 |

State the inferred tier to the user before continuing: "I'm building this as a Tier 3 weapon because of the charge + sweep behavior. Continuing…"
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add tier inference rules"
```

---

### Task 13: Write Architect-Thesis subagent prompt

**Files:**
- Modify: `.claude/skills/forge.md`

- [ ] **Step 1: Append to Section 3**

````markdown
### 3.1 Architect-Thesis [Opus]

Spawn with this exact prompt template:

```
You are the Architect-Thesis subagent. Generate exactly 3 distinct weapon concepts for the Forge pipeline.

INPUT (JSON):
{{
  "prompt": "<user description>",
  "tier": <1|2|3>,
  "forbidden_patterns": ["bullet feel", "plain fireball", "generic dust trail"]
}}

REQUIREMENTS:
- Produce 3 named concepts that read as visually and mechanically distinct
- Each concept must specify: name, one-sentence fantasy, spectacle plan, basis_atoms list
- For Tier 3: at least 2 of the 3 must include a charge phase or multi-projectile payoff
- Avoid every pattern in forbidden_patterns — never describe a weapon as a "fireball-like" or "bullet-like" shot
- Names must be evocative, not generic ("Riftspite", "Hollow Verdict") — never "Magic Sword" or "Cool Bow"

OUTPUT (JSON only — no prose):
{{
  "concepts": [
    {{
      "name": "...",
      "fantasy": "...",
      "spectacle_plan": "1-2 sentences describing what makes the projectile feel distinct",
      "basis_atoms": ["charge_phase", "beam_lance", "phase_swap", ...]
    }},
    ...
  ]
}}
```

Use Opus model. Pass the rendered JSON input as the only message.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add Architect-Thesis subagent prompt"
```

---

### Task 14: Write Architect-Manifest subagent prompt

**Files:**
- Modify: `.claude/skills/forge.md`

- [ ] **Step 1: Append to Section 3**

The manifest schema is large — embed a reference to the existing JSON schema and let the subagent read it. Concretely include the canonical fields it must populate.

````markdown
### 3.2 Architect-Manifest [Sonnet]

Spawn with:

```
You are the Architect-Manifest subagent. Expand the winning concept into a full Forge manifest.

INPUT (JSON):
{{
  "winning_concept": {{ name, fantasy, spectacle_plan, basis_atoms }},
  "tier": <1|2|3>,
  "tier1_omit_fields": ["spectacle_plan.ai_phases", "spectacle_plan.render_passes", "mechanics_ir"]
}}

REQUIRED FIELDS:
- item_name: PascalCase, no spaces (e.g. "Riftspite")
- display_name: human-readable
- tooltip: 1 sentence
- content_type, type, sub_type
- stats: {damage, knockback, crit_chance, use_time, auto_reuse, rarity}
- visuals: {color_palette, description, icon_size: [int, int]}
- mechanics: {shoot_projectile?, on_hit_buff?, custom_projectile, shot_style, crafting_material, crafting_cost, crafting_tile}
- references: {item: {needed: bool}, projectile: {needed: bool}}  ← set true only when an unusual silhouette would benefit from a real-world reference image

TIER-DEPENDENT FIELDS:
- Tier 1: OMIT spectacle_plan.ai_phases, spectacle_plan.render_passes, mechanics_ir entirely (do not emit empty arrays)
- Tier 2: include spectacle_plan with 1-2 ai_phases, 1-2 render_passes, mechanics_ir.atoms with 1-2 entries
- Tier 3: include full spectacle_plan and mechanics_ir.atoms with 3-6 entries; projectile_visuals.animation_tier should be "generated_frames:3"

FORBIDDEN:
- Do not include must_not_include patterns that contradict the spectacle_plan
- Do not invent mechanics atoms outside the basis_atoms list

OUTPUT (JSON only):
{{ "manifest": <full manifest object> }}
```

Use Sonnet model.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add Architect-Manifest subagent prompt"
```

---

### Task 15: Write Coder subagent prompt

**Files:**
- Modify: `.claude/skills/forge.md`

- [ ] **Step 1: Append to Section 3**

````markdown
### 3.3 Coder [Sonnet]

Spawn with:

```
You are the Coder subagent. Generate Terraria mod C# source code from the manifest.

INPUT (JSON):
{{
  "manifest": <full manifest>,
  "compile_errors": [str],   // empty on first attempt
  "reviewer_issues": [str],  // empty unless re-spawned by reviewer
  "attempt_number": <int>,
  "global_attempts_used": <int>
}}

OUTPUT (JSON only):
{{ "cs_code": "<complete C# source>" }}

REQUIREMENTS:
- Namespace: ForgeGeneratedMod.Content.Items
- File contains a single ModItem subclass named ${{manifest.item_name}}
- If manifest.mechanics.custom_projectile is true: include a ModProjectile subclass named ${{manifest.item_name}}Projectile in namespace ForgeGeneratedMod.Content.Projectiles
- Use using directives: Terraria; Terraria.ID; Terraria.ModLoader; Microsoft.Xna.Framework; Microsoft.Xna.Framework.Graphics; Terraria.GameContent; Terraria.DataStructures; Terraria.Audio
- Override SetDefaults() with stats from manifest.stats
- Override AddRecipes() using manifest.mechanics.crafting_material × crafting_cost at crafting_tile
- For Tier 3: implement charge phases via Projectile.ai[0]/ai[1] tick counters, secondary projectile spawns via Projectile.NewProjectile in OnHit hooks, beam lance bodies via line collision (Collision.CheckAABBvLineCollision)
- For Tier 1: simple SetDefaults + AddRecipes only

FORBIDDEN APIs / patterns:
- Do not use ProjectileID.Bullet for non-bullet weapons (AmmoID.Bullet for ammo is fine)
- Do not generate hjson — the MCP tool derives it deterministically from manifest
- Do not write file headers/comments describing the implementation; the code speaks for itself

IF compile_errors is non-empty:
- The errors are CS####/TML### diagnostics from the previous attempt. Fix each one specifically. Do not rewrite unrelated code.

IF reviewer_issues is non-empty:
- Address every issue listed. Each issue is a deterministic critique violation. The fix must satisfy the rule, not paper over it.
```

Use Sonnet model.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add Coder subagent prompt"
```

---

### Task 16: Write Reviewer subagent prompt

**Files:**
- Modify: `.claude/skills/forge.md`

- [ ] **Step 1: Append to Section 3**

The reviewer's checklist comes from `core/critique_rules.py`. The skill embeds the rule list in plain English so the subagent can reason about it without importing Python.

````markdown
### 3.4 Reviewer [Sonnet]

Spawn with:

```
You are the Reviewer subagent. Critique generated Terraria C# against the deterministic rule list.

INPUT (JSON):
{{
  "cs_code": "<C# source>",
  "manifest": <full manifest>,
  "critique_checklist": [
    "Top-level namespace must be ForgeGeneratedMod.Content.Items",
    "Projectile class (if present) must be in ForgeGeneratedMod.Content.Projectiles",
    "ModProjectile.SetDefaults must set Projectile.width and Projectile.height matching manifest.projectile_visuals.icon_size",
    "Use ProjectileID.Bullet only when manifest.mechanics.shoot_projectile == 'ProjectileID.Bullet'",
    "AmmoID.Bullet in shoot_consumable arrays does NOT count as bullet feel",
    "Do not call NPC.GetTargetData() or any banned reflective APIs",
    "Tier 3: spectacle plan atoms in manifest must be reflected in code (charge counters, secondary projectiles, beam lances)",
    "All public methods that override base class must use 'public override'"
  ]
}}

OUTPUT (JSON only):
{{
  "approved": <bool>,
  "issues": [<string per violated rule, naming the rule and the offending line>]
}}

If approved is true, issues MUST be []. If issues is non-empty, approved MUST be false.
```

Use Sonnet model.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add Reviewer subagent prompt"
```

---

### Task 17: Write Reference-Finder subagent prompt

**Files:**
- Modify: `.claude/skills/forge.md`

- [ ] **Step 1: Append to Section 3**

````markdown
### 3.5 Reference-Finder [Opus]

Spawn ONCE per slot for which `manifest.references.<slot>.needed == true`. Provide the agent the WebSearch and WebFetch tools.

```
You are the Reference-Finder subagent. Find one good reference image to inform pixel-art generation.

INPUT (JSON):
{{
  "slot": "item" | "projectile",
  "visual_description": "<text from manifest>",
  "weapon_fantasy": "<text from concept>",
  "must_not_feel_like": [str],
  "generation_id": "<timestamp slug>"
}}

PROCEDURE:
1. Use WebSearch with 2-3 query variations targeting the visual description (concept art, game art, isolated subject photography). Avoid queries that obviously match a vanilla Terraria item.
2. From the top results, evaluate candidates against these criteria, in priority order:
   a. Isolated subject on a clean or transparent background
   b. Silhouette + color align with visual_description
   c. Not a recognisable vanilla Terraria item
   d. Resolution >= 256px on the short side
   e. Avoids anything in must_not_feel_like
3. Use WebFetch to verify the chosen image actually loads and looks right. If it does not, try another candidate.
4. Download the best image to: agents/.forge_staging/${{generation_id}}/ref_${{slot}}.png (use Bash with curl or wget)

OUTPUT (JSON only):
{{
  "reference_path": "<absolute path or null if no suitable image found>",
  "reasoning": "<one sentence explaining the choice>"
}}

If no candidate satisfies the criteria, return reference_path: null. Never return a path you have not actually downloaded.
```

Use Opus model. Provide tools: WebSearch, WebFetch, Bash, Read.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add Reference-Finder subagent prompt"
```

---

### Task 18: Write Sprite-Judge subagent prompt

**Files:**
- Modify: `.claude/skills/forge.md`

- [ ] **Step 1: Append to Section 3**

````markdown
### 3.6 Sprite-Judge [Opus]

Spawn with the Read tool available so it can view each candidate image.

```
You are the Sprite-Judge subagent. Choose the best item sprite and best projectile sprite from candidate sets.

INPUT (JSON):
{{
  "item_candidates": ["path1", "path2", "path3"],
  "projectile_candidates": ["path1", "path2", "path3"],
  "weapon_description": "<one-sentence fantasy>"
}}

PROCEDURE:
1. Use the Read tool to view every path in item_candidates.
2. For the item slot, choose the candidate that best satisfies:
   a. Clean readable silhouette at 2x zoom
   b. Color palette aligned with the weapon fantasy
   c. Pixel art quality (no smudgy AA artifacts, no stray pixels outside the silhouette)
   d. Distinct from generic vanilla Terraria items
3. Use the Read tool to view every path in projectile_candidates.
4. For the projectile slot, choose the candidate that best satisfies:
   a. Reads at small size (Terraria sprites are typically 18-24px)
   b. Trail/glow elements would render cleanly with shaders applied at runtime
   c. Does not look like a plain bullet, plain fireball, or vanilla projectile

OUTPUT (JSON only):
{{
  "item_sprite": "<chosen path>",
  "projectile_sprite": "<chosen path>",
  "reasoning": "<one sentence per pick>"
}}
```

Use Opus model. Provide tools: Read.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add Sprite-Judge subagent prompt"
```

---

### Task 19: Write orchestration rules

**Files:**
- Modify: `.claude/skills/forge.md` (replace `## 4 — Orchestration` placeholder)

- [ ] **Step 1: Replace the section**

````markdown
## 4 — Orchestration

Execute these steps in order. Track `global_attempts_used` across the entire run.

1. **Init.** Create `generation_id` as `datetime.now().strftime("%Y%m%d_%H%M%S")`. Set `global_attempts_used = 0`.
2. **Tier inference.** Apply Section 2 rules. Tell the user: "Building as Tier N because …"
3. **Thesis.** Spawn 3.1. Present the 3 concepts to the user as a numbered list. Wait for their pick — unless they previously said "you choose" or "surprise me", in which case pick the most distinctive concept yourself and tell the user which.
4. **Manifest.** Spawn 3.2 with the winning concept.
5. **Compile loop.** Repeat until reviewer approves OR `global_attempts_used >= 6`:
   1. Spawn 3.3 (Coder) with current `compile_errors`, `reviewer_issues`, `attempt_number`, `global_attempts_used`. Increment `global_attempts_used`.
   2. Call `forge_compile(cs_code, manifest, generation_id)`.
   3. If status == "error": set `compile_errors = result.errors`; if budget remaining, loop to step 5.1; else surface to user with the errors and stop.
   4. Spawn 3.4 (Reviewer) with `cs_code`, `manifest`.
   5. If `approved == true`: exit loop.
   6. Else: set `reviewer_issues = result.issues`, set `compile_errors = []`. If budget remaining, loop to step 5.1; else surface to user and stop.
6. **References.** For each slot in `["item", "projectile"]` where `manifest.references.<slot>.needed == true`, spawn 3.5 (Reference-Finder).
7. **Sprite generation.** Call `forge_generate_sprite` once per slot with the description / size / animation_frames pulled from the manifest, and the `reference_path` returned by 3.5 (or `null`).
8. **Sprite judging.** Spawn 3.6 (Sprite-Judge) with both candidate lists.
9. **Status check.** Call `forge_status()`. If `tmodloader_running == false`: tell user to open tModLoader and stop here. If `forge_connector_alive == false`: warn user and ask "continue anyway? (yes/no)".
10. **Inject.** Call `forge_inject(item_name, cs_code, manifest, item_sprite_path, projectile_sprite_path, generation_id)`.
11. **Report.** Tell the user: item display name, tier, crafting recipe ("`crafting_cost`× `crafting_material` at `crafting_tile`"), and that they need to reload mods in tModLoader.

If user later says "iterate" or "tweak" without a new prompt, reuse the existing manifest as a starting point and skip step 3.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add orchestration rules"
```

---

### Task 20: Write error escalation table

**Files:**
- Modify: `.claude/skills/forge.md` (replace `## 5 — Error Escalation` placeholder)

- [ ] **Step 1: Replace the section**

```markdown
## 5 — Error Escalation

Compile + reviewer share the global 6-attempt budget.

| Attempt | Trigger | Behaviour |
|---|---|---|
| 1 | First codegen | Silent — spawn Coder, compile, continue |
| 2 | Compile error or reviewer fail | Silent — spawn fresh Coder with errors, retry |
| 3 | Compile error or reviewer fail | Silent — spawn fresh Coder, retry |
| 4 | Compile error or reviewer fail | Tell user: "Still fixing compile issues (attempt 4/6)…" |
| 5 | Compile error or reviewer fail | Tell user: "Attempt 5/6 — remaining errors: …" |
| 6 | Compile error or reviewer fail | Surface full error to user, ask continue/abort |

Other failures:

| Failure | Behaviour |
|---|---|
| FAL.ai unreachable | Tell user, offer procedural fallback sprite generated with PIL |
| ForgeConnector offline | Warn user, ask to confirm before inject |
| tModLoader not running | Block inject, tell user to open tModLoader first |
| MCP server tool throws | Surface the error to the user verbatim — do not retry |
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/forge.md
git commit -m "feat(skill): add error escalation table"
```

---

## Phase 4 — Wire Up + Smoke Test

### Task 21: Register MCP server in `.claude/settings.json`

**Files:**
- Modify (or create): `.claude/settings.json`

- [ ] **Step 1: Check current settings**

```bash
cat .claude/settings.json 2>/dev/null
```

- [ ] **Step 2: Update settings.json**

Merge this into the existing JSON (or create the file with this content):

```json
{
  "mcpServers": {
    "forge": {
      "command": "python",
      "args": ["agents/mcp_server.py"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

- [ ] **Step 3: Verify the server starts**

```bash
cd agents && timeout 3 python mcp_server.py < /dev/null || echo "expected — server runs until stdin closes"
```
Expected: server prints nothing on startup (FastMCP is stdio-based) and exits when input closes.

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: register Forge MCP server in claude settings"
```

---

### Task 22: End-to-end smoke test (Tier 1)

**Files:**
- Create: `agents/tests/test_smoke_tier1.py`

- [ ] **Step 1: Write the test**

This test exercises the MCP server end-to-end by calling each tool with realistic inputs, mocking only the tModLoader build and FAL.ai call.

```python
"""End-to-end smoke test of the MCP server (Tier 1 weapon)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from mcp_server import forge_compile, forge_generate_sprite, forge_inject, forge_status


def test_full_pipeline_tier1(tmp_path: Path) -> None:
    generation_id = "20260430_120000"
    manifest = {
        "item_name": "TestStarterBow",
        "display_name": "Test Starter Bow",
        "tooltip": "A simple bow",
        "stats": {"damage": 10, "knockback": 2, "use_time": 28, "rarity": "ItemRarityID.Blue"},
        "mechanics": {
            "custom_projectile": False,
            "shoot_projectile": "ProjectileID.WoodenArrowFriendly",
            "crafting_material": "ItemID.Wood",
            "crafting_cost": 10,
            "crafting_tile": "TileID.WorkBenches",
        },
    }
    cs_code = (
        "using Terraria; using Terraria.ID; using Terraria.ModLoader;\n"
        "namespace ForgeGeneratedMod.Content.Items {\n"
        "  public class TestStarterBow : ModItem {\n"
        "    public override void SetDefaults() { Item.damage = 10; }\n"
        "  }\n"
        "}\n"
    )

    item_sprite = tmp_path / "item.png"
    item_sprite.write_bytes(b"\x89PNG\r\n\x1a\n")
    proj_sprite = tmp_path / "proj.png"
    proj_sprite.write_bytes(b"\x89PNG\r\n\x1a\n")

    mod_sources = tmp_path / "ModSources"
    (mod_sources / "ForgeGeneratedMod").mkdir(parents=True)

    with patch("mcp_server.STAGING_ROOT", tmp_path / "staging"), \
         patch("mcp_server._mod_sources_root", return_value=mod_sources), \
         patch("mcp_server._invoke_tmodloader_build") as mock_build, \
         patch("mcp_server._run_pixelsmith_audition") as mock_sprite:
        mock_build.return_value = MagicMock(returncode=0, stdout="Build success", stderr="")
        mock_sprite.return_value = [str(item_sprite), str(item_sprite), str(item_sprite)]

        compile_result = forge_compile(cs_code, manifest, generation_id)
        assert compile_result["status"] == "success"

        sprite_result = forge_generate_sprite(
            description="simple wooden bow",
            size=[40, 40],
            animation_frames=1,
            kind="item",
            reference_path=None,
            generation_id=generation_id,
        )
        assert sprite_result["status"] == "success"
        assert len(sprite_result["candidate_paths"]) == 3

        status_result = forge_status()
        assert status_result["forge_connector_alive"] is False  # no heartbeat in test fixture

        inject_result = forge_inject(
            item_name="TestStarterBow",
            cs_code=cs_code,
            manifest=manifest,
            item_sprite_path=str(item_sprite),
            projectile_sprite_path=str(proj_sprite),
            generation_id=generation_id,
        )
        assert inject_result["status"] == "success"
        assert inject_result["reload_required"] is True

    assert (mod_sources / "ForgeGeneratedMod" / "Content" / "Items" / "TestStarterBow.cs").exists()
    inject_payload = json.loads((mod_sources / "forge_inject.json").read_text())
    assert inject_payload["item_name"] == "TestStarterBow"
```

- [ ] **Step 2: Run the test**

```bash
cd agents && python -m pytest tests/test_smoke_tier1.py -v
```
Expected: PASS — full pipeline runs without errors.

- [ ] **Step 3: Commit**

```bash
git add agents/tests/test_smoke_tier1.py
git commit -m "test: add Tier 1 end-to-end smoke test for MCP server"
```

---

## Phase 5 — Archive Old Code

The pipeline is now driven entirely by `mcp_server.py` + the skill. Move the old code into `archive/` so it stays available for reference but does not pollute imports.

### Task 23: Archive `BubbleTeaTerminal/` **[CODEX]**

- [ ] **Step 1: Delegate to Codex**

Use `codex:codex-rescue` with this prompt:

> Move the directory `BubbleTeaTerminal/` (in the repo root at `/Users/user/Desktop/the-forge`) into `archive/BubbleTeaTerminal/` using `git mv`. Then verify nothing in `agents/` imports from it (run `grep -rn "BubbleTeaTerminal" agents/` and report any matches). If there are no matches, commit the move with the message: `chore: archive BubbleTeaTerminal — replaced by Forge MCP skill`.

- [ ] **Step 2: Verify**

```bash
ls archive/BubbleTeaTerminal/
[ ! -d BubbleTeaTerminal ] && echo "moved cleanly"
```
Expected: directory exists in archive, not in repo root.

---

### Task 24: Archive `agents/orchestrator.py`, `architect/`, `forge_master/` **[CODEX]**

- [ ] **Step 1: Delegate to Codex**

Use `codex:codex-rescue`:

> Move these into `archive/` from `/Users/user/Desktop/the-forge`:
> - `agents/orchestrator.py` → `archive/agents/orchestrator.py`
> - `agents/orchestrator_smoke.py` → `archive/agents/orchestrator_smoke.py`
> - `agents/architect/` → `archive/agents/architect/`
> - `agents/forge_master/` → `archive/agents/forge_master/`
> - `agents/run_pipeline_cli.py` → `archive/agents/run_pipeline_cli.py`
> - `agents/stress_tier3_basis.py` → `archive/agents/stress_tier3_basis.py`
> - `agents/stress_tier3_codegen.py` → `archive/agents/stress_tier3_codegen.py`
> - `agents/probe_enrichment.py` → `archive/agents/probe_enrichment.py`
> - `agents/param_sweep.py` → `archive/agents/param_sweep.py`
>
> Use `git mv` for each. Then run `cd agents && python -m pytest -q` and report all failing tests. Do NOT fix the failures — just list them. Then commit with: `chore: archive Python agent code — replaced by MCP server + skill`.

- [ ] **Step 2: Address remaining test failures**

Read the Codex report. Tests in `agents/tests/test_orchestrator.py`, `agents/tests/test_tier3_*.py`, `agents/tests/test_direct_inject_asset_guards.py`, and `agents/forge_master/test_*.py` will all fail or be missing. Move those test files to `archive/` as well:

```bash
git mv agents/tests/test_orchestrator.py archive/agents/tests/
git mv agents/tests/test_tier3_basis_stress_script.py archive/agents/tests/
git mv agents/tests/test_tier3_codegen_stress_script.py archive/agents/tests/
git mv agents/tests/test_tier3_prompt_director_basis_flow.py archive/agents/tests/
git mv agents/tests/test_direct_inject_asset_guards.py archive/agents/tests/
```

(forge_master and architect test files moved with their parent directories already.)

- [ ] **Step 3: Run remaining tests to confirm green**

```bash
cd agents && python -m pytest -q
```
Expected: PASS — only the new MCP server tests, core tests, gatekeeper tests, and pixelsmith tests run, and all pass.

- [ ] **Step 4: Commit**

```bash
git add agents/tests/ archive/agents/tests/
git commit -m "chore: move tests for archived agents into archive/"
```

---

### Task 25: Update README to reflect new architecture

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "How It Works" section**

Append to README.md:

```markdown
## Architecture (post-MCP migration)

The Forge runs as a Claude Code skill backed by a thin MCP server.

- `.claude/skills/forge.md` — workflow, tier inference, all subagent prompts
- `agents/mcp_server.py` — 4 execution tools: forge_compile, forge_generate_sprite, forge_inject, forge_status
- `agents/core/` — shared compile / hjson / staging / critique modules
- `agents/pixelsmith/` — FAL.ai sprite generation (unchanged)
- `agents/gatekeeper/` — tModLoader build + atomic inject (unchanged from old pipeline core)
- `mod/ForgeConnector/` — C# tModLoader watcher (unchanged)
- `archive/` — preserved old Python orchestrator + Go TUI (no longer wired in)

To use: open this repo in Claude Code and say "make a [weapon]". The skill drives Architect / Coder / Reviewer / Reference-Finder / Sprite-Judge subagents and orchestrates the MCP tools end-to-end.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for MCP+skill architecture"
```

---

## Final Self-Check

After completing every task above, run:

```bash
cd agents && python -m pytest -q
```
Expected: all green.

```bash
grep -rn "from forge_master\|from architect" agents/ --include="*.py"
```
Expected: no matches.

```bash
ls .claude/skills/forge.md agents/mcp_server.py
```
Expected: both files exist.

If everything passes, the migration is complete. Open Claude Code in this directory and say "make a starter wooden bow" — you should see the skill drive a full Tier 1 generation end-to-end.
