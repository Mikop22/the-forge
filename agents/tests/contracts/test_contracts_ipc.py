"""Round-trip tests for ModSources IPC Pydantic models."""

from __future__ import annotations

import json

from contracts.ipc import GenerationStatus, OrchestratorHeartbeat, UserRequest


def test_user_request_minimal_compile() -> None:
    raw = {"prompt": "Ice blade", "tier": "Tier2"}
    m = UserRequest.model_validate(raw)
    assert m.prompt == "Ice blade"
    assert m.tier == "Tier2"
    assert m.mode == "compile"
    assert m.content_type == "Weapon"
    assert m.content_type_explicit is None


def test_user_request_omitted_sub_type_defaults_empty_for_inference() -> None:
    """Regression: hardcoding sub_type='Sword' here used to leak through the
    orchestrator validate+merge step and override `_request_sub_type` keyword
    inference, forcing every prompt to Sword. Default must be empty so the
    orchestrator can infer Bow/Gun/Staff/etc. from the prompt text."""
    raw = {"prompt": "Water bow", "mode": "instant"}
    m = UserRequest.model_validate(raw)
    assert m.sub_type == ""


def test_user_request_instant_ignores_unknown_keys() -> None:
    raw = {
        "prompt": "x",
        "mode": "instant",
        "future_field": 123,
    }
    m = UserRequest.model_validate(raw)
    assert m.mode == "instant"
    assert not hasattr(m, "future_field")


def test_user_request_accepts_content_type_explicit_flag() -> None:
    raw = {
        "prompt": "Obsidian pickaxe",
        "mode": "instant",
        "content_type": "Weapon",
        "content_type_explicit": False,
    }
    m = UserRequest.model_validate(raw)
    assert m.content_type == "Weapon"
    assert m.content_type_explicit is False


def test_generation_status_ready() -> None:
    raw = {
        "status": "ready",
        "stage_pct": 100,
        "batch_list": ["MyItem"],
        "message": "Ready",
        "manifest": {"item_name": "MyItem"},
        "sprite_path": "/a/b.png",
        "inject_mode": True,
    }
    m = GenerationStatus.model_validate(raw)
    assert m.status == "ready"
    assert m.inject_mode is True
    assert m.manifest is not None and m.manifest["item_name"] == "MyItem"


def test_generation_status_error() -> None:
    raw = {
        "status": "error",
        "error_code": "PIPELINE_FAIL",
        "message": "boom",
    }
    m = GenerationStatus.model_validate(raw)
    assert m.status == "error"
    assert m.error_code == "PIPELINE_FAIL"


def test_heartbeat_json_roundtrip() -> None:
    h = OrchestratorHeartbeat(
        pid=42,
        timestamp=1.5,
        mod_sources_root="/Mods",
    )
    back = OrchestratorHeartbeat.model_validate_json(json.dumps(h.model_dump()))
    assert back.pid == 42
    assert back.mod_sources_root == "/Mods"
