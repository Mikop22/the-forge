from contracts.workshop import RuntimeSummary, WorkshopRequest, WorkshopStatus


def test_workshop_request_supports_variants_action() -> None:
    req = WorkshopRequest.model_validate(
        {
            "action": "variants",
            "session_id": "sess-1",
            "snapshot_id": 11,
            "bench_item_id": "storm-brand",
            "directive": "make the projectile feel heavier",
        }
    )

    assert req.action == "variants"
    assert req.snapshot_id == 11
    assert req.directive == "make the projectile feel heavier"


def test_workshop_status_carries_bench_and_shelf() -> None:
    status = WorkshopStatus.model_validate(
        {
            "session_id": "sess-1",
            "bench": {"item_id": "storm-brand", "label": "Storm Brand"},
            "shelf": [{"variant_id": "v1", "label": "Heavier Shot"}],
        }
    )

    assert status.bench.item_id == "storm-brand"
    assert status.shelf[0].variant_id == "v1"


def test_runtime_summary_exposes_live_banner_fields() -> None:
    summary = RuntimeSummary.model_validate(
        {
            "bridge_alive": True,
            "world_loaded": True,
            "live_item_name": "Storm Brand",
            "last_inject_status": "item_injected",
            "last_runtime_note": "Ready on bench",
        }
    )

    assert summary.bridge_alive is True
    assert summary.live_item_name == "Storm Brand"
