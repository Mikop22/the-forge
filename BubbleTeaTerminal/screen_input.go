package main

import (
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

func (m model) updateInput(msg tea.Msg) (tea.Model, tea.Cmd) {
	if key, ok := msg.(tea.KeyMsg); ok {
		switch key.Type {
		case tea.KeyEsc:
			m.state = screenMode
			return m, nil
		case tea.KeyEnter:
			prompt := strings.TrimSpace(m.commandInput.Value())
			if prompt == "" {
				prompt = strings.TrimSpace(m.textInput.Value())
			}
			return m.handleShellCommand(prompt)
		}
	}

	var cmd tea.Cmd
	m.commandInput, cmd = m.commandInput.Update(msg)
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
