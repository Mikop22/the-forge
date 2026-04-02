package main

import (
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	_ "image/png"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type screen int

const (
	screenMode screen = iota
	screenWizard
	screenInput
	screenForge
	screenStaging
)

type forgeDoneMsg struct{}
type forgeErrMsg struct{ message string }
type pollStatusMsg struct{}
type injectDoneMsg struct{ err error }
type bridgeStatusMsg struct{ alive bool }

type animTickMsg time.Time
type pollConnectorStatusMsg struct{ attempt int }
type connectorStatusMsg struct{ status string }

type previewMode int

const (
	previewModeActions previewMode = iota
	previewModeReprompt
	previewModeStats
)

type optionItem struct {
	title string
	desc  string
}

func (i optionItem) Title() string       { return i.title }
func (i optionItem) Description() string { return i.desc }
func (i optionItem) FilterValue() string { return i.title }

type itemStats struct {
	Damage     int     `json:"damage"`
	Knockback  float64 `json:"knockback"`
	CritChance int     `json:"crit_chance"`
	UseTime    int     `json:"use_time"`
	Rarity     string  `json:"rarity"`
}

type craftedItem struct {
	label           string
	tier            string
	contentType     string
	subType         string
	craftingStation string
	stats           itemStats
	spritePath      string
}

type statField struct {
	key     string
	label   string
	step    float64
	minimum float64
}

type wizardStep struct {
	question string
	options  []optionItem
}

var contentTypeOptions = []optionItem{
	{title: "Weapon", desc: "Melee, ranged, and magic armaments"},
	{title: "Accessory", desc: "Passive mobility, defense, and buffs"},
	{title: "Summon", desc: "Minion staves with persistent companions"},
	{title: "Consumable", desc: "Potions, ammo, and thrown items"},
	{title: "Tool", desc: "Hooks and fishing gear"},
}

var tierOptions = []optionItem{
	{title: "Starter", desc: "Early game balance and simple effects"},
	{title: "Dungeon", desc: "Midgame utility with stronger scaling"},
	{title: "Hardmode", desc: "High pressure combat and synergy hooks"},
	{title: "Endgame", desc: "Peak-tier stats and complex behavior"},
}

var subTypeOptions = map[string][]optionItem{
	"Weapon": {
		{title: "Sword", desc: "Broad melee arc with direct contact"},
		{title: "Bow", desc: "Ranged weapon built around arrows"},
		{title: "Staff", desc: "Magic focus with projectile casting"},
		{title: "Gun", desc: "Fast ranged weapon with bullet fire"},
		{title: "Cannon", desc: "Heavy launcher with loud impact"},
		{title: "Spear", desc: "Reach-focused thrusting weapon"},
	},
	"Accessory": {
		{title: "Wings", desc: "Flight time and aerial mobility"},
		{title: "Shield", desc: "Defense, dash, and survivability"},
		{title: "Movement", desc: "Speed and traversal boosts"},
		{title: "StatBoost", desc: "Passive combat enhancement"},
	},
	"Summon": {
		{title: "MinionStaff", desc: "Summons a persistent helper minion"},
	},
	"Consumable": {
		{title: "HealPotion", desc: "Restores life on use"},
		{title: "ManaPotion", desc: "Restores mana on use"},
		{title: "BuffPotion", desc: "Applies a temporary buff"},
		{title: "ThrownWeapon", desc: "Consumable damage item"},
		{title: "Ammo", desc: "Stackable ammunition"},
	},
	"Tool": {
		{title: "Hook", desc: "Grapple through terrain with a tether"},
		{title: "FishingRod", desc: "Fishing utility with power scaling"},
	},
}

var previewStatFields = []statField{
	{key: "damage", label: "Damage", step: 1, minimum: 1},
	{key: "use_time", label: "Use Time", step: 1, minimum: 1},
	{key: "knockback", label: "Knockback", step: 0.5, minimum: 0},
}

type model struct {
	state  screen
	width  int
	height int

	craftedItems []craftedItem

	textInput  textinput.Model
	previewInput textinput.Model
	modeList   list.Model
	wizardList list.Model
	spinner    spinner.Model

	prompt          string
	tier            string
	contentType     string
	subType         string
	damageClass     string
	styleChoice     string
	projectile      string
	craftingStation string

	wizardIndex   int
	errMsg        string
	injecting     bool
	animTick      int
	heat          int
	revealPhase   int
	lastForgeVerb int
	termCompact   bool

	forgeItemName  string // item name returned from the backend
	forgeErr       string // error message from the backend
	stageLabel     string // current pipeline stage label
	stageTargetPct int    // target heat % from pipeline status

	forgeManifest  map[string]interface{} // full manifest from backend
	forgeSprPath   string                 // sprite PNG path from backend
	forgeProjPath  string                 // projectile sprite PNG path from backend
	injectMode     bool                   // true = instant inject (template pool), false = legacy compile
	previewMode    previewMode
	previewItem    *craftedItem
	statEditIndex  int

	bridgeAlive   bool   // forge_connector_alive.json present with live PID
	injectErr     string // non-empty if command_trigger write failed
	injectStatus  string // "reload_triggered", "reload_failed", "item_injected", "inject_failed", "timeout", or ""
	pendingManifest map[string]interface{}
	pendingArtFeedback string
}

const (
	compactWidthThreshold  = 84
	compactHeightThreshold = 24
)

var forgeVerbs = []string{"Tempering", "Binding", "Etching", "Awakening"}
var wizardGlyphs = []string{"\u26e8", "\u2694", "\u2736", "\u27b6"}

// ---------------------------------------------------------------------------
// Filesystem helpers – handshake with the Python orchestrator
// ---------------------------------------------------------------------------

func modSourcesDir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, "Library", "Application Support", "Terraria", "tModLoader", "ModSources")
}

