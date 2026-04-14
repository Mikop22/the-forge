package main

import (
	"encoding/json"
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
		if !isVisibleSessionEventKind(event.Kind) {
			continue
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
	feed := s.renderFeedContainer(m, content)
	command := s.renderCommandBar(m)
	parts := make([]string, 0, 3)
	if strings.TrimSpace(top) != "" {
		parts = append(parts, top)
	}
	if strings.TrimSpace(feed) != "" {
		parts = append(parts, feed)
	}
	parts = append(parts, command)
	return strings.Join(parts, "\n")
}

func (s sessionShellState) renderTopStrip(m model) string {
	return ""
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

func (s sessionShellState) renderFeedContainer(m model, content string) string {
	feed := s.renderEventRows(m)
	body := []string{feed}
	if m.shellError != "" {
		body = append(body, styles.Error.Render(m.shellError))
	} else if m.shellNotice != "" {
		body = append(body, styles.Hint.Render(m.shellNotice))
	}
	if operation := renderOperationLine(m); operation != "" {
		body = append(body, operation)
	}
	if pinned := s.renderPinnedMemoryBlock(); pinned != "" {
		body = append(body, pinned)
	}
	if trimmed := strings.TrimSpace(content); trimmed != "" {
		body = append(body, trimmed)
	}
	return strings.Join(body, "\n")
}

func renderOperationLine(m model) string {
	label := strings.TrimSpace(m.operationLabel)
	switch m.operationKind {
	case operationForging:
		if label == "" {
			label = "item"
		}
		if m.operationStale {
			return styles.Hint.Render("Still waiting for the forge...")
		}
		return styles.Injecting.Render("⟳ Forging " + label)
	case operationDirector:
		if label == "" {
			label = "director"
		}
		return styles.Injecting.Render("⟳ Waiting on " + label)
	case operationInjecting:
		if label == "" {
			label = "item"
		}
		return styles.Injecting.Render("⟳ Injecting " + label + " into Terraria")
	default:
		return ""
	}
}

func (s sessionShellState) renderPinnedMemoryBlock() string {
	if len(s.pinnedNotes) == 0 {
		return ""
	}

	lines := []string{styles.Hint.Render("Pinned memory")}
	for _, note := range s.pinnedNotes {
		lines = append(lines, styles.Body.Render("• "+note))
	}
	return strings.Join(lines, "\n")
}

func (s sessionShellState) renderCommandBar(m model) string {
	command := strings.TrimSpace(m.commandInput.Value())
	return strings.Join([]string{
		styles.Hint.Render(strings.Repeat("─", shellContentWidth(m))),
		styles.Meta.Render(">") + " " + styles.PromptInput.Render(command),
	}, "\n")
}

func shellContentWidth(m model) int {
	if m.contentWidth > 0 {
		return m.contentWidth
	}
	if m.width > 0 {
		return clampInt(m.width-4, 32, 120)
	}
	return 120
}
