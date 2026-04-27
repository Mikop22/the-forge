package main

import (
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

func (m model) updateMode(msg tea.Msg) (tea.Model, tea.Cmd) {
	if key, ok := msg.(tea.KeyMsg); ok {
		switch key.Type {
		case tea.KeyEsc:
			m.contentType = ""
			m.contentTypeExplicit = false
			m.state = screenInput
			m.commandInput.Focus()
			return m, nil
		case tea.KeyEnter:
			selected, _ := m.modeList.SelectedItem().(optionItem)
			m.contentType = selected.title
			m.contentTypeExplicit = true
			m.subType = ""
			m.tier = ""
			m.wizardIndex = 0
			m.configureWizardStep()
			m.state = screenWizard
			return m, nil
		}
	}

	var cmd tea.Cmd
	m.modeList, cmd = m.modeList.Update(msg)
	return m, cmd
}

func (m model) modeView() string {
	return strings.Join([]string{
		styles.TitleRune.Render("What do you want to forge?"),
		styles.Subtitle.Render("Choose a content family"),
		"",
		m.modeList.View(),
		styles.Hint.Render("↑/↓ navigate  •  Enter select  •  Esc back"),
	}, "\n")
}
