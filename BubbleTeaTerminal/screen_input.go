package main

import (
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"theforge/internal/ipc"
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
			if prompt == "" {
				m.errMsg = "Prompt cannot be empty."
				return m, nil
			}
			route := routeWorkshopCommand(prompt, m.hasActiveWorkshopBench(), m.workshop.Shelf)
			m.errMsg = ""
			switch route.Action {
			case commandActionForge:
				if strings.TrimSpace(route.Directive) == "" {
					m.errMsg = "Prompt cannot be empty."
					return m, nil
				}
				m.prompt = route.Directive
				m.appendFeedEvent(sessionEventKindPrompt, "Forge: "+route.Directive)
				return m.enterForge()
			case commandActionVariants, commandActionBench, commandActionRestore:
				if !m.hasActiveWorkshopBench() {
					m.errMsg = "No active bench."
					return m, nil
				}
				payload := buildWorkshopRequestPayloadFromRoute(route, m.workshop.SessionID, m.workshop.Bench.ItemID, m.workshop.SnapshotID)
				if err := ipc.WriteWorkshopRequest(payload); err != nil {
					m.errMsg = "Director request failed: " + err.Error()
					return m, nil
				}
				m.appendFeedEvent(sessionEventKindSystem, "Workshop action sent: "+string(route.Action))
				m.state = screenStaging
				m.commandMode = false
				return m, ipc.PollWorkshopStatusCmd(0)
			case commandActionTry:
				if !m.hasActiveWorkshopBench() {
					m.errMsg = "No active bench."
					return m, nil
				}
				return m.tryCurrentBench()
			case commandActionStatus, commandActionMemory, commandActionWhatChanged, commandActionHelp:
				response := m.shellInfoResponse(route)
				if response != "" {
					m.appendFeedEvent(sessionEventKindSystem, response)
				}
				return m, nil
			case commandActionUnsupported:
				if isEmptyForgeCommand(prompt) {
					m.errMsg = "Prompt cannot be empty."
					return m, nil
				}
				m.errMsg = "Unsupported command."
				return m, nil
			default:
				m.errMsg = "Unsupported command."
				return m, nil
			}
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
	lines := []string{
		styles.TitleRune.Render("The Forge"),
		styles.Subtitle.Render("Choose your forge path."),
	}
	if selection != "" {
		lines = append(lines, styles.Meta.Render(selection))
	}
	if m.errMsg != "" {
		lines = append(lines, styles.Error.Render(m.errMsg))
	}
	lines = append(lines, "", styles.Hint.Render("Use the command bar below  •  Esc manual mode"))
	return strings.Join(lines, "\n")
}
