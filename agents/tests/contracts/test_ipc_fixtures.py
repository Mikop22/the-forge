"""Golden IPC JSON fixtures shared with BubbleTeaTerminal (see internal/ipc/ipc_test.go)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.ipc import GenerationStatus, UserRequest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "fixtures" / "ipc"


def test_fixture_generation_status_ready_matches_pydantic() -> None:
    raw = json.loads((_FIXTURES / "generation_status_ready.json").read_text(encoding="utf-8"))
    m = GenerationStatus.model_validate(raw)
    assert m.status == "ready"
    assert m.batch_list == ["FixtureBlade"]
    assert m.inject_mode is True


def test_fixture_user_request_instant_matches_pydantic() -> None:
    raw = json.loads((_FIXTURES / "user_request_instant.json").read_text(encoding="utf-8"))
    m = UserRequest.model_validate(raw)
    assert m.mode == "instant"
    assert m.prompt == "Fixture prompt"


@pytest.mark.parametrize(
    "name",
    ["generation_status_ready.json", "user_request_instant.json"],
)
def test_fixtures_are_committed(name: str) -> None:
    p = _FIXTURES / name
    assert p.is_file(), f"missing fixture: {p}"
