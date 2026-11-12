# claude-light

A stop light for [Claude Code](https://claude.com/claude-code) on macOS. When a session needs
you and you have not answered for a while, one big lamp floats over the top-right of your
screen, above every window and full-screen app, on every Space, with two bongs. It stays there
until you answer or click it. It never takes keyboard focus.

| Lamp | Means |
|---|---|
| 🟢 **QUESTION FOR YOU** | Claude is mid-turn and blocked on you: a question, a permission prompt, an MCP input dialog |
| 🟡 **WAITING FOR YOU** | Claude finished its turn and is waiting on you |
| 🔴 **ERROR** | an API error ended the turn; or the API has been unreachable for 2+ minutes while a session is working; or a `claude` process died mid-turn |

Green and yellow wait for the **delay** (2 minutes by default) before the ball appears, so a
session you are actively working with never lights it. Red shows at once. With several
sessions, the worst colour shows, with the folder names of the sessions behind it.

A dot in the menu bar shows the current state immediately (no delay) and holds every setting.

It works in any terminal Claude Code runs in (Terminal, iTerm2, VS Code, Orca, ...): it hooks
Claude Code itself, not the terminal.

## Install

Needs macOS and the Xcode Command Line Tools (`xcode-select --install`).

    git clone https://github.com/simmysam3/claude-light.git && cd claude-light
    zsh install.sh

The installer runs the tests, copies everything to `~/.claude-light`, builds the ball, adds
nine hooks to `~/.claude/settings.json` (your other settings and hooks are left alone; a backup
is written next to the file; a symlinked settings file stays a symlink) and starts a launchd
agent that runs at login. Run it again to upgrade; your settings are kept.

Uninstall: `zsh uninstall.sh` (stops the agent, removes only its own hooks, deletes `~/.claude-light`).

## Settings

From the menu bar dot, or the command line:

    ~/.claude-light/bin/claude-light status
    ~/.claude-light/bin/claude-light on | off                 # the whole light
    ~/.claude-light/bin/claude-light sound on | off           # visual only, or two bongs
    ~/.claude-light/bin/claude-light delay 2m                 # 0 = immediate; 30, 90, 5m ...
    ~/.claude-light/bin/claude-light size 5                   # 1-10: tenths of the screen height
    ~/.claude-light/bin/claude-light message on | off         # show the end of Claude's last message
    ~/.claude-light/bin/claude-light preview red              # see it now (6 s)

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
  launchd plist if you reach Claude through another endpoint.
- Bongs only when the ball appears or gets worse; a click acknowledges what is showing now.
- Headless sessions (`claude -p`, SDK) and subagents never light it.

## Privacy

Everything stays on your Mac. The hooks write one small JSON file per session to
`~/.claude-light/state/` (folder, state, process id, and the last ~1200 characters of Claude's
last message, so the ball can show it when you turn that on). Nothing is sent anywhere except
the API reachability probe above.

## Files

| | |
|---|---|
| `src/lightcore.py` | every decision, pure functions |
| `src/hook.py` | the Claude Code hook: one event in, one session file out |
| `src/lightd.py` | the watcher: session files -> `display.json`; crash and API checks |
| `src/lightctl.py` | the settings writer (`config.json`), used by the CLI and the menu bar |
| `src/settings_hooks.py` | adds/removes the hooks in `settings.json` |
| `src/ball.swift` | the ball and the menu bar dot: draws `display.json`, plays the bong |
| `src/bong.py` | synthesizes the bell |
| `tests/` | `python3 -m unittest discover -s tests` |

Logs (watcher errors, one line per bong): `~/.claude-light/lightd.log`.

## License

MIT, Copyright (c) 2026 Attense, Inc. See [LICENSE](LICENSE).
