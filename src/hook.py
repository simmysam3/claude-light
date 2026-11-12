#!/usr/bin/python3
"""claude-light hook: one Claude Code hook event on stdin -> one session state file.

Usage (from settings.json): hook.py "$PPID"   ($PPID = the claude process; on Windows no argument)
Never prints, never fails: Claude must not notice it.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import fsutil  # noqa: E402
import lightcore as lc  # noqa: E402
import procinfo  # noqa: E402

STATE_DIR = os.path.expanduser("~/.claude-light/state")
IDENTIFY_ON = ("SessionStart", "UserPromptSubmit")


def run(argv, stdin_text, state_dir, now, proc_info, getppid=os.getppid):
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
    if "pid" not in new or payload.get("hook_event_name") in IDENTIFY_ON:
        # POSIX: the shell passes "$PPID" (= claude). Windows runs us without a shell: our parent IS claude.
        _identify(new, argv[1] if len(argv) > 1 else getppid(), proc_info)
    _save(path, new)


def _identify(s, ppid, proc_info):
    try:
        pid = int(ppid)
    except (TypeError, ValueError):
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
    fsutil.write_json(path, data)


def main():
    try:
        run(sys.argv, sys.stdin.read(), STATE_DIR, time.time(), procinfo.identify)
    except Exception:  # never disturb Claude
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
