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


if __name__ == "__main__":
    unittest.main()
