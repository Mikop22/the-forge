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
			"damage":     float64(12),
			"use_time":   float64(20),
			"knockback":  float64(4.5),
			"crit_chance": float64(4),
			"rarity":     "ItemRarityID.White",
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
