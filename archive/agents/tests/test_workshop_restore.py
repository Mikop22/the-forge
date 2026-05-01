import pytest

import orchestrator
from contracts.workshop import WorkshopRequest
from core.workshop_session import WorkshopSessionStore


def test_restore_targets_round_trip(tmp_path) -> None:
    store = WorkshopSessionStore(tmp_path)
    store.save(
        {
            "session_id": "sess-1",
            "bench": {"item_id": "current"},
            "baseline": {"item_id": "baseline"},
            "last_live": {"item_id": "live"},
        }
    )

    loaded = store.load("sess-1")
    assert loaded["baseline"]["item_id"] == "baseline"
    assert loaded["last_live"]["item_id"] == "live"


def test_restore_requires_existing_session(tmp_path) -> None:
    store = WorkshopSessionStore(tmp_path)
    bench = {"item_id": "storm-brand", "label": "Storm Brand"}

    with pytest.raises(RuntimeError, match="No existing workshop session"):
        orchestrator._handle_workshop_request(
            WorkshopRequest.model_validate(
                {
                    "action": "restore",
                    "session_id": "sess-missing",
                    "restore_target": "baseline",
                    "bench": bench,
                }
            ),
            store=store,
        )
