package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"theforge/internal/modsources"
)

type sessionShellState struct {
	events      []sessionEvent
	scopes      map[sessionEventKind]int
	pinnedNotes []string
}

type sessionShellStatusEvent struct {
	Kind        string `json:"kind"`
	Message     string `json:"message"`
	TimestampMS *int64 `json:"timestamp_ms,omitempty"`
	Scope       int    `json:"scope,omitempty"`
}

type sessionShellStatusPayload struct {
	SessionID    string                    `json:"session_id,omitempty"`
	SnapshotID   int                       `json:"snapshot_id,omitempty"`
	RecentEvents []sessionShellStatusEvent `json:"recent_events,omitempty"`
	PinnedNotes  []string                  `json:"pinned_notes,omitempty"`
}

func newSessionShellState() sessionShellState {
	return sessionShellState{
		events:      make([]sessionEvent, 0, 16),
		scopes:      make(map[sessionEventKind]int),
		pinnedNotes: loadPinnedMemoryNotes(),
	}
}

func loadSessionShellState() sessionShellState {
	state := newSessionShellState()

	path := filepath.Join(modsources.Dir(), "session_shell_status.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return state
	}

	var payload struct {
		RecentEvents []struct {
			Kind        string `json:"kind"`
			Message     string `json:"message"`
			TimestampMS *int64 `json:"timestamp_ms"`
			Scope       *int   `json:"scope"`
		} `json:"recent_events"`
		PinnedNotes []string `json:"pinned_notes"`
	}
	if err := json.Unmarshal(data, &payload); err != nil {
		return state
	}

	state.events = make([]sessionEvent, 0, min(maxSessionFeedEvents, len(payload.RecentEvents)))
	for _, entry := range payload.RecentEvents {
		message := strings.TrimSpace(entry.Message)
		if message == "" {
			continue
		}

		event := sessionEvent{
			Kind:    normalizeSessionEventKind(entry.Kind),
			Message: message,
		}
		if entry.TimestampMS != nil {
			event.CreatedAt = time.UnixMilli(*entry.TimestampMS).UTC()
		}
		if entry.Scope != nil {
			event.Scope = *entry.Scope
		}
		state.events = append(state.events, event)
	}
	if len(state.events) > maxSessionFeedEvents {
		state.events = append([]sessionEvent(nil), state.events[len(state.events)-maxSessionFeedEvents:]...)
	}

	state.pinnedNotes = normalizePinnedNotes(payload.PinnedNotes)
	return state
}

func (m *model) persistSessionShellState() {
	path := filepath.Join(modsources.Dir(), "session_shell_status.json")
	payload := sessionShellStatusPayload{}

	if data, err := os.ReadFile(path); err == nil {
		_ = json.Unmarshal(data, &payload)
	}

	if payload.SessionID == "" {
		payload.SessionID = strings.TrimSpace(m.workshop.SessionID)
	}
	if payload.SnapshotID <= 0 {
		payload.SnapshotID = m.workshop.SnapshotID
	}

	if len(m.sessionShell.pinnedNotes) > 0 {
		payload.PinnedNotes = normalizePinnedNotes(m.sessionShell.pinnedNotes)
	} else if len(payload.PinnedNotes) > 0 {
		payload.PinnedNotes = normalizePinnedNotes(payload.PinnedNotes)
	}

	payload.RecentEvents = make([]sessionShellStatusEvent, 0, len(m.sessionShell.events))
	for _, event := range m.sessionShell.events {
		entry := sessionShellStatusEvent{
			Kind:    string(event.Kind),
			Message: event.Message,
			Scope:   event.Scope,
		}
		if !event.CreatedAt.IsZero() {
			timestampMS := event.CreatedAt.UTC().UnixMilli()
			entry.TimestampMS = &timestampMS
		}
		payload.RecentEvents = append(payload.RecentEvents, entry)
	}

	text, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return
	}
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, append(text, '\n'), 0644); err != nil {
		return
	}
	_ = os.Rename(tmp, path)
}

func normalizeSessionEventKind(kind string) sessionEventKind {
	switch strings.TrimSpace(strings.ToLower(kind)) {
	case "prompt":
		return sessionEventKindPrompt
	case "runtime":
		return sessionEventKindRuntime
	case "memory":
		return sessionEventKindMemory
	case "history":
		return sessionEventKindHistory
	case "failure", "error":
		return sessionEventKindFailure
	case "feed", "system":
		return sessionEventKindSystem
	default:
		if kind == "" {
			return sessionEventKindSystem
		}
		return sessionEventKind(kind)
	}
}

func (s sessionShellState) render(m model, content string) string {
	s.pinnedNotes = loadPinnedMemoryNotes()
	top := s.renderTopStrip(m)
	feed := s.renderFeedContainer(content)
	command := s.renderCommandBar(m)
	return strings.Join([]string{top, feed, command}, "\n")
}

func (s sessionShellState) renderTopStrip(m model) string {
	statusBits := []string{"Forge Director"}
	if m.bridgeAlive {
		statusBits = append(statusBits, "runtime online")
	} else {
		statusBits = append(statusBits, "runtime offline")
	}
	if benchLabel := activeBenchLabel(m); benchLabel != "" {
		statusBits = append(statusBits, "bench: "+benchLabel)
	}
	if shelfCount := len(m.workshop.Shelf); shelfCount > 0 {
		label := "variants"
		if shelfCount == 1 {
			label = "variant"
		}
		statusBits = append(statusBits, fmt.Sprintf("shelf: %d %s", shelfCount, label))
	}
	return strings.Join([]string{
		styles.Meta.Render("Top Strip"),
		styles.Body.Render(strings.Join(statusBits, " | ")),
	}, "\n")
}

func activeBenchLabel(m model) string {
	if label := strings.TrimSpace(m.forgeItemName); label != "" {
		return label
	}
	if label := strings.TrimSpace(m.workshop.Bench.Label); label != "" {
		return label
	}
	return strings.TrimSpace(m.workshop.Bench.ItemID)
}

func (s sessionShellState) renderFeedContainer(content string) string {
	feed := s.renderEventRows()
	body := []string{feed}
	if pinned := s.renderPinnedMemoryBlock(); pinned != "" {
		body = append(body, pinned)
	}
	if trimmed := strings.TrimSpace(content); trimmed != "" {
		body = append(body, trimmed)
	}
	return strings.Join([]string{
		styles.Meta.Render("Feed Container"),
		styles.FrameCalm.Render(strings.Join(body, "\n\n")),
	}, "\n")
}

func (s sessionShellState) renderPinnedMemoryBlock() string {
	if len(s.pinnedNotes) == 0 {
		return ""
	}

	lines := []string{styles.Meta.Render("Pinned memory")}
	for _, note := range s.pinnedNotes {
		lines = append(lines, styles.Body.Render("• "+note))
	}
	return strings.Join(lines, "\n")
}

func (s sessionShellState) renderCommandBar(m model) string {
	command := strings.TrimSpace(m.commandInput.Value())
	if command == "" {
		command = m.commandInput.Placeholder
	}
	body := []string{}
	if suggestion := m.shellSuggestion(); suggestion != "" {
		body = append(body, styles.Hint.Render(suggestion))
	}
	body = append(body, styles.PromptInput.Render(command))
	return strings.Join([]string{
		styles.Meta.Render("Persistent Command Bar"),
		strings.Join(body, "\n"),
	}, "\n")
}
