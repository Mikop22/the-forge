#!/bin/bash
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$script_dir/../scripts/tforge-mcp-start"
