"""Bounded transcript and memory contract for the Forge Director shell."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SessionEventKind = Literal["feed", "memory", "runtime", "system"]


class SessionEvent(BaseModel):
    """A single event in the session transcript."""

    model_config = ConfigDict(extra="ignore")

    kind: SessionEventKind
    message: str
    timestamp_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionShellState(BaseModel):
    """Persisted session shell state with a small recent-event ring buffer."""

    model_config = ConfigDict(extra="ignore")

    MAX_RECENT_EVENTS: ClassVar[int] = 8
    MAX_PINNED_NOTES: ClassVar[int] = 5

    session_id: str = ""
    snapshot_id: int = 0
    recent_events: list[SessionEvent] = Field(default_factory=list)
    pinned_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize(self) -> "SessionShellState":
        self.recent_events = self._trim_recent_events(self.recent_events)
        self.pinned_notes = self._trim_pinned_notes(self.pinned_notes)
        return self

    @classmethod
    def _trim_recent_events(
        cls, events: Iterable[SessionEvent | dict[str, Any]]
    ) -> list[SessionEvent]:
        normalized = [SessionEvent.model_validate(event) for event in events]
        return normalized[-cls.MAX_RECENT_EVENTS :]

    @classmethod
    def _trim_pinned_notes(cls, notes: Iterable[str]) -> list[str]:
        trimmed: list[str] = []
        for note in notes:
            cleaned = str(note).strip()
            if not cleaned:
                continue
            trimmed.append(cleaned)
            if len(trimmed) >= cls.MAX_PINNED_NOTES:
                break
        return trimmed


class SessionShellStatus(SessionShellState):
    """Minimal snapshot mirrored back to the TUI."""
