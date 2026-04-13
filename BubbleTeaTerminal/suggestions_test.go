package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSuggestionsShowsForgeWhenNoBenchExists(t *testing.T) {
	m := initialModel()
	m.commandInput.SetValue("")

	got := m.View()
	if !strings.Contains(got, "/forge") {
		t.Fatalf("empty shell view = %q, want forge suggestion when no active bench exists", got)
	}
}

func TestSuggestionsShowsVariantsWhenBenchExists(t *testing.T) {
	m := initialModel()
	m.workshop.Bench = workshopBench{
		ItemID: "storm-brand",
		Label:  "Storm Brand",
	}
	m.commandInput.SetValue("")

	got := m.View()
	if !strings.Contains(got, "/variants") {
		t.Fatalf("empty shell view = %q, want /variants suggestion when an active bench exists", got)
	}
}

func TestSuggestionsShowsBenchWhenShelfExists(t *testing.T) {
	m := initialModel()
	m.workshop.Bench = workshopBench{
		ItemID: "storm-brand",
		Label:  "Storm Brand",
	}
	m.workshop.Shelf = []workshopVariant{
		{VariantID: "storm-brand-v1", Label: "Heavier Shot"},
	}
	m.commandInput.SetValue("")

	got := m.View()
	if !strings.Contains(got, "/bench") {
		t.Fatalf("empty shell view = %q, want /bench suggestion when shelf variants are available", got)
	}
}

func TestSuggestionsHydratesPinnedMemoryFromSessionShellStatus(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	status := `{
  "session_id": "sess-1",
  "snapshot_id": 9,
  "recent_events": [],
  "pinned_notes": ["keep the cashout", "trail too noisy"]
}`
	if err := os.WriteFile(filepath.Join(modSources, "session_shell_status.json"), []byte(status), 0644); err != nil {
		t.Fatalf("write session_shell_status.json: %v", err)
	}

	m := initialModel()
	m.commandInput.SetValue("")

	got := m.View()
	if !strings.Contains(got, "Pinned memory") || !strings.Contains(got, "keep the cashout") {
		t.Fatalf("shell view = %q, want pinned memory notes rendered from persisted session shell status", got)
	}
}

func TestSuggestionsOmitsPinnedMemoryWhenAbsent(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	status := `{
  "session_id": "sess-1",
  "snapshot_id": 9,
  "recent_events": [],
  "pinned_notes": []
}`
	if err := os.WriteFile(filepath.Join(modSources, "session_shell_status.json"), []byte(status), 0644); err != nil {
		t.Fatalf("write session_shell_status.json: %v", err)
	}

	m := initialModel()
	m.commandInput.SetValue("")

	got := m.View()
	if strings.Contains(got, "Pinned memory") {
		t.Fatalf("shell view = %q, want pinned memory block omitted when no notes are present", got)
	}
}

func TestSuggestionsRefreshesPinnedMemoryAfterStatusChange(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	statusPath := filepath.Join(modSources, "session_shell_status.json")
	initial := `{
  "session_id": "sess-1",
  "snapshot_id": 9,
  "recent_events": [],
  "pinned_notes": []
}`
	if err := os.WriteFile(statusPath, []byte(initial), 0644); err != nil {
		t.Fatalf("write initial session_shell_status.json: %v", err)
	}

	m := initialModel()
	m.commandInput.SetValue("")

	initialView := m.View()
	if strings.Contains(initialView, "Pinned memory") {
		t.Fatalf("initial shell view = %q, want no pinned memory block", initialView)
	}

	updated := `{
  "session_id": "sess-1",
  "snapshot_id": 10,
  "recent_events": [],
  "pinned_notes": ["keep the cashout"]
}`
	if err := os.WriteFile(statusPath, []byte(updated), 0644); err != nil {
		t.Fatalf("write updated session_shell_status.json: %v", err)
	}

	nextView := m.View()
	if !strings.Contains(nextView, "Pinned memory") || !strings.Contains(nextView, "keep the cashout") {
		t.Fatalf("updated shell view = %q, want refreshed pinned memory notes from disk", nextView)
	}
}
