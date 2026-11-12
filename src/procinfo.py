"""claude-light: who is process <pid>? A start time (pid reuse proof) and a command line, per OS."""
import os
import subprocess
import sys


def parse_proc_stat(text):
    """Linux /proc/<pid>/stat -> the process start time (clock ticks since boot) as a string."""
    _, close, rest = (text or "").rpartition(")")
    fields = rest.split() if close else []
    return fields[19] if len(fields) > 19 and fields[19].isdigit() else None


def parse_proc_cmdline(raw):
    """Linux /proc/<pid>/cmdline (NUL-separated bytes) -> one space-separated string."""
    return " ".join(p.decode("utf-8", "replace") for p in (raw or b"").split(b"\x00") if p)


def identify(pid, platform=None, proc_root="/proc"):
    """(start time, command line) of a live process, or None."""
    platform = platform or sys.platform
    try:
        pid = int(pid)
        if platform.startswith("linux"):
            start = _linux_start(pid, proc_root)
            if start is None:
                return None
            with open(os.path.join(proc_root, str(pid), "cmdline"), "rb") as f:
                return start, parse_proc_cmdline(f.read())
        if platform == "win32":
            start = _win_start(pid)
            return (start, "") if start else None   # Windows: no cheap command line; treated as interactive
        out = _ps(["-o", "lstart=,args=", "-p", str(pid)]).strip()
        return (out[:24], out[24:].strip()) if len(out) >= 25 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def starts(pids, platform=None, proc_root="/proc"):
    """{pid: start time} for those of pids still alive; None if the lookup itself failed."""
    platform = platform or sys.platform
    pids = sorted(set(int(p) for p in pids))
    if not pids:
        return {}
    try:
        if platform.startswith("linux"):
            found = {p: _linux_start(p, proc_root) for p in pids}
        elif platform == "win32":
            found = {p: _win_start(p) for p in pids}
        else:
            return parse_ps(_ps(["-o", "pid=,lstart=", "-p", ",".join(map(str, pids))]))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return {p: s for p, s in found.items() if s}


def parse_ps(text):
    """`ps -o pid=,lstart=` output -> {pid: start time}."""
    table = {}
    for line in text.splitlines():
        pid, _, start = line.strip().partition(" ")
        if pid.isdigit():
            table[int(pid)] = start.strip()
    return table


def _ps(args):
    """Run /bin/ps in the C locale (stable date format). A pid that matched nothing is not an error
    (exit 1, silent); anything ps complains about is, and raises so callers answer "unknown"."""
    done = subprocess.run(["/bin/ps"] + args, capture_output=True, text=True, timeout=5,
                          env=dict(os.environ, LC_ALL="C"))
    if done.stderr.strip():
        raise OSError(done.stderr.strip())
    return done.stdout


def _linux_start(pid, proc_root):
    try:
        with open(os.path.join(proc_root, str(pid), "stat")) as f:
            return parse_proc_stat(f.read())
    except OSError:
        return None


def _win_start(pid):
    """Creation time of a RUNNING process (FILETIME as a string), or None."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    handle = k32.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:   # STILL_ACTIVE
            return None
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not k32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                   ctypes.byref(kernel), ctypes.byref(user)):
            return None
        return str((created.dwHighDateTime << 32) | created.dwLowDateTime)
    finally:
        k32.CloseHandle(handle)
