package ipc

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"theforge/internal/modsources"
)

type GenerationStatus struct {
	Status               string
	ItemName             string
	ErrMsg               string
	StagePct             int
	StageLabel           string
	Manifest             map[string]interface{}
	SpritePath           string
	ProjectileSpritePath string
	InjectMode           bool
}

type PollStatusMsg struct{}

type UserRequest struct {
	Prompt              string `json:"prompt"`
	Tier                string `json:"tier,omitempty"`
	Mode                string `json:"mode,omitempty"`
	ContentType         string `json:"content_type,omitempty"`
	ContentTypeExplicit bool   `json:"content_type_explicit"`
	SubType             string `json:"sub_type,omitempty"`
	CraftingStation     string `json:"crafting_station,omitempty"`
}

type PollConnectorStatusMsg struct {
	Attempt int
}

type PollWorkshopStatusMsg struct {
	Attempt int
}

type RuntimeSummary struct {
	BridgeAlive      bool
	WorldLoaded      bool
	LiveItemName     string
	LastInjectStatus string
	LastRuntimeNote  string
	UpdatedAt        string
}

type WorkshopBench struct {
	ItemID               string
	Label                string
	Manifest             map[string]interface{}
	SpritePath           string
	ProjectileSpritePath string
}

type WorkshopVariant struct {
	VariantID            string
	Label                string
	Rationale            string
	ChangeSummary        string
	Manifest             map[string]interface{}
	SpritePath           string
	ProjectileSpritePath string
}

type WorkshopStatus struct {
	SessionID  string
	SnapshotID int
	Bench      WorkshopBench
	Shelf      []WorkshopVariant
	LastAction string
	Error      string
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
		return "Tier1_Starter"
	}
}

