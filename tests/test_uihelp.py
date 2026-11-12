import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import uihelp  # noqa: E402


def display(tray="", enabled=True, status="All quiet"):
    return {"tray": tray, "status": status, "config": {"enabled": enabled}}


class TestWaybar(unittest.TestCase):
    def test_coloured_dot_quiet_ring_and_off(self):
        busy = uihelp.waybar_line(display("yellow", status="A session is waiting: webapp"))
        self.assertEqual(busy, {"text": "<span color='#FFC214'>●</span>", "alt": "yellow",
                                "class": "yellow", "tooltip": "A session is waiting: webapp"})
        self.assertEqual(uihelp.waybar_line(display())["text"], "○")
        off = uihelp.waybar_line(display("red", enabled=False, status="claude-light is off"))
        self.assertEqual((off["text"], off["class"]), ("⊘", "off"))
        self.assertEqual(uihelp.waybar_line(None)["class"], "off")          # no display yet


class TestMenuEntries(unittest.TestCase):
    def test_ticks_show_the_current_settings_and_each_line_maps_to_a_command(self):
        cfg = {"enabled": True, "sound": False, "grace_seconds": 120, "size": 5, "show_message": False}
        entries = dict(uihelp.menu_entries(cfg))
        self.assertEqual(entries["✓ Light on"], ["off"])
        self.assertEqual(entries["   Sound"], ["sound", "on"])
        self.assertEqual(entries["   Show Claude's message"], ["message", "on"])
        self.assertEqual(entries["✓ Delay: 2 minutes"], ["delay", "120"])
        self.assertEqual(entries["   Delay: 5 minutes"], ["delay", "300"])
        self.assertEqual(entries["✓ Size: 50%"], ["size", "5"])
        self.assertEqual(entries["   Size: 100%"], ["size", "10"])
        self.assertEqual(entries["   Preview: red"], ["preview", "red"])
        self.assertEqual(len(uihelp.menu_entries(cfg)), 3 + 6 + 10 + 3)


class TestPickTools(unittest.TestCase):
    def which(self, *installed):
        return lambda name: "/usr/bin/" + name if name in installed else None

    def test_picker_prefers_omarchys_walker(self):
        self.assertEqual(uihelp.pick_dmenu(self.which("walker", "rofi")), ["/usr/bin/walker", "--dmenu"])
        self.assertEqual(uihelp.pick_dmenu(self.which("rofi")), ["/usr/bin/rofi", "-dmenu", "-i"])
        self.assertIsNone(uihelp.pick_dmenu(self.which()))

    def test_player_prefers_pipewire(self):
        self.assertEqual(uihelp.pick_player(self.which("pw-play", "aplay"), "/b.wav"), ["/usr/bin/pw-play", "/b.wav"])
        self.assertEqual(uihelp.pick_player(self.which("aplay"), "/b.wav"), ["/usr/bin/aplay", "-q", "/b.wav"])
        self.assertIsNone(uihelp.pick_player(self.which(), "/b.wav"))


if __name__ == "__main__":
    unittest.main()
