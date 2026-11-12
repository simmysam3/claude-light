#!/bin/zsh
# claude-light installer (macOS). From a clone of the repo:   zsh install.sh
# Safe to run again (upgrades in place, keeps your settings).
set -euo pipefail
SRC="${0:A:h}"
R="$HOME/.claude-light"
LABEL="local.claude-light"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"

[[ "$(uname)" == Darwin ]] || { echo "claude-light runs on macOS only." >&2; exit 1; }
command -v swiftc >/dev/null || { echo "Needs the Xcode Command Line Tools: xcode-select --install" >&2; exit 1; }

echo "1/5 tests"
(cd "$SRC" && /usr/bin/python3 -m unittest discover -s tests -q)

echo "2/5 files -> $R"
mkdir -p "$R/src" "$R/bin" "$R/state"
cp "$SRC"/src/*.py "$SRC"/src/ball.swift "$R/src/"
cp "$SRC"/bin/claude-light "$SRC"/README.md "$R/"
mv "$R/claude-light" "$R/bin/claude-light"
chmod +x "$R"/src/*.py "$R/bin/claude-light"

echo "3/5 build the ball and the bong"
swiftc -O -o "$R/bin/ball" "$R/src/ball.swift"
/usr/bin/python3 "$R/src/bong.py" "$R/bong.wav"
if [[ -e "$R/disabled" ]]; then /usr/bin/python3 "$R/src/lightctl.py" off >/dev/null; rm -f "$R/disabled"; fi
if [[ -e "$R/muted" ]]; then /usr/bin/python3 "$R/src/lightctl.py" sound off >/dev/null; rm -f "$R/muted"; fi

echo "4/5 Claude Code hooks"
/usr/bin/python3 "$R/src/settings_hooks.py" add "$SETTINGS"

echo "5/5 watcher (launchd $LABEL, starts at login)"
mkdir -p "${PLIST:h}"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/python3</string><string>$R/src/lightd.py</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Interactive</string>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>StandardOutPath</key><string>$R/lightd.log</string>
  <key>StandardErrorPath</key><string>$R/lightd.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
# bootout returns before launchd has finished unloading; a bootstrap sent too soon fails with
# "Bootstrap failed: 5: Input/output error". Wait for the old copy to go, then retry once.
for i in {1..40}; do
  launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || break
  sleep 0.25
done
if ! launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null; then
  sleep 2
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
fi

echo
echo "claude-light is installed: a dot in the menu bar (top right) holds every setting."
echo "Try it: $R/bin/claude-light preview yellow"
