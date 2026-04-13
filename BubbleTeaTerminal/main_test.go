package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

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

	if got := strings.TrimSpace(m.commandInput.Placeholder); got == "" {
		t.Fatal("command input placeholder is empty, want a startup prompt")
	}
}

func TestInitialModelOmitsStandalonePromptFormInStartupView(t *testing.T) {
	m := initialModel()

	got := m.View()
	if strings.Contains(got, "Describe your item") {
		t.Fatalf("startup view = %q, want it to omit the legacy standalone prompt form from the main body", got)
	}
	if !strings.Contains(got, "Persistent Command Bar") {
		t.Fatalf("startup view = %q, want the persistent command bar to remain the entry point", got)
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

	if got := len(m.sessionShell.events); got != 2 {
		t.Fatalf("startup session events = %d, want 2 hydrated events from session_shell_status.json", got)
	}
	if got := m.sessionShell.events[0].Message; got != "Forge: Storm Brand" {
		t.Fatalf("first startup session event = %q, want Forge: Storm Brand", got)
	}
	if got := m.sessionShell.events[1].Message; got != "Forge progress 47%" {
		t.Fatalf("second startup session event = %q, want Forge progress 47%%", got)
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
	if !strings.Contains(gotView, "bench: Storm Brand") {
		t.Fatalf("startup shell view = %q, want top strip to surface hydrated bench context", gotView)
	}
	if !strings.Contains(gotView, "shelf: 1 variant") {
		t.Fatalf("startup shell view = %q, want top strip to surface hydrated shelf context", gotView)
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
	if got := m.View(); !strings.Contains(got, "runtime online") {
		t.Fatalf("startup shell view = %q, want runtime online when bridge heartbeat is live", got)
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
	if got := len(payload.RecentEvents); got != 3 {
		t.Fatalf("recent_events = %d, want 3", got)
	}
	if payload.RecentEvents[0].Message != "Forge progress: 58%" {
		t.Fatalf("updated runtime event = %q, want Forge progress: 58%%", payload.RecentEvents[0].Message)
	}
	if payload.RecentEvents[2].Message != "Workshop action sent: bench" {
		t.Fatalf("appended event = %q, want Workshop action sent: bench", payload.RecentEvents[2].Message)
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
	wantOrder := []string{"Top Strip", "Feed Container", "Persistent Command Bar"}
	last := -1
	for _, want := range wantOrder {
		idx := strings.Index(got, want)
		if idx < 0 {
			t.Fatalf("session shell render = %q, want it to contain region %q", got, want)
		}
		if idx <= last {
			t.Fatalf("session shell render = %q, want region %q after previous region", got, want)
		}
		last = idx
	}
	if strings.Contains(got, "Sigils") {
		t.Fatalf("session shell render = %q, want it to omit legacy shell chrome", got)
	}
	if !strings.Contains(got, "forge the shell") {
		t.Fatalf("session shell render = %q, want it to contain feed content text", got)
	}
}

func TestInputShell(t *testing.T) {
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
	if got := next.View(); !strings.Contains(got, "Top Strip") || !strings.Contains(got, "Persistent Command Bar") {
		t.Fatalf("shell view = %q, want persistent shell chrome", got)
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
	if got := next.View(); !strings.Contains(got, "Top Strip") || !strings.Contains(got, "Persistent Command Bar") {
		t.Fatalf("wizard shell view = %q, want persistent shell chrome", got)
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
	if got := ready.View(); !strings.Contains(got, "Top Strip") || !strings.Contains(got, "Persistent Command Bar") {
		t.Fatalf("ready shell view = %q, want persistent shell chrome", got)
	}

	updated, _ = ready.Update(forgeDoneMsg{})
	staged, ok := updated.(model)
	if !ok {
		t.Fatalf("updated model has unexpected type %T", updated)
	}
	if staged.state != screenStaging {
		t.Fatalf("forge flow staged state = %v, want %v", staged.state, screenStaging)
	}
	if got := staged.View(); !strings.Contains(got, "Top Strip") || !strings.Contains(got, "Persistent Command Bar") {
		t.Fatalf("staged shell view = %q, want persistent shell chrome", got)
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

	if err := writeUserRequest("Echo Hook", "Hardmode", "Tool", "Hook", "", extra); err != nil {
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
