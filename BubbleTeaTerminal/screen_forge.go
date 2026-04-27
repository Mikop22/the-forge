package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"

	"theforge/internal/ipc"
	"theforge/internal/modsources"
)

const (
	forgeStalePollThreshold   = 10
	forgeTimeoutPollThreshold = 90
)

func (m model) updateForge(msg tea.Msg) (tea.Model, tea.Cmd) {
	// Allow escaping an error state or canceling an in-flight forge.
	if key, ok := msg.(tea.KeyMsg); ok {
		if key.Type == tea.KeyEsc {
			if m.forgeErr != "" || m.operationKind == operationForging {
				m.state = screenInput
				m.forgeErr = ""
				m.operationKind = operationIdle
				m.operationStale = false
				m.appendFeedEvent(sessionEventKindSystem, "Forge cancelled.")
				m.commandInput.Focus()
				return m, nil
			}
		}
		if m.forgeErr != "" && key.Type == tea.KeyRunes && len(key.Runes) > 0 && (key.Runes[0] == 'r' || key.Runes[0] == 'R') {
			m.forgeErr = ""
			m.forgePollCount = 0
			m.heat = 0
			m.stageTargetPct = 0
			m.stageLabel = ""
			return m.enterForge()
		}
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
		m.forgePollCount++
		ps := ipc.ReadGenerationStatus()
		switch ps.Status {
		case "ready":
			m.forgeItemName = ps.ItemName
			m.forgeManifest = ps.Manifest
			m.forgeSprPath = ps.SpritePath
			m.forgeProjPath = ps.ProjectileSpritePath
			m.heat = 100
			m.operationKind = operationIdle
			m.operationStale = false
			m.appendFeedEvent(sessionEventKindSystem, "Forge complete: "+strings.TrimSpace(ps.ItemName))
			return m, func() tea.Msg { return forgeDoneMsg{} }
		case "error":
			if ps.ErrMsg != "" {
				m.appendFeedEvent(sessionEventKindFailure, "Forge error: "+ps.ErrMsg)
			}
			m.operationKind = operationIdle
			m.operationStale = false
			return m, func() tea.Msg { return forgeErrMsg{message: ps.ErrMsg} }
		default:
			if m.forgePollCount >= forgeTimeoutPollThreshold {
				m.operationKind = operationIdle
				m.operationStale = false
				return m, func() tea.Msg { return forgeErrMsg{message: "Forge timed out."} }
			}
			// "building" or file not yet written — update stage and keep polling.
			if ps.StagePct > m.stageTargetPct {
				m.stageTargetPct = ps.StagePct
			}
			if ps.StageLabel != "" {
				m.stageLabel = ps.StageLabel
			}
			label := ps.StageLabel
			if label == "" {
				label = "Building"
			}
			m.operationStale = m.forgePollCount >= forgeStalePollThreshold
			if m.operationStale {
				m.operationLabel = "forge"
			}
			m.upsertFeedEvent(sessionEventKindRuntime, fmt.Sprintf("Forge progress: %d%% %s", ps.StagePct, label))
			return m, ipc.PollStatusCmd()
		}
	case forgeErrMsg:
		m.forgeErr = msg.message
		m.operationKind = operationIdle
		m.operationStale = false
		return m, nil
	case forgeDoneMsg:
		m.state = screenStaging
		item := m.buildCraftedItem()
		m.previewItem = &item
		m.workshop.SetBenchFromCraftedItem(item, m.forgeManifest)
		m.previewMode = previewModeActions
		m.statEditIndex = 0
		m.previewInput.SetValue("")
		m.injecting = false
		m.revealPhase = 1
		checkBridgeCmd := func() tea.Msg { return bridgeStatusMsg{alive: ipc.ReadBridgeHeartbeat()} }
		return m, tea.Batch(m.spinner.Tick, checkBridgeCmd, runtimeSummaryCmd())
	}
	return m, nil
}

func (m model) forgeView() string {
	if m.forgeErr != "" {
		return strings.Join([]string{
			styles.Error.Render("✘ Forge Failed"),
			"",
			styles.Body.Render(m.forgeErr),
			"",
			styles.Hint.Render("r to retry  ·  Esc to go back"),
		}, "\n")
	}
	label := m.stageLabel
	if label == "" {
		label = forgeVerbs[m.lastForgeVerb%len(forgeVerbs)] + "..."
	}
	elapsed := fmtElapsed(m.operationStartedAt)
	elapsedStr := ""
	if elapsed != "" {
		elapsedStr = "  " + styles.Hint.Render(elapsed)
	}
	return strings.Join([]string{
		styles.TitleRune.Render("The Forge"),
		styles.Progress.Render("Heat " + m.heatBar()),
		"",
		fmt.Sprintf("%s %s%s", m.spinner.View(), styles.Subtitle.Render(label), elapsedStr),
		"",
		styles.Hint.Render("Architecting manifest and forging sprite"),
	}, "\n")
}

func (m model) enterForge() (tea.Model, tea.Cmd) {
	m.state = screenForge
	m.sessionShell.beginScope(sessionEventKindRuntime)
	m.heat = 0
	m.stageTargetPct = 0
	m.stageLabel = ""
	m.animTick = 0
	m.lastForgeVerb = 0
	m.revealPhase = 0
	m.forgeErr = ""
	m.forgeItemName = ""
	m.forgePollCount = 0

	prompt := m.prompt
	m.operationKind = operationForging
	m.operationLabel = prompt
	m.operationStartedAt = time.Now().UTC()
	m.operationStale = false

	tier := m.tier
	contentType := m.contentType
	contentTypeExplicit := m.contentTypeExplicit
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
		if err := ipc.WriteUserRequest(prompt, tier, contentType, subType, craftingStation, contentTypeExplicit, extra); err != nil {
			return forgeErrMsg{message: "Failed to write request: " + err.Error()}
		}
		return ipc.PollStatusMsg{}
	}
	return m, tea.Batch(m.spinner.Tick, startCmd)
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
