#!/usr/bin/python3
"""claude-light watcher: session files -> display.json, plus crash and API checks."""
import glob
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import fsutil  # noqa: E402
import lightcore as lc  # noqa: E402
import procinfo  # noqa: E402


class Watcher:
    def __init__(self, root, alive, probe, probe_every=15.0):
        self.root = root
        self.state_dir = os.path.join(root, "state")
        self.alive = alive
        self.probe = probe
        self.probe_every = probe_every
        self.prev = None
        self.api_down = None
        self.last_probe = None
        self.acked_path = os.path.join(root, "acked.json")
        self.acked = set(_read_json(self.acked_path) or [])

    def tick(self, now):
        cfg = lc.normalize_config(_read_json(os.path.join(self.root, "config.json")))
        sessions = self._sessions(now)
        self._check_api(sessions, now)
        found = lc.alerts(sessions, self.api_down, now, grace=cfg["grace_seconds"])
        if not cfg["enabled"]:
            found = []
        self._take_acks(found)
        display = lc.compute_display(found, self.acked, self.prev)
        display["sound"] = cfg["sound"]
        display["size"] = cfg["size"]
        everything = lc.alerts(sessions, self.api_down, now, grace=0)   # no delay, no clicks
        display["tray"] = max((a["color"] for a in everything), key=lc.SEVERITY.get) if everything else ""
        display["config"] = cfg
        if not cfg["show_message"]:
            display["message"] = ""
        display["status"] = lc.status_line(display, cfg["enabled"])
        _write_json(os.path.join(self.root, "display.json"), display)
        self.prev = display
        return display

    def _check_api(self, sessions, now):
        working = any(s.get("state") in (lc.RUNNING, lc.GREEN) and s.get("interactive", True)
                      for s in sessions)
        if not working:
            self.api_down, self.last_probe = None, None
            return
        if self.last_probe is not None and now - self.last_probe > 3 * self.probe_every:
            self.api_down = None  # we were asleep (lid shut): an old failure says nothing now
        if self.last_probe is None or now - self.last_probe >= self.probe_every:
            self.last_probe = now
            self.api_down = lc.track_api(self.api_down, self.probe(), now)

    def _take_acks(self, found):
        """Fold the ball's click (ack.json) into the remembered set; forget stale keys."""
        ack_path = os.path.join(self.root, "ack.json")
        ack = _read_json(ack_path)
        if ack is not None:
            os.remove(ack_path)
        clicked = set((ack or {}).get("keys") or [])
        current = set(a["key"] for a in found)
        acked = (self.acked | clicked) & current
        if acked != self.acked:
            self.acked = acked
            _write_json(self.acked_path, sorted(acked))

    def _sessions(self, now):
        """Load every session file, applying the process check as we go."""
        out = []
        for path in sorted(glob.glob(os.path.join(self.state_dir, "*.json"))):
            s = _read_json(path)
            if not isinstance(s, dict):
                continue
            if s.get("state") in (lc.RUNNING, lc.GREEN) and transcript_interrupted(s.get("transcript_path")):
                s = dict(s, state=lc.IDLE)  # Esc ended the turn; Stop never fired
            checked = lc.check_alive(s, self.alive(s), now)
            if checked is None:
                os.remove(path)
                continue
            if checked != s:
                _write_json(path, checked)
            out.append(checked)
        return out


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


_write_json = fsutil.write_json
parse_ps = procinfo.parse_ps


def process_alive(session, table):
    """Is the session's claude process (same pid AND same start time) still running?"""
    if "pid" not in session or table is None:   # None = the lookup failed: never cry crash
        return True
    return table.get(session["pid"]) == session.get("pid_start")


def api_reachable(url, timeout=10.0):
    """Did anything answer at url? Any HTTP status counts; only network failure is 'down'."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "claude-light"})
    try:
        urllib.request.urlopen(req, timeout=timeout).close()
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def transcript_interrupted(path):
    """Was the session's last turn ended by the user pressing Esc? (Stop does not fire then.)"""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 65536))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError):
        return False
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") not in ("user", "assistant"):
            continue  # bookkeeping (last-prompt, cost-state, attachments...)
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        return entry["type"] == "user" and str(content).startswith("[Request interrupted by user")
    return False


def ball_command(platform, root, python):
    """The command that starts the ball (and its menu) on this OS."""
    if platform == "win32":
        import ntpath
        j = ntpath.join
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-File",
                j(root, "windows", "ball.ps1"), j(root, "display.json"), j(root, "bong.wav"), python]
    import posixpath
    j = posixpath.join
    files = [j(root, "display.json"), j(root, "bong.wav")]
    if platform.startswith("linux"):
        return [python, j(root, "linux", "ball.py")] + files
    return [j(root, "bin", "ball")] + files


# ---- runtime (launchd / systemd / the Windows Startup folder run this) -------------

ROOT = os.path.expanduser("~/.claude-light")
PROBE_URL = os.environ.get("CLAUDE_LIGHT_PROBE_URL", "https://api.anthropic.com/")
BALL_RESTART_SECONDS = 10


def _session_pids(root):
    pids = []
    for path in glob.glob(os.path.join(root, "state", "*.json")):
        s = _read_json(path)
        if isinstance(s, dict) and isinstance(s.get("pid"), int):
            pids.append(s["pid"])
    return pids


def main():
    os.makedirs(os.path.join(ROOT, "state"), exist_ok=True)
    if sys.platform == "win32" and sys.stderr is None:   # pythonw has no console: log to a file
        sys.stderr = open(os.path.join(ROOT, "lightd.log"), "a", buffering=1)
    bong_wav = os.path.join(ROOT, "bong.wav")
    if not os.path.exists(bong_wav):
        import bong
        bong.make(bong_wav)
    procs = {"table": None, "at": 0.0}
    watcher = Watcher(ROOT, alive=lambda s: process_alive(s, procs["table"]),
                      probe=lambda: api_reachable(PROBE_URL, 5.0))
    stopping = []
    signal.signal(signal.SIGTERM, lambda *a: stopping.append(1))
    signal.signal(signal.SIGINT, lambda *a: stopping.append(1))
    command = ball_command(sys.platform, ROOT, sys.executable)
    flags = 0x08000000 if sys.platform == "win32" else 0     # CREATE_NO_WINDOW
    ball, ball_started = None, 0.0
    while not stopping:
        now = time.time()
        if now - procs["at"] >= 2.0:
            procs["table"], procs["at"] = procinfo.starts(_session_pids(ROOT)), now
        try:
            watcher.tick(now)
        except Exception as e:  # keep the light alive; log and carry on
            sys.stderr.write("tick failed: %r\n" % (e,))
        if (ball is None or ball.poll() is not None) and now - ball_started >= BALL_RESTART_SECONDS:
            try:
                ball, ball_started = subprocess.Popen(command, creationflags=flags), now
            except OSError as e:
                sys.stderr.write("ball failed to start: %r\n" % (e,))
                ball, ball_started = None, now
        time.sleep(1.0)
    if ball is not None:
        ball.terminate()


if __name__ == "__main__":
    main()
