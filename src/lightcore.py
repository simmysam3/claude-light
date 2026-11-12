"""claude-light: pure decision logic (no I/O). Python 3.9 compatible."""

import os
import re

IDLE = "idle"
RUNNING = "running"
BACKGROUND = "background"  # turn over, but Claude's own background tasks will wake it
GREEN = "green"
YELLOW = "yellow"
RED = "red"


def apply_event(session, payload, now):
    """Return the session record after one hook event (None = forget it)."""
    s = dict(session or {})
    name = payload.get("hook_event_name")
    if name == "SessionEnd":
        return None
    for key in ("session_id", "cwd", "transcript_path"):
        if payload.get(key):
            s[key] = payload[key]
    if "state" not in s:
        _set(s, IDLE, now)
    if payload.get("agent_id") and name != "Notification":
        return s  # subagent/teammate activity says nothing about the main turn
    if now < s.get("seen", 0):
        return s  # an async hook that landed after a newer event: stale
    s["seen"] = now
    if name == "SessionStart":
        if payload.get("source") != "compact" or "state" not in s:
            _set(s, IDLE, now)
    elif name == "Stop":
        busy = any(t.get("status", "running") in ("running", "pending")
                   for t in payload.get("background_tasks") or [])
        _set(s, BACKGROUND if busy else YELLOW, now)
        _keep_message(s, payload.get("last_assistant_message"))
    elif name == "UserPromptSubmit":
        _set(s, RUNNING, now)
    elif name == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion":
        _set(s, GREEN, now)
        questions = (payload.get("tool_input") or {}).get("questions") or [{}]
        _keep_message(s, " / ".join(q.get("question", "") for q in questions if isinstance(q, dict)))
    elif name in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        _set(s, RUNNING, now)
    elif name == "Notification" and payload.get("notification_type") in NEEDS_INPUT:
        _set(s, GREEN, now)
        _keep_message(s, payload.get("message"))
    elif name == "StopFailure":
        _set(s, RED, now)
        s["reason"] = "API error: %s" % payload.get("error", "unknown")
    return s


# Notification types that mean Claude is mid-turn and blocked on an answer.
NEEDS_INPUT = (
    "permission_prompt",
    "elicitation_dialog",
    "elicitation_url_dialog",
    "worker_permission_prompt",
    "agent_needs_input",
)


def _set(s, state, now):
    s["state"] = state
    s["since"] = now
    s.pop("reason", None)
    s.pop("message", None)


MESSAGE_KEEP = 1200  # characters; the ask is at the end of a reply, so keep the tail


def _keep_message(s, text):
    text = (text or "").strip() if isinstance(text, str) else ""
    if text:
        s["message"] = text[-MESSAGE_KEEP:]


API_DOWN_SECONDS = 120
GRACE_SECONDS = 120  # green/yellow wait this long unanswered before the ball shows


def alerts(sessions, api_down_since=None, now=0.0, grace=GRACE_SECONDS):
    """Everything currently asking for attention, as {key, color, text}."""
    out = []
    sessions = [s for s in sessions if s.get("interactive", True)]
    working = any(s.get("state") in (RUNNING, GREEN) for s in sessions)
    if working and api_down_since is not None and now - api_down_since >= API_DOWN_SECONDS:
        out.append({"key": "api|%s" % api_down_since, "color": RED,
                    "text": "API unreachable for 2+ min"})
    for s in sessions:
        waiting = s.get("state") in (GREEN, YELLOW)
        if waiting and now - (s.get("since") or 0) < grace:
            continue  # the person may still be at the keyboard: only nag once the delay is up
        if s.get("state") in SEVERITY:
            name = os.path.basename((s.get("cwd") or "").rstrip("/")) or "claude"
            text = "%s: %s" % (name, s["reason"]) if s.get("reason") else name
            out.append({
                "key": "%s|%s|%s" % (s.get("session_id"), s["state"], s.get("since")),
                "color": s["state"],
                "text": text,
                "since": s.get("since") or 0,
                "message": s.get("message", ""),
            })
    return out


SEVERITY = {GREEN: 1, YELLOW: 2, RED: 3}
HEADLINE = {GREEN: "QUESTION FOR YOU", YELLOW: "WAITING FOR YOU", RED: "ERROR"}


def compute_display(alerts, acked, prev):
    """What the ball shows: {visible, color, label, keys, alert_id}."""
    prev = prev or {"visible": False, "alert_id": 0}
    alert_id = prev.get("alert_id", 0)
    live = [a for a in alerts if a["key"] not in acked]
    if not live:
        return {"visible": False, "keys": [], "alert_id": alert_id}
    color = max((a["color"] for a in live), key=SEVERITY.get)
    if not prev.get("visible") or SEVERITY[color] > SEVERITY.get(prev.get("color"), 0):
        alert_id += 1
    texts = []
    for a in live:
        if a["color"] == color and a["text"] not in texts:
            texts.append(a["text"])
    newest = max((a for a in live if a["color"] == color), key=lambda a: a.get("since", 0))
    return {"visible": True, "color": color, "keys": [a["key"] for a in live],
            "alert_id": alert_id, "headline": HEADLINE[color], "detail": " · ".join(texts),
            "message": tail_text(newest.get("message", ""))}


def check_alive(session, alive, now):
    """Apply the watcher's process check (None = forget the session)."""
    if alive:
        return session
    state = session.get("state")
    if state in (RUNNING, GREEN):
        s = dict(session)
        _set(s, RED, now)
        s["reason"] = "session crashed"
        return s
    if state in (IDLE, YELLOW, BACKGROUND):
        return None
    return session


def track_api(down_since, ok, now):
    """When the API first became unreachable (None = reachable)."""
    if ok:
        return None
    return now if down_since is None else down_since


def is_interactive(args):
    """Is this claude command line a session with a person at the keyboard?"""
    words = (args or "").split()
    return not any(w in ("-p", "--print", "--input-format") for w in words)


DEFAULT_CONFIG = {"enabled": True, "sound": True, "grace_seconds": 120, "size": 5, "show_message": False}


def normalize_config(raw):
    """config.json (written by the menu bar, the CLI or a person) -> a safe, complete config."""
    raw = raw if isinstance(raw, dict) else {}
    c = dict(DEFAULT_CONFIG)
    for key in ("enabled", "sound", "show_message"):
        if isinstance(raw.get(key), bool):
            c[key] = raw[key]
    for key, low, high in (("grace_seconds", 0, 86400), ("size", 1, 10)):
        v = raw.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            c[key] = int(min(high, max(low, v)))
    return c


def tail_text(text, limit=280):
    """The end of a message, at most `limit` characters, cut on a word, prefixed with an ellipsis."""
    plain = " ".join(re.sub(r"[*`#>_]+", "", text or "").split())  # markdown marks and newlines out
    if len(plain) <= limit:
        return plain
    cut = plain[-limit:]
    space = cut.find(" ")
    if 0 <= space < len(cut) - 1:
        cut = cut[space + 1:]
    return "…" + cut


STATUS_NAME = {GREEN: "Question waiting", YELLOW: "A session is waiting", RED: "Error"}


def status_line(display, enabled):
    """One sentence for a tray tooltip or menu header."""
    if not enabled:
        return "claude-light is off"
    if display.get("visible"):
        return "%s: %s" % (STATUS_NAME.get(display.get("color"), "Alert"), display.get("detail", ""))
    if display.get("tray") in STATUS_NAME:
        return "%s (ball after the delay)" % STATUS_NAME[display["tray"]]
    return "All quiet"
