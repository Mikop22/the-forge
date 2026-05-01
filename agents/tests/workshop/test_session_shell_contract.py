from contracts.session_shell import SessionEvent, SessionShellState


def test_session_shell_state_trims_recent_events_to_ring_buffer() -> None:
    state = SessionShellState(
        session_id="sess-1",
        snapshot_id=42,
        recent_events=[
            SessionEvent(kind="feed", message=f"event-{index}")
            for index in range(SessionShellState.MAX_RECENT_EVENTS + 2)
        ],
        pinned_notes=["keep the cashout", "trail too noisy"],
    )

    assert len(state.recent_events) == SessionShellState.MAX_RECENT_EVENTS
    assert state.recent_events[0].message == "event-2"
    assert state.recent_events[-1].message == f"event-{SessionShellState.MAX_RECENT_EVENTS + 1}"
    assert state.snapshot_id == 42
    assert state.pinned_notes == ["keep the cashout", "trail too noisy"]
