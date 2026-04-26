package main

import (
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	_ "image/png"
	"math"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"theforge/internal/ipc"
	"theforge/internal/modsources"
)

type workshopStatusMsg struct {
	status ipc.WorkshopStatus
}

func (m *model) applyWorkshopStatus(status ipc.WorkshopStatus) {
	m.workshop.ApplyStatus(status)
	m.workshopNotice = ""
	if status.Error != "" {
		m.workshopNotice = "Director error: " + status.Error
	}
	if workshopBenchHasRenderableContent(m.workshop.Bench) {
		preview := craftedItemFromWorkshopBench(m.workshop.Bench)
		m.previewItem = &preview
		m.forgeItemName = preview.label
		m.forgeManifest = m.workshop.Bench.Manifest
		m.forgeSprPath = m.workshop.Bench.SpritePath
		m.forgeProjPath = m.workshop.Bench.ProjectilePath
	}
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
		m.workshop.Runtime.BridgeAlive = msg.alive
		return m, nil
	case runtimeSummaryMsg:
		m.applyRuntimeSummaryBanner(msg.banner)
		return m, runtimeSummaryCmd()
	case ipc.PollConnectorStatusMsg:
		const maxAttempts = 60 // 30 seconds at 500ms intervals
		if status, detail := ipc.ReadConnectorStatusPayload(); status != "" {
			return m, func() tea.Msg { return connectorStatusMsg{status: status, detail: detail} }
		}
		if msg.Attempt >= maxAttempts {
			return m, func() tea.Msg { return connectorStatusMsg{status: "timeout"} }
		}
		return m, ipc.PollConnectorStatusCmd(msg.Attempt + 1)
	case ipc.PollWorkshopStatusMsg:
		const maxAttempts = 20
		status := ipc.ReadWorkshopStatus()
		if status.SessionID != "" {
			return m, func() tea.Msg { return workshopStatusMsg{status: status} }
		}
		if msg.Attempt >= maxAttempts {
			m.workshopNotice = "Director did not answer yet."
			return m, nil
		}
		return m, ipc.PollWorkshopStatusCmd(msg.Attempt + 1)
	case connectorStatusMsg:
		m.injecting = false
		m.operationKind = operationIdle
		m.operationStale = false
		m.injectStatus = msg.status
		m.injectDetail = msg.detail
		m.workshop.Runtime.LastInjectStatus = msg.status
		if msg.detail != "" {
			m.workshop.Runtime.LastRuntimeNote = msg.detail
		}
		if msg.status != "" {
			detail := msg.detail
			if detail != "" {
				m.appendFeedEvent(sessionEventKindSystem, fmt.Sprintf("Connector %s: %s", msg.status, detail))
			} else {
				m.appendFeedEvent(sessionEventKindSystem, "Connector "+msg.status)
			}
		}
		if msg.status == "item_injected" || msg.status == "item_pending" {
			// For instant inject, auto-clear the forge_inject.json to prevent re-inject
			_ = os.Remove(filepath.Join(modsources.Dir(), "forge_inject.json"))
		}
		return m, nil
	case workshopStatusMsg:
		m.applyWorkshopStatus(msg.status)
		m.operationKind = operationIdle
		m.operationStale = false
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

		if m.commandMode {
			switch key.Type {
			case tea.KeyEsc:
				m.commandMode = false
				m.commandInput.Blur()
				m.commandInput.SetValue("")
				return m, nil
			case tea.KeyEnter:
				raw := strings.TrimSpace(m.commandInput.Value())
				if raw == "" {
					m.commandMode = false
					m.commandInput.Blur()
					return m, nil
				}
				m.commandMode = false
				m.commandInput.Blur()
				m.commandInput.SetValue("")
				return m.handleShellCommand(raw)
			}

			var cmd tea.Cmd
			m.commandInput, cmd = m.commandInput.Update(msg)
			return m, cmd
		}

		switch key.String() {
		case "/", "tab":
			m.commandMode = true
			m.commandInput.Focus()
			if key.String() == "/" {
				m.commandInput.SetValue("/")
			} else {
				m.commandInput.SetValue("")
			}
			m.workshopNotice = ""
			return m, nil
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
			m.commandInput.Focus()
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
			label := m.forgeItemName
			if strings.TrimSpace(m.workshop.Bench.Label) != "" {
				label = m.workshop.Bench.Label
			}
			m.operationKind = operationInjecting
			m.operationLabel = label
			m.operationStartedAt = time.Now().UTC()
			m.operationStale = false
			m.appendFeedEvent(sessionEventKindSystem, "Accept & Inject: "+label)
			m.appendPreviewHistory()
			// Always use the instant inject path: write forge_inject.json and
			// let the ForgeConnector mod pick it up on the next game tick.
			dir := modsources.Dir()
			_ = os.Remove(filepath.Join(dir, "forge_connector_status.json"))
			injectItemName := label
			if err := ipc.WriteInjectFile(m.forgeManifest, injectItemName, m.forgeSprPath, m.forgeProjPath); err != nil {
				m.injecting = false
				m.operationKind = operationIdle
				m.operationStale = false
				m.injectErr = err.Error()
				return m, nil
			}
			return m, ipc.PollConnectorStatusCmd(0)
		}
	}
	return m, nil
}

