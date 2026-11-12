#!/usr/bin/python3
"""claude-light settings: the one writer of config.json (used by the CLI and the menu bar).

  lightctl.py on | off | sound on|off | message on|off | size 1-10 | delay <seconds|Nm> | status
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import fsutil  # noqa: E402
import lightcore as lc  # noqa: E402
import uihelp  # noqa: E402

ROOT = os.path.expanduser("~/.claude-light")
SWITCHES = {"sound": "sound", "message": "show_message"}


def apply_command(cfg, args):
    """Return (new config, one-line reply) for a settings command, or raise ValueError."""
    cfg = lc.normalize_config(cfg)
    cmd, rest = (args[0] if args else ""), args[1:]
    if cmd in ("on", "off") and not rest:
        cfg["enabled"] = cmd == "on"
        return cfg, "claude-light: %s" % cmd.upper()
    if cmd in SWITCHES and len(rest) == 1 and rest[0] in ("on", "off"):
        cfg[SWITCHES[cmd]] = rest[0] == "on"
        return cfg, "claude-light: %s %s" % (cmd, rest[0].upper())
    if cmd == "size" and len(rest) == 1 and rest[0].isdigit() and 1 <= int(rest[0]) <= 10:
        cfg["size"] = int(rest[0])
        return cfg, "claude-light: size %d0%% of the screen" % cfg["size"]
    if cmd == "delay" and len(rest) == 1:
        cfg["grace_seconds"] = _seconds(rest[0])
        return cfg, "claude-light: delay %s" % describe_delay(cfg["grace_seconds"])
    raise ValueError("usage: on | off | sound on|off | message on|off | size 1-10 | delay <seconds|Nm>")


def _seconds(text):
    t = text.strip().lower()
    mult = 60 if t.endswith("m") else 1
    t = t[:-1] if t[-1:] in ("m", "s") else t
    if not t.isdigit():
        raise ValueError("delay must be seconds (30) or minutes (2m)")
    return int(t) * mult


def describe_delay(seconds):
    if seconds == 0:
        return "none (immediate)"
    return "%d min" % (seconds // 60) if seconds % 60 == 0 else "%d s" % seconds


def describe(cfg):
    return "\n".join([
        "switch : %s" % ("ON" if cfg["enabled"] else "OFF"),
        "sound  : %s" % ("ON" if cfg["sound"] else "OFF"),
        "delay  : %s" % describe_delay(cfg["grace_seconds"]),
        "size   : %d0%% of the screen" % cfg["size"],
        "message: %s" % ("shown" if cfg["show_message"] else "hidden"),
    ])


def waybar(root, follow=False):
    """One Waybar JSON line from display.json; with follow, a new line whenever it changes."""
    last = None
    while True:
        try:
            with open(os.path.join(root, "display.json")) as f:
                display = json.load(f)
        except (OSError, ValueError):
            display = None
        line = json.dumps(uihelp.waybar_line(display), ensure_ascii=False)
        if line != last:
            print(line, flush=True)
            last = line
        if not follow:
            return 0
        time.sleep(0.5)


def run_menu(root, choose):
    """Offer the settings as a list; apply the line chosen (choose returns None on cancel)."""
    entries = uihelp.menu_entries(_load_config(root))
    picked = dict(entries).get(choose([label for label, _ in entries]) or "")
    return main(picked, root=root) if picked else 0


def dmenu_chooser(labels):
    import shutil
    import subprocess
    command = uihelp.pick_dmenu(shutil.which)
    if not command:
        sys.stderr.write("claude-light: no picker found (walker, fuzzel, wofi or rofi)\n")
        return None
    done = subprocess.run(command, input="\n".join(labels) + "\n", capture_output=True, text=True)
    return done.stdout.rstrip("\n") or None


def _load_config(root):
    try:
        with open(os.path.join(root, "config.json")) as f:
            return lc.normalize_config(json.load(f))
    except (OSError, ValueError):
        return lc.normalize_config(None)


def main(argv, root=ROOT):
    path = os.path.join(root, "config.json")
    try:
        with open(path) as f:
            cfg = lc.normalize_config(json.load(f))
    except (OSError, ValueError):
        cfg = lc.normalize_config(None)
    if not argv or argv[0] == "status":
        print(describe(cfg))
        return 0
    if argv[0] == "waybar":
        return waybar(root, follow="--follow" in argv)
    if argv[0] == "menu":
        return run_menu(root, dmenu_chooser)
    if argv[0] == "preview":
        color = argv[1] if len(argv) > 1 else "yellow"
        if color not in ("green", "yellow", "red"):
            sys.stderr.write("claude-light: preview green|yellow|red\n")
            return 2
        fsutil.write_json(os.path.join(root, "preview.json"), {"color": color})
        print("claude-light: previewing %s for 6 s (needs the watcher running)" % color)
        return 0
    try:
        cfg, reply = apply_command(cfg, argv)
    except ValueError as e:
        sys.stderr.write("claude-light: %s\n" % e)
        return 2
    fsutil.write_json(path, cfg)
    print(reply)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
