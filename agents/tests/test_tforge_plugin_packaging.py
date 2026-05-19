from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_plugin_manifest_registers_tforge_with_sensitive_fal_key() -> None:
    manifest_path = REPO_ROOT / ".claude-plugin" / "plugin.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "tforge"
    assert manifest["displayName"] == "Tforge"
    assert "./commands/" in manifest["commands"]
    assert "./.claude/commands/forge.md" in manifest["commands"]

    fal_key = manifest["userConfig"]["fal_key"]
    assert fal_key["type"] == "string"
    assert fal_key["sensitive"] is True
    assert fal_key.get("required", False) is False


def test_marketplace_exposes_tforge_from_repo_root() -> None:
    marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"

    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

    assert marketplace["name"] == "tforge"
    assert marketplace["metadata"]["description"]
    assert marketplace["plugins"][0]["name"] == "tforge"
    assert marketplace["plugins"][0]["source"] == "./"


def test_mcp_config_uses_plugin_relative_paths() -> None:
    mcp_config = (REPO_ROOT / ".mcp.json").read_text(encoding="utf-8")

    assert "${CLAUDE_PLUGIN_ROOT}" in mcp_config
    assert "/Users/" not in mcp_config
    assert "scripts/tforge-mcp-start" in mcp_config


def test_setup_and_doctor_commands_are_registered() -> None:
    commands_dir = REPO_ROOT / "commands"

    assert (commands_dir / "setup.md").is_file()
    assert (commands_dir / "doctor.md").is_file()


def test_setup_and_doctor_commands_execute_scripts_directly() -> None:
    setup_command = (REPO_ROOT / "commands" / "setup.md").read_text(encoding="utf-8")
    doctor_command = (REPO_ROOT / "commands" / "doctor.md").read_text(encoding="utf-8")

    assert "disable-model-invocation: true" in setup_command
    assert "allowed-tools:" in setup_command
    assert "!`${CLAUDE_PLUGIN_ROOT}/scripts/tforge-setup`" in setup_command

    assert "disable-model-invocation: true" in doctor_command
    assert "allowed-tools:" in doctor_command
    assert "!`${CLAUDE_PLUGIN_ROOT}/scripts/tforge-doctor`" in doctor_command


def test_runtime_scripts_are_executable_and_plugin_aware() -> None:
    script_paths = [
        REPO_ROOT / "scripts" / "tforge-setup",
        REPO_ROOT / "scripts" / "tforge-doctor",
        REPO_ROOT / "scripts" / "tforge-mcp-start",
    ]

    for script_path in script_paths:
        assert script_path.is_file()
        assert os.access(script_path, os.X_OK)

    combined = "\n".join(
        script_path.read_text(encoding="utf-8") for script_path in script_paths
    )
    assert "CLAUDE_PLUGIN_ROOT" in combined
    assert "CLAUDE_PLUGIN_DATA" in combined
    assert "CLAUDE_PLUGIN_OPTION_fal_key" in combined


def test_mcp_start_prefers_plugin_fal_key_and_windows_venv_python(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin-root"
    plugin_data = tmp_path / "plugin-data"
    output = tmp_path / "fal-key.txt"
    agents_dir = plugin_root / "agents"
    windows_scripts = plugin_data / "venv" / "Scripts"
    agents_dir.mkdir(parents=True)
    windows_scripts.mkdir(parents=True)
    (agents_dir / "mcp_server.py").write_text("print('unused')\n", encoding="utf-8")

    fake_python = windows_scripts / "python.exe"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s' \"$FAL_KEY\" > \"$TFORGE_TEST_OUTPUT\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(plugin_root),
        "CLAUDE_PLUGIN_DATA": str(plugin_data),
        "CLAUDE_PLUGIN_OPTION_fal_key": "plugin-config-key",
        "FAL_KEY": "shell-key",
        "TFORGE_TEST_OUTPUT": str(output),
    }

    subprocess.run(
        [str(REPO_ROOT / "scripts" / "tforge-mcp-start")],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert output.read_text(encoding="utf-8") == "plugin-config-key"


def test_doctor_reports_missing_dotnet(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin-root"
    plugin_data = tmp_path / "plugin-data"
    mod_sources = tmp_path / "mod-sources"
    venv_bin = plugin_data / "venv" / "bin"
    (plugin_root / "agents" / "pixelsmith" / "node_modules" / "@fal-ai" / "client").mkdir(
        parents=True
    )
    (plugin_root / "agents" / "pixelsmith" / "terraria_weights.safetensors").write_text(
        "weights", encoding="utf-8"
    )
    (plugin_root / "scripts").mkdir(parents=True)
    (plugin_root / ".mcp.json").write_text("${CLAUDE_PLUGIN_ROOT}\n", encoding="utf-8")
    (plugin_root / "scripts" / "tforge-mcp-start").write_text("#!/bin/sh\n", encoding="utf-8")
    (plugin_root / "scripts" / "tforge-mcp-start").chmod(0o755)
    (mod_sources / "ForgeConnector").mkdir(parents=True)
    venv_bin.mkdir(parents=True)
    fake_python = venv_bin / "python3.12"
    fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_python.chmod(0o755)

    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(plugin_root),
        "CLAUDE_PLUGIN_DATA": str(plugin_data),
        "CLAUDE_PLUGIN_OPTION_fal_key": "plugin-config-key",
        "FORGE_MOD_SOURCES_DIR": str(mod_sources),
        "PATH": "/usr/bin:/bin",
    }

    proc = subprocess.run(
        [str(REPO_ROOT / "scripts" / "tforge-doctor")],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "dotnet" in proc.stdout


def test_plugin_data_paths_are_forwarded_to_pixelsmith_runtime() -> None:
    setup_script = (REPO_ROOT / "scripts" / "tforge-setup").read_text(encoding="utf-8")
    start_script = (REPO_ROOT / "scripts" / "tforge-mcp-start").read_text(encoding="utf-8")
    doctor_script = (REPO_ROOT / "scripts" / "tforge-doctor").read_text(encoding="utf-8")
    lib_script = (REPO_ROOT / "scripts" / "tforge-lib.sh").read_text(encoding="utf-8")
    pixelsmith = (REPO_ROOT / "agents" / "pixelsmith" / "pixelsmith.py").read_text(
        encoding="utf-8"
    )
    runner = (REPO_ROOT / "agents" / "pixelsmith" / "fal_flux2_runner.mjs").read_text(
        encoding="utf-8"
    )

    for env_name in (
        "TFORGE_NODE_DEPS_DIR",
        "TFORGE_PIXELSMITH_WEIGHTS_PATH",
        "TFORGE_LORA_CACHE_FILE",
    ):
        assert env_name in setup_script + lib_script
        assert env_name in start_script + lib_script
        assert env_name in doctor_script + lib_script

    assert "set_runtime_paths" in setup_script
    assert "set_runtime_paths" in start_script
    assert "set_runtime_paths" in doctor_script
    assert "TFORGE_PIXELSMITH_WEIGHTS_PATH" in pixelsmith
    assert "TFORGE_NODE_DEPS_DIR" in runner
    assert "TFORGE_LORA_CACHE_FILE" in runner

