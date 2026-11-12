#!/usr/bin/env bash
# claude-light uninstaller (macOS and Linux): stops the watcher, removes the hooks it added, deletes
# ~/.claude-light.   --keep-hooks leaves the hooks in settings.json (they do nothing without
# ~/.claude-light): use it when that settings file is shared with another machine that keeps claude-light.
set -uo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
R="$HOME/.claude-light"
SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
PY=/usr/bin/python3
[ -x "$PY" ] || PY="$(command -v python3 || echo python3)"

if [ "$(uname)" = Darwin ]; then
  LABEL="local.claude-light"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
else
  systemctl --user disable --now claude-light.service 2>/dev/null || true
  rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/claude-light.service"
  systemctl --user daemon-reload 2>/dev/null || true
fi

if [ "${1:-}" != "--keep-hooks" ]; then
  HOOKS="$R/src/settings_hooks.py"
  [ -f "$HOOKS" ] || HOOKS="$SRC/src/settings_hooks.py"
  "$PY" "$HOOKS" remove "$SETTINGS"
fi
rm -rf "$R"
echo "claude-light removed."
