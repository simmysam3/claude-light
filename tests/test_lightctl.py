import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import lightcore as lc  # noqa: E402
import lightctl  # noqa: E402


def run(*args, cfg=None):
    return lightctl.apply_command(cfg or dict(lc.DEFAULT_CONFIG), list(args))[0]


class TestCommands(unittest.TestCase):
    def test_each_setting(self):
        self.assertFalse(run("off")["enabled"])
        self.assertTrue(run("on", cfg=dict(lc.DEFAULT_CONFIG, enabled=False))["enabled"])
        self.assertFalse(run("sound", "off")["sound"])
        self.assertTrue(run("message", "on")["show_message"])
        self.assertEqual(run("size", "8")["size"], 8)
        self.assertEqual(run("delay", "30")["grace_seconds"], 30)
        self.assertEqual(run("delay", "5m")["grace_seconds"], 300)
        self.assertEqual(run("delay", "0")["grace_seconds"], 0)

    def test_bad_input_is_refused_not_guessed(self):
        for bad in (("size", "11"), ("size", "big"), ("delay", "soon"), ("sound", "loud"), ("fly",)):
            with self.assertRaises(ValueError, msg=bad):
                run(*bad)


class TestPreviewCommand(unittest.TestCase):
    def test_preview_asks_the_running_ball_and_refuses_odd_colours(self):
        import json
        import tempfile
        root = tempfile.mkdtemp()
        self.assertEqual(lightctl.main(["preview", "red"], root=root), 0)
        with open(os.path.join(root, "preview.json")) as f:
            self.assertEqual(json.load(f), {"color": "red"})
        os.remove(os.path.join(root, "preview.json"))
        self.assertEqual(lightctl.main(["preview", "blue"], root=root), 2)
        self.assertFalse(os.path.exists(os.path.join(root, "preview.json")))


class TestWaybarCommand(unittest.TestCase):
    def test_prints_the_dot_for_waybar(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        root = tempfile.mkdtemp()
        with open(os.path.join(root, "display.json"), "w") as f:
            json.dump({"tray": "red", "status": "Error: webapp", "config": {"enabled": True}}, f)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(lightctl.main(["waybar"], root=root), 0)
        self.assertEqual(json.loads(out.getvalue())["class"], "red")


class TestMenuCommand(unittest.TestCase):
    def test_the_chosen_line_is_applied_and_cancel_changes_nothing(self):
        import json
        import tempfile
        root = tempfile.mkdtemp()
        shown = []

        def choose(labels):
            shown.extend(labels)
            return "✓ Sound"

        self.assertEqual(lightctl.run_menu(root, choose), 0)
        self.assertIn("✓ Light on", shown)
        with open(os.path.join(root, "config.json")) as f:
            self.assertFalse(json.load(f)["sound"])
        self.assertEqual(lightctl.run_menu(root, lambda labels: None), 0)       # Esc in the picker
        with open(os.path.join(root, "config.json")) as f:
            self.assertFalse(json.load(f)["sound"])


if __name__ == "__main__":
    unittest.main()
