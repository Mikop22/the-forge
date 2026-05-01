package main

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

func TestAutocompleteFiltersOnPrefix(t *testing.T) {
	items := filterAutocomplete("/fo")
	if len(items) == 0 {
		t.Fatal("filterAutocomplete(\"/fo\") = empty, want at least /forge")
	}
	if items[0].Slash != "/forge" {
		t.Fatalf("first match = %q, want /forge", items[0].Slash)
	}
}

func TestAutocompleteReturnsAllOnSlashOnly(t *testing.T) {
	items := filterAutocomplete("/")
	if len(items) < 8 {
		t.Fatalf("filterAutocomplete(\"/\") = %d items, want all commands (>=8)", len(items))
	}
}

func TestAutocompleteHidesVariantsCommand(t *testing.T) {
	items := filterAutocomplete("/")
	for _, item := range items {
		if item.Slash == "/variants" {
			t.Fatal("autocomplete shows /variants, want hidden until variants UX is ready")
		}
	}
}

func TestAutocompleteReturnsNilOnNonSlash(t *testing.T) {
	items := filterAutocomplete("radiant spear")
	if items != nil {
		t.Fatalf("filterAutocomplete(non-slash) = %v, want nil", items)
	}
}

func TestAutocompleteReturnsNilOnEmptyInput(t *testing.T) {
	items := filterAutocomplete("")
	if items != nil {
		t.Fatalf("filterAutocomplete(\"\") = %v, want nil", items)
	}
}

func TestAutocompleteDrawerRendersWhenSlashTyped(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/")
	m.width = 120
	m.height = 40

	got := m.View()
	if !strings.Contains(got, "/forge") {
		t.Fatalf("view = %q, want autocomplete drawer showing /forge when '/' typed", got)
	}
	if !strings.Contains(got, "Generate a new item") {
		t.Fatalf("view = %q, want command description in autocomplete drawer", got)
	}
}

func TestAutocompleteDrawerHiddenWhenNoMatch(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/zzz")

	got := m.View()
	// Drawer should show a no-match hint, NOT a command description.
	if strings.Contains(got, "Generate a new item") {
		t.Fatalf("view = %q, want no command descriptions when no match", got)
	}
}

func TestAutocompleteDrawerHighlightsSelectedRow(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/")
	m.autocompleteIndex = 1
	m.width = 120

	got := m.View()
	if !strings.Contains(got, "/history") {
		t.Fatalf("view = %q, want /history in drawer", got)
	}
}

func TestAutocompleteDownArrowMovesSelection(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/")
	m.autocompleteIndex = 0

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyDown})
	next := updated.(model)

	if next.autocompleteIndex != 1 {
		t.Fatalf("autocompleteIndex after Down = %d, want 1", next.autocompleteIndex)
	}
}

func TestAutocompleteDownArrowMovesSelectionInStagingCommandMode(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenStaging
	m.commandMode = true
	m.commandInput.Focus()
	m.commandInput.SetValue("/")
	m.autocompleteIndex = 0

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyDown})
	next := updated.(model)

	if next.autocompleteIndex != 1 {
		t.Fatalf("autocompleteIndex after Down in staging command mode = %d, want 1", next.autocompleteIndex)
	}
}

func TestAutocompleteUpArrowMovesSelection(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/")
	m.autocompleteIndex = 2

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyUp})
	next := updated.(model)

	if next.autocompleteIndex != 1 {
		t.Fatalf("autocompleteIndex after Up = %d, want 1", next.autocompleteIndex)
	}
}

func TestAutocompleteTabCompletesCommand(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/fo")
	m.autocompleteIndex = 0

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyTab})
	next := updated.(model)

	if next.commandInput.Value() != "/forge " {
		t.Fatalf("input after Tab = %q, want \"/forge \"", next.commandInput.Value())
	}
}

// TestAutocompleteDrawerNoLineExceedsTerminalWidth verifies that every row in the
// drawer — including /bench <id or number> which previously wrapped at slashWidth=20 —
// fits within the declared terminal width.
func TestAutocompleteDrawerNoLineExceedsTerminalWidth(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	const termWidth = 80
	m := initialModel()
	m.commandInput.SetValue("/")
	m.width = termWidth
	m.contentWidth = termWidth - 4 // mirrors WindowSizeMsg handler: clampInt(Width-4, 32, 120)

	drawer := renderAutocompleteDrawer(m)
	if drawer == "" {
		t.Fatal("renderAutocompleteDrawer = empty, want full command list for '/'")
	}
	for _, line := range strings.Split(drawer, "\n") {
		w := lipgloss.Width(line)
		if w > termWidth {
			t.Errorf("line width %d > terminal %d: %q", w, termWidth, line)
		}
	}
	// Specifically check /bench row doesn't split across lines.
	if !strings.Contains(drawer, "/bench") {
		t.Fatal("drawer missing /bench entry")
	}
	benchLine := ""
	for _, line := range strings.Split(drawer, "\n") {
		if strings.Contains(line, "/bench") {
			benchLine = line
			break
		}
	}
	if benchLine == "" {
		t.Fatal("/bench not found on its own line — may have wrapped")
	}
	if !strings.Contains(benchLine, "id or number") {
		t.Errorf("/bench line = %q, want arg hint '<id or number>' on the same line", benchLine)
	}
}

// TestSplashRendersTreeIcon verifies the splash block contains Terraria-style
// tree characters and does NOT contain the old box/building shape.
func TestSplashRendersTreeIcon(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.width = 120
	m.height = 40

	splash := renderSplash(m)
	// Tree shape must be present.
	if !strings.Contains(splash, "▄█▄") {
		t.Errorf("splash = %q, want tree top '▄█▄'", splash)
	}
	// Old box icon must be gone.
	if strings.Contains(splash, "██    ██") {
		t.Errorf("splash = %q, want old box icon removed", splash)
	}
	// Must still carry title text.
	if !strings.Contains(splash, "The Forge") {
		t.Errorf("splash = %q, want 'The Forge' title", splash)
	}
}

func TestAutocompleteDrawerShowsNoMatchHint(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/zzz")
	m.width = 120

	drawer := renderAutocompleteDrawer(m)
	if !strings.Contains(drawer, "No matching commands") {
		t.Fatalf("renderAutocompleteDrawer('/zzz') = %q, want 'No matching commands' hint", drawer)
	}
}

func TestAutocompleteEscDismissesDrawer(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	next := updated.(model)

	if got := filterAutocomplete(next.commandInput.Value()); got != nil {
		t.Fatalf("autocomplete still active after Esc, input = %q", next.commandInput.Value())
	}
}

func TestAutocompleteDrawerDimsBenchCommandsWhenNoBench(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/")
	m.width = 120
	m.contentWidth = 116

	drawer := renderAutocompleteDrawer(m)
	if !strings.Contains(drawer, "/forge") {
		t.Fatalf("drawer = %q, want /forge present", drawer)
	}
	if strings.Contains(drawer, "/variants") {
		t.Fatalf("drawer = %q, want /variants hidden", drawer)
	}

	m.workshop.Bench.ItemID = "storm-brand"
	drawer2 := renderAutocompleteDrawer(m)
	if strings.Contains(drawer2, "/variants") {
		t.Fatalf("drawer2 = %q, want /variants hidden when bench active", drawer2)
	}
}
