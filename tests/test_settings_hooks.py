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

    def test_windows_hooks_run_python_directly_and_come_out_again(self):
        win = sh.windows_hook(self.PY)
        added = sh.add_hooks({"hooks": {"Stop": [{"hooks": [THEIRS]}]}}, hook=win)
        stop = [g for g in added["hooks"]["Stop"] if g != {"hooks": [THEIRS]}]
        self.assertEqual(len(stop), 1)
        self.assertEqual(stop[0]["hooks"][0]["command"], self.PY)
        self.assertEqual(stop[0]["hooks"][0]["args"][0], "-c")
        self.assertEqual(sh.add_hooks(copy.deepcopy(added), hook=win), added)          # idempotent
        self.assertEqual(sh.remove_hooks(added), {"hooks": {"Stop": [{"hooks": [THEIRS]}]}})

    def run_guard(self, home):
        import subprocess
        args = sh.windows_hook(sys.executable)["args"]
        return subprocess.run([sys.executable] + args, input=b"{}", capture_output=True,
                              env=dict(os.environ, HOME=home, USERPROFILE=home))

    def test_a_missing_install_exits_0_never_2(self):
        import tempfile
        done = self.run_guard(tempfile.mkdtemp())                 # no .claude-light at all
        self.assertEqual(done.returncode, 0, done.stderr)         # 2 would BLOCK prompts and turn ends

    def test_an_installed_hook_runs_as_main_with_its_own_path(self):
        import tempfile
        home = tempfile.mkdtemp()
        os.makedirs(os.path.join(home, ".claude-light", "src"))
        with open(os.path.join(home, ".claude-light", "src", "hook.py"), "w") as f:
            f.write("import sys\nif __name__ == '__main__':\n    print('ran', sys.argv[0].endswith('hook.py'), len(sys.argv))\n")
        done = self.run_guard(home)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, b"ran True 1"))


class TestSettingsEncoding(unittest.TestCase):
    def test_utf8_settings_survive_a_cp1252_default(self):
        import builtins
        import json
        import tempfile
        from unittest import mock
        real_open = builtins.open

        def windows_open(file, mode="r", *a, encoding=None, **kw):   # Windows: text files default to cp1252
            if "b" not in mode and encoding is None:
                encoding = "cp1252"
            return real_open(file, mode, *a, encoding=encoding, **kw)

        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        with real_open(path, "w", encoding="utf-8") as f:
            json.dump({"statusLine": "Á ✓ ready"}, f, ensure_ascii=False)
        with mock.patch("builtins.open", windows_open):
            sh.update_file(path, sh.add_hooks)
        with real_open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["statusLine"], "Á ✓ ready")


class TestExecHooksNeverInASharedFile(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "symlinks need Developer Mode on Windows")
    def test_add_exec_refuses_a_symlinked_settings_file(self):
        import tempfile
        d = tempfile.mkdtemp()
        real, link = os.path.join(d, "shared.json"), os.path.join(d, "settings.json")
        with open(real, "w") as f:
            f.write("{}\n")
        os.symlink(real, link)
        self.assertEqual(sh.main(["add-exec", r"C:\Py\pythonw.exe", link]), 1)
        with open(real) as f:
            self.assertEqual(f.read(), "{}\n")


if __name__ == "__main__":
    unittest.main()
