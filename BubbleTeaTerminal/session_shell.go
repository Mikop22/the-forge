package main

import (
	"strings"
)

type sessionShellState struct {
	events      []sessionEvent
	scopes      map[sessionEventKind]int
	pinnedNotes []string
}

func newSessionShellState() sessionShellState {
	return sessionShellState{
		events:      make([]sessionEvent, 0, 16),
		scopes:      make(map[sessionEventKind]int),
		pinnedNotes: loadPinnedMemoryNotes(),
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
	if m.forgeItemName != "" {
		statusBits = append(statusBits, "bench: "+m.forgeItemName)
	}
	return strings.Join([]string{
		styles.Meta.Render("Top Strip"),
		styles.Body.Render(strings.Join(statusBits, " | ")),
	}, "\n")
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