func tierToKey(tier string) string {
	switch tier {
	case "Starter":
		return "Tier1_Starter"
	case "Dungeon":
		return "Tier2_Dungeon"
	case "Hardmode":
		return "Tier3_Hardmode"
	case "Endgame":
		return "Tier4_Endgame"
	default:
		return "Tier1_Starter" // "Auto" and anything unknown defaults to starter
	}
}

func writeUserRequest(prompt, tier, contentType, subType, craftingStation string, extra map[string]interface{}) error {
	dir := modSourcesDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	payload := map[string]interface{}{
		"prompt": prompt,
		"tier":   tierToKey(tier),
		"mode":   "instant",
	}
	if contentType != "" {
		payload["content_type"] = contentType
	}
	if subType != "" {
		payload["sub_type"] = subType
	}
	if craftingStation != "" && craftingStation != "Auto" {
		payload["crafting_station"] = craftingStation
	}
	for key, value := range extra {
		if value != nil {
			payload[key] = value
		}
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	dst := filepath.Join(dir, "user_request.json")
	tmp := dst + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, dst)
}

type pipelineStatus struct {
	status              string
	itemName            string
	errMsg              string
	stagePct            int
	stageLabel          string
	manifest            map[string]interface{}
	spritePath          string
	projectileSpritePath string
	injectMode          bool
}

func readGenerationStatus() pipelineStatus {
	data, err := os.ReadFile(filepath.Join(modSourcesDir(), "generation_status.json"))
	if err != nil {
		return pipelineStatus{}
	}
	var result map[string]interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		return pipelineStatus{}
	}
	ps := pipelineStatus{}
	ps.status, _ = result["status"].(string)
	if batchList, ok := result["batch_list"].([]interface{}); ok && len(batchList) > 0 {
		ps.itemName, _ = batchList[0].(string)
	}
	ps.errMsg, _ = result["message"].(string)
	ps.stageLabel, _ = result["stage_label"].(string)
	if pct, ok := result["stage_pct"].(float64); ok {
		ps.stagePct = int(pct)
	}
	if manifest, ok := result["manifest"].(map[string]interface{}); ok {
		ps.manifest = manifest
	}
	ps.spritePath, _ = result["sprite_path"].(string)
	ps.projectileSpritePath, _ = result["projectile_sprite_path"].(string)
	if im, ok := result["inject_mode"].(bool); ok {
		ps.injectMode = im
	}
	return ps
}

func pollStatusCmd() tea.Cmd {
	return tea.Tick(2*time.Second, func(t time.Time) tea.Msg {
		return pollStatusMsg{}
	})
}

