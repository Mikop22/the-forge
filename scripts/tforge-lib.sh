resolve_venv_python() {
  venv_dir="$1"
  for candidate in \
    "$venv_dir/bin/python3.12" \
    "$venv_dir/bin/python" \
    "$venv_dir/Scripts/python.exe" \
    "$venv_dir/Scripts/python"; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

set_runtime_paths() {
  plugin_root="$1"
  plugin_data="$2"

  if [ -n "$plugin_data" ]; then
    pixelsmith_data="$plugin_data/pixelsmith"
    TFORGE_NODE_DEPS_DIR="$pixelsmith_data/node"
    TFORGE_PIXELSMITH_WEIGHTS_PATH="$pixelsmith_data/terraria_weights.safetensors"
    TFORGE_LORA_CACHE_FILE="$pixelsmith_data/.lora_url_cache.json"
  else
    pixelsmith_data="$plugin_root/agents/pixelsmith"
    TFORGE_NODE_DEPS_DIR="$pixelsmith_data"
    TFORGE_PIXELSMITH_WEIGHTS_PATH="$pixelsmith_data/terraria_weights.safetensors"
    TFORGE_LORA_CACHE_FILE="$pixelsmith_data/.lora_url_cache.json"
  fi

  export TFORGE_NODE_DEPS_DIR
  export TFORGE_PIXELSMITH_WEIGHTS_PATH
  export TFORGE_LORA_CACHE_FILE
}

read_fal_key_from_env_file() {
  env_file="$1"
  if [ -f "$env_file" ]; then
    sed -n 's/^FAL_KEY=//p; s/^FAL_API_KEY=//p' "$env_file" | head -n 1
  fi
}
