package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"theforge/internal/ipc"
)

func feedMessages(m model) []string {
	msgs := make([]string, 0, len(m.sessionShell.events))
	for _, event := range m.sessionShell.events {
		msgs = append(msgs, event.Message)
	}
	return msgs
}

func TestSessionFeed(t *testing.T) {
	t.Run("ForgeProgressEmitsAndUpdatesFeedEntry", TestForgeProgressEmitsAndUpdatesFeedEntry)
	t.Run("WorkshopActionsAddFeedEntry", TestWorkshopActionsAddFeedEntry)
	t.Run("ConnectorResultsAddFeedEntry", TestConnectorResultsAddFeedEntry)
	t.Run("ShellViewShowsFeed", TestShellViewShowsFeed)
	t.Run("SecondForgeRunAppendsNewProgressRow", TestSecondForgeRunAppendsNewProgressRow)
}

func TestForgeProgressEmitsAndUpdatesFeedEntry(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("FORGE_MOD_SOURCES_DIR", dir)

	m := initialModel()
	m.state = screenForge

	if err := os.WriteFile(filepath.Join(dir, "generation_status.json"), []byte(`{"status":"building","stage_pct":12,"stage_label":"Tempering"}`), 0o644); err != nil {
		t.Fatalf("write initial generation status: %v", err)
	}

	updated, _ := m.updateForge(ipc.PollStatusMsg{})
	m = updated.(model)

	if got := len(m.sessionShell.events); got != 1 {
		t.Fatalf("feed entries after first progress update = %d, want 1", got)
	}

	if got := m.sessionShell.events[0].Message; !strings.Contains(got, "12") {
		t.Fatalf("first forge progress message = %q, want it to mention 12", got)
	}

	if err := os.WriteFile(filepath.Join(dir, "generation_status.json"), []byte(`{"status":"building","stage_pct":47,"stage_label":"Binding"}`), 0o644); err != nil {
		t.Fatalf("write updated generation status: %v", err)
	}

	updated, _ = m.updateForge(ipc.PollStatusMsg{})
	m = updated.(model)

	if got := len(m.sessionShell.events); got != 1 {
		t.Fatalf("feed entries after progress refresh = %d, want 1 updated entry", got)
	}
	if got := m.sessionShell.events[0].Message; !strings.Contains(got, "47") {
		t.Fatalf("refreshed forge progress message = %q, want it to mention 47", got)
	}
}

func TestWorkshopActionsAddFeedEntry(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("FORGE_MOD_SOURCES_DIR", dir)

	m := initialModel()
	m.state = screenStaging
	m.previewItem = &craftedItem{label: "Storm Brand"}
	m.forgeManifest = map[string]interface{}{"stats": map[string]interface{}{"damage": 24.0}}
	m.forgeItemName = "Storm Brand"

	before := len(m.sessionShell.events)
	updated, _ := m.updateStaging(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'a'}})
	m = updated.(model)

	if got := len(m.sessionShell.events); got <= before {
		t.Fatalf("feed entries after workshop action = %d, want more than %d", got, before)
	}
}

func TestConnectorResultsAddFeedEntry(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())

	m := initialModel()
	m.state = screenStaging
	m.injecting = true

	before := len(m.sessionShell.events)
	updated, _ := m.updateStaging(connectorStatusMsg{status: "item_injected", detail: "Storm Brand delivered"})
	m = updated.(model)

	if got := len(m.sessionShell.events); got <= before {
		t.Fatalf("feed entries after connector result = %d, want more than %d", got, before)
	}
	if got := feedMessages(m); len(got) == 0 || !strings.Contains(got[len(got)-1], "Storm Brand delivered") {
		t.Fatalf("latest connector feed message = %#v, want it to include connector detail", got)
	}
}

func TestShellViewShowsFeed(t *testing.T) {
	m := initialModel()
	m.sessionShell.events = []sessionEvent{
		{Kind: sessionEventKindSystem, Message: "Forge progress 47%"},
	}

	got := m.View()
	if !strings.Contains(got, "Forge progress 47%") {
		t.Fatalf("session shell view = %q, want it to contain feed entry text", got)
	}
}

func TestSecondForgeRunAppendsNewProgressRow(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("FORGE_MOD_SOURCES_DIR", dir)

	m := initialModel()
	m.prompt = "First run"
	m.state = screenForge

	if err := os.WriteFile(filepath.Join(dir, "generation_status.json"), []byte(`{"status":"building","stage_pct":12,"stage_label":"Tempering"}`), 0o644); err != nil {
		t.Fatalf("write first generation status: %v", err)
	}
	updated, _ := m.updateForge(ipc.PollStatusMsg{})
	m = updated.(model)

	m.prompt = "Second run"
	updated, _ = m.enterForge()
	m = updated.(model)

	if err := os.WriteFile(filepath.Join(dir, "generation_status.json"), []byte(`{"status":"building","stage_pct":47,"stage_label":"Binding"}`), 0o644); err != nil {
		t.Fatalf("write second generation status: %v", err)
	}
	updated, _ = m.updateForge(ipc.PollStatusMsg{})
	m = updated.(model)

	if got := len(m.sessionShell.events); got != 2 {
		t.Fatalf("feed entries after second forge run = %d, want 2", got)
	}
	if got := m.sessionShell.events[0].Message; !strings.Contains(got, "12") {
		t.Fatalf("first forge run message = %q, want it to stay on the first run", got)
	}
	if got := m.sessionShell.events[1].Message; !strings.Contains(got, "47") {
		t.Fatalf("second forge run message = %q, want it to be a new progress row", got)
	}
}
