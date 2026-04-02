package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
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

func TestInitialModelStartsAtContentSelection(t *testing.T) {
	m := initialModel()
	if m.state != screenMode {
		t.Fatalf("initial state = %v, want %v", m.state, screenMode)
	}

	items := m.modeList.Items()
	if len(items) < 5 {
		t.Fatalf("mode list has %d items, want at least 5", len(items))
	}

	first, ok := items[0].(optionItem)
	if !ok {
		t.Fatalf("first mode item has unexpected type %T", items[0])
	}
	if first.title != "Weapon" {
		t.Fatalf("first content option = %q, want Weapon", first.title)
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

func TestRenderPreviewAnimationShowsShootMotion(t *testing.T) {
	frame := renderPreviewAnimation("▀▀", "Weapon", "Gun", 3)
	if !strings.Contains(frame, "•") {
		t.Fatalf("shoot animation = %q, want projectile dot", frame)
	}
}
