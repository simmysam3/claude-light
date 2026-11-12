"""claude-light: small pure helpers for the Linux and Windows front ends (Waybar, menus, sound)."""

DOT = {"green": "#1AE661", "yellow": "#FFC214", "red": "#FF2924"}


def waybar_line(display):
    """display.json -> the JSON object a Waybar custom module (return-type json) expects."""
    d = display if isinstance(display, dict) else {}
    if not d or not (d.get("config") or {}).get("enabled", True):
        return {"text": "⊘", "alt": "off", "class": "off", "tooltip": d.get("status", "claude-light is off")}
    color = d.get("tray") or ""
    if color in DOT:
        text = "<span color='%s'>●</span>" % DOT[color]
    else:
        text, color = "○", "quiet"
    return {"text": text, "alt": color, "class": color, "tooltip": d.get("status", "")}


def menu_entries(cfg):
    """[(label, lightctl args)] for a one-level picker menu (walker/fuzzel/wofi/rofi)."""
    def mark(on):
        return "✓ " if on else "   "

    out = []
    for title, key, on_args, off_args in (("Light on", "enabled", ["on"], ["off"]),
                                          ("Sound", "sound", ["sound", "on"], ["sound", "off"]),
                                          ("Show Claude's message", "show_message",
                                           ["message", "on"], ["message", "off"])):
        out.append((mark(cfg[key]) + title, off_args if cfg[key] else on_args))
    for label, secs in DELAYS:
        out.append((mark(cfg["grace_seconds"] == secs) + "Delay: " + label, ["delay", str(secs)]))
    for n in range(1, 11):
        out.append((mark(cfg["size"] == n) + "Size: %d0%%" % n, ["size", str(n)]))
    for color in ("green", "yellow", "red"):
        out.append(("   Preview: " + color, ["preview", color]))
    return out


DELAYS = [("Immediately", 0), ("30 seconds", 30), ("1 minute", 60), ("2 minutes", 120),
          ("5 minutes", 300), ("10 minutes", 600)]


def pick_dmenu(which):
    """The first installed picker that reads choices on stdin, as a command list (or None)."""
    for name, flags in (("walker", ["--dmenu"]), ("fuzzel", ["--dmenu"]), ("wofi", ["--dmenu"]),
                        ("rofi", ["-dmenu", "-i"])):
        path = which(name)
        if path:
            return [path] + flags
    return None


def pick_player(which, wav):
    """The first installed command-line WAV player, as a command list (or None)."""
    for name, flags in (("pw-play", []), ("paplay", []), ("aplay", ["-q"])):
        path = which(name)
        if path:
            return [path] + flags + [wav]
    return None
