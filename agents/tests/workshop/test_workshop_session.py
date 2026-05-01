from contracts.session_shell import SessionEvent, SessionShellState
from core.workshop_session import WorkshopSessionStore


def test_session_store_round_trips_bench_and_shelf(tmp_path) -> None:
    store = WorkshopSessionStore(tmp_path)
    store.save(
        {
            "session_id": "sess-1",
            "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
            "shelf": [{"variant_id": "v1", "label": "Heavier Shot"}],
        }
    )

    loaded = store.load("sess-1")
    assert loaded["bench"]["item_id"] == "storm-brand"
    assert loaded["shelf"][0]["variant_id"] == "v1"


def test_session_store_save_does_not_create_active_pointer_file(tmp_path) -> None:
    store = WorkshopSessionStore(tmp_path)

    store.save({"session_id": "sess-1", "bench": {"item_id": "storm-brand"}})

    assert not (tmp_path / "active_session.txt").exists()
    assert store.active_session_id() == "sess-1"
    assert store.load_active()["bench"]["item_id"] == "storm-brand"


def test_session_store_tracks_active_session(tmp_path) -> None:
    store = WorkshopSessionStore(tmp_path)
    store.save({"session_id": "sess-1", "bench": {"item_id": "storm-brand"}})
    store.save({"session_id": "sess-2", "bench": {"item_id": "orbit-furnace"}})

    assert store.active_session_id() == "sess-2"
    assert store.load_active()["bench"]["item_id"] == "orbit-furnace"


def test_session_store_corrupt_json_load_returns_empty_dict(tmp_path) -> None:
    store = WorkshopSessionStore(tmp_path)
    bad = tmp_path / "sess-bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert store.load("sess-bad") == {}


def test_session_store_round_trips_session_shell_state(tmp_path) -> None:
    store = WorkshopSessionStore(tmp_path)
    shell = SessionShellState(
        session_id="sess-1",
        snapshot_id=7,
        recent_events=[
            SessionEvent(kind="feed", message="forged manifest"),
            SessionEvent(kind="memory", message="keep the cashout"),
        ],
        pinned_notes=["keep the cashout", "trail too noisy"],
    )

    store.save_session_shell("sess-1", shell)

    loaded_shell = store.load_session_shell("sess-1")
    assert loaded_shell is not None
    assert loaded_shell.session_id == "sess-1"
    assert loaded_shell.snapshot_id == 7
    assert [event.message for event in loaded_shell.recent_events] == [
        "forged manifest",
        "keep the cashout",
    ]
    assert loaded_shell.pinned_notes == ["keep the cashout", "trail too noisy"]


def test_session_store_recovers_stale_active_pointer_from_newest_session(tmp_path) -> None:
    store = WorkshopSessionStore(tmp_path)
    store.save({"session_id": "sess-1", "bench": {"item_id": "storm-brand"}})
    store.save({"session_id": "sess-2", "bench": {"item_id": "orbit-furnace"}})
    (tmp_path / "active_session.txt").write_text("sess-missing\n", encoding="utf-8")

    assert store.active_session_id() == "sess-2"
    assert store.load_active()["bench"]["item_id"] == "orbit-furnace"
