package main

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"theforge/internal/ipc"
)

func initialModel() model {
	ti := textinput.New()
	ti.Placeholder = "Describe your forged item..."
	ti.CharLimit = 120
	ti.Width = 54
	ti.Prompt = ""

	pi := textinput.New()
	pi.Placeholder = "What should change?"
	pi.CharLimit = 120
	pi.Width = 42
	pi.Prompt = ""

	ci := textinput.New()
	ci.Placeholder = "Describe your forged item..."
	ci.CharLimit = 160
	ci.Width = 56
	ci.Prompt = ""
	ci.Focus()

	s := spinner.New(spinner.WithSpinner(spinner.MiniDot), spinner.WithStyle(lipgloss.NewStyle().Foreground(colorRune)))

	delegate := list.NewDefaultDelegate()
	modeItems := make([]list.Item, 0, len(contentTypeOptions))
	for _, option := range contentTypeOptions {
		modeItems = append(modeItems, option)
	}
	modeList := list.New(modeItems, delegate, 56, 8)
	modeList.SetFilteringEnabled(false)
	modeList.SetShowHelp(false)
	modeList.SetShowStatusBar(false)
	modeList.SetShowPagination(false)
	modeList.DisableQuitKeybindings()
	modeList.Title = "What do you want to forge?"

	wizardList := list.New([]list.Item{}, delegate, 56, 8)
	wizardList.SetFilteringEnabled(false)
	wizardList.SetShowHelp(false)
	wizardList.SetShowStatusBar(false)
	wizardList.SetShowPagination(false)
	wizardList.DisableQuitKeybindings()
	wizardList.SetHeight(12)

	workshop := loadWorkshopState()
	bridgeAlive := ipc.ReadBridgeHeartbeat()
	workshop.Runtime.BridgeAlive = bridgeAlive
	contentWidth := 120

	return model{
		state:        screenInput,
		contentWidth: contentWidth,
		textInput:    ti,
		previewInput: pi,
		commandInput: ci,
		modeList:     modeList,
		wizardList:   wizardList,
		spinner:      s,
		sessionShell: loadSessionShellState(),
		workshop:     workshop,
		bridgeAlive:  bridgeAlive,
	}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(
		textinput.Blink,
		animTickCmd(),
		runtimeSummaryNowCmd(),
		tea.SetWindowTitle("The Forge"),
	)
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		if msg.Type == tea.KeyCtrlC {
			return m, tea.Quit
		}
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.termCompact = msg.Width < compactWidthThreshold || msg.Height < compactHeightThreshold
		m.contentWidth = clampInt(msg.Width-4, 32, 120)
		panelWidth := clampInt(msg.Width-4, 32, 88)
		listWidth := max(1, panelWidth-8)
		m.modeList.SetWidth(listWidth)
		m.wizardList.SetWidth(listWidth)
		m.commandInput.Width = max(1, m.contentWidth-2)
		m.textInput.Width = max(1, m.contentWidth-2)
		m.previewInput.Width = max(1, min(42, m.contentWidth-2))
	case animTickMsg:
		m.animTick++
		return m, animTickCmd()
	case runtimeSummaryMsg:
		m.applyRuntimeSummaryBanner(msg.banner)
		return m, runtimeSummaryCmd()
	}

	switch m.state {
	case screenInput:
		return m.updateInput(msg)
	case screenMode:
		return m.updateMode(msg)
	case screenWizard:
		return m.updateWizard(msg)
	case screenForge:
		return m.updateForge(msg)
	case screenStaging:
		return m.updateStaging(msg)
	default:
		return m, nil
	}
}

func clampInt(value, minimum, maximum int) int {
	if value < minimum {
		return minimum
	}
	if value > maximum {
		return maximum
	}
	return value
}
func (m model) View() string {
	content := m.screenView()
	panel := m.sessionShell.render(m, content)

	if m.width <= 0 || m.height <= 0 {
		return panel
	}

	return lipgloss.Place(
		m.width,
		m.height,
		lipgloss.Left,
		lipgloss.Bottom,
		panel,
		lipgloss.WithWhitespaceBackground(colorBg),
	)
}

func (m model) screenView() string {
	switch m.state {
	case screenInput:
		return m.inputView()
	case screenMode:
		return m.modeView()
	case screenWizard:
		return m.wizardView()
	case screenForge:
		return m.forgeView()
	case screenStaging:
		return m.stagingView()
	default:
		return ""
	}
}
func animTickCmd() tea.Cmd {
	return tea.Tick(200*time.Millisecond, func(t time.Time) tea.Msg {
		return animTickMsg(t)
	})
}
func buildMetaLine(item craftedItem) string {
	parts := []string{}
	if item.contentType != "" {
		parts = append(parts, item.contentType)
	}
	if item.subType != "" {
		parts = append(parts, item.subType)
	}
	if item.tier != "" {
		parts = append(parts, item.tier)
	}
	if len(parts) == 0 {
		return ""
	}
	return strings.Join(parts, " · ")
}
func (m model) renderShell(content string) string {
	ember := styles.Ember.Render(m.emberStrip())
	frame := styles.FrameCalm
	switch m.state {
	case screenWizard, screenMode:
		frame = styles.FrameCharged
	case screenForge, screenStaging:
		frame = styles.FrameCracked
	}

	panelBody := frame.Render(content)
	if m.termCompact {
		return strings.Join([]string{ember, panelBody}, "\n")
	}

	sigil := styles.SigilColumn.Render(m.sigilColumn())
	return strings.Join([]string{ember, lipgloss.JoinHorizontal(lipgloss.Top, panelBody, "  ", sigil)}, "\n")
}

func (m model) emberStrip() string {
	patterns := []string{
		"·  *   ·   +   ·  *",
		"*   ·   +   ·  *   ·",
		"+   ·  *   ·   +   ·",
	}
	return patterns[m.animTick%len(patterns)]
}

func (m model) sigilColumn() string {
	slots := []string{"Type", "Sub", "Tier", "Prompt", "Forge"}
	values := []string{
		m.contentType,
		m.subType,
		m.tier,
		truncateLabel(strings.TrimSpace(m.prompt), 10),
		m.craftingStation,
	}
	lines := []string{styles.Meta.Render("Sigils")}
	for i := range slots {
		mark := "○"
		label := slots[i]
		if values[i] != "" {
			mark = "◉"
			label = values[i]
		}
		lines = append(lines, styles.Body.Render(fmt.Sprintf("%s %s", mark, label)))
	}
	return strings.Join(lines, "\n")
}

func truncateLabel(value string, maxLen int) string {
	if maxLen <= 0 || len(value) <= maxLen {
		return value
	}
	if maxLen <= 3 {
		return value[:maxLen]
	}
	return value[:maxLen-3] + "..."
}
func main() {
	ipc.EnsureOrchestrator()
	ipc.WarnPathMismatches()
	p := tea.NewProgram(initialModel(), tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "error running forge ui: %v\n", err)
		os.Exit(1)
	}
}
