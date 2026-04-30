package main

import (
	tea "github.com/charmbracelet/bubbletea"
)

func (m model) handleMouse(msg tea.MouseMsg) (tea.Model, tea.Cmd) {
	if msg.Action != tea.MouseActionPress || msg.Button != tea.MouseButtonLeft {
		return m, nil
	}

	switch m.state {
	case screenInput:
		m.commandInput.Focus()
	case screenStaging:
		if m.previewMode == previewModeReprompt {
			m.previewInput.Focus()
			m.commandInput.Blur()
			return m, nil
		}
		if m.previewMode == previewModeActions {
			m.commandMode = false
			m.commandInput.Focus()
			m.workshopNotice = ""
		}
	case screenForge:
		if m.forgeErr != "" {
			m.commandInput.Focus()
		}
	}
	return m, nil
}
