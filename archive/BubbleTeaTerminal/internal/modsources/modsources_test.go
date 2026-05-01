package modsources

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDirHonorsConfigTomlWhenEnvUnset(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("FORGE_MOD_SOURCES_DIR", "")

	custom := filepath.Join(home, "custom", "ModSources")
	writeForgeConfigWithModSources(t, home, custom)

	if got := Dir(); got != custom {
		t.Fatalf("Dir() = %q, want config mod_sources_dir %q", got, custom)
	}
}

func TestDirPrefersEnvOverConfig(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	envDir := filepath.Join(home, "from-env")
	cfgDir := filepath.Join(home, "from-config")
	t.Setenv("FORGE_MOD_SOURCES_DIR", envDir)
	writeForgeConfigWithModSources(t, home, cfgDir)

	if got := Dir(); got != envDir {
		t.Fatalf("Dir() = %q, want FORGE_MOD_SOURCES_DIR %q", got, envDir)
	}
}

func TestDirTrimsEnvWhitespace(t *testing.T) {
	home := t.TempDir()
	ms := filepath.Join(home, "MS")
	t.Setenv("HOME", home)
	t.Setenv("FORGE_MOD_SOURCES_DIR", "  "+ms+"  ")

	if got := Dir(); got != ms {
		t.Fatalf("Dir() = %q, want %q", got, ms)
	}
}

func writeForgeConfigWithModSources(t *testing.T, home, modSources string) {
	t.Helper()
	cfgDir := filepath.Join(home, ".config", "theforge")
	if err := os.MkdirAll(cfgDir, 0o755); err != nil {
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
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
}