func writeJSONAtomic(path string, payload interface{}, indent bool) error {
	data, err := func() ([]byte, error) {
		if indent {
			return json.MarshalIndent(payload, "", "  ")
		}
		return json.Marshal(payload)
	}()
	if err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func parseGenerationStatusBytes(data []byte) GenerationStatus {
	var result map[string]interface{}
	if json.Unmarshal(data, &result) != nil {
		return GenerationStatus{}
	}
	ps := GenerationStatus{}
	ps.Status, _ = result["status"].(string)
	if itemName, ok := result["item_name"].(string); ok && itemName != "" {
		ps.ItemName = itemName
	} else if batchList, ok := result["batch_list"].([]interface{}); ok && len(batchList) > 0 {
		ps.ItemName, _ = batchList[0].(string)
	}
	ps.ErrMsg, _ = result["message"].(string)
	ps.StageLabel, _ = result["stage_label"].(string)
	if pct, ok := result["stage_pct"].(float64); ok {
		ps.StagePct = int(pct)
	}
	if manifest, ok := result["manifest"].(map[string]interface{}); ok {
		ps.Manifest = manifest
	}
	ps.SpritePath, _ = result["sprite_path"].(string)
	ps.ProjectileSpritePath, _ = result["projectile_sprite_path"].(string)
	if injectMode, ok := result["inject_mode"].(bool); ok {
		ps.InjectMode = injectMode
	}
	return ps
}

func mergeGatekeeperGenerationStatus(root GenerationStatus, gkRaw []byte) GenerationStatus {
	if root.Status == "ready" || root.Status == "error" {
		return root
	}
	var gk map[string]interface{}
	if json.Unmarshal(gkRaw, &gk) != nil {
		return root
	}
	st, _ := gk["status"].(string)
	if st == "" {
		return root
	}
	msg, _ := gk["message"].(string)
	switch st {
	case "finishing":
		root.Status = "building"
		if msg != "" {
			root.StageLabel = msg
		}
		if root.StagePct < 95 {
			root.StagePct = 95
		}
	case "building":
		if lbl, ok := gk["stage_label"].(string); ok && lbl != "" {
			root.StageLabel = lbl
		} else if msg != "" {
			root.StageLabel = msg
		}
		if pct, ok := gk["stage_pct"].(float64); ok {
			root.StagePct = max(root.StagePct, int(pct))
		} else if root.StagePct < 85 {
			root.StagePct = 85
		}
	case "error":
		root.Status = "error"
		if msg != "" {
			root.ErrMsg = msg
		}
		if code, ok := gk["error_code"].(string); ok && code != "" {
			if root.ErrMsg != "" {
				root.ErrMsg = root.ErrMsg + " (" + code + ")"
			} else {
				root.ErrMsg = code
			}
		}
	}
	return root
}

func ReadGenerationStatus() GenerationStatus {
	dir := modsources.Dir()
	rootPath := filepath.Join(dir, "generation_status.json")
	data, err := os.ReadFile(rootPath)
	if err != nil {
		return GenerationStatus{}
	}
	root := parseGenerationStatusBytes(data)
	if root.Status == "" {
		return root
	}
	gkPath := filepath.Join(dir, "ForgeGeneratedMod", "generation_status.json")
	gkData, err := os.ReadFile(gkPath)
	if err != nil {
		return root
	}
	return mergeGatekeeperGenerationStatus(root, gkData)
}

func PollStatusCmd() tea.Cmd {
	return tea.Tick(2*time.Second, func(time.Time) tea.Msg {
		return PollStatusMsg{}
	})
}

func PollConnectorStatusCmd(attempt int) tea.Cmd {
	return tea.Tick(500*time.Millisecond, func(time.Time) tea.Msg {
		return PollConnectorStatusMsg{Attempt: attempt}
	})
}

func PollWorkshopStatusCmd(attempt int) tea.Cmd {
	return tea.Tick(500*time.Millisecond, func(time.Time) tea.Msg {
		return PollWorkshopStatusMsg{Attempt: attempt}
	})
}

func ReadConnectorStatusPayload() (status string, detail string) {
	data, err := os.ReadFile(filepath.Join(modsources.Dir(), "forge_connector_status.json"))
	if err != nil {
		return "", ""
	}
	var result map[string]interface{}
	if json.Unmarshal(data, &result) != nil {
		return "", ""
	}
	status, _ = result["status"].(string)
	if message, ok := result["message"].(string); ok && message != "" {
		detail = message
	}
	if detail == "" {
		if itemName, ok := result["item_name"].(string); ok && itemName != "" {
			detail = itemName
		}
	}
	return status, detail
}

func ReadRuntimeSummary() RuntimeSummary {
	data, err := os.ReadFile(filepath.Join(modsources.Dir(), "forge_runtime_summary.json"))
	if err != nil {
		return RuntimeSummary{}
	}

	var payload map[string]interface{}
	if json.Unmarshal(data, &payload) != nil {
		return RuntimeSummary{}
	}

	summary := RuntimeSummary{}
	summary.BridgeAlive, _ = payload["bridge_alive"].(bool)
	summary.WorldLoaded, _ = payload["world_loaded"].(bool)
	summary.LiveItemName, _ = payload["live_item_name"].(string)
	summary.LastInjectStatus, _ = payload["last_inject_status"].(string)
	summary.LastRuntimeNote, _ = payload["last_runtime_note"].(string)
	summary.UpdatedAt, _ = payload["updated_at"].(string)
	return summary
}

func ReadWorkshopStatus() WorkshopStatus {
	data, err := os.ReadFile(filepath.Join(modsources.Dir(), "workshop_status.json"))
	if err != nil {
		return WorkshopStatus{}
	}

	var payload map[string]interface{}
	if json.Unmarshal(data, &payload) != nil {
		return WorkshopStatus{}
	}

	status := WorkshopStatus{}
	status.SessionID, _ = payload["session_id"].(string)
	if snapshotID, ok := payload["snapshot_id"].(float64); ok {
		status.SnapshotID = int(snapshotID)
	}
	status.LastAction, _ = payload["last_action"].(string)
	status.Error, _ = payload["error"].(string)

	if benchRaw, ok := payload["bench"].(map[string]interface{}); ok {
		status.Bench.ItemID, _ = benchRaw["item_id"].(string)
		status.Bench.Label, _ = benchRaw["label"].(string)
		status.Bench.Manifest, _ = benchRaw["manifest"].(map[string]interface{})
		status.Bench.SpritePath, _ = benchRaw["sprite_path"].(string)
		status.Bench.ProjectileSpritePath, _ = benchRaw["projectile_sprite_path"].(string)
	}

	if shelfRaw, ok := payload["shelf"].([]interface{}); ok {
		status.Shelf = make([]WorkshopVariant, 0, len(shelfRaw))
		for _, entry := range shelfRaw {
			raw, ok := entry.(map[string]interface{})
			if !ok {
				continue
			}
			variant := WorkshopVariant{}
			variant.VariantID, _ = raw["variant_id"].(string)
			variant.Label, _ = raw["label"].(string)
			variant.Rationale, _ = raw["rationale"].(string)
			variant.ChangeSummary, _ = raw["change_summary"].(string)
			variant.Manifest, _ = raw["manifest"].(map[string]interface{})
			variant.SpritePath, _ = raw["sprite_path"].(string)
			variant.ProjectileSpritePath, _ = raw["projectile_sprite_path"].(string)
			status.Shelf = append(status.Shelf, variant)
		}
	}

	return status
}

func WriteUserRequest(prompt, tier, contentType, subType, craftingStation string, contentTypeExplicit bool, extra map[string]interface{}) error {
	dir := modsources.Dir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	payload := map[string]interface{}{
		"prompt":                prompt,
		"tier":                  tierToKey(tier),
		"mode":                  "instant",
		"content_type_explicit": contentTypeExplicit,
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
	return writeJSONAtomic(filepath.Join(dir, "user_request.json"), payload, false)
}

func WriteInjectFile(manifest map[string]interface{}, itemName, spritePath, projectileSpritePath string) error {
	dir := modsources.Dir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	payload := map[string]interface{}{
		"action":                 "inject",
		"item_name":              itemName,
		"manifest":               manifest,
		"sprite_path":            spritePath,
		"projectile_sprite_path": projectileSpritePath,
		"timestamp":              time.Now().UTC().Format(time.RFC3339),
	}
	return writeJSONAtomic(filepath.Join(dir, "forge_inject.json"), payload, true)
}

func ClearWorkshopStatus() error {
	path := filepath.Join(modsources.Dir(), "workshop_status.json")
	empty := map[string]interface{}{
		"bench": map[string]interface{}{},
		"shelf": []interface{}{},
	}
	return writeJSONAtomic(path, empty, false)
}

func WriteWorkshopRequest(payload map[string]interface{}) error {
	dir := modsources.Dir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	_ = os.Remove(filepath.Join(dir, "workshop_status.json"))
	return writeJSONAtomic(filepath.Join(dir, "workshop_request.json"), payload, true)
}

func readHeartbeatPID(path string) (int, bool) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, false
	}
	var hb map[string]interface{}
	if err := json.Unmarshal(data, &hb); err != nil {
		return 0, false
	}
	if status, _ := hb["status"].(string); status != "listening" {
		return 0, false
	}
	pidFloat, ok := hb["pid"].(float64)
	if !ok {
		return 0, false
	}
	return int(pidFloat), true
}

