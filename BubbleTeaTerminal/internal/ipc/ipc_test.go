package ipc

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"theforge/internal/modsources"
)

func TestParseDotEnvStripsCommentsOutsideQuotes(t *testing.T) {
	envPath := filepath.Join(t.TempDir(), ".env")
	content := "" +
		"OPENAI_API_KEY=\"sk-test\" # local key\n" +
		"PLAIN=value # trailing comment\n" +
		"HASHED=\"value # keep this\"\n" +
		"SINGLE='two words' # note\n"
	if err := os.WriteFile(envPath, []byte(content), 0o644); err != nil {
		t.Fatalf("write env: %v", err)
	}

	got := ParseDotEnv(envPath)
	want := []string{
		"OPENAI_API_KEY=sk-test",
		"PLAIN=value",
		"HASHED=value # keep this",
		"SINGLE=two words",
	}

	if len(got) != len(want) {
		t.Fatalf("ParseDotEnv() returned %d pairs, want %d: %#v", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("ParseDotEnv()[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

func TestReadHeartbeatUsesDistinctFiles(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	dir := modsources.Dir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	bridgeHeartbeat := []byte(`{"status":"listening","pid":` + strconv.Itoa(os.Getpid()) + `}`)
	if err := os.WriteFile(filepath.Join(dir, "forge_connector_alive.json"), bridgeHeartbeat, 0o644); err != nil {
		t.Fatalf("write bridge heartbeat: %v", err)
	}

	if !ReadBridgeHeartbeat() {
		t.Fatal("ReadBridgeHeartbeat() = false, want true for live bridge heartbeat")
	}
	if ReadOrchestratorHeartbeat() {
		t.Fatal("ReadOrchestratorHeartbeat() = true with only bridge heartbeat present")
	}

	orchestratorHeartbeat := []byte(`{"status":"listening","pid":` + strconv.Itoa(os.Getpid()) + `}`)
	if err := os.WriteFile(filepath.Join(dir, "orchestrator_alive.json"), orchestratorHeartbeat, 0o644); err != nil {
		t.Fatalf("write orchestrator heartbeat: %v", err)
	}

	if !ReadOrchestratorHeartbeat() {
		t.Fatal("ReadOrchestratorHeartbeat() = false, want true for live orchestrator heartbeat")
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

	if err := WriteUserRequest("Echo Hook", "Hardmode", "Tool", "Hook", "", true, extra); err != nil {
		t.Fatalf("WriteUserRequest() error = %v", err)
	}

	data, err := os.ReadFile(filepath.Join(modsources.Dir(), "user_request.json"))
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

func TestUserRequestContentTypeExplicitRoundTrip(t *testing.T) {
	request := UserRequest{
		Prompt:              "obsidian pickaxe",
		Tier:                "Tier1_Starter",
		Mode:                "instant",
		ContentType:         "Weapon",
		ContentTypeExplicit: false,
		SubType:             "Pickaxe",
	}

	data, err := json.Marshal(request)
	if err != nil {
		t.Fatalf("marshal UserRequest: %v", err)
	}

	var back UserRequest
	if err := json.Unmarshal(data, &back); err != nil {
		t.Fatalf("unmarshal UserRequest: %v", err)
	}

	if back.ContentTypeExplicit {
		t.Fatalf("ContentTypeExplicit = true, want false")
	}
	if back.ContentType != "Weapon" || back.SubType != "Pickaxe" {
		t.Fatalf("round-trip request = %#v, want Weapon/Pickaxe", back)
	}
}

func TestWriteInjectFileIncludesSpritePaths(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	manifest := map[string]interface{}{
		"item_name": "Storm Brand",
		"stats": map[string]interface{}{
			"damage": 42,
		},
	}
	if err := WriteInjectFile(manifest, "Storm Brand", "/tmp/item.png", "/tmp/projectile.png"); err != nil {
		t.Fatalf("WriteInjectFile() error = %v", err)
	}

	data, err := os.ReadFile(filepath.Join(modsources.Dir(), "forge_inject.json"))
	if err != nil {
		t.Fatalf("read forge_inject.json: %v", err)
	}

	var payload map[string]interface{}
	if err := json.Unmarshal(data, &payload); err != nil {
		t.Fatalf("unmarshal inject payload: %v", err)
	}
	if got := payload["sprite_path"]; got != "/tmp/item.png" {
		t.Fatalf("sprite_path = %#v, want /tmp/item.png", got)
	}
	if got := payload["projectile_sprite_path"]; got != "/tmp/projectile.png" {
		t.Fatalf("projectile_sprite_path = %#v, want /tmp/projectile.png", got)
	}
}

func TestReadGenerationStatusMergesGatekeeperStatus(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	rootJSON := `{"status":"building","stage_label":"Gatekeeper — Compiling mod...","stage_pct":80}`
	if err := os.WriteFile(filepath.Join(ms, "generation_status.json"), []byte(rootJSON), 0o644); err != nil {
		t.Fatalf("write root status: %v", err)
	}
	gkJSON := `{"status":"building","message":"Compiling C#..."}`
	if err := os.WriteFile(filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"), []byte(gkJSON), 0o644); err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := ReadGenerationStatus()
	if ps.Status != "building" {
		t.Fatalf("Status = %q, want building", ps.Status)
	}
	if ps.StagePct < 85 {
		t.Fatalf("StagePct = %d, want at least 85 from gatekeeper merge", ps.StagePct)
	}
	if !strings.Contains(ps.StageLabel, "Compiling") {
		t.Fatalf("StageLabel = %q, want gatekeeper message merged", ps.StageLabel)
	}
}

func TestReadGenerationStatusDoesNotMergeWhenRootStatusEmpty(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(ms, "generation_status.json"), []byte(`{}`), 0o644); err != nil {
		t.Fatalf("write root status: %v", err)
	}
	if err := os.WriteFile(filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"), []byte(`{"status":"building","message":"should-not-merge"}`), 0o644); err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := ReadGenerationStatus()
	if ps.Status != "" {
		t.Fatalf("Status = %q, want empty when root has no status field", ps.Status)
	}
}

func TestReadGenerationStatusIgnoresGatekeeperWithoutRoot(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"), []byte(`{"status":"building","message":"stale-only-gatekeeper"}`), 0o644); err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := ReadGenerationStatus()
	if ps.Status != "" {
		t.Fatalf("Status = %q, want empty when root generation_status.json is absent", ps.Status)
	}
}

func TestReadGenerationStatusKeepsRootReadyOverGatekeeperError(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	rootJSON := `{"status":"ready","stage_pct":100,"batch_list":["Blade"]}`
	if err := os.WriteFile(filepath.Join(ms, "generation_status.json"), []byte(rootJSON), 0o644); err != nil {
		t.Fatalf("write root status: %v", err)
	}
	gkJSON := `{"status":"error","message":"stale"}`
	if err := os.WriteFile(filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"), []byte(gkJSON), 0o644); err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := ReadGenerationStatus()
	if ps.Status != "ready" {
		t.Fatalf("Status = %q, want ready (root wins)", ps.Status)
	}
}

func TestReadRuntimeSummary(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	dir := modsources.Dir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}

	payload := `{
  "bridge_alive": true,
  "world_loaded": true,
  "live_item_name": "Storm Brand",
  "last_inject_status": "item_injected",
  "last_runtime_note": "Ready on bench"
}`
	if err := os.WriteFile(filepath.Join(dir, "forge_runtime_summary.json"), []byte(payload), 0o644); err != nil {
		t.Fatalf("write forge_runtime_summary.json: %v", err)
	}

	summary := ReadRuntimeSummary()
	if !summary.BridgeAlive {
		t.Fatal("BridgeAlive = false, want true")
	}
	if !summary.WorldLoaded {
		t.Fatal("WorldLoaded = false, want true")
	}
	if summary.LiveItemName != "Storm Brand" {
		t.Fatalf("LiveItemName = %q, want Storm Brand", summary.LiveItemName)
	}
}
