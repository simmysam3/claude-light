#!/bin/zsh
# claude-light uninstaller: stops the watcher, removes the hooks it added, deletes ~/.claude-light.
set -uo pipefail
SRC="${0:A:h}"
R="$HOME/.claude-light"
LABEL="local.claude-light"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
HOOKS="$R/src/settings_hooks.py"
[[ -f "$HOOKS" ]] || HOOKS="$SRC/src/settings_hooks.py"
/usr/bin/python3 "$HOOKS" remove "$SETTINGS"
rm -rf "$R"
echo "claude-light removed (a backup of your settings is next to it: settings.json.claude-light-backup)"
