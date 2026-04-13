package main

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
)

func (m model) updateWizard(msg tea.Msg) (tea.Model, tea.Cmd) {
	if key, ok := msg.(tea.KeyMsg); ok {
		switch key.Type {
		case tea.KeyEsc:
			if m.wizardIndex == 0 {
				m.state = screenMode
				return m, nil
			}
			m.wizardIndex--
			switch m.wizardIndex {
			case 0:
				m.subType = ""
			case 1:
				m.tier = ""
			}
			m.configureWizardStep()
			return m, nil
		case tea.KeyEnter:
			selected, _ := m.wizardList.SelectedItem().(optionItem)
			switch m.wizardIndex {
			case 0:
				m.subType = selected.title
			case 1:
				m.tier = selected.title
			}
			m.wizardIndex++
			if m.wizardIndex >= 2 {
				m.state = screenInput
				m.commandInput.Focus()
				return m, nil
			}
			m.configureWizardStep()
			return m, nil
		}
	}

	var cmd tea.Cmd
	m.wizardList, cmd = m.wizardList.Update(msg)
	return m, cmd
}

func (m model) wizardView() string {
	step := fmt.Sprintf("Step %d of %d", m.wizardIndex+2, 3)
	glyph := wizardGlyphs[m.wizardIndex%len(wizardGlyphs)]
	lines := []string{
		styles.TitleRune.Render(glyph + "  Forge Path"),
		styles.Progress.Render(step),
		styles.Meta.Render(m.contentType),
	}
	lines = append(lines, "", m.wizardList.View(), styles.Hint.Render("↑/↓ navigate  •  Enter select  •  Esc back"))
	return strings.Join(lines, "\n")
}

func (m *model) configureWizardStep() {
	step := m.currentWizardStep()
	items := make([]list.Item, 0, len(step.options))
	for _, option := range step.options {
		items = append(items, option)
	}
	m.wizardList.SetItems(items)
	m.wizardList.Select(0)
	m.wizardList.SetHeight(max(12, len(step.options)*2+2))
	m.wizardList.Title = step.question
}

func (m model) currentWizardStep() wizardStep {
	switch m.wizardIndex {
	case 0:
		return wizardStep{
			question: fmt.Sprintf("Choose %s Type", m.contentType),
			options:  subTypeOptions[m.contentType],
		}
	default:
		return wizardStep{
			question: "Choose Tier",
			options:  tierOptions,
		}
	}
}
