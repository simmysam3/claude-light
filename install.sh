#!/usr/bin/env bash
# claude-light installer for macOS and Linux. From a clone of the repo:   bash install.sh
# (Windows: powershell -NoProfile -ExecutionPolicy Bypass -File windows\install.ps1)
# Safe to run again (upgrades in place, keeps your settings).
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
R="$HOME/.claude-light"
SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
OS="$(uname)"
PY=/usr/bin/python3
[ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "claude-light needs python3." >&2; exit 1; }

case "$OS" in
  Darwin)
    command -v swiftc >/dev/null || { echo "Needs the Xcode Command Line Tools: xcode-select --install" >&2; exit 1; } ;;
  Linux)
    if ! "$PY" - 2>/dev/null <<'EOF'
import ctypes
ctypes.CDLL("libgtk4-layer-shell.so")
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gtk4LayerShell, PangoCairo
import cairo
EOF
    then
      echo "claude-light needs GTK 4 with layer-shell for Python. On Arch / Omarchy:" >&2
      echo "  sudo pacman -S --needed python-gobject python-cairo gtk4 gtk4-layer-shell" >&2
      echo "(Other distros: PyGObject, pycairo, GTK 4 and gtk4-layer-shell from your package manager.)" >&2
      exit 1
    fi ;;
  *)
    echo "Unsupported system: $OS. On Windows run windows\\install.ps1." >&2; exit 1 ;;
esac

echo "1/5 tests"
(cd "$SRC" && "$PY" -m unittest discover -s tests -q)

echo "2/5 files -> $R"
mkdir -p "$R/src" "$R/bin" "$R/state"
cp "$SRC"/src/*.py "$R/src/"
cp "$SRC/README.md" "$R/"
cp "$SRC/bin/claude-light" "$R/bin/claude-light"
chmod +x "$R"/src/*.py "$R/bin/claude-light"

echo "3/5 the ball and the bong"
if [ "$OS" = Darwin ]; then
  cp "$SRC/src/ball.swift" "$R/src/"
  swiftc -O -o "$R/bin/ball" "$R/src/ball.swift"
else
  mkdir -p "$R/linux"
  cp "$SRC/linux/ball.py" "$R/linux/"
  chmod +x "$R/linux/ball.py"
fi
"$PY" "$R/src/bong.py" "$R/bong.wav"
if [ -e "$R/disabled" ]; then "$PY" "$R/src/lightctl.py" off >/dev/null; rm -f "$R/disabled"; fi
if [ -e "$R/muted" ]; then "$PY" "$R/src/lightctl.py" sound off >/dev/null; rm -f "$R/muted"; fi

echo "4/5 Claude Code hooks"
"$PY" "$R/src/settings_hooks.py" add "$SETTINGS"

if [ "$OS" = Darwin ]; then
  LABEL="local.claude-light"
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  echo "5/5 watcher (launchd $LABEL, starts at login)"
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$R/src/lightd.py</string></array>
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
  for _ in $(seq 1 40); do
    launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || break
    sleep 0.25
  done
  if ! launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null; then
    sleep 2
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
  fi
  echo
  echo "claude-light is installed: a dot in the menu bar (top right) holds every setting."
else
  UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  echo "5/5 watcher (systemd user service claude-light, starts with your graphical session)"
  mkdir -p "$UNIT_DIR"
  cat > "$UNIT_DIR/claude-light.service" <<EOF
[Unit]
Description=claude-light (a stop light for Claude Code)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=$PY $R/src/lightd.py
Restart=always
RestartSec=3

[Install]
WantedBy=graphical-session.target
EOF
  # The ball draws on Wayland: hand this session's display variables to the user service manager.
  systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE 2>/dev/null || true
  systemctl --user daemon-reload
  systemctl --user enable claude-light.service >/dev/null
  systemctl --user restart claude-light.service
  echo
  echo "claude-light is installed. For the status dot and settings menu in Waybar, add this module"
  echo "to ~/.config/waybar/config.jsonc (and \"custom/claude-light\" to \"modules-right\"):"
  cat <<'EOF'

  "custom/claude-light": {
    "exec": "~/.claude-light/bin/claude-light waybar --follow",
    "return-type": "json",
    "on-click": "~/.claude-light/bin/claude-light menu",
    "tooltip": true
  }

EOF
  echo "then reload Waybar:  pkill -SIGUSR2 waybar"
fi
echo "Try it: $R/bin/claude-light preview yellow"