func readHeartbeatFile(path string) bool {
	pid, ok := readHeartbeatPID(path)
	if !ok {
		return false
	}
	return processAlive(pid)
}

func processStatAlive(stat string) bool {
	return !strings.HasPrefix(strings.TrimSpace(stat), "Z")
}

func processAlive(pid int) bool {
	proc, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	if proc.Signal(syscall.Signal(0)) != nil {
		return false
	}
	out, err := exec.Command("ps", "-p", strconv.Itoa(pid), "-o", "stat=").Output()
	if err != nil {
		return true
	}
	return processStatAlive(string(out))
}

func processCommandLine(pid int) (string, error) {
	if runtime.GOOS == "windows" {
		return "", fmt.Errorf("process command-line verification is unsupported on windows")
	}
	out, err := exec.Command("ps", "-p", strconv.Itoa(pid), "-o", "command=").Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

func processLooksLikeForgeOrchestrator(pid int) bool {
	cmdline, err := processCommandLine(pid)
	if err != nil {
		return false
	}
	normalized := filepath.ToSlash(cmdline)
	return strings.Contains(normalized, "orchestrator.py")
}

func ReadBridgeHeartbeat() bool {
	return readHeartbeatFile(filepath.Join(modsources.Dir(), "forge_connector_alive.json"))
}

func ReadOrchestratorHeartbeat() bool {
	return readHeartbeatFile(filepath.Join(modsources.Dir(), "orchestrator_alive.json"))
}

func readHeartbeatModSourcesRoot(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	var hb map[string]interface{}
	if json.Unmarshal(data, &hb) != nil {
		return ""
	}
	if path, ok := hb["mod_sources_root"].(string); ok && path != "" {
		return path
	}
	if path, ok := hb["mod_sources_dir"].(string); ok && path != "" {
		return path
	}
	return ""
}

func WarnPathMismatches() {
	local := filepath.Clean(modsources.Dir())
	orch := readHeartbeatModSourcesRoot(filepath.Join(modsources.Dir(), "orchestrator_alive.json"))
	if orch != "" && filepath.Clean(orch) != local {
		fmt.Fprintf(os.Stderr, "[forge] warning: orchestrator reports ModSources %q but this TUI resolves %q; align FORGE_MOD_SOURCES_DIR and ~/.config/theforge/config.toml\n", orch, local)
	}
	bridgePath := filepath.Join(modsources.Dir(), "forge_connector_alive.json")
	bridge := readHeartbeatModSourcesRoot(bridgePath)
	if bridge != "" && filepath.Clean(bridge) != local {
		fmt.Fprintf(os.Stderr, "[forge] warning: ForgeConnector reports ModSources %q but this TUI resolves %q; set FORGE_MOD_SOURCES_DIR for both the game and this terminal\n", bridge, local)
	}
	if strings.TrimSpace(os.Getenv("FORGE_MOD_SOURCES_DIR")) == "" {
		if cfg := modsources.DirFromConfig(); cfg != "" {
			def := filepath.Clean(modsources.DirForOS(runtime.GOOS))
			if filepath.Clean(cfg) != def && bridge == "" {
				fmt.Fprintln(os.Stderr, "[forge] hint: ~/.config/theforge/config.toml sets a non-default ModSources; set FORGE_MOD_SOURCES_DIR when launching tModLoader so ForgeConnector uses the same folder as this TUI.")
			}
		}
	}
}

func findOrchestratorPath() string {
	candidates := []string{}
	if exe, err := os.Executable(); err == nil {
		candidates = append(candidates, filepath.Join(filepath.Dir(exe), "..", "agents", "orchestrator.py"))
	}
	if envPath := os.Getenv("FORGE_ORCHESTRATOR_PATH"); envPath != "" {
		candidates = append(candidates, envPath)
	}
	candidates = append(candidates, filepath.Join("..", "agents", "orchestrator.py"))
	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err == nil {
			abs, _ := filepath.Abs(candidate)
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

// ParseDotEnv reads a .env file and returns key=value pairs with inline comments removed.
func ParseDotEnv(path string) []string {
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
		if len(val) >= 2 && ((val[0] == '"' && val[len(val)-1] == '"') || (val[0] == '\'' && val[len(val)-1] == '\'')) {
			val = val[1 : len(val)-1]
		}
		pairs = append(pairs, key+"="+val)
	}
	return pairs
}

func stopProcessFromHeartbeat(path string) {
	pid, ok := readHeartbeatPID(path)
	if !ok {
		return
	}
	proc, err := os.FindProcess(pid)
	if err != nil || !processAlive(pid) {
		return
	}
	if !processLooksLikeForgeOrchestrator(pid) {
		_ = os.Remove(path)
		return
	}
	_ = proc.Signal(syscall.SIGTERM)

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if proc.Signal(syscall.Signal(0)) != nil {
			return
		}
		time.Sleep(50 * time.Millisecond)
	}
	_ = proc.Kill()
}

func stopOwnedProcess(cmd *exec.Cmd, done <-chan error) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	_ = cmd.Process.Signal(syscall.SIGTERM)
	select {
	case <-done:
		return
	case <-time.After(2 * time.Second):
		_ = cmd.Process.Kill()
		<-done
	}
}

