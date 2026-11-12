import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import hook  # noqa: E402

START = "Wed Nov 11 19:52:26 2026"


def fake_proc(pid):
    return (START, "claude --effort xhigh") if pid == 4242 else None


class TestHookWrites(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def send(self, payload, ppid="4242", now=10.0):
        hook.run(["hook.py", ppid], json.dumps(payload), self.dir, now, fake_proc)

    def read(self, sid="s1"):
        with open(os.path.join(self.dir, sid + ".json")) as f:
            return json.load(f)

    def test_stop_event_writes_yellow_with_process_identity(self):
        self.send({"hook_event_name": "Stop", "session_id": "s1", "cwd": "/x/webapp"})
        s = self.read()
        self.assertEqual((s["state"], s["cwd"]), ("yellow", "/x/webapp"))
        self.assertEqual((s["pid"], s["pid_start"], s["interactive"]), (4242, START, True))

    def test_session_end_deletes_the_file(self):
        self.send({"hook_event_name": "Stop", "session_id": "s1"})
        self.send({"hook_event_name": "SessionEnd", "session_id": "s1"})
        self.assertEqual(os.listdir(self.dir), [])

    def test_odd_session_ids_are_refused(self):
        self.send({"hook_event_name": "Stop", "session_id": "../evil"})
        self.assertEqual(os.listdir(self.dir), [])


class TestParentWithoutArgument(unittest.TestCase):
    def test_no_pid_argument_uses_the_hooks_own_parent(self):
        d = tempfile.mkdtemp()
        payload = {"hook_event_name": "Stop", "session_id": "s1", "cwd": "/x/webapp"}
        hook.run(["hook.py"], json.dumps(payload), d, 10.0, fake_proc, getppid=lambda: 4242)
        with open(os.path.join(d, "s1.json")) as f:
            self.assertEqual(json.load(f)["pid"], 4242)


if __name__ == "__main__":
    unittest.main()
