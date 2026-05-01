package ipc

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

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

func TestProcessStatAliveRejectsZombieState(t *testing.T) {
	if processStatAlive("Z+") {
		t.Fatal("processStatAlive(\"Z+\") = true, want false for zombie process")
	}
	if !processStatAlive("S+") {
		t.Fatal("processStatAlive(\"S+\") = false, want true for sleeping process")
	}
}

func TestStartOrchestratorSessionReplacesExistingAndCleanupStopsOwnedProcess(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	modSources := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", modSources)

	agentsDir := t.TempDir()
	orchPath := filepath.Join(agentsDir, "orchestrator.py")
	pidFile := filepath.Join(home, "owned.pid")
	script := `
import os
import signal
import sys
import time

pid_file = os.environ["FORGE_TEST_ORCH_PIDFILE"]
with open(pid_file, "w", encoding="utf-8") as fh:
    fh.write(str(os.getpid()))

def stop(signum, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, stop)
while True:
    time.sleep(0.1)
`
	if err := os.WriteFile(orchPath, []byte(script), 0o755); err != nil {
		t.Fatalf("write fake orchestrator: %v", err)
	}
	if err := os.WriteFile(filepath.Join(agentsDir, ".env"), []byte("FORGE_TEST_ORCH_PIDFILE="+pidFile+"\n"), 0o644); err != nil {
		t.Fatalf("write fake env: %v", err)
	}
	t.Setenv("FORGE_ORCHESTRATOR_PATH", orchPath)

	oldPidFile := filepath.Join(home, "old.pid")
	oldCmd := exec.Command("python3", orchPath)
	oldCmd.Env = append(os.Environ(), "FORGE_TEST_ORCH_PIDFILE="+oldPidFile)
	if err := oldCmd.Start(); err != nil {
		t.Fatalf("start old orchestrator: %v", err)
	}
	defer oldCmd.Process.Kill()
	_ = waitForPIDFile(t, oldPidFile)
	if err := os.MkdirAll(modSources, 0o755); err != nil {
		t.Fatalf("mkdir mod sources: %v", err)
	}
	oldHeartbeat := []byte(`{"status":"listening","pid":` + strconv.Itoa(oldCmd.Process.Pid) + `}`)
	if err := os.WriteFile(filepath.Join(modSources, "orchestrator_alive.json"), oldHeartbeat, 0o644); err != nil {
		t.Fatalf("write old heartbeat: %v", err)
	}

	cleanup := StartOrchestratorSession()
	defer cleanup()

	done := make(chan error, 1)
	go func() { done <- oldCmd.Wait() }()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("old orchestrator still running after session start")
	}

	ownedPID := waitForPIDFile(t, pidFile)
	ownedProc, err := os.FindProcess(ownedPID)
	if err != nil {
		t.Fatalf("find owned process: %v", err)
	}
	if err := ownedProc.Signal(syscall.Signal(0)); err != nil {
		t.Fatalf("owned orchestrator is not running: %v", err)
	}

	cleanup()
	waitForProcessExit(t, ownedProc)
}

func TestStopProcessFromHeartbeatDoesNotKillUnrelatedPID(t *testing.T) {
	dir := t.TempDir()
	cmd := exec.Command("python3", "-c", "import signal,time; signal.signal(signal.SIGTERM, lambda *_: exit(7)); time.sleep(60)")
	if err := cmd.Start(); err != nil {
		t.Fatalf("start unrelated process: %v", err)
	}
	defer cmd.Process.Kill()

	heartbeatPath := filepath.Join(dir, "orchestrator_alive.json")
	heartbeat := []byte(`{"status":"listening","pid":` + strconv.Itoa(cmd.Process.Pid) + `}`)
	if err := os.WriteFile(heartbeatPath, heartbeat, 0o644); err != nil {
		t.Fatalf("write heartbeat: %v", err)
	}

	stopProcessFromHeartbeat(heartbeatPath)

	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	select {
	case err := <-done:
		t.Fatalf("unrelated process exited after stale heartbeat stop: %v", err)
	case <-time.After(250 * time.Millisecond):
	}

	if err := cmd.Process.Signal(syscall.Signal(0)); err != nil {
		t.Fatalf("unrelated process was stopped from stale heartbeat: %v", err)
	}
}

func waitForPIDFile(t *testing.T, path string) int {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		data, err := os.ReadFile(path)
		if err == nil {
			pid, parseErr := strconv.Atoi(strings.TrimSpace(string(data)))
			if parseErr == nil {
				return pid
			}
		}
		time.Sleep(25 * time.Millisecond)
	}
	t.Fatalf("pid file %s was not written", path)
	return 0
}

func waitForProcessExit(t *testing.T, proc *os.Process) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if err := proc.Signal(syscall.Signal(0)); err != nil {
			return
		}
		time.Sleep(25 * time.Millisecond)
	}
	t.Fatal("owned orchestrator still running after cleanup")
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

func TestReadGenerationStatusKeepsRootErrorOverGatekeeperFinishing(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	ms := filepath.Join(home, "ModSources")
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	if err := os.MkdirAll(filepath.Join(ms, "ForgeGeneratedMod"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	rootJSON := `{"status":"error","message":"Artist failed"}`
	if err := os.WriteFile(filepath.Join(ms, "generation_status.json"), []byte(rootJSON), 0o644); err != nil {
		t.Fatalf("write root status: %v", err)
	}
	gkJSON := `{"status":"finishing","message":"Compilation successful. Finalizing..."}`
	if err := os.WriteFile(filepath.Join(ms, "ForgeGeneratedMod", "generation_status.json"), []byte(gkJSON), 0o644); err != nil {
		t.Fatalf("write gatekeeper status: %v", err)
	}

	ps := ReadGenerationStatus()
	if ps.Status != "error" {
		t.Fatalf("Status = %q, want error (root wins)", ps.Status)
	}
	if ps.ErrMsg != "Artist failed" {
		t.Fatalf("ErrMsg = %q, want root error message", ps.ErrMsg)
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
