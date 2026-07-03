#!/usr/bin/env bash
# Sync GA sessions to agent-session-search format
# Run after any GA session completes to make it searchable

set -euo pipefail

GA_DIR="/home/moclaw/projects/external/genericagent"
GA_SESSION_OUT="$GA_DIR/temp/session_search"

# Ensure symlink exists
if [ ! -L "$HOME/.codex/sessions/ga_import" ]; then
    ln -sf "$GA_SESSION_OUT" "$HOME/.codex/sessions/ga_import"
fi

# Run converter
cd "$GA_DIR"
python3 tools/ga-to-session-search.py

echo "Sync complete."
