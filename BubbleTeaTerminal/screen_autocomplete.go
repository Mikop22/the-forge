package main

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
)

type autocompleteEntry struct {
	Slash         string
	ArgHint       string
	Desc          string
	RequiresBench bool
}

var autocompleteRegistry = []autocompleteEntry{
	{"/forge", "<prompt>", "Generate a new item from scratch", false},
	{"/history", "", "Show generated items you can return to", false},
	{"/view", "<number-or-name>", "Preview a generated item from history", false},
	{"/bench", "<id or number>", "Set a shelf variant as the active bench", true},
	{"/try", "", "Reinject the current bench item into Terraria", true},
	{"/restore", "baseline | live", "Restore bench to a previous state", true},
	{"/status", "", "Show bench label and runtime state", false},
	{"/memory", "", "Show pinned memory notes", false},
	{"/what-changed", "", "Summarise changes since last bench", false},
	{"/clear", "", "Clear the active bench and shelf", false},
	{"/help", "", "List all available commands", false},
}

// renderAutocompleteDrawer renders a two-column command list below the prompt.
// Returns "" when there are no matches. The bottom-anchored panel layout
// naturally shifts content upward as lines are added here.
func renderAutocompleteDrawer(m model) string {
	entries := filterAutocomplete(m.commandInput.Value())

	// Show "no matches" hint when user has typed a /command that matches nothing.
	if len(entries) == 0 {
		if v := m.commandInput.Value(); strings.HasPrefix(v, "/") && len(v) > 1 {
			return lipgloss.NewStyle().Foreground(colorDim).Render("No matching commands")
		}
		return ""
	}

	idx := m.autocompleteIndex
	if idx < 0 {
		idx = 0
	}
	if idx >= len(entries) {
		idx = len(entries) - 1
	}

	hasBench := m.hasActiveWorkshopBench()
	const slashWidth = 26
	contentW := shellContentWidth(m)
	descWidth := max(1, contentW-slashWidth)

	unavailStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#4A4357"))
	dimStyle := lipgloss.NewStyle().Foreground(colorDim)
	selSlash := lipgloss.NewStyle().Foreground(colorRune).Bold(true)
	selDesc := lipgloss.NewStyle().Foreground(colorText)

	lines := make([]string, 0, len(entries))
	for i, e := range entries {
		name := e.Slash
		if e.ArgHint != "" {
			name += " " + e.ArgHint
		}
		unavailable := e.RequiresBench && !hasBench
		switch {
		case i == idx && !unavailable:
			lines = append(lines, selSlash.Width(slashWidth).Render(name)+selDesc.Width(descWidth).Render(e.Desc))
		case unavailable:
			lines = append(lines, unavailStyle.Width(slashWidth).Render(name)+unavailStyle.Width(descWidth).Render(e.Desc+" (no bench)"))
		default:
			lines = append(lines, dimStyle.Width(slashWidth).Render(name)+dimStyle.Width(descWidth).Render(e.Desc))
		}
	}
	return strings.Join(lines, "\n")
}

// filterAutocomplete returns matching entries for the given raw input value.
// Returns nil when input is empty or does not start with "/".
func filterAutocomplete(input string) []autocompleteEntry {
	if input == "" || !strings.HasPrefix(input, "/") {
		return nil
	}
	lower := strings.ToLower(input)
	var out []autocompleteEntry
	for _, e := range autocompleteRegistry {
		if strings.HasPrefix(e.Slash, lower) {
			out = append(out, e)
		}
	}
	return out
}
