package main

import (
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	_ "image/png"
	"math"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"theforge/internal/ipc"
	"theforge/internal/modsources"
)

// ---------------------------------------------------------------------------

func initialModel() model {
	ti := textinput.New()
	ti.Placeholder = "Describe your forged item..."
	ti.Focus()
	ti.CharLimit = 120
	ti.Width = 54
	ti.Prompt = ""

	pi := textinput.New()
	pi.Placeholder = "What should change?"
	pi.CharLimit = 120
	pi.Width = 42
	pi.Prompt = ""

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

	return model{
		state:       screenMode,
		textInput:   ti,
		previewInput: pi,
		modeList:    modeList,
		wizardList:  wizardList,
		spinner:     s,
	}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(
		textinput.Blink,
		animTickCmd(),
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
		panelWidth := max(56, msg.Width-10)
		if panelWidth > 88 {
			panelWidth = 88
		}
		m.modeList.SetWidth(panelWidth - 8)
		m.wizardList.SetWidth(panelWidth - 8)
	case animTickMsg:
		m.animTick++
		return m, animTickCmd()
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

func (m model) updateInput(msg tea.Msg) (tea.Model, tea.Cmd) {
	if key, ok := msg.(tea.KeyMsg); ok {
		switch key.Type {
		case tea.KeyEsc:
			m.state = screenWizard
			return m, nil
		case tea.KeyEnter:
			prompt := strings.TrimSpace(m.textInput.Value())
			if prompt == "" {
				m.errMsg = "Prompt cannot be empty."
				return m, nil
			}
			m.prompt = prompt
			m.errMsg = ""
			return m.enterForge()
		}
	}

	var cmd tea.Cmd
	m.textInput, cmd = m.textInput.Update(msg)
	return m, cmd
}

func (m model) updateMode(msg tea.Msg) (tea.Model, tea.Cmd) {
	if key, ok := msg.(tea.KeyMsg); ok {
		switch key.Type {
		case tea.KeyEnter:
			selected, _ := m.modeList.SelectedItem().(optionItem)
			m.contentType = selected.title
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
				m.textInput.Focus()
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

func (m model) updateForge(msg tea.Msg) (tea.Model, tea.Cmd) {
	// Allow escaping an error state.
	if key, ok := msg.(tea.KeyMsg); ok && key.Type == tea.KeyEsc && m.forgeErr != "" {
		m.state = screenInput
		m.forgeErr = ""
		m.textInput.Focus()
		return m, nil
	}

	switch msg := msg.(type) {
	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		m.lastForgeVerb = m.animTick % len(forgeVerbs)
		// Animate heat smoothly toward the stage target.
		if m.heat < m.stageTargetPct {
			m.heat += 2
			if m.heat > m.stageTargetPct {
				m.heat = m.stageTargetPct
			}
		}
		return m, cmd
	case ipc.PollStatusMsg:
		ps := ipc.ReadGenerationStatus()
		switch ps.Status {
		case "ready":
			m.forgeItemName = ps.ItemName
			m.forgeManifest = ps.Manifest
			m.forgeSprPath = ps.SpritePath
			m.forgeProjPath = ps.ProjectileSpritePath
			m.heat = 100
			return m, func() tea.Msg { return forgeDoneMsg{} }
		case "error":
			return m, func() tea.Msg { return forgeErrMsg{message: ps.ErrMsg} }
		default:
			// "building" or file not yet written — update stage and keep polling.
			if ps.StagePct > m.stageTargetPct {
				m.stageTargetPct = ps.StagePct
			}
			if ps.StageLabel != "" {
				m.stageLabel = ps.StageLabel
			}
			return m, ipc.PollStatusCmd()
		}
	case forgeErrMsg:
		m.forgeErr = msg.message
		return m, nil
	case forgeDoneMsg:
		m.state = screenStaging
		item := m.buildCraftedItem()
		m.previewItem = &item
		m.previewMode = previewModeActions
		m.statEditIndex = 0
		m.previewInput.SetValue("")
		m.injecting = false
		m.revealPhase = 1
		checkBridgeCmd := func() tea.Msg { return bridgeStatusMsg{alive: ipc.ReadBridgeHeartbeat()} }
		return m, tea.Batch(m.spinner.Tick, checkBridgeCmd)
	}
	return m, nil
}

func (m model) updateStaging(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		if m.revealPhase < 3 {
			m.revealPhase++
			return m, m.spinner.Tick
		}
		return m, cmd
	case bridgeStatusMsg:
		m.bridgeAlive = msg.alive
		return m, nil
	case ipc.PollConnectorStatusMsg:
		const maxAttempts = 60 // 30 seconds at 500ms intervals
		if status, detail := ipc.ReadConnectorStatusPayload(); status != "" {
			return m, func() tea.Msg { return connectorStatusMsg{status: status, detail: detail} }
		}
		if msg.Attempt >= maxAttempts {
			return m, func() tea.Msg { return connectorStatusMsg{status: "timeout"} }
		}
		return m, ipc.PollConnectorStatusCmd(msg.Attempt + 1)
	case connectorStatusMsg:
		m.injecting = false
		m.injectStatus = msg.status
		m.injectDetail = msg.detail
		if msg.status == "item_injected" || msg.status == "item_pending" {
			// For instant inject, auto-clear the forge_inject.json to prevent re-inject
			_ = os.Remove(filepath.Join(modsources.Dir(), "forge_inject.json"))
		}
		return m, nil
	}

	if key, ok := msg.(tea.KeyMsg); ok {
		if m.previewMode == previewModeReprompt {
			switch key.Type {
			case tea.KeyEsc:
				m.previewMode = previewModeActions
				m.previewInput.SetValue("")
				return m, nil
			case tea.KeyEnter:
				feedback := strings.TrimSpace(m.previewInput.Value())
				if feedback == "" {
					m.injectErr = "Reprompt feedback cannot be empty."
					return m, nil
				}
				m.pendingManifest = m.forgeManifest
				m.pendingArtFeedback = feedback
				m.previewMode = previewModeActions
				m.previewInput.SetValue("")
				m.injectErr = ""
				return m.enterForge()
			}
			var cmd tea.Cmd
			m.previewInput, cmd = m.previewInput.Update(msg)
			return m, cmd
		}

		if m.previewMode == previewModeStats {
			switch key.String() {
			case "esc", "enter":
				m.previewMode = previewModeActions
				return m, nil
			case "up", "k":
				if m.statEditIndex > 0 {
					m.statEditIndex--
				}
				return m, nil
			case "down", "j":
				if m.statEditIndex < len(previewStatFields)-1 {
					m.statEditIndex++
				}
				return m, nil
			case "left", "h", "-":
				m.adjustPreviewStat(-1)
				return m, nil
			case "right", "l", "+":
				m.adjustPreviewStat(1)
				return m, nil
			}
		}

		switch key.String() {
		case "c", "C":
			m.resetForCraftAnother()
			return m, nil
		case "d", "D":
			m.previewItem = nil
			m.forgeManifest = nil
			m.forgeSprPath = ""
			m.forgeProjPath = ""
			m.injectErr = ""
			m.injectStatus = ""
			m.injectDetail = ""
			m.state = screenInput
			m.textInput.Focus()
			return m, nil
		case "r", "R":
			m.previewMode = previewModeReprompt
			m.previewInput.Focus()
			m.injectErr = ""
			return m, nil
		case "s", "S":
			m.previewMode = previewModeStats
			m.injectErr = ""
			return m, nil
		case "a", "A", "enter":
			if m.injecting {
				return m, nil // debounce
			}
			m.injecting = true
			m.injectErr = ""
			m.injectStatus = ""
			m.injectDetail = ""
			m.appendPreviewHistory()
			// Always use the instant inject path: write forge_inject.json and
			// let the ForgeConnector mod pick it up on the next game tick.
			dir := modsources.Dir()
			_ = os.Remove(filepath.Join(dir, "forge_connector_status.json"))
			if err := ipc.WriteInjectFile(m.forgeManifest, m.forgeItemName, m.forgeSprPath, m.forgeProjPath); err != nil {
				m.injecting = false
				m.injectErr = err.Error()
				return m, nil
			}
			return m, ipc.PollConnectorStatusCmd(0)
		}
	}
	return m, nil
}

func (m model) View() string {
	content := m.screenView()
	panel := m.renderShell(content)

	if m.width <= 0 || m.height <= 0 {
		return panel
	}

	return lipgloss.Place(
		m.width,
		m.height,
		lipgloss.Center,
		lipgloss.Center,
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

func (m model) inputView() string {
	selection := buildMetaLine(craftedItem{
		contentType: m.contentType,
		subType:     m.subType,
		tier:        m.tier,
	})
	lines := []string{
		styles.TitleRune.Render("The Forge"),
		styles.Subtitle.Render("Describe your item"),
	}
	if selection != "" {
		lines = append(lines, styles.Meta.Render(selection))
	}
	lines = append(lines,
		"",
		styles.PromptInput.Render(m.textInput.View()),
	)
	if m.errMsg != "" {
		lines = append(lines, styles.Error.Render(m.errMsg))
	}
	lines = append(lines, "", styles.Hint.Render("Enter forge  •  Esc back"))
	return strings.Join(lines, "\n")
}

func (m model) modeView() string {
	return strings.Join([]string{
		styles.TitleRune.Render("What do you want to forge?"),
		styles.Subtitle.Render("Choose a content family"),
		"",
		m.modeList.View(),
		styles.Hint.Render("↑/↓ navigate  •  Enter select"),
	}, "\n")
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

func (m model) forgeView() string {
	if m.forgeErr != "" {
		return strings.Join([]string{
			styles.Error.Render("✘ Forge Failed"),
			"",
			styles.Body.Render(m.forgeErr),
			"",
			styles.Hint.Render("Esc to go back"),
		}, "\n")
	}
	label := m.stageLabel
	if label == "" {
		label = forgeVerbs[m.lastForgeVerb%len(forgeVerbs)] + "..."
	}
	return strings.Join([]string{
		styles.TitleRune.Render("The Forge"),
		styles.Progress.Render("Heat " + m.heatBar()),
		"",
		fmt.Sprintf("%s %s", m.spinner.View(), styles.Subtitle.Render(label)),
		"",
		styles.Hint.Render("Architecting manifest and forging sprite"),
	}, "\n")
}

func (m model) stagingView() string {
	headerLines := []string{
		styles.Success.Render("✔ Preview Ready"),
		styles.Subtitle.Render("Preview Screen"),
		"",
	}

	if m.previewItem == nil {
		headerLines = append(headerLines, styles.Hint.Render("No preview available."))
	} else {
		latest := *m.previewItem

		headerLines = append(headerLines, styles.Inventory.Render(m.revealItem(latest.label)))
		if m.revealPhase >= 3 {
			meta := buildMetaLine(latest)
			if meta != "" {
				headerLines = append(headerLines, styles.Meta.Render(meta))
			}
		}

		if m.revealPhase >= 3 {
			sprite := renderSprite(latest.spritePath)
			projSprite := renderSprite(latest.projSpritePath)
			stats := renderStats(latest.stats)

			if sprite != "" || projSprite != "" || stats != "" {
				headerLines = append(headerLines, "")
				var panels []string
				if sprite != "" {
					spriteBox := styles.SpriteFrame.Render(sprite)
					panels = append(panels, spriteBox)
				}
				if projSprite != "" {
					arrow := styles.Hint.Render("→")
					projBox := styles.SpriteFrame.Render(projSprite)
					panels = append(panels, arrow, projBox)
				}
				if stats != "" {
					statsBox := styles.StatsFrame.Render(stats)
					panels = append(panels, statsBox)
				}
				headerLines = append(headerLines, lipgloss.JoinHorizontal(lipgloss.Top, panels...))
			}
		}

		if len(m.craftedItems) > 0 {
			headerLines = append(headerLines, "", styles.Hint.Render("Accepted loadout:"))
			for i := 0; i < len(m.craftedItems); i++ {
				item := m.craftedItems[i]
				headerLines = append(headerLines, styles.Hint.Render(fmt.Sprintf("  %d. %s", i+1, item.label)))
			}
		}
	}

	headerLines = append(headerLines, "")

	// Bridge status line.
	if m.bridgeAlive {
		headerLines = append(headerLines, styles.Success.Render("⬡ Bridge Online"))
	} else {
		headerLines = append(headerLines, styles.Hint.Render("⬡ Bridge Offline — open Terraria with ForgeConnector loaded"))
	}

	if m.injectErr != "" {
		headerLines = append(headerLines, styles.Error.Render("✘ "+m.injectErr))
	}

	switch {
	case m.injecting:
		headerLines = append(headerLines, "", styles.Injecting.Render("⟳ Injecting into Terraria..."))
	case m.injectStatus == "item_injected":
		headerLines = append(headerLines, "", styles.Success.Render("✔ Item appeared in your inventory!"))
		headerLines = append(headerLines, styles.Hint.Render("[C] Craft Another"))
	case m.injectStatus == "item_pending":
		headerLines = append(headerLines, "", styles.Success.Render("✔ Item registered — enter a world to receive it"))
		if m.injectDetail != "" {
			headerLines = append(headerLines, styles.Hint.Render(m.injectDetail))
		}
		headerLines = append(headerLines, styles.Hint.Render("[C] Craft Another"))
	case m.injectStatus == "inject_failed":
		headerLines = append(headerLines, "", styles.Error.Render("✘ Injection failed"))
		if m.injectDetail != "" {
			headerLines = append(headerLines, styles.Hint.Render(m.injectDetail))
		}
		headerLines = append(headerLines, styles.Hint.Render("[C] Craft Another   [ENTER] Retry"))
	case m.injectStatus == "reload_triggered":
		headerLines = append(headerLines, "", styles.Success.Render("✔ Mod reloading in Terraria"))
		headerLines = append(headerLines, styles.Hint.Render("[C] Craft Another"))
	case m.injectStatus == "reload_failed":
		headerLines = append(headerLines, "", styles.Error.Render("✘ Connector reached but reload failed"))
		headerLines = append(headerLines, styles.Hint.Render("[C] Craft Another   [ENTER] Retry"))
	case m.injectStatus == "timeout":
		headerLines = append(headerLines, "", styles.Error.Render("✘ No response from Terraria"))
		headerLines = append(headerLines, styles.Hint.Render("[C] Craft Another   [ENTER] Retry"))
	default:
		switch m.previewMode {
		case previewModeReprompt:
			headerLines = append(headerLines, "", styles.Subtitle.Render("Reprompt sprite"))
			headerLines = append(headerLines, styles.PromptInput.Render(m.previewInput.View()))
			headerLines = append(headerLines, styles.Hint.Render("Enter regenerate  •  Esc cancel"))
		case previewModeStats:
			headerLines = append(headerLines, "", styles.Subtitle.Render("Tweak stats"))
			for i, field := range previewStatFields {
				cursor := " "
				if i == m.statEditIndex {
					cursor = "▸"
				}
				value := "—"
				if statsMap, ok := m.forgeManifest["stats"].(map[string]interface{}); ok {
					if current, ok := toFloat(statsMap[field.key]); ok {
						if field.step >= 1 {
							value = fmt.Sprintf("%.0f", current)
						} else {
							value = fmt.Sprintf("%.1f", current)
						}
					}
				}
				headerLines = append(headerLines, styles.Body.Render(fmt.Sprintf("%s %-10s %s", cursor, field.label, value)))
			}
			headerLines = append(headerLines, styles.Hint.Render("↑/↓ field  •  ←/→ adjust  •  Enter done"))
		default:
			headerLines = append(headerLines, "", styles.Hint.Render("[R] Reprompt sprite   [S] Tweak stats   [A] Accept & Inject   [D] Discard   [C] Reset"))
		}
	}

	return strings.Join(headerLines, "\n")
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

func (m model) enterForge() (tea.Model, tea.Cmd) {
	m.state = screenForge
	m.heat = 0
	m.stageTargetPct = 0
	m.stageLabel = ""
	m.animTick = 0
	m.lastForgeVerb = 0
	m.revealPhase = 0
	m.forgeErr = ""
	m.forgeItemName = ""

	prompt := m.prompt
	tier := m.tier
	contentType := m.contentType
	subType := m.subType
	craftingStation := m.craftingStation
	pendingManifest := m.pendingManifest
	pendingArtFeedback := strings.TrimSpace(m.pendingArtFeedback)
	m.pendingManifest = nil
	m.pendingArtFeedback = ""
	startCmd := func() tea.Msg {
		// Clear any stale status from a previous run.
		_ = os.Remove(filepath.Join(modsources.Dir(), "generation_status.json"))
		extra := map[string]interface{}{}
		if pendingManifest != nil {
			extra["existing_manifest"] = pendingManifest
		}
		if pendingArtFeedback != "" {
			extra["art_feedback"] = pendingArtFeedback
		}
		if err := ipc.WriteUserRequest(prompt, tier, contentType, subType, craftingStation, extra); err != nil {
			return forgeErrMsg{message: "Failed to write request: " + err.Error()}
		}
		return ipc.PollStatusMsg{}
	}
	return m, tea.Batch(m.spinner.Tick, startCmd)
}

func animTickCmd() tea.Cmd {
	return tea.Tick(200*time.Millisecond, func(t time.Time) tea.Msg {
		return animTickMsg(t)
	})
}

func (m *model) resetForCraftAnother() {
	m.state = screenMode
	m.prompt = ""
	m.tier = ""
	m.contentType = ""
	m.subType = ""
	m.damageClass = ""
	m.styleChoice = ""
	m.projectile = ""
	m.wizardIndex = 0
	m.errMsg = ""
	m.injecting = false
	m.revealPhase = 0
	m.heat = 0
	m.forgeItemName = ""
	m.forgeErr = ""
	m.stageLabel = ""
	m.stageTargetPct = 0
	m.craftingStation = ""
	m.forgeManifest = nil
	m.forgeSprPath = ""
	m.forgeProjPath = ""
	m.previewMode = previewModeActions
	m.previewItem = nil
	m.statEditIndex = 0
	m.bridgeAlive = false
	m.injectErr = ""
	m.injectStatus = ""
	m.injectDetail = ""
	m.pendingManifest = nil
	m.pendingArtFeedback = ""
	m.textInput.SetValue("")
	m.previewInput.SetValue("")
	m.textInput.Focus()
	m.modeList.Select(0)
}

func (m model) buildCraftedItem() craftedItem {
	name := strings.TrimSpace(m.prompt)
	if name == "" {
		name = "Unnamed Artifact"
	}
	label := name
	if m.forgeItemName != "" {
		label = m.forgeItemName // real item name from backend
	} else if m.tier != "" {
		label = fmt.Sprintf("%s (%s)", name, m.tier)
	}

	return craftedItem{
		label:           label,
		tier:            m.tier,
		contentType:     m.contentType,
		subType:         m.subType,
		craftingStation: m.craftingStation,
		stats:           extractItemStats(m.forgeManifest),
		spritePath:      m.forgeSprPath,
		projSpritePath:  m.forgeProjPath,
	}
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

func extractItemStats(manifest map[string]interface{}) itemStats {
	var stats itemStats
	if manifest == nil {
		return stats
	}
	statsMap, ok := manifest["stats"].(map[string]interface{})
	if !ok {
		return stats
	}
	if v, ok := toFloat(statsMap["damage"]); ok {
		stats.Damage = int(v)
	}
	if v, ok := toFloat(statsMap["knockback"]); ok {
		stats.Knockback = v
	}
	if v, ok := toFloat(statsMap["crit_chance"]); ok {
		stats.CritChance = int(v)
	}
	if v, ok := toFloat(statsMap["use_time"]); ok {
		stats.UseTime = int(v)
	}
	if v, ok := statsMap["rarity"].(string); ok {
		stats.Rarity = v
	}
	return stats
}

func toFloat(value interface{}) (float64, bool) {
	switch v := value.(type) {
	case float64:
		return v, true
	case float32:
		return float64(v), true
	case int:
		return float64(v), true
	case int64:
		return float64(v), true
	case json.Number:
		fv, err := v.Float64()
		return fv, err == nil
	default:
		return 0, false
	}
}

func (m *model) adjustPreviewStat(direction int) {
	if m.forgeManifest == nil || len(previewStatFields) == 0 {
		return
	}
	statsMap, ok := m.forgeManifest["stats"].(map[string]interface{})
	if !ok {
		return
	}
	field := previewStatFields[m.statEditIndex]
	current, _ := toFloat(statsMap[field.key])
	next := current + field.step*float64(direction)
	if next < field.minimum {
		next = field.minimum
	}
	if field.step >= 1 {
		next = math.Round(next)
	} else {
		next = math.Round(next*2) / 2
	}
	statsMap[field.key] = next
	m.forgeManifest["stats"] = statsMap
	if m.previewItem != nil {
		m.previewItem.stats = extractItemStats(m.forgeManifest)
	}
}

func (m *model) appendPreviewHistory() {
	if m.previewItem == nil {
		return
	}
	if len(m.craftedItems) > 0 {
		last := m.craftedItems[len(m.craftedItems)-1]
		if last.label == m.previewItem.label &&
			last.tier == m.previewItem.tier &&
			last.contentType == m.previewItem.contentType &&
			last.subType == m.previewItem.subType {
			return
		}
	}
	m.craftedItems = append(m.craftedItems, *m.previewItem)
}


// ---------------------------------------------------------------------------
// Sprite ASCII-art renderer
// ---------------------------------------------------------------------------

func colorToHex(c color.Color) string {
	r, g, b, _ := c.RGBA()
	return fmt.Sprintf("#%02x%02x%02x", r>>8, g>>8, b>>8)
}

func isTransparent(c color.Color) bool {
	_, _, _, a := c.RGBA()
	return a < 0x8000
}

// renderSprite reads a PNG file and renders it as colored half-block (▀)
// characters. Each character encodes two vertical pixels: top pixel as
// foreground, bottom pixel as background. Transparent pixels use the
// terminal default. Sprites are typically 32×32 or 64×64.
func renderSprite(path string) string {
	if path == "" {
		return ""
	}
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()

	img, _, err := image.Decode(f)
	if err != nil {
		return ""
	}

	bounds := img.Bounds()
	w := bounds.Max.X - bounds.Min.X
	h := bounds.Max.Y - bounds.Min.Y

	// Find the bounding box of non-transparent pixels to crop whitespace.
	minX, minY, maxX, maxY := w, h, 0, 0
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			if !isTransparent(img.At(x, y)) {
				if x < minX {
					minX = x
				}
				if y < minY {
					minY = y
				}
				if x > maxX {
					maxX = x
				}
				if y > maxY {
					maxY = y
				}
			}
		}
	}

	if maxX < minX || maxY < minY {
		return "" // fully transparent
	}

	// Crop to bounding box.
	cropW := maxX - minX + 1
	cropH := maxY - minY + 1

	// Scale down if the sprite is too large for the terminal.
	// Target max ~20 columns wide, ~16 rows tall (32 pixel rows at 2px/char).
	scale := 1
	if cropW > 40 {
		s := int(math.Ceil(float64(cropW) / 40.0))
		if s > scale {
			scale = s
		}
	}
	if cropH > 32 {
		s := int(math.Ceil(float64(cropH) / 32.0))
		if s > scale {
			scale = s
		}
	}

	outW := cropW / scale
	outH := cropH / scale
	if outW == 0 {
		outW = 1
	}
	if outH == 0 {
		outH = 1
	}

	// Sample pixels with scaling.
	pixel := func(px, py int) color.Color {
		sx := minX + px*scale
		sy := minY + py*scale
		if sx >= bounds.Max.X || sy >= bounds.Max.Y {
			return color.Transparent
		}
		return img.At(sx, sy)
	}

	// Render using half-block technique: ▀ with top=fg, bottom=bg.
	var lines []string
	for row := 0; row < outH; row += 2 {
		var lineChars []string
		for col := 0; col < outW; col++ {
			top := pixel(col, row)
			var bottom color.Color = color.Transparent
			if row+1 < outH {
				bottom = pixel(col, row+1)
			}

			topTrans := isTransparent(top)
			botTrans := isTransparent(bottom)

			switch {
			case topTrans && botTrans:
				lineChars = append(lineChars, " ")
			case topTrans:
				// Only bottom pixel visible — use lower half block ▄
				s := lipgloss.NewStyle().Foreground(lipgloss.Color(colorToHex(bottom)))
				lineChars = append(lineChars, s.Render("▄"))
			case botTrans:
				// Only top pixel visible — use upper half block ▀
				s := lipgloss.NewStyle().Foreground(lipgloss.Color(colorToHex(top)))
				lineChars = append(lineChars, s.Render("▀"))
			default:
				// Both pixels visible — ▀ with top as fg, bottom as bg
				s := lipgloss.NewStyle().
					Foreground(lipgloss.Color(colorToHex(top))).
					Background(lipgloss.Color(colorToHex(bottom)))
				lineChars = append(lineChars, s.Render("▀"))
			}
		}
		lines = append(lines, strings.Join(lineChars, ""))
	}

	return strings.Join(lines, "\n")
}

// ---------------------------------------------------------------------------
// Stats panel renderer
// ---------------------------------------------------------------------------

func friendlyRarity(raw string) string {
	// Convert "ItemRarityID.White" → "White"
	if i := strings.LastIndex(raw, "."); i >= 0 && i+1 < len(raw) {
		return raw[i+1:]
	}
	if raw == "" {
		return "—"
	}
	return raw
}

func renderStats(stats itemStats) string {
	if stats.Damage == 0 && stats.UseTime == 0 {
		return "" // no stats available
	}

	labelStyle := styles.StatsLabel
	valStyle := styles.StatsValue

	row := func(icon, label, value string) string {
		return fmt.Sprintf("%s %s %s",
			labelStyle.Render(icon),
			labelStyle.Render(fmt.Sprintf("%-10s", label)),
			valStyle.Render(value),
		)
	}

	lines := []string{
		styles.StatsTitle.Render("Stats"),
		"",
		row("⚔", "Damage", fmt.Sprintf("%d", stats.Damage)),
		row("◈", "Knockback", fmt.Sprintf("%.1f", stats.Knockback)),
		row("◎", "Crit", fmt.Sprintf("%d%%", stats.CritChance)),
		row("⏱", "Use Time", fmt.Sprintf("%d", stats.UseTime)),
		row("★", "Rarity", friendlyRarity(stats.Rarity)),
	}

	return strings.Join(lines, "\n")
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

func (m model) heatBar() string {
	total := 12
	filled := (m.heat * total) / 100
	if filled > total {
		filled = total
	}
	empty := total - filled
	return strings.Repeat("█", filled) + strings.Repeat("░", empty) + fmt.Sprintf(" %d%%", m.heat)
}

func (m model) revealItem(item string) string {
	switch {
	case m.revealPhase <= 0:
		return "..."
	case m.revealPhase == 1:
		return strings.Repeat("░", min(8, len(item)))
	case m.revealPhase == 2:
		n := len(item) / 2
		if n < 1 {
			n = 1
		}
		return item[:n] + "..."
	default:
		return item
	}
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
