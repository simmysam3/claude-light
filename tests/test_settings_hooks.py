import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import settings_hooks as sh  # noqa: E402

THEIRS = {"type": "command", "command": "their-formatter.sh"}


def ours(settings):
    return {e: [g for g in groups if any(sh.MARK in h.get("command", "") for h in g.get("hooks", []))]
            for e, groups in settings.get("hooks", {}).items()}


class TestAddRemove(unittest.TestCase):
    def test_add_puts_one_group_on_each_event_and_keeps_theirs(self):
        before = {"model": "opus", "hooks": {"Stop": [{"hooks": [THEIRS]}]}}
        after = sh.add_hooks(copy.deepcopy(before))
        self.assertEqual(after["model"], "opus")
        self.assertIn({"hooks": [THEIRS]}, after["hooks"]["Stop"])
        mine = ours(after)
        self.assertEqual(sorted(e for e, g in mine.items() if len(g) == 1), sorted(sh.EVENTS))
        self.assertEqual(mine["PreToolUse"][0]["matcher"], "AskUserQuestion")
        self.assertNotIn("async", mine["Stop"][0]["hooks"][0])

    def test_add_twice_does_not_duplicate(self):
        once = sh.add_hooks({})
        self.assertEqual(sh.add_hooks(copy.deepcopy(once)), once)

    def test_remove_takes_only_ours(self):
        both = sh.add_hooks({"hooks": {"Stop": [{"hooks": [THEIRS]}]}})
        self.assertEqual(sh.remove_hooks(both), {"hooks": {"Stop": [{"hooks": [THEIRS]}]}})
        self.assertEqual(sh.remove_hooks(sh.add_hooks({})), {})


class TestUpdateFile(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()

    @unittest.skipIf(sys.platform == "win32", "symlinks need Developer Mode on Windows")
    def test_writes_through_a_symlink_and_keeps_a_backup(self):
        import json
        real = os.path.join(self.dir, "real.json")
        link = os.path.join(self.dir, "settings.json")
        with open(real, "w") as f:
            f.write('{\n  "model": "opus"\n}\n')
        os.symlink(real, link)
        sh.update_file(link, sh.add_hooks)
        self.assertTrue(os.path.islink(link))
        with open(real) as f:
            self.assertIn("Stop", json.load(f)["hooks"])
        with open(real + ".claude-light-backup") as f:
            self.assertEqual(f.read(), '{\n  "model": "opus"\n}\n')

    def test_refuses_a_broken_file_and_creates_a_missing_one(self):
        broken = os.path.join(self.dir, "broken.json")
        with open(broken, "w") as f:
            f.write("{ not json")
        with self.assertRaises(ValueError):
            sh.update_file(broken, sh.add_hooks)
        with open(broken) as f:
            self.assertEqual(f.read(), "{ not json")
        missing = os.path.join(self.dir, "sub", "settings.json")
        sh.update_file(missing, sh.add_hooks)
        self.assertTrue(os.path.exists(missing))


class TestWindowsExecForm(unittest.TestCase):
    PY = r"C:\Users\x\AppData\Local\Programs\Python\Python312\pythonw.exe"
    HOOK = r"C:\Users\x\.claude-light\src\hook.py"

    def test_windows_hooks_run_python_directly_and_come_out_again(self):
        win = sh.windows_hook(self.PY, self.HOOK)
        added = sh.add_hooks({"hooks": {"Stop": [{"hooks": [THEIRS]}]}}, hook=win)
        stop = [g for g in added["hooks"]["Stop"] if g != {"hooks": [THEIRS]}]
        self.assertEqual(stop, [{"hooks": [{"type": "command", "command": self.PY, "args": [self.HOOK],
                                            "timeout": 5}]}])
        self.assertEqual(sh.add_hooks(copy.deepcopy(added), hook=win), added)          # idempotent
        self.assertEqual(sh.remove_hooks(added), {"hooks": {"Stop": [{"hooks": [THEIRS]}]}})


if __name__ == "__main__":
    unittest.main()
