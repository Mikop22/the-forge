package main

import (
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

func (m model) updateInput(msg tea.Msg) (tea.Model, tea.Cmd) {
	if key, ok := msg.(tea.KeyMsg); ok {
		// When autocomplete is active, intercept navigation keys first.
		if entries := filterAutocomplete(m.commandInput.Value()); entries != nil {
			switch key.Type {
			case tea.KeyDown:
				m.autocompleteIndex++
				if m.autocompleteIndex >= len(entries) {
					m.autocompleteIndex = len(entries) - 1
				}
				return m, nil
			case tea.KeyUp:
				m.autocompleteIndex--
				if m.autocompleteIndex < 0 {
					m.autocompleteIndex = 0
				}
				return m, nil
			case tea.KeyTab:
				if m.autocompleteIndex < len(entries) {
					m.commandInput.SetValue(entries[m.autocompleteIndex].Slash + " ")
					m.commandInput.CursorEnd()
					m.autocompleteIndex = 0
				}
				return m, nil
			case tea.KeyEnter:
				if m.autocompleteIndex < len(entries) {
					selected := entries[m.autocompleteIndex]
					if selected.ArgHint == "" {
						// No argument needed — execute immediately.
						m.commandInput.SetValue("")
						m.autocompleteIndex = 0
						return m.handleShellCommand(selected.Slash)
					}
					// Argument required — complete into input so user can add it.
					m.commandInput.SetValue(selected.Slash + " ")
					m.commandInput.CursorEnd()
					m.autocompleteIndex = 0
				}
				return m, nil
			case tea.KeyEsc:
				m.commandInput.SetValue("")
				m.autocompleteIndex = 0
				return m, nil
			}
		}

		switch key.Type {
		case tea.KeyEsc:
			m.state = screenMode
			return m, nil
		case tea.KeyEnter:
			prompt := strings.TrimSpace(m.commandInput.Value())
			if prompt == "" {
				prompt = strings.TrimSpace(m.textInput.Value())
			}
			m.autocompleteIndex = 0
			return m.handleShellCommand(prompt)
		}
	}

	var cmd tea.Cmd
	m.commandInput, cmd = m.commandInput.Update(msg)
	if filterAutocomplete(m.commandInput.Value()) == nil {
		m.autocompleteIndex = 0
	}
	return m, cmd
}

func (m model) inputView() string {
	selection := buildMetaLine(craftedItem{
		contentType: m.contentType,
		subType:     m.subType,
		tier:        m.tier,
	})
	lines := []string{}
	if selection != "" {
		lines = append(lines, styles.Meta.Render(selection))
	}
	if m.errMsg != "" {
		lines = append(lines, styles.Error.Render(m.errMsg))
	}
	return strings.Join(lines, "\n")
}
