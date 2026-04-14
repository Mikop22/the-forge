package main

import (
	"fmt"
	"strings"
	"time"
)

const maxSessionFeedEvents = 12

func isVisibleSessionEventKind(kind sessionEventKind) bool {
	switch kind {
	case sessionEventKindMemory, sessionEventKindFailure:
		return true
	default:
		return false
	}
}

func (s *sessionShellState) beginScope(kind sessionEventKind) {
	s.scopes[kind]++
}

func (s *sessionShellState) appendEvent(kind sessionEventKind, message string) {
	message = strings.TrimSpace(message)
	if message == "" {
		return
	}
	if !isVisibleSessionEventKind(kind) {
		return
	}

	s.events = append(s.events, sessionEvent{
		Kind:      kind,
		Message:   message,
		CreatedAt: time.Now().UTC(),
		Scope:     s.scopes[kind],
	})
	if len(s.events) > maxSessionFeedEvents {
		s.events = append([]sessionEvent(nil), s.events[len(s.events)-maxSessionFeedEvents:]...)
	}
}

func (s *sessionShellState) upsertEvent(kind sessionEventKind, message string) {
	message = strings.TrimSpace(message)
	if message == "" {
		return
	}
	if !isVisibleSessionEventKind(kind) {
		return
	}

	scope := s.scopes[kind]
	for i := len(s.events) - 1; i >= 0; i-- {
		if s.events[i].Kind == kind && s.events[i].Scope == scope {
			s.events[i].Message = message
			s.events[i].CreatedAt = time.Now().UTC()
			return
		}
	}

	s.events = append(s.events, sessionEvent{
		Kind:      kind,
		Message:   message,
		CreatedAt: time.Now().UTC(),
		Scope:     scope,
	})
	if len(s.events) > maxSessionFeedEvents {
		s.events = append([]sessionEvent(nil), s.events[len(s.events)-maxSessionFeedEvents:]...)
	}
}

func (m *model) appendFeedEvent(kind sessionEventKind, message string) {
	m.sessionShell.appendEvent(kind, message)
	m.persistSessionShellState()
}

func (m *model) upsertFeedEvent(kind sessionEventKind, message string) {
	m.sessionShell.upsertEvent(kind, message)
	m.persistSessionShellState()
}

func (s sessionShellState) renderEventRow(event sessionEvent) string {
	label := strings.ToUpper(string(event.Kind))
	switch event.Kind {
	case sessionEventKindPrompt:
		label = "PROMPT"
	case sessionEventKindSystem:
		label = "SYSTEM"
	case sessionEventKindRuntime:
		label = "RUNTIME"
	case sessionEventKindFailure:
		label = "ERROR"
	case sessionEventKindHistory:
		label = "HISTORY"
	case sessionEventKindMemory:
		label = "MEMORY"
	}

	return styles.Body.Render(fmt.Sprintf("%s  %s", label, event.Message))
}

func (s sessionShellState) renderEventRows(m model) string {
	if len(s.events) == 0 {
		if benchLabel := activeBenchLabel(m); benchLabel != "" {
			return strings.Join([]string{
				styles.Hint.Render("↳ Welcome back"),
				styles.Body.Render("  Bench "+styles.TitleRune.Render(benchLabel)+" ready."),
			}, "\n")
		}
		return ""
	}

	rows := make([]string, 0, len(s.events))
	for _, event := range s.events {
		rows = append(rows, s.renderEventRow(event))
	}
	return strings.Join(rows, "\n")
}
