from pathlib import Path

_CONNECTOR_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "mod"
    / "ForgeConnector"
    / "ForgeConnectorSystem.cs"
)


def test_connector_writes_runtime_summary_file() -> None:
    source = _CONNECTOR_SOURCE.read_text(encoding="utf-8")
    assert "forge_runtime_summary.json" in source
    assert "WriteRuntimeSummary(" in source
    assert "live_item_name" in source
    assert "last_runtime_note" in source
    assert "updated_at" in source
    assert "RuntimeSummaryRefreshInterval" in source


def test_connector_does_not_mark_failed_item_as_live() -> None:
    source = _CONNECTOR_SOURCE.read_text(encoding="utf-8")
    assert 'UpdateRuntimeSummaryState("inject_failed", clearLiveItemName: true, runtimeNote:' in source
    assert 'UpdateRuntimeSummaryState("inject_failed", itemName' not in source


def test_runtime_summary_reverts_to_menu_note_when_not_in_world() -> None:
    source = _CONNECTOR_SOURCE.read_text(encoding="utf-8")
    assert "string note = worldLoaded" in source
    assert ': "At main menu."' in source


def test_runtime_summary_refreshes_updated_at_even_when_signature_is_stable() -> None:
    source = _CONNECTOR_SOURCE.read_text(encoding="utf-8")
    assert "_lastRuntimeSummaryWriteAt" in source
    assert "DateTime.UtcNow" in source