func StartOrchestratorSession() func() {
	orchPath := findOrchestratorPath()
	if orchPath == "" {
		fmt.Fprintln(os.Stderr, "[forge] orchestrator.py not found; set FORGE_ORCHESTRATOR_PATH or run from the project root")
		return func() {}
	}
	stopProcessFromHeartbeat(filepath.Join(modsources.Dir(), "orchestrator_alive.json"))

	agentsDir := filepath.Dir(orchPath)
	logPath := filepath.Join(agentsDir, "orchestrator.log")
	logFile, _ := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)

	python := filepath.Join(agentsDir, ".venv", "bin", "python3")
	if _, err := os.Stat(python); err != nil {
		python = "python3"
	}

	cmd := exec.Command(python, orchPath)
	cmd.Dir = agentsDir
	cmd.Env = append(os.Environ(), ParseDotEnv(filepath.Join(agentsDir, ".env"))...)

	if logFile != nil {
		cmd.Stdout = logFile
		cmd.Stderr = logFile
	}
	if err := cmd.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "[forge] failed to start orchestrator: %v\n", err)
		if logFile != nil {
			_ = logFile.Close()
		}
		return func() {}
	}

	done := make(chan error, 1)
	go func() {
		done <- cmd.Wait()
		if logFile != nil {
			_ = logFile.Close()
		}
	}()

	var once sync.Once
	return func() {
		once.Do(func() {
			stopOwnedProcess(cmd, done)
		})
	}
}
