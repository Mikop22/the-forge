package modsources

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

func configPath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("could not determine home directory: %w", err)
	}
	return filepath.Join(home, ".config", "theforge", "config.toml"), nil
}

func trimInlineComment(val string) string {
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

// DirFromConfig reads mod_sources_dir from ~/.config/theforge/config.toml.
func DirFromConfig() string {
	cfgPath, err := configPath()
	if err != nil {
		return ""
	}
	data, err := os.ReadFile(cfgPath)
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			break
		}
		eqIdx := strings.Index(line, "=")
		if eqIdx < 0 {
			continue
		}
		key := strings.TrimSpace(line[:eqIdx])
		if key != "mod_sources_dir" {
			continue
		}
		val := strings.TrimSpace(line[eqIdx+1:])
		val = trimInlineComment(val)
		if len(val) >= 2 && ((val[0] == '"' && val[len(val)-1] == '"') || (val[0] == '\'' && val[len(val)-1] == '\'')) {
			val = val[1 : len(val)-1]
		}
		dir := strings.TrimSpace(val)
		if dir != "" {
			return dir
		}
	}
	return ""
}

// DirForOS returns the default tModLoader ModSources path for a given OS.
func DirForOS(goos string) string {
	home, _ := os.UserHomeDir()
	switch goos {
	case "darwin":
		return filepath.Join(home, "Library", "Application Support", "Terraria", "tModLoader", "ModSources")
	case "windows":
		userProfile := os.Getenv("USERPROFILE")
		if userProfile == "" {
			userProfile = home
		}
		return filepath.Join(userProfile, "Documents", "My Games", "Terraria", "tModLoader", "ModSources")
	case "linux":
		return filepath.Join(home, ".local", "share", "Terraria", "tModLoader", "ModSources")
	default:
		return filepath.Join(home, "Library", "Application Support", "Terraria", "tModLoader", "ModSources")
	}
}

// Dir resolves the active ModSources root for the TUI and orchestrator bridge.
func Dir() string {
	if dir := strings.TrimSpace(os.Getenv("FORGE_MOD_SOURCES_DIR")); dir != "" {
		return dir
	}
	if dir := DirFromConfig(); dir != "" {
		return dir
	}
	return DirForOS(runtime.GOOS)
}
