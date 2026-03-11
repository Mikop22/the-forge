#!/bin/bash
# Wrapper script for tModLoader headless builds on macOS.
# macOS SIP strips DYLD_* env vars from child processes, so we must
# set DYLD_LIBRARY_PATH in-process and exec dotnet to preserve it.

TMOD_DIR="$1"
shift

cd "$TMOD_DIR" || exit 1

if [ -d "Libraries/Native/OSX" ]; then
    export DYLD_LIBRARY_PATH="$TMOD_DIR/Libraries/Native/OSX"
fi

exec dotnet tModLoader.dll "$@"