func pollConnectorStatusCmd(attempt int) tea.Cmd {
	return tea.Tick(500*time.Millisecond, func(t time.Time) tea.Msg {
		return pollConnectorStatusMsg{attempt: attempt}
	})
}

func readConnectorStatus() string {
	data, err := os.ReadFile(filepath.Join(modSourcesDir(), "forge_connector_status.json"))
	if err != nil {
		return ""
	}
	var result map[string]interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		return ""
	}
	status, _ := result["status"].(string)
	return status
}

// writeCommandTrigger atomically writes command_trigger.json to ModSources.
// It also removes any stale forge_connector_status.json so the TUI does not
// read a result from a previous execution.
func writeCommandTrigger() error {
	dir := modSourcesDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	_ = os.Remove(filepath.Join(dir, "forge_connector_status.json"))
	data, err := json.Marshal(map[string]string{
		"action":    "execute",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
	if err != nil {
		return err
	}
	dst := filepath.Join(dir, "command_trigger.json")
	tmp := dst + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, dst)
}

// writeInjectFile writes forge_inject.json from the TUI's stored manifest data.
func writeInjectFile(manifest map[string]interface{}, itemName, spritePath, projectileSpritePath string) error {
	dir := modSourcesDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	payload := map[string]interface{}{
		"action":                 "inject",
		"item_name":             itemName,
		"manifest":              manifest,
		"sprite_path":           spritePath,
		"projectile_sprite_path": projectileSpritePath,
		"timestamp":             time.Now().UTC().Format(time.RFC3339),
	}
	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	dst := filepath.Join(dir, "forge_inject.json")
	tmp := dst + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, dst)
}

// readHeartbeatFile returns true if the JSON heartbeat file exists,
// has status "listening", and its PID is still alive.
func readHeartbeatFile(path string) bool {
	data, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	var hb map[string]interface{}
	if err := json.Unmarshal(data, &hb); err != nil {
		return false
	}
	if status, _ := hb["status"].(string); status != "listening" {
		return false
	}
	pidFloat, ok := hb["pid"].(float64)
	if !ok {
		return false
	}
	pid := int(pidFloat)
	proc, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	// Signal(0) checks liveness without sending a real signal.
	return proc.Signal(syscall.Signal(0)) == nil
}

// readBridgeHeartbeat returns true if forge_connector_alive.json exists
// and points at a live bridge process.
func readBridgeHeartbeat() bool {
	return readHeartbeatFile(filepath.Join(modSourcesDir(), "forge_connector_alive.json"))
}

