#!/usr/bin/python3
"""claude-light settings: the one writer of config.json (used by the CLI and the menu bar).

  lightctl.py on | off | sound on|off | message on|off | size 1-10 | delay <seconds|Nm> | status
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import lightcore as lc  # noqa: E402

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
    try:
        cfg, reply = apply_command(cfg, argv)
    except ValueError as e:
        sys.stderr.write("claude-light: %s\n" % e)
        return 2
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=1)
    os.replace(tmp, path)
    print(reply)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