func (m model) tryCurrentBench() (tea.Model, tea.Cmd) {
	if m.workshop.Bench.Manifest == nil {
		m.workshopNotice = "Bench is empty."
		return m, nil
	}
	m.state = screenStaging
	m.injecting = true
	m.operationKind = operationInjecting
	m.operationLabel = m.workshop.Bench.Label
	m.operationStartedAt = time.Now().UTC()
	m.operationStale = false
	m.injectErr = ""
	m.injectStatus = ""
	m.injectDetail = ""
	m.appendFeedEvent(sessionEventKindSystem, "Workshop try: "+m.workshop.Bench.Label)
	_ = os.Remove(filepath.Join(modsources.Dir(), "forge_connector_status.json"))
	if err := ipc.WriteInjectFile(
		m.workshop.Bench.Manifest,
		m.workshop.Bench.Label,
		m.workshop.Bench.SpritePath,
		m.workshop.Bench.ProjectilePath,
	); err != nil {
		m.injecting = false
		m.operationKind = operationIdle
		m.operationStale = false
		m.workshopNotice = "Bench try failed: " + err.Error()
		return m, nil
	}
	m.workshopNotice = "Bench injected into Terraria."
	return m, ipc.PollConnectorStatusCmd(0)
}

func (m model) stagingView() string {
	headerLines := []string{
		styles.Success.Render("✔ Workshop Ready"),
		styles.Subtitle.Render("Bench"),
		"",
	}

	if m.previewItem == nil {
		headerLines = append(headerLines, styles.Hint.Render("No preview available."))
	} else {
		latest := *m.previewItem
		benchLabel := latest.label
		if m.workshop.Bench.Label != "" {
			benchLabel = m.workshop.Bench.Label
		}

		headerLines = append(headerLines, styles.Inventory.Render(m.revealItem(benchLabel)))
		if m.revealPhase >= 3 {
			meta := buildMetaLine(latest)
			if meta != "" {
				headerLines = append(headerLines, styles.Meta.Render(meta))
			}
			if m.workshop.SessionID != "" {
				headerLines = append(headerLines, styles.Hint.Render("Session "+m.workshop.SessionID))
			}
			if len(m.workshop.Shelf) == 0 {
				headerLines = append(headerLines, styles.Hint.Render("Shelf empty — ask for variants next."))
			} else {
				headerLines = append(headerLines, styles.Hint.Render("Shelf"))
				for i, variant := range m.workshop.Shelf {
					line := fmt.Sprintf("  %d. %s", i+1, variant.Label)
					if variant.ChangeSummary != "" {
						line += " — " + variant.ChangeSummary
					}
					headerLines = append(headerLines, styles.Hint.Render(line))
				}
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
					panels = append(panels, styles.SpriteFrame.Render(sprite))
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
				if m.contentWidth > 0 && m.contentWidth < 90 {
					headerLines = append(headerLines, panels...)
				} else {
					headerLines = append(headerLines, lipgloss.JoinHorizontal(lipgloss.Top, panels...))
				}
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

	if runtimeState := m.renderRuntimeState(); runtimeState != "" {
		headerLines = append(headerLines, "", runtimeState)
	}

	if m.injectErr != "" {
		headerLines = append(headerLines, styles.Error.Render("✘ "+m.injectErr))
	}
	if m.workshopNotice != "" {
		headerLines = append(headerLines, styles.Hint.Render(m.workshopNotice))
	}

	switch {
	case m.injectStatus == "item_injected":
		headerLines = append(headerLines, "", styles.Success.Render("✔ Item appeared in your inventory!"))
		headerLines = append(headerLines, styles.Hint.Render("[C] Craft Another"))
	case m.injectStatus == "item_pending":
		headerLines = append(headerLines, "", styles.Pending.Render("◐ Item registered — enter a world to receive it"))
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
			headerLines = append(headerLines, "", styles.Hint.Render("Tab or / opens the director command bar"))
			if m.commandMode {
				headerLines = append(headerLines, "", styles.Subtitle.Render("Director"))
				headerLines = append(headerLines, styles.PromptInput.Render(m.commandInput.View()))
				headerLines = append(headerLines, styles.Hint.Render("Enter send  •  Esc cancel"))
			}
		}
	}

	return strings.Join(headerLines, "\n")
}

func (m model) renderRuntimeState() string {
	if !m.shouldRenderRuntimeState() {
		return ""
	}

	lines := []string{}
	if m.workshop.Runtime.BridgeAlive {
		worldLine := "⬡ Runtime Online"
		if m.workshop.Runtime.WorldLoaded {
			worldLine += " · World Loaded"
		} else {
			worldLine += " · Main Menu"
		}
		lines = append(lines, styles.Success.Render(worldLine))
	} else {
		lines = append(lines, styles.Hint.Render("⬡ Runtime Offline — open Terraria with ForgeConnector loaded"))
	}
	if m.workshop.Runtime.LiveItemName != "" {
		lines = append(lines, styles.Hint.Render("Live item: "+m.workshop.Runtime.LiveItemName))
	}
	if m.workshop.Runtime.LastInjectStatus != "" {
		lines = append(lines, styles.Hint.Render("Inject status: "+m.workshop.Runtime.LastInjectStatus))
	}
	if m.workshop.Runtime.LastRuntimeNote != "" {
		lines = append(lines, styles.Hint.Render(m.workshop.Runtime.LastRuntimeNote))
	}
	return strings.Join(lines, "\n")
}

func (m model) shouldRenderRuntimeState() bool {
	if !m.workshop.Runtime.BridgeAlive {
		return true
	}
	if m.injecting || m.injectErr != "" || m.injectStatus != "" {
		return true
	}
	if m.workshop.Runtime.LastInjectStatus != "" {
		return true
	}
	note := strings.TrimSpace(m.workshop.Runtime.LastRuntimeNote)
	return strings.Contains(strings.ToLower(note), "stale") || strings.Contains(strings.ToLower(note), "error")
}

func (m *model) resetForCraftAnother() {
	m.state = screenInput
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
	m.commandMode = false
	m.workshopNotice = ""
	m.shellNotice = ""
	m.shellError = ""
	m.pendingManifest = nil
	m.pendingArtFeedback = ""
	m.operationKind = operationIdle
	m.operationLabel = ""
	m.operationStartedAt = time.Time{}
	m.operationStale = false
	m.forgePollCount = 0
	m.workshop = newWorkshopState()
	m.textInput.SetValue("")
	m.previewInput.SetValue("")
	m.commandInput.SetValue("")
	m.commandInput.Focus()
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
	img, ok := loadSpriteImage(path)
	if !ok {
		return ""
	}
	return renderSpriteImage(img)
}

func loadSpriteImage(path string) (image.Image, bool) {
	if path == "" {
		return nil, false
	}
	f, err := os.Open(path)
	if err != nil {
		return nil, false
	}
	defer f.Close()

	img, _, err := image.Decode(f)
	if err != nil {
		return nil, false
	}

	bounds := img.Bounds()
	minX, minY, maxX, maxY := bounds.Max.X, bounds.Max.Y, bounds.Min.X, bounds.Min.Y
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
		return nil, false
	}

	cropRect := image.Rect(0, 0, maxX-minX+1, maxY-minY+1)
	cropped := image.NewRGBA(cropRect)
	draw.Draw(cropped, cropRect, img, image.Point{X: minX, Y: minY}, draw.Src)
	return cropped, true
}

func renderSpriteImage(img image.Image) string {
	bounds := img.Bounds()
	cropW := bounds.Dx()
	cropH := bounds.Dy()

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
		sx := bounds.Min.X + px*scale
		sy := bounds.Min.Y + py*scale
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
