package main

import (
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/muesli/termenv"

	"theforge/internal/ipc"
)

func TestParseDotEnvStripsCommentsOutsideQuotes(t *testing.T) {
	envPath := filepath.Join(t.TempDir(), ".env")
	content := "" +
		"OPENAI_API_KEY=\"sk-test\" # local key\n" +
		"PLAIN=value # trailing comment\n" +
		"HASHED=\"value # keep this\"\n" +
		"SINGLE='two words' # note\n"
	if err := os.WriteFile(envPath, []byte(content), 0644); err != nil {
		t.Fatalf("write env: %v", err)
	}

	got := parseDotEnv(envPath)
	want := []string{
		"OPENAI_API_KEY=sk-test",
		"PLAIN=value",
		"HASHED=value # keep this",
		"SINGLE=two words",
	}

	if len(got) != len(want) {
		t.Fatalf("parseDotEnv() returned %d pairs, want %d: %#v", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("parseDotEnv()[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

func TestReadOrchestratorHeartbeatUsesDistinctFile(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	dir := modSourcesDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	bridgeHeartbeat := []byte(`{"status":"listening","pid":` + strconv.Itoa(os.Getpid()) + `}`)
	if err := os.WriteFile(filepath.Join(dir, "forge_connector_alive.json"), bridgeHeartbeat, 0644); err != nil {
		t.Fatalf("write bridge heartbeat: %v", err)
	}

	if !readBridgeHeartbeat() {
		t.Fatal("readBridgeHeartbeat() = false, want true for live bridge heartbeat")
	}
	if readOrchestratorHeartbeat() {
		t.Fatal("readOrchestratorHeartbeat() = true with only bridge heartbeat present")
	}

	orchestratorHeartbeat := []byte(`{"status":"listening","pid":` + strconv.Itoa(os.Getpid()) + `}`)
	if err := os.WriteFile(filepath.Join(dir, "orchestrator_alive.json"), orchestratorHeartbeat, 0644); err != nil {
		t.Fatalf("write orchestrator heartbeat: %v", err)
	}

	if !readOrchestratorHeartbeat() {
		t.Fatal("readOrchestratorHeartbeat() = false, want true for live orchestrator heartbeat")
	}
}

func TestInitialModelStartsAtShellPrompt(t *testing.T) {
	m := initialModel()
	if m.state != screenInput {
		t.Fatalf("initial state = %v, want %v", m.state, screenInput)
	}
	// Placeholder is intentionally empty — the splash header provides context.
	if m.commandInput.Focused() != true {
		t.Fatal("command input should be focused on startup")
	}
}

func TestInitialModelOmitsStandalonePromptFormInStartupView(t *testing.T) {
	m := initialModel()

	got := m.View()
	if strings.Contains(got, "Describe your item") {
		t.Fatalf("startup view = %q, want it to omit the legacy standalone prompt form from the main body", got)
	}
	lines := strings.Split(strings.TrimSpace(got), "\n")
	if len(lines) < 2 || !strings.Contains(lines[len(lines)-1], "─") {
		t.Fatalf("startup view = %q, want a separator line at the bottom", got)
	}
	if !strings.HasPrefix(strings.TrimSpace(lines[len(lines)-2]), ">") {
		t.Fatalf("startup view = %q, want prompt line above the separator", got)
	}
}

func TestInitialModelHydratesSessionShellAndWorkshopStatusFromMirroredFiles(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	sessionShellStatus := `{
  "session_id": "sess-1",
  "snapshot_id": 9,
  "recent_events": [
    {"kind": "prompt", "message": "Forge: Storm Brand"},
    {"kind": "system", "message": "Forge progress 47%"}
  ],
  "pinned_notes": ["keep the cashout"]
}`
	if err := os.WriteFile(filepath.Join(modSources, "session_shell_status.json"), []byte(sessionShellStatus), 0644); err != nil {
		t.Fatalf("write session_shell_status.json: %v", err)
	}

	workshopStatus := `{
  "session_id": "bench-storm-brand",
  "bench": {
    "item_id": "storm-brand",
    "label": "Storm Brand",
    "manifest": {
      "type": "Weapon",
      "sub_type": "Staff",
      "crafting_station": "Mythril Anvil"
    }
  },
  "shelf": [
    {"variant_id": "storm-brand-v1", "label": "Heavier Shot"}
  ],
  "last_action": "ready"
}`
	if err := os.WriteFile(filepath.Join(modSources, "workshop_status.json"), []byte(workshopStatus), 0644); err != nil {
		t.Fatalf("write workshop_status.json: %v", err)
	}

	m := initialModel()

	if got := len(m.sessionShell.events); got != 0 {
		t.Fatalf("startup session events = %d, want noisy prompt/runtime/system rows filtered out", got)
	}
	if got := m.workshop.SessionID; got != "bench-storm-brand" {
		t.Fatalf("startup workshop session = %q, want bench-storm-brand", got)
	}
	if got := m.workshop.Bench.Label; got != "Storm Brand" {
		t.Fatalf("startup bench label = %q, want Storm Brand", got)
	}
	if got := len(m.workshop.Shelf); got != 1 {
		t.Fatalf("startup shelf len = %d, want 1 hydrated shelf variant", got)
	}
	if got := m.workshop.Shelf[0].VariantID; got != "storm-brand-v1" {
		t.Fatalf("startup shelf variant = %q, want storm-brand-v1", got)
	}
	if !m.hasActiveWorkshopBench() {
		t.Fatal("startup model has no active workshop bench, want hydrated bench context")
	}
	if got := m.shellSuggestion(); got != "/bench <variant-id-or-number>" {
		t.Fatalf("startup shell suggestion = %q, want /bench <variant-id-or-number>", got)
	}

	gotView := m.View()
	if strings.Contains(gotView, "↳ Welcome back") || strings.Contains(gotView, "Bench Storm Brand ready") {
		t.Fatalf("startup shell view = %q, want duplicate active-bench welcome removed", gotView)
	}
}

func TestInitialModelInitializesRuntimeFreshnessOnStartup(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	heartbeat := []byte(`{"status":"listening","pid":` + strconv.Itoa(os.Getpid()) + `}`)
	if err := os.WriteFile(filepath.Join(modSources, "forge_connector_alive.json"), heartbeat, 0644); err != nil {
		t.Fatalf("write bridge heartbeat: %v", err)
	}

	m := initialModel()
	if !m.bridgeAlive {
		t.Fatal("startup bridgeAlive = false, want true from live bridge heartbeat")
	}
	if got := m.View(); strings.Contains(got, "↳ Welcome back") {
		t.Fatalf("startup shell view = %q, want no welcome message without an active bench", got)
	}
	if got := m.View(); !strings.Contains(got, "\n> ") || strings.Contains(got, "offline") {
		t.Fatalf("startup shell view = %q, want a prompt-only layout without top status text", got)
	}

	cmd := m.Init()
	if cmd == nil {
		t.Fatal("startup Init command = nil, want startup runtime freshness commands")
	}
	msg := cmd()
	batch, ok := msg.(tea.BatchMsg)
	if !ok {
		t.Fatalf("startup Init command returned %T, want tea.BatchMsg", msg)
	}
	if got := len(batch); got < 4 {
		t.Fatalf("startup command count = %d, want runtime freshness command included with startup commands", got)
	}
}

func TestFeedEventUpdatesPersistBackToSessionShellStatus(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	initialStatus := `{
  "session_id": "sess-1",
  "snapshot_id": 9,
  "recent_events": [
    {"kind": "runtime", "message": "Forge progress: 47%"},
    {"kind": "system", "message": "Bench ready"}
  ],
  "pinned_notes": ["keep the cashout"]
}`
	if err := os.WriteFile(filepath.Join(modSources, "session_shell_status.json"), []byte(initialStatus), 0644); err != nil {
		t.Fatalf("write session_shell_status.json: %v", err)
	}

	m := initialModel()
	m.upsertFeedEvent(sessionEventKindRuntime, "Forge progress: 58%")
	m.appendFeedEvent(sessionEventKindSystem, "Workshop action sent: bench")

	raw, err := os.ReadFile(filepath.Join(modSources, "session_shell_status.json"))
	if err != nil {
		t.Fatalf("read session_shell_status.json: %v", err)
	}

	var payload struct {
		SessionID    string   `json:"session_id"`
		SnapshotID   int      `json:"snapshot_id"`
		PinnedNotes  []string `json:"pinned_notes"`
		RecentEvents []struct {
			Kind    string `json:"kind"`
			Message string `json:"message"`
		} `json:"recent_events"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		t.Fatalf("unmarshal session shell status: %v", err)
	}

	if payload.SessionID != "sess-1" {
		t.Fatalf("session_id = %q, want sess-1", payload.SessionID)
	}
	if payload.SnapshotID != 9 {
		t.Fatalf("snapshot_id = %d, want 9", payload.SnapshotID)
	}
	if len(payload.PinnedNotes) != 1 || payload.PinnedNotes[0] != "keep the cashout" {
		t.Fatalf("pinned_notes = %#v, want keep the cashout", payload.PinnedNotes)
	}
	if got := len(payload.RecentEvents); got != 0 {
		t.Fatalf("recent_events = %d, want noisy runtime/system rows omitted from persistence", got)
	}
}

func TestInitialModelDropsNoisyFeedEventsFromPersistedSessionShellStatus(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	status := `{
  "session_id": "sess-1",
  "snapshot_id": 9,
  "recent_events": [
    {"kind": "prompt", "message": "Forge: radiant spear"},
    {"kind": "runtime", "message": "Forge progress: 40%"},
    {"kind": "system", "message": "Workshop Ready"},
    {"kind": "memory", "message": "keep the cashout"}
  ],
  "pinned_notes": ["keep the cashout"]
}`
	if err := os.WriteFile(filepath.Join(modSources, "session_shell_status.json"), []byte(status), 0644); err != nil {
		t.Fatalf("write session_shell_status.json: %v", err)
	}

	m := initialModel()

	if got := len(m.sessionShell.events); got != 1 {
		t.Fatalf("startup visible session events = %d, want only the non-noisy memory entry", got)
	}
	if got := m.sessionShell.events[0].Kind; got != sessionEventKindMemory {
		t.Fatalf("startup visible session event kind = %q, want memory", got)
	}
	if got := m.sessionShell.events[0].Message; got != "keep the cashout" {
		t.Fatalf("startup visible session event message = %q, want keep the cashout", got)
	}
	if strings.Contains(m.View(), "Forge progress") || strings.Contains(m.View(), "Workshop Ready") || strings.Contains(m.View(), "Forge: radiant spear") {
		t.Fatalf("startup session shell view = %q, want noisy prompt/runtime/system rows removed", m.View())
	}
}

func TestInitialModelShowsWelcomeMessageForActiveBench(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	workshopStatus := `{
  "session_id": "bench-applegun",
  "bench": {"item_id": "apple-gun", "label": "AppleGun", "manifest": {"type": "Weapon"}},
  "shelf": [],
  "last_action": "ready"
}`
	if err := os.WriteFile(filepath.Join(modSources, "workshop_status.json"), []byte(workshopStatus), 0644); err != nil {
		t.Fatalf("write workshop_status.json: %v", err)
	}

	m := initialModel()
	got := m.View()
	if strings.Contains(got, "↳ Welcome back") || strings.Contains(got, "Bench AppleGun ready") {
		t.Fatalf("startup shell view = %q, want duplicate active-bench welcome removed", got)
	}
}

func TestWorkshopRequestPayloadCarriesSnapshotIDFromWorkshopStatus(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	workshopStatus := `{
  "session_id": "sess-1",
  "snapshot_id": 7,
  "bench": {
    "item_id": "storm-brand",
    "label": "Storm Brand",
    "manifest": {"type": "Weapon"}
  },
  "shelf": [
    {"variant_id": "storm-brand-v1", "label": "Heavier Shot"}
  ],
  "last_action": "ready"
}`
	if err := os.WriteFile(filepath.Join(modSources, "workshop_status.json"), []byte(workshopStatus), 0644); err != nil {
		t.Fatalf("write workshop_status.json: %v", err)
	}

	m := initialModel()
	m.state = screenStaging
	m.commandMode = true
	m.commandInput.SetValue("/bench 1")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}
	if next.commandMode {
		t.Fatal("command mode still enabled after sending workshop request")
	}

	raw, err := os.ReadFile(filepath.Join(modSources, "workshop_request.json"))
	if err != nil {
		t.Fatalf("read workshop_request.json: %v", err)
	}

	var payload map[string]interface{}
	if err := json.Unmarshal(raw, &payload); err != nil {
		t.Fatalf("unmarshal workshop request: %v", err)
	}

	if got := payload["session_id"]; got != "sess-1" {
		t.Fatalf("session_id = %#v, want sess-1", got)
	}
	if got := payload["bench_item_id"]; got != "storm-brand" {
		t.Fatalf("bench_item_id = %#v, want storm-brand", got)
	}
	if got := payload["snapshot_id"]; got != float64(7) {
		t.Fatalf("snapshot_id = %#v, want 7", got)
	}
	if got := payload["variant_id"]; got != "storm-brand-v1" {
		t.Fatalf("variant_id = %#v, want storm-brand-v1", got)
	}
}

func TestSessionShellRendersThreeRegions(t *testing.T) {
	m := initialModel()
	m.state = screenInput
	m.commandInput.SetValue("forge the shell")

	got := m.View()
	if !strings.Contains(got, "> ") {
		t.Fatalf("session shell render = %q, want a raw prompt line", got)
	}
	if strings.Contains(got, "Sigils") {
		t.Fatalf("session shell render = %q, want it to omit legacy shell chrome", got)
	}
	if strings.Contains(got, "Feed Container") {
		t.Fatalf("session shell render = %q, want feed frame chrome removed", got)
	}
	if strings.Contains(got, " | ") {
		t.Fatalf("session shell render = %q, want status line without pipe separators", got)
	}
	// Splash header intentionally contains "The Forge" — check framed title block is gone instead.
	if strings.Contains(got, "╭") || strings.Contains(got, "╰") {
		t.Fatalf("session shell render = %q, want the framed title block removed", got)
	}
	if strings.Contains(got, "Esc manual mode") {
		t.Fatalf("session shell render = %q, want the mode hint removed", got)
	}
	if strings.Contains(got, "/forge") || strings.Contains(got, "/variants") || strings.Contains(got, "/bench") {
		t.Fatalf("session shell render = %q, want no inline command suggestions in the footer", got)
	}
	if !strings.Contains(got, "─") {
		t.Fatalf("session shell render = %q, want a terminal separator line above the prompt", got)
	}
}

func TestInputShell(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	if m.hasActiveWorkshopBench() {
		t.Fatalf("initial model has an active bench, want none")
	}

	m.commandInput.SetValue("radiant spear")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}

	if next.state != screenForge {
		t.Fatalf("initial shell Enter state = %v, want %v for forge prompt entry", next.state, screenForge)
	}
	if got := strings.TrimSpace(next.prompt); got != "radiant spear" {
		t.Fatalf("forge prompt = %q, want radiant spear", got)
	}
	if got := next.View(); !strings.Contains(got, "\n> ") || strings.Contains(got, "offline") {
		t.Fatalf("shell view = %q, want prompt-only chrome without top status text", got)
	}
}

func TestInputShellLocalCommandsRenderVisibleResponse(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("/help")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}

	got := next.View()
	if !strings.Contains(got, "Commands:") {
		t.Fatalf("shell view = %q, want visible /help response", got)
	}
}

func TestStagingSharedCommandBarLocalCommandsRenderVisibleResponse(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenStaging
	m.commandInput.Focus()
	m.commandInput.SetValue("/status")
	m.workshop.Bench = workshopBench{
		ItemID: "apple-gun",
		Label:  "AppleGun",
	}

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}

	got := next.View()
	if !strings.Contains(got, "Status:") || !strings.Contains(got, "AppleGun") {
		t.Fatalf("staging shell view = %q, want visible /status response", got)
	}
	if next.commandMode {
		t.Fatal("director command mode enabled after local command")
	}
}

func TestStagingSlashUsesSharedCommandBarWithoutDirectorPanel(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenStaging
	m.commandMode = false
	m.commandInput.SetValue("")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	next := updated.(model)

	if next.commandMode {
		t.Fatal("slash opened director command mode, want shared command bar")
	}
	if next.commandInput.Value() != "/" {
		t.Fatalf("command input = %q, want slash in shared command bar", next.commandInput.Value())
	}
	if strings.Contains(next.View(), "Director") {
		t.Fatalf("view contains Director panel: %q", next.View())
	}
}

func stagingPreviewTestModel(t *testing.T, compact bool, contentWidth int) model {
	t.Helper()

	home := t.TempDir()
	t.Setenv("HOME", home)
	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)
	if err := os.MkdirAll(modSources, 0755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	m := initialModel()
	m.state = screenStaging
	m.termCompact = compact
	m.contentWidth = contentWidth
	m.revealPhase = 3
	m.bridgeAlive = true
	m.workshop.Runtime.BridgeAlive = true
	m.previewItem = &craftedItem{
		label:       "Storm Brand",
		contentType: "Weapon",
		subType:     "Staff",
		stats: itemStats{
			Damage:  18,
			UseTime: 22,
		},
	}
	m.workshop.Bench = workshopBench{
		ItemID: "storm-brand",
		Label:  "Storm Brand",
		Manifest: map[string]interface{}{
			"type":     "Weapon",
			"sub_type": "Staff",
		},
	}
	return m
}

func writeStagingPreviewSprite(t *testing.T, dir string, name string) string {
	t.Helper()

	path := filepath.Join(dir, name)
	img := image.NewRGBA(image.Rect(0, 0, 16, 16))
	for y := 0; y < 16; y++ {
		for x := 0; x < 16; x++ {
			img.Set(x, y, color.RGBA{R: 80, G: 220, B: 128, A: 255})
		}
	}

	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create preview sprite: %v", err)
	}
	defer file.Close()

	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode preview sprite: %v", err)
	}
	return path
}

func TestRenderSpriteImageUsesWhiteMatteForTransparentPixels(t *testing.T) {
	previousProfile := lipgloss.ColorProfile()
	lipgloss.SetColorProfile(termenv.TrueColor)
	t.Cleanup(func() {
		lipgloss.SetColorProfile(previousProfile)
	})

	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	img.Set(0, 0, color.Transparent)
	img.Set(0, 1, color.RGBA{R: 255, G: 0, B: 0, A: 255})
	img.Set(1, 0, color.RGBA{R: 0, G: 255, B: 0, A: 255})
	img.Set(1, 1, color.Transparent)

	got := renderSpriteImage(img)

	if !strings.Contains(got, "255;255;255") {
		t.Fatalf("renderSpriteImage() = %q, want white matte background for transparent pixels", got)
	}
}

func TestSpritePreviewPreservesFullCanvasAndUpscalesTwoX(t *testing.T) {
	path := filepath.Join(t.TempDir(), "padded.png")
	img := image.NewRGBA(image.Rect(0, 0, 4, 4))
	img.Set(2, 1, color.RGBA{R: 255, G: 0, B: 0, A: 255})

	file, err := os.Create(path)
	if err != nil {
		t.Fatalf("create padded sprite: %v", err)
	}
	if err := png.Encode(file, img); err != nil {
		t.Fatalf("encode padded sprite: %v", err)
	}
	if err := file.Close(); err != nil {
		t.Fatalf("close padded sprite: %v", err)
	}

	loaded, ok := loadSpriteImage(path)
	if !ok {
		t.Fatal("loadSpriteImage() = false, want padded sprite to load")
	}
	if got := loaded.Bounds().Dx(); got != 4 {
		t.Fatalf("loaded width = %d, want full canvas width 4", got)
	}
	if got := loaded.Bounds().Dy(); got != 4 {
		t.Fatalf("loaded height = %d, want full canvas height 4", got)
	}

	rendered := renderSpriteImage(loaded)
	lines := strings.Split(rendered, "\n")
	if got := len(lines); got != 4 {
		t.Fatalf("rendered rows = %d, want 2x canvas height rendered as 4 terminal rows", got)
	}
	for i, line := range lines {
		if got := lipgloss.Width(line); got != 8 {
			t.Fatalf("rendered line %d width = %d, want 2x canvas width 8\n%s", i, got, rendered)
		}
	}
}

func TestStagingViewPreviewLinesDoNotExceedTerminalWidth(t *testing.T) {
	m := stagingPreviewTestModel(t, false, 96)

	got := m.stagingView()
	for i, line := range strings.Split(got, "\n") {
		if width := lipgloss.Width(line); width > m.contentWidth {
			t.Fatalf("stagingView line %d width = %d, want <= %d\n%s", i, width, m.contentWidth, got)
		}
	}
}

func TestStagingViewPreviewPanelsStackAt100Columns(t *testing.T) {
	m := stagingPreviewTestModel(t, false, 100)
	spriteDir := t.TempDir()
	m.previewItem.spritePath = writeStagingPreviewSprite(t, spriteDir, "item.png")
	m.previewItem.projSpritePath = writeStagingPreviewSprite(t, spriteDir, "projectile.png")

	spritePanel := styles.SpriteFrame.Render(renderSprite(m.previewItem.spritePath))
	projectilePanel := styles.SpriteFrame.Render(renderSprite(m.previewItem.projSpritePath))
	statsPanel := styles.StatsFrame.Render(renderStats(m.previewItem.stats))
	horizontalWidth := lipgloss.Width(lipgloss.JoinHorizontal(
		lipgloss.Top,
		spritePanel,
		styles.Hint.Render("→"),
		projectilePanel,
		statsPanel,
	))

	got := m.stagingView()
	for i, line := range strings.Split(got, "\n") {
		if width := lipgloss.Width(line); width >= horizontalWidth {
			t.Fatalf("stagingView line %d width = %d, want stacked panels narrower than horizontal width %d\n%s", i, width, horizontalWidth, got)
		}
	}
}

func TestInputShellTryUsesActiveBench(t *testing.T) {
	home := t.TempDir()
	modSources := filepath.Join(home, "ModSources")
	t.Setenv("HOME", home)
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	m := initialModel()
	m.workshop.SessionID = "bench-storm-brand"
	m.workshop.SnapshotID = 7
	m.workshop.Bench = workshopBench{
		ItemID: "storm-brand",
		Label:  "Storm Brand",
		Manifest: map[string]interface{}{
			"type": "Weapon",
		},
	}
	m.commandInput.SetValue("/try")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}

	if next.state != screenStaging {
		t.Fatalf("state after /try = %v, want %v", next.state, screenStaging)
	}
	if !next.injecting {
		t.Fatal("injecting = false, want true after /try")
	}

	data, err := os.ReadFile(filepath.Join(modSources, "forge_inject.json"))
	if err != nil {
		t.Fatalf("read forge_inject.json: %v", err)
	}
	var payload map[string]interface{}
	if err := json.Unmarshal(data, &payload); err != nil {
		t.Fatalf("unmarshal forge_inject.json: %v", err)
	}
	if got := payload["item_name"]; got != "Storm Brand" {
		t.Fatalf("item_name = %#v, want Storm Brand", got)
	}
}

func TestWizardShell(t *testing.T) {
	m := initialModel()
	m.state = screenMode

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}
	if next.state != screenWizard {
		t.Fatalf("mode selection state = %v, want %v after choosing the manual wizard path", next.state, screenWizard)
	}
	if !next.contentTypeExplicit {
		t.Fatal("contentTypeExplicit = false, want true after choosing the manual wizard path")
	}
	if got := next.View(); !strings.Contains(got, "\n> ") || strings.Contains(got, "offline") {
		t.Fatalf("wizard shell view = %q, want prompt-only chrome without top status text", got)
	}
}

func TestModeShellEscReturnsToInput(t *testing.T) {
	m := initialModel()
	m.state = screenInput

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	mode, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}
	if mode.state != screenMode {
		t.Fatalf("state after first Esc = %v, want %v", mode.state, screenMode)
	}
	if got := mode.modeView(); !strings.Contains(got, "Esc back") {
		t.Fatalf("mode view = %q, want visible Esc back hint", got)
	}

	updated, _ = mode.Update(tea.KeyMsg{Type: tea.KeyEsc})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}
	if next.state != screenInput {
		t.Fatalf("state after second Esc = %v, want %v", next.state, screenInput)
	}
	if next.contentTypeExplicit {
		t.Fatal("contentTypeExplicit = true, want false after returning from mode selection without choosing")
	}
}

func TestForgeToInjectFlow(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("FORGE_MOD_SOURCES_DIR", dir)

	m := initialModel()
	m.commandInput.SetValue("moonlit hook")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}
	if next.state != screenForge {
		t.Fatalf("forge flow start state = %v, want %v", next.state, screenForge)
	}

	if err := os.WriteFile(filepath.Join(dir, "generation_status.json"), []byte(`{"status":"ready","item_name":"Moonlit Hook","manifest":{"stats":{"damage":12}}}`), 0644); err != nil {
		t.Fatalf("write ready status: %v", err)
	}
	updated, _ = next.Update(ipc.PollStatusMsg{})
	ready, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}
	if ready.state != screenForge {
		t.Fatalf("forge flow ready poll state = %v, want %v", ready.state, screenForge)
	}
	if got := ready.View(); !strings.Contains(got, "\n> ") || strings.Contains(got, "offline") {
		t.Fatalf("ready shell view = %q, want prompt-only chrome without top status text", got)
	}

	updated, _ = ready.Update(forgeDoneMsg{})
	staged, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}
	if staged.state != screenStaging {
		t.Fatalf("forge flow staged state = %v, want %v", staged.state, screenStaging)
	}
	if got := staged.View(); !strings.Contains(got, "\n> ") || strings.Contains(got, "offline") {
		t.Fatalf("staged shell view = %q, want prompt-only chrome without top status text", got)
	}
}

func TestForgeShowsTransientOperationFeedback(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("moonlit hook")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}

	got := next.View()
	if !strings.Contains(got, "Forging moonlit hook") {
		t.Fatalf("forge shell view = %q, want transient forge operation feedback", got)
	}
}

func TestForgeShowsStaleAndTimeoutFeedback(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.prompt = "moonlit hook"
	updated, _ := m.enterForge()
	m = updated.(model)

	for i := 0; i < forgeStalePollThreshold; i++ {
		updated, _ = m.Update(ipc.PollStatusMsg{})
		m = updated.(model)
	}
	if got := m.View(); !strings.Contains(got, "Forge slow") {
		t.Fatalf("stale forge view = %q, want stale forge feedback", got)
	}

	for i := forgeStalePollThreshold; i < forgeTimeoutPollThreshold-1; i++ {
		updated, _ = m.Update(ipc.PollStatusMsg{})
		m = updated.(model)
	}
	updated, cmd := m.Update(ipc.PollStatusMsg{})
	m = updated.(model)
	if cmd == nil {
		t.Fatal("timeout poll command = nil, want forgeErrMsg command")
	}
	updated, _ = m.Update(cmd())
	m = updated.(model)
	if m.forgeErr != "Forge timed out." {
		t.Fatalf("forgeErr = %q, want Forge timed out.", m.forgeErr)
	}
	if got := m.View(); !strings.Contains(got, "Forge timed out.") {
		t.Fatalf("timeout forge view = %q, want timeout error feedback", got)
	}
}

func TestSessionShellCommandBarIsPlainTextPrompt(t *testing.T) {
	m := initialModel()

	got := m.View()
	lines := strings.Split(strings.TrimSpace(got), "\n")
	if len(lines) < 2 || !strings.Contains(lines[len(lines)-1], "─") {
		t.Fatalf("command bar render = %q, want a separator line at the bottom", got)
	}
	if !strings.HasPrefix(strings.TrimSpace(lines[len(lines)-2]), ">") {
		t.Fatalf("command bar render = %q, want prompt line above the separator", got)
	}
	if strings.Contains(lines[len(lines)-2], "Describe your forged item") {
		t.Fatalf("command bar render = %q, want no placeholder text in the prompt line", got)
	}
}

func TestSessionShellAnchorsToBottomOfTerminal(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.workshop.Bench = workshopBench{ItemID: "apple-gun", Label: "AppleGun"}
	m.width = 120
	m.height = 40

	got := m.View()
	lines := strings.Split(got, "\n")
	firstNonEmpty := -1
	for i, line := range lines {
		if strings.TrimSpace(line) != "" {
			firstNonEmpty = i
			break
		}
	}
	if firstNonEmpty <= 0 {
		t.Fatalf("session shell render = %q, want the first non-empty line to appear after leading terminal whitespace", got)
	}
	if !strings.Contains(got, "The Forge") {
		t.Fatalf("session shell render = %q, want splash header", got)
	}
	if strings.Contains(got, "↳ Welcome back") {
		t.Fatalf("session shell render = %q, want duplicate welcome message removed", got)
	}
}

func TestSessionShellDoesNotLeaveLargeGapBeforePrompt(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.workshop.Bench = workshopBench{ItemID: "apple-gun", Label: "AppleGun"}
	m.width = 120
	m.height = 40

	got := m.View()
	lines := strings.Split(got, "\n")
	splashIndex := -1
	promptIndex := -1
	for i, line := range lines {
		trimmed := strings.TrimSpace(line)
		if splashIndex < 0 && strings.Contains(trimmed, "The Forge") {
			splashIndex = i
		}
		if strings.HasPrefix(trimmed, ">") {
			promptIndex = i
			break
		}
	}
	if splashIndex < 0 {
		t.Fatalf("session shell render = %q, want splash header", got)
	}
	if promptIndex < 0 {
		t.Fatalf("session shell render = %q, want a visible prompt line", got)
	}
	if promptIndex-splashIndex > 6 {
		t.Fatalf("session shell render = %q, want the prompt to sit directly under the separator line", got)
	}
}

func TestSessionShellUsesTerminalWidthForSeparator(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 40, Height: 12})
	next := updated.(model)

	got := next.View()
	for _, line := range strings.Split(got, "\n") {
		if lipgloss.Width(line) > 40 {
			t.Fatalf("line width = %d for %q, want <= 40 in view %q", lipgloss.Width(line), line, got)
		}
	}
	if !strings.Contains(got, strings.Repeat("─", 36)) {
		t.Fatalf("view = %q, want separator derived from terminal width", got)
	}
}

func TestConfigureWizardStepUsesSubtypeOptionsForContentType(t *testing.T) {
	m := initialModel()
	m.contentType = "Accessory"
	m.wizardIndex = 0
	m.configureWizardStep()

	items := m.wizardList.Items()
	var titles []string
	for _, item := range items {
		option, ok := item.(optionItem)
		if !ok {
			t.Fatalf("wizard item has unexpected type %T", item)
		}
		titles = append(titles, option.title)
	}

	want := []string{"Wings", "Shield", "Movement", "StatBoost"}
	if strings.Join(titles, ",") != strings.Join(want, ",") {
		t.Fatalf("wizard titles = %v, want %v", titles, want)
	}
}

func TestWriteUserRequestIncludesContentMetadataAndRepromptFields(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	manifest := map[string]interface{}{
		"item_name": "EchoHook",
		"stats": map[string]interface{}{
			"damage": 24,
		},
	}
	extra := map[string]interface{}{
		"existing_manifest": manifest,
		"art_feedback":      "more chain detail",
	}

	if err := writeUserRequest("Echo Hook", "Hardmode", "Tool", "Hook", "", true, extra); err != nil {
		t.Fatalf("writeUserRequest() error = %v", err)
	}

	data, err := os.ReadFile(filepath.Join(modSourcesDir(), "user_request.json"))
	if err != nil {
		t.Fatalf("read user_request.json: %v", err)
	}

	var payload map[string]interface{}
	if err := json.Unmarshal(data, &payload); err != nil {
		t.Fatalf("unmarshal payload: %v", err)
	}

	if got := payload["content_type"]; got != "Tool" {
		t.Fatalf("content_type = %#v, want Tool", got)
	}
	if got := payload["content_type_explicit"]; got != true {
		t.Fatalf("content_type_explicit = %#v, want true", got)
	}
	if got := payload["sub_type"]; got != "Hook" {
		t.Fatalf("sub_type = %#v, want Hook", got)
	}
	if got := payload["art_feedback"]; got != "more chain detail" {
		t.Fatalf("art_feedback = %#v, want reprompt text", got)
	}
	if _, ok := payload["existing_manifest"].(map[string]interface{}); !ok {
		t.Fatalf("existing_manifest missing or wrong type: %#v", payload["existing_manifest"])
	}
}

func TestAdjustPreviewStatMutatesManifest(t *testing.T) {
	m := initialModel()
	m.forgeManifest = map[string]interface{}{
		"stats": map[string]interface{}{
			"damage":      float64(12),
			"use_time":    float64(20),
			"knockback":   float64(4.5),
			"crit_chance": float64(4),
			"rarity":      "ItemRarityID.White",
		},
	}
	item := craftedItem{}
	m.previewItem = &item
	m.previewItem.stats = extractItemStats(m.forgeManifest)

	m.statEditIndex = 0
	m.adjustPreviewStat(1)

	statsMap := m.forgeManifest["stats"].(map[string]interface{})
	if got := statsMap["damage"]; got != float64(13) {
		t.Fatalf("damage after tweak = %#v, want 13", got)
	}
	if got := m.previewItem.stats.Damage; got != 13 {
		t.Fatalf("preview damage = %d, want 13", got)
	}

	m.statEditIndex = 2
	m.adjustPreviewStat(1)
	if got := statsMap["knockback"]; got != float64(5) {
		t.Fatalf("knockback after tweak = %#v, want 5.0", got)
	}
}

func TestModSourcesDirHonorsConfigTomlWhenEnvUnset(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("FORGE_MOD_SOURCES_DIR", "")

	custom := filepath.Join(home, "custom", "ModSources")
	writeForgeConfigWithModSources(t, home, custom)

	got := modSourcesDir()
	if got != custom {
		t.Fatalf("modSourcesDir() = %q, want config mod_sources_dir %q", got, custom)
	}
}

func TestModSourcesDirPrefersEnvOverConfig(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	envDir := filepath.Join(home, "from-env")
	cfgDir := filepath.Join(home, "from-config")
	t.Setenv("FORGE_MOD_SOURCES_DIR", envDir)
	writeForgeConfigWithModSources(t, home, cfgDir)

	got := modSourcesDir()
	if got != envDir {
		t.Fatalf("modSourcesDir() = %q, want FORGE_MOD_SOURCES_DIR %q", got, envDir)
	}
}

func TestMergeGatekeeperGenerationStatus(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	rootJSON := `{"status":"building","stage_label":"Gatekeeper — Compiling mod...","stage_pct":80}`
	if err := os.WriteFile(filepath.Join(ms, "generation_status.json"), []byte(rootJSON), 0644); err != nil {
		t.Fatalf("write root status: %v", err)
	}
	gkJSON := `{"status":"building","message":"Compiling C#..."}`
	if err := os.WriteFile(filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"), []byte(gkJSON), 0644); err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := readGenerationStatus()
	if ps.status != "building" {
		t.Fatalf("status = %q, want building", ps.status)
	}
	if ps.stagePct < 85 {
		t.Fatalf("stagePct = %d, want at least 85 from gatekeeper merge", ps.stagePct)
	}
	if !strings.Contains(ps.stageLabel, "Compiling") {
		t.Fatalf("stageLabel = %q, want gatekeeper message merged", ps.stageLabel)
	}
}

func TestReadGenerationStatusDoesNotMergeWhenRootStatusEmpty(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(ms, "generation_status.json"), []byte(`{}`), 0644); err != nil {
		t.Fatalf("write root status: %v", err)
	}
	if err := os.WriteFile(
		filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"),
		[]byte(`{"status":"building","message":"should-not-merge"}`),
		0644,
	); err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := readGenerationStatus()
	if ps.status != "" {
		t.Fatalf("status = %q, want empty when root has no status field", ps.status)
	}
}

func TestReadGenerationStatusIgnoresGatekeeperWithoutRoot(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	err := os.WriteFile(
		filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"),
		[]byte(`{"status":"building","message":"stale-only-gatekeeper"}`),
		0644,
	)
	if err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := readGenerationStatus()
	if ps.status != "" {
		t.Fatalf("status = %q, want empty when root generation_status.json is absent", ps.status)
	}
}

func TestModSourcesDirTrimsEnvWhitespace(t *testing.T) {
	home := t.TempDir()
	ms := filepath.Join(home, "MS")
	t.Setenv("HOME", home)
	t.Setenv("FORGE_MOD_SOURCES_DIR", "  "+ms+"  ")
	got := modSourcesDir()
	if got != ms {
		t.Fatalf("modSourcesDir() = %q, want %q", got, ms)
	}
}

func TestMergeGatekeeperDoesNotOverrideReady(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	rootJSON := `{"status":"ready","stage_pct":100,"batch_list":["Blade"]}`
	if err := os.WriteFile(filepath.Join(ms, "generation_status.json"), []byte(rootJSON), 0644); err != nil {
		t.Fatalf("write root status: %v", err)
	}
	gkJSON := `{"status":"error","message":"stale"}`
	if err := os.WriteFile(filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"), []byte(gkJSON), 0644); err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := readGenerationStatus()
	if ps.status != "ready" {
		t.Fatalf("status = %q, want ready (root wins)", ps.status)
	}
}

func writeForgeConfigWithModSources(t *testing.T, home, modSources string) {
	t.Helper()
	cfgDir := filepath.Join(home, ".config", "theforge")
	if err := os.MkdirAll(cfgDir, 0755); err != nil {
		t.Fatalf("mkdir config dir: %v", err)
	}
	escaped := strings.ReplaceAll(strings.ReplaceAll(modSources, `\`, `\\`), `"`, `\"`)
	content := `mode = "cloud"
mod_sources_dir = "` + escaped + `"

[cloud]
openai_api_key = ""
fal_key = ""
fal_img2img_enabled = false

[local]
ollama_model = "llama3.1"
ollama_base_url = "http://localhost:11434"
weights_path = ""
`
	path := filepath.Join(cfgDir, "config.toml")
	if err := os.WriteFile(path, []byte(content), 0600); err != nil {
		t.Fatalf("write config: %v", err)
	}
}

func TestUserPromptAppearsInFeedAfterSubmit(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.commandInput.SetValue("glowing war axe")

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next := updated.(model)

	// Verify the user event is in the feed slice.
	found := false
	for _, ev := range next.sessionShell.events {
		if ev.Kind == sessionEventKindUser && ev.Message == "glowing war axe" {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("user event not in feed slice; events = %v", next.sessionShell.events)
	}

	// Also verify it renders in the view.
	got := next.View()
	if !strings.Contains(got, "glowing war axe") {
		t.Fatalf("view = %q, want user prompt echoed in feed", got)
	}
}

func TestErrorEventRendersWithPrefix(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.sessionShell.appendEvent(sessionEventKindFailure, "pipeline collapsed: ArtistAgent failed")

	got := m.View()
	if !strings.Contains(got, "✗") {
		t.Fatalf("view = %q, want error event rendered with ✗ icon", got)
	}
	if !strings.Contains(got, "pipeline collapsed") {
		t.Fatalf("view = %q, want error message text in view", got)
	}
}

func TestOperationLineShowsElapsedTime(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.operationKind = operationForging
	m.operationLabel = "iron sword"
	m.operationStartedAt = time.Now().Add(-15 * time.Second)

	got := m.View()
	if !strings.Contains(got, "15s") && !strings.Contains(got, "14s") {
		t.Fatalf("view = %q, want elapsed seconds in operation line", got)
	}
}

func TestCommandBarRendersKeyboardHintStrip(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()

	got := m.View()
	if !strings.Contains(got, "/ for commands") {
		t.Fatalf("view = %q, want keyboard hint strip above separator", got)
	}
}

func TestTopStatusBarShowsBenchName(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.workshop.Bench = workshopBench{ItemID: "iron-sword", Label: "Iron Sword"}
	m.width = 120
	m.height = 40

	got := m.View()
	if !strings.Contains(got, "Iron Sword") {
		t.Fatalf("view = %q, want bench label in top status bar", got)
	}
}

func TestTopStatusBarShowsRuntimeOfflineWhenBridgeDown(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.bridgeAlive = false
	m.width = 120
	m.height = 40

	got := m.View()
	if !strings.Contains(got, "offline") {
		t.Fatalf("view = %q, want 'offline' in status bar when bridge is down", got)
	}
}

func TestForgeViewShowsElapsedWhenForging(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenForge
	m.operationKind = operationForging
	m.operationStartedAt = time.Now().UTC().Add(-15 * time.Second)
	m.stageLabel = "Architecting"

	view := m.forgeView()
	if !strings.Contains(view, "15s") && !strings.Contains(view, "14s") {
		t.Fatalf("forgeView() = %q, want elapsed time visible during forge", view)
	}
}

func TestRenderOperationLineStaleIsActionable(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.operationKind = operationForging
	m.operationStale = true
	m.operationStartedAt = time.Now().UTC().Add(-30 * time.Second)
	m.operationLabel = "radiant sword"

	line := renderOperationLine(m)
	if !strings.Contains(line, "Esc") {
		t.Fatalf("renderOperationLine stale = %q, want Esc hint", line)
	}
	if !strings.Contains(line, "slow") && !strings.Contains(line, "Slow") {
		t.Fatalf("renderOperationLine stale = %q, want 'slow' language", line)
	}
}

func TestEscCancelsInFlightForge(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenForge
	m.operationKind = operationForging
	m.operationLabel = "iron sword"

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	next := updated.(model)

	if next.state != screenInput {
		t.Fatalf("state after Esc = %v, want screenInput", next.state)
	}
	if next.operationKind != operationIdle {
		t.Fatalf("operationKind after Esc = %v, want operationIdle", next.operationKind)
	}
}

func TestForgeErrorRetryWithRKey(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenForge
	m.forgeErr = "Forge timed out."
	m.prompt = "radiant sword"

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'r'}})
	next := updated.(model)

	if next.state != screenForge {
		t.Fatalf("state = %v, want screenForge after retry", next.state)
	}
	if next.forgeErr != "" {
		t.Fatalf("forgeErr = %q, want empty after retry", next.forgeErr)
	}
	if next.operationKind != operationForging {
		t.Fatalf("operationKind = %q, want operationForging after retry", next.operationKind)
	}
}

func TestForgeErrorEscGoesBackToInput(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.state = screenForge
	m.forgeErr = "Forge timed out."
	m.prompt = "radiant sword"

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	next := updated.(model)

	if next.state != screenInput {
		t.Fatalf("state = %v, want screenInput after Esc on error", next.state)
	}
	if next.forgeErr != "" {
		t.Fatalf("forgeErr = %q, want empty after Esc", next.forgeErr)
	}
}
