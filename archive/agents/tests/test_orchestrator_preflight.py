from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

import orchestrator


class _FakeChromium:
    def __init__(self, executable_path: str | Exception) -> None:
        self._executable_path = executable_path

    @property
    def executable_path(self) -> str:
        if isinstance(self._executable_path, Exception):
            raise self._executable_path
        return self._executable_path


class _FakePlaywright:
    def __init__(self, executable_path: str | Exception) -> None:
        self.chromium = _FakeChromium(executable_path)

    def __enter__(self) -> "_FakePlaywright":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _install_fake_playwright(
    monkeypatch: pytest.MonkeyPatch, executable_path: str | Exception
) -> None:
    playwright_module = types.ModuleType("playwright")
    sync_api_module = types.ModuleType("playwright.sync_api")
    sync_api_module.sync_playwright = lambda: _FakePlaywright(executable_path)
    monkeypatch.setitem(sys.modules, "playwright", playwright_module)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api_module)


def _patch_status_writer(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    payloads: list[dict] = []
    monkeypatch.setattr(orchestrator, "_write_status", payloads.append)
    return payloads


def _set_valid_preflight_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    weights_path = tmp_path / "terraria_weights.safetensors"
    weights_path.write_text("weights", encoding="utf-8")
    chromium_path = tmp_path / "chromium"
    chromium_path.write_text("browser", encoding="utf-8")
    monkeypatch.setenv("FAL_KEY", "fal-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setattr(orchestrator, "PIXELSMITH_WEIGHTS_PATH", weights_path)
    _install_fake_playwright(monkeypatch, str(chromium_path))
    return chromium_path


def _assert_preflight_failure(
    payloads: list[dict],
    capsys: pytest.CaptureFixture[str],
    expected_message: str,
) -> None:
    assert len(payloads) == 1
    assert payloads[0]["status"] == "error"
    assert payloads[0]["error_code"] == "PREFLIGHT_FAIL"
    assert expected_message in payloads[0]["message"]
    assert expected_message in capsys.readouterr().err


def test_missing_fal_key_fails_with_preflight_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_valid_preflight_inputs(monkeypatch, tmp_path)
    monkeypatch.delenv("FAL_KEY", raising=False)
    payloads = _patch_status_writer(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        orchestrator._run_preflight_checks()

    assert exc.value.code == 1
    _assert_preflight_failure(payloads, capsys, "FAL_KEY")


def test_missing_openai_api_key_fails_with_preflight_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_valid_preflight_inputs(monkeypatch, tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    payloads = _patch_status_writer(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        orchestrator._run_preflight_checks()

    assert exc.value.code == 1
    _assert_preflight_failure(payloads, capsys, "OPENAI_API_KEY")


def test_missing_pixelsmith_weights_file_fails_with_expected_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_valid_preflight_inputs(monkeypatch, tmp_path)
    missing_weights = tmp_path / "missing" / "terraria_weights.safetensors"
    monkeypatch.setattr(orchestrator, "PIXELSMITH_WEIGHTS_PATH", missing_weights)
    payloads = _patch_status_writer(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        orchestrator._run_preflight_checks()

    assert exc.value.code == 1
    _assert_preflight_failure(payloads, capsys, str(missing_weights.resolve()))


def test_all_preflight_checks_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _set_valid_preflight_inputs(monkeypatch, tmp_path)
    payloads = _patch_status_writer(monkeypatch)

    assert orchestrator._run_preflight_checks() is None
    assert payloads == []


def test_playwright_executable_path_raises_preflight_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_valid_preflight_inputs(monkeypatch, tmp_path)
    _install_fake_playwright(monkeypatch, RuntimeError("playwright missing"))
    payloads = _patch_status_writer(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        orchestrator._run_preflight_checks()

    assert exc.value.code == 1
    _assert_preflight_failure(payloads, capsys, "Playwright Chromium")
