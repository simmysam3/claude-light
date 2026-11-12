#!/usr/bin/python3
"""Add or remove the claude-light hooks in a Claude Code settings.json, leaving everything else alone.

  settings_hooks.py add|remove [settings.json]     (default: ~/.claude/settings.json)
"""
import json
import os
import sys

MARK = ".claude-light/src/hook.py"
COMMAND = ('if [ -x "$HOME/.claude-light/src/hook.py" ]; then "$HOME/.claude-light/src/hook.py" "$PPID"; '
           'else cat >/dev/null; fi; exit 0')
EVENTS = ["SessionStart", "SessionEnd", "UserPromptSubmit", "Stop", "StopFailure", "Notification",
          "PreToolUse", "PostToolUse", "PostToolUseFailure"]


def _is_ours(group):
    return any(MARK in h.get("command", "") for h in group.get("hooks", []) if isinstance(h, dict))


def add_hooks(settings):
    hooks = settings.setdefault("hooks", {})
    for event in EVENTS:
        groups = hooks.setdefault(event, [])
        if any(_is_ours(g) for g in groups):
            continue
        group = {"hooks": [{"type": "command", "command": COMMAND, "timeout": 5}]}
        if event == "PreToolUse":
            group = {"matcher": "AskUserQuestion", **group}
        groups.append(group)
    return settings


def remove_hooks(settings):
    hooks = settings.get("hooks", {})
    for event in list(hooks):
        kept = [g for g in hooks[event] if not _is_ours(g)]
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if "hooks" in settings and not hooks:
        del settings["hooks"]
    return settings


def update_file(path, change):
    """Apply change(settings_dict) to the settings file at path.

    Writes the real file behind a symlink (never replaces the link), keeps a backup of the
    previous text, refuses a file that is not a JSON object, creates a missing one.
    """
    real = os.path.realpath(path)
    old_text = None
    if os.path.exists(real):
        with open(real) as f:
            old_text = f.read()
        try:
            settings = json.loads(old_text) if old_text.strip() else {}
        except ValueError:
            raise ValueError("%s is not valid JSON; fix it first, nothing was changed" % path)
        if not isinstance(settings, dict):
            raise ValueError("%s is not a JSON object; nothing was changed" % path)
    else:
        settings = {}
        os.makedirs(os.path.dirname(real), exist_ok=True)
    new_text = json.dumps(change(settings), indent=2, ensure_ascii=False) + "\n"
    if new_text == old_text:
        return False
    if old_text is not None:
        with open(real + ".claude-light-backup", "w") as f:
            f.write(old_text)
    tmp = "%s.claude-light.tmp" % real
    with open(tmp, "w") as f:
        f.write(new_text)
    os.replace(tmp, real)
    return True


def main(argv):
    if not argv or argv[0] not in ("add", "remove"):
        sys.stderr.write("usage: settings_hooks.py add|remove [settings.json]\n")
        return 2
    path = os.path.expanduser(argv[1] if len(argv) > 1 else "~/.claude/settings.json")
    change = add_hooks if argv[0] == "add" else remove_hooks
    try:
        changed = update_file(path, change)
    except ValueError as e:
        sys.stderr.write("claude-light: %s\n" % e)
        return 1
    print("claude-light: hooks %s in %s" % (
        ("added" if argv[0] == "add" else "removed") if changed else "already up to date", path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
