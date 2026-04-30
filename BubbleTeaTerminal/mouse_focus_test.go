package main

import (
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func TestMouseClickFocusesInputCommandBar(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenInput
	m.commandInput.Blur()

	updated, _ := m.Update(tea.MouseMsg{
		Action: tea.MouseActionPress,
		Button: tea.MouseButtonLeft,
		X:      4,
		Y:      20,
	})
	next := updated.(model)

	if !next.commandInput.Focused() {
		t.Fatal("command input is not focused after mouse click")
	}
}

func TestMouseClickFocusesStagingCommandBarWithoutDirectorPanel(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenStaging
	m.commandMode = false
	m.commandInput.Blur()

	updated, _ := m.Update(tea.MouseMsg{
		Action: tea.MouseActionPress,
		Button: tea.MouseButtonLeft,
		X:      4,
		Y:      20,
	})
	next := updated.(model)

	if next.commandMode {
		t.Fatal("mouse click opened director command mode in staging")
	}
	if !next.commandInput.Focused() {
		t.Fatal("command input is not focused after mouse click in staging")
	}
}
