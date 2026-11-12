# claude-light

A stop light for [Claude Code](https://claude.com/claude-code) on **macOS, Linux and Windows**.
When a session needs you and you have not answered for a while, one big lamp floats over the
top-right of your screen, above every window, with two bongs. It stays there until you answer or
click it. It never takes keyboard focus.

| Lamp | Means |
|---|---|
| 🟢 **QUESTION FOR YOU** | Claude is mid-turn and blocked on you: a question, a permission prompt, an MCP input dialog |
| 🟡 **WAITING FOR YOU** | Claude finished its turn and is waiting on you |
| 🔴 **ERROR** | an API error ended the turn; or the API has been unreachable for 2+ minutes while a session is working; or a `claude` process died mid-turn |

Green and yellow wait for the **delay** (2 minutes by default) before the ball appears, so a
session you are actively working with never lights it. Red shows at once. With several
sessions, the worst colour shows, with the folder names of the sessions behind it.

A status dot (menu bar on macOS, system tray on Windows, Waybar on Linux) shows the current state
immediately (no delay) and holds every setting.

It works in any terminal Claude Code runs in (Terminal, iTerm2, VS Code, Orca, ...): it hooks
Claude Code itself, not the terminal.

## Install

    git clone https://github.com/simmysam3/claude-light.git && cd claude-light

**macOS** (needs the Xcode Command Line Tools: `xcode-select --install`):

    bash install.sh

> **Status:** macOS is in daily use. The Linux and Windows versions are new and have not yet been
> run on real machines: expect rough edges, and please open an issue with what you see.

**Linux**, Wayland compositors with layer-shell: Hyprland (Omarchy), Sway, KDE Plasma, river, ...
(GNOME has no layer-shell: there the ball shows but cannot stay on top). Needs GTK 4 with
layer-shell for Python; on Arch / Omarchy:

    sudo pacman -S --needed python-gobject python-cairo gtk4 gtk4-layer-shell
    bash install.sh

The installer prints a Waybar module to paste into `~/.config/waybar/config.jsonc`; click the dot for
the settings menu (shown in walker, fuzzel, wofi or rofi, whichever you have). The watcher runs as
the systemd user service `claude-light` (logs: `journalctl --user -u claude-light`). It starts with
`graphical-session.target`; if after a reboot `systemctl --user is-active claude-light` says
inactive, your session does not reach that target: add `exec-once = systemctl --user start
claude-light` to your Hyprland config.

**Windows** (needs Python 3 from python.org or `winget install Python.Python.3.12`; no admin):

    powershell -NoProfile -ExecutionPolicy Bypass -File windows\install.ps1

The tray icon holds every setting; it starts at sign-in from your Startup folder. The Windows
hooks run Python directly (no shell) and do nothing if `.claude-light` is missing. The installer
refuses a `settings.json` that is a link to a shared file, since Windows-only hooks there would
break the other machines.

Every installer runs the tests first, copies everything to `~/.claude-light`, and adds nine
hooks to `~/.claude/settings.json` (your other settings and hooks are left alone; a backup is
written next to the file; a symlinked settings file stays a symlink). Run it again to upgrade;
your settings are kept.

Uninstall: `bash uninstall.sh` (Windows: `windows\uninstall.ps1`). Add `--keep-hooks`
(`-KeepHooks`) if your `settings.json` is shared with another machine that keeps claude-light.

## Settings

From the status dot, or the command line (`~/.claude-light/bin/claude-light`, on Windows
`%USERPROFILE%\.claude-light\bin\claude-light.cmd`):

    claude-light status
    claude-light on | off                 # the whole light
    claude-light sound on | off           # visual only, or two bongs
    claude-light delay 2m                 # 0 = immediate; 30, 90, 5m ...
    claude-light size 5                   # 1-10: tenths of the screen height
    claude-light message on | off         # show the end of Claude's last message on the ball
    claude-light preview red              # see it now (6 s)
    claude-light menu                     # Linux: the settings picker (what the Waybar dot opens)
    claude-light restart

## How it decides

- **Yellow** comes from the `Stop` hook. A turn that ends while Claude's own background tasks
  still run is not "waiting" (no yellow): Claude will wake when they finish.
- **Green** comes from `AskUserQuestion` and from permission/input notifications.
- **Esc** does not fire `Stop`; the watcher reads the transcript's last message, and an
  "[Request interrupted by user]" there ends the turn quietly.
- **Crash**: a session whose `claude` process (pid + start time) vanishes mid-turn without a
  `SessionEnd`. A session closed while idle or waiting is just forgotten.
- **API**: while a session is working, a `HEAD https://api.anthropic.com/` every 15 s (no
  credentials, nothing sent); any HTTP answer counts as up. Set `CLAUDE_LIGHT_PROBE_URL` in the
  watcher's environment if you reach Claude through another endpoint.
- Bongs only when the ball appears or gets worse; a click acknowledges what is showing now.
- Headless sessions (`claude -p`, SDK) and subagents never light it (on Windows, headless
  sessions cannot be told apart yet and are treated as interactive).

## Privacy

Everything stays on your computer. The hooks write one small JSON file per session to
`~/.claude-light/state/` (folder, state, process id, and the last ~1200 characters of Claude's
last message, so the ball can show it when you turn that on). Nothing is sent anywhere except
the API reachability probe above.

## Files

| | |
|---|---|
| `src/lightcore.py` | every decision, pure functions |
| `src/hook.py` | the Claude Code hook: one event in, one session file out |
| `src/lightd.py` | the watcher: session files -> `display.json`; crash and API checks; starts the ball |
| `src/lightctl.py` | the settings writer (`config.json`), the CLI, the Waybar output and the Linux menu |
| `src/procinfo.py` | process identity per OS (`ps`, `/proc`, Win32) |
| `src/settings_hooks.py` | adds/removes the hooks in `settings.json` |
| `src/uihelp.py`, `src/fsutil.py`, `src/bong.py` | helpers; the bell is synthesized |
| `src/ball.swift` | macOS: the ball and the menu bar dot |
| `linux/ball.py` | Linux: the ball (GTK 4 + layer-shell) |
| `windows/ball.ps1` | Windows: the ball and the tray icon (WPF) |
| `tests/` | `python3 -m unittest discover -s tests` |

Logs: `~/.claude-light/lightd.log` (macOS), `journalctl --user -u claude-light` (Linux),
`%USERPROFILE%\.claude-light\lightd.log` and `ball.log` (Windows).

## License

MIT, Copyright (c) 2026 Attense, Inc. See [LICENSE](LICENSE).