// readOrchestratorHeartbeat returns true if orchestrator_alive.json exists
// and points at a live orchestrator process.
func readOrchestratorHeartbeat() bool {
	return readHeartbeatFile(filepath.Join(modSourcesDir(), "orchestrator_alive.json"))
}

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
	case pollStatusMsg:
		ps := readGenerationStatus()
		switch ps.status {
		case "ready":
			m.forgeItemName = ps.itemName
			m.forgeManifest = ps.manifest
			m.forgeSprPath = ps.spritePath
			m.forgeProjPath = ps.projectileSpritePath
			m.injectMode = ps.injectMode
			m.heat = 100
			return m, func() tea.Msg { return forgeDoneMsg{} }
		case "error":
			return m, func() tea.Msg { return forgeErrMsg{message: ps.errMsg} }
		default:
			// "building" or file not yet written — update stage and keep polling.
			if ps.stagePct > m.stageTargetPct {
				m.stageTargetPct = ps.stagePct
			}
			if ps.stageLabel != "" {
				m.stageLabel = ps.stageLabel
			}
			return m, pollStatusCmd()
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
		checkBridgeCmd := func() tea.Msg { return bridgeStatusMsg{alive: readBridgeHeartbeat()} }
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
	case injectDoneMsg:
		if msg.err != nil {
			m.injecting = false
			m.injectErr = msg.err.Error()
			return m, nil
		}
		// Trigger written successfully — poll for connector confirmation.
		return m, pollConnectorStatusCmd(0)
	case pollConnectorStatusMsg:
		const maxAttempts = 60 // 30 seconds at 500ms intervals
		if status := readConnectorStatus(); status != "" {
			return m, func() tea.Msg { return connectorStatusMsg{status: status} }
		}
		if msg.attempt >= maxAttempts {
			return m, func() tea.Msg { return connectorStatusMsg{status: "timeout"} }
		}
		return m, pollConnectorStatusCmd(msg.attempt + 1)
	case connectorStatusMsg:
		m.injecting = false
		m.injectStatus = msg.status
		if msg.status == "item_injected" {
			// For instant inject, auto-clear the forge_inject.json to prevent re-inject
			_ = os.Remove(filepath.Join(modSourcesDir(), "forge_inject.json"))
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
			m.appendPreviewHistory()
			if m.injectMode {
				// Write forge_inject.json fresh from stored manifest data.
				// The orchestrator's copy may have been consumed by a prior attempt.
				dir := modSourcesDir()
				_ = os.Remove(filepath.Join(dir, "forge_connector_status.json"))
				if err := writeInjectFile(m.forgeManifest, m.forgeItemName, m.forgeSprPath, m.forgeProjPath); err != nil {
					m.injecting = false
					m.injectErr = err.Error()
					return m, nil
				}
				return m, pollConnectorStatusCmd(0)
			}
			// Legacy: trigger mod reload via command_trigger.json.
			injectCmd := func() tea.Msg {
				return injectDoneMsg{err: writeCommandTrigger()}
			}
			return m, injectCmd
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
			sprite := renderPreviewAnimation(renderSprite(latest.spritePath), latest.contentType, latest.subType, m.animTick)
			stats := renderStats(latest.stats)

			if sprite != "" || stats != "" {
				headerLines = append(headerLines, "")
				var panels []string
				if sprite != "" {
					spriteBox := styles.SpriteFrame.Render(sprite)
					panels = append(panels, spriteBox)
				}
				if stats != "" {
					statsBox := styles.StatsFrame.Render(stats)
					panels = append(panels, statsBox)
				}
				if len(panels) == 2 {
					headerLines = append(headerLines, lipgloss.JoinHorizontal(lipgloss.Top, panels[0], "  ", panels[1]))
				} else if len(panels) == 1 {
					headerLines = append(headerLines, panels[0])
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
		if m.injectMode {
			headerLines = append(headerLines, "", styles.Injecting.Render("⟳ Injecting into Terraria..."))
		} else {
			headerLines = append(headerLines, "", styles.Injecting.Render("⟳ Waiting for Terraria..."))
		}
	case m.injectStatus == "item_injected":
		headerLines = append(headerLines, "", styles.Success.Render("✔ Item appeared in your inventory!"))
		headerLines = append(headerLines, styles.Hint.Render("[C] Craft Another"))
	case m.injectStatus == "inject_failed":
		headerLines = append(headerLines, "", styles.Error.Render("✘ Injection failed"))
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
		_ = os.Remove(filepath.Join(modSourcesDir(), "generation_status.json"))
		extra := map[string]interface{}{}
		if pendingManifest != nil {
			extra["existing_manifest"] = pendingManifest
		}
		if pendingArtFeedback != "" {
			extra["art_feedback"] = pendingArtFeedback
		}
		if err := writeUserRequest(prompt, tier, contentType, subType, craftingStation, extra); err != nil {
			return forgeErrMsg{message: "Failed to write request: " + err.Error()}
		}
		return pollStatusMsg{}
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
	m.injectMode = false
	m.previewMode = previewModeActions
	m.previewItem = nil
	m.statEditIndex = 0
	m.bridgeAlive = false
	m.injectErr = ""
	m.injectStatus = ""
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

func renderPreviewAnimation(sprite, contentType, subType string, tick int) string {
	if sprite == "" {
		return ""
	}
	switch {
	case contentType == "Summon":
		bob := []int{0, 1, 0, 1}[tick%4]
		return fmt.Sprintf("☺\n%s%s", strings.Repeat(" ", bob), sprite)
	case contentType == "Accessory":
		return sprite + "\n+" + " passive aura"
	case contentType == "Consumable":
		if tick%4 == 0 {
			return sprite + "\n gulp"
		}
		return sprite
	case subType == "Gun" || subType == "Bow" || subType == "Staff" || subType == "Cannon":
		return fmt.Sprintf("@ %s %s•", sprite, strings.Repeat(" ", tick%4))
	case subType == "Spear":
		return shiftPreviewSprite(sprite, tick%4)
	default:
		swingMarks := []string{"\\", "|", "/", "-"}
		return fmt.Sprintf("%s %s", swingMarks[tick%len(swingMarks)], shiftPreviewSprite(sprite, tick%3))
	}
}

func shiftPreviewSprite(sprite string, offset int) string {
	if offset <= 0 {
		return sprite
	}
	lines := strings.Split(sprite, "\n")
	for i, line := range lines {
		lines[i] = strings.Repeat(" ", offset) + line
	}
	return strings.Join(lines, "\n")
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

// findOrchestratorPath returns the path to orchestrator.py by checking
// locations relative to the binary and the working directory.
func findOrchestratorPath() string {
	candidates := []string{}
	if exe, err := os.Executable(); err == nil {
		candidates = append(candidates, filepath.Join(filepath.Dir(exe), "..", "agents", "orchestrator.py"))
	}
	if envPath := os.Getenv("FORGE_ORCHESTRATOR_PATH"); envPath != "" {
		candidates = append(candidates, envPath)
	}
	candidates = append(candidates,
		filepath.Join("..", "agents", "orchestrator.py"),
	)
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			abs, _ := filepath.Abs(p)
			return abs
		}
	}
	return ""
}

func trimDotEnvComment(val string) string {
	inQuote := byte(0)
	escaped := false

	for i := 0; i < len(val); i++ {
		ch := val[i]

		if escaped {
			escaped = false
			continue
		}
		if inQuote != 0 {
			if ch == '\\' {
				escaped = true
				continue
			}
			if ch == inQuote {
				inQuote = 0
			}
			continue
		}

		switch ch {
		case '"', '\'':
			inQuote = ch
		case '#':
			if i == 0 || val[i-1] == ' ' || val[i-1] == '\t' {
				return strings.TrimSpace(val[:i])
			}
		}
	}

	return strings.TrimSpace(val)
}

// parseDotEnv reads a .env file and returns key=value pairs.
// Handles quoted values and strips inline comments outside quotes.
func parseDotEnv(path string) []string {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var pairs []string
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		eqIdx := strings.Index(line, "=")
		if eqIdx < 0 {
			continue
		}
		key := strings.TrimSpace(line[:eqIdx])
		val := strings.TrimSpace(line[eqIdx+1:])
		val = trimDotEnvComment(val)

		// Strip surrounding quotes.
		if len(val) >= 2 && ((val[0] == '"' && val[len(val)-1] == '"') || (val[0] == '\'' && val[len(val)-1] == '\'')) {
			val = val[1 : len(val)-1]
		}

		pairs = append(pairs, key+"="+val)
	}
	return pairs
}

// ensureOrchestrator starts orchestrator.py if it is not already running.
// Logs are appended to orchestrator.log in the agents directory.
func ensureOrchestrator() {
	orchPath := findOrchestratorPath()
	if orchPath == "" {
		fmt.Fprintln(os.Stderr, "[forge] orchestrator.py not found — set FORGE_ORCHESTRATOR_PATH or run from the project root")
		return
	}

	// Skip only if the orchestrator heartbeat shows a live Python daemon.
	if readOrchestratorHeartbeat() {
		return
	}

	agentsDir := filepath.Dir(orchPath)
	logPath := filepath.Join(agentsDir, "orchestrator.log")
	logFile, _ := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)

	// Prefer the project venv's Python so all dependencies are available.
	python := filepath.Join(agentsDir, ".venv", "bin", "python3")
	if _, err := os.Stat(python); err != nil {
		python = "python3"
	}

	cmd := exec.Command(python, orchPath)
	cmd.Dir = agentsDir

	// Inherit current environment and inject .env vars so API keys are available.
	cmd.Env = append(os.Environ(), parseDotEnv(filepath.Join(agentsDir, ".env"))...)

	if logFile != nil {
		cmd.Stdout = logFile
		cmd.Stderr = logFile
	}
	if err := cmd.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "[forge] failed to start orchestrator: %v\n", err)
	}
}

func main() {
	ensureOrchestrator()
	p := tea.NewProgram(initialModel(), tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "error running forge ui: %v\n", err)
		os.Exit(1)
	}
}
