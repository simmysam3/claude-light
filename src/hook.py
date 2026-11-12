#!/usr/bin/python3
"""claude-light hook: one Claude Code hook event on stdin -> one session state file.

Usage (from settings.json): hook.py "$PPID"   ($PPID = the claude process)
Never prints, never fails: Claude must not notice it.
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import lightcore as lc  # noqa: E402

STATE_DIR = os.path.expanduser("~/.claude-light/state")
IDENTIFY_ON = ("SessionStart", "UserPromptSubmit")


def run(argv, stdin_text, state_dir, now, proc_info):
    payload = json.loads(stdin_text)
    sid = payload.get("session_id") or ""
    if not re.match(r"^[A-Za-z0-9_-]+$", sid):
        return
    path = os.path.join(state_dir, sid + ".json")
    old = _load(path)
    new = lc.apply_event(old, payload, now)
    if new is None:
        if os.path.exists(path):
            os.remove(path)
        return
    if ("pid" not in new or payload.get("hook_event_name") in IDENTIFY_ON) and len(argv) > 1:
        _identify(new, argv[1], proc_info)
    _save(path, new)


def _identify(s, ppid, proc_info):
    try:
        pid = int(ppid)
    except ValueError:
        return
    info = proc_info(pid)
    if info:
        s["pid"], s["pid_start"] = pid, info[0]
        s["interactive"] = lc.is_interactive(info[1])


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def ps_info(pid):
    """(start time, command line) of a live process, or None."""
    try:
        out = subprocess.run(["/bin/ps", "-o", "lstart=,args=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=3,
                             env=dict(os.environ, LC_ALL="C")).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if len(out) < 25:
        return None
    return out[:24], out[24:].strip()


def main():
    try:
        run(sys.argv, sys.stdin.read(), STATE_DIR, time.time(), ps_info)
    except Exception:  # never disturb Claude
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
