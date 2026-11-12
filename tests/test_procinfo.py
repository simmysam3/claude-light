import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import procinfo  # noqa: E402

# Real shape of /proc/<pid>/stat: field 2 is "(comm)", field 22 is starttime.
STAT = ("4242 (claude) S 4100 4242 4100 34816 4242 4194560 8213 0 12 0 731 102 0 0 20 0 "
        "19 0 987654 1234567890 54321 18446744073709551615 1 1 0 0 0 0 0 4096 0\n")
ODD = STAT.replace("(claude)", "(we ird) (x)")   # comm may hold spaces and parentheses


class TestProcStat(unittest.TestCase):
    def test_start_time_is_field_22_even_with_an_odd_name(self):
        self.assertEqual(procinfo.parse_proc_stat(STAT), "987654")
        self.assertEqual(procinfo.parse_proc_stat(ODD), "987654")
        self.assertIsNone(procinfo.parse_proc_stat("garbage"))


class TestProcCmdline(unittest.TestCase):
    def test_nul_separated_arguments_become_one_line(self):
        self.assertEqual(procinfo.parse_proc_cmdline(b"claude\x00-p\x00hello world\x00"), "claude -p hello world")
        self.assertEqual(procinfo.parse_proc_cmdline(b""), "")


class TestLinuxLookups(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.proc = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.proc, "4242"))
        with open(os.path.join(self.proc, "4242", "stat"), "w") as f:
            f.write(STAT)
        with open(os.path.join(self.proc, "4242", "cmdline"), "wb") as f:
            f.write(b"claude\x00--resume\x00abc\x00")

    def test_identify_and_starts_read_proc(self):
        self.assertEqual(procinfo.identify(4242, "linux", self.proc), ("987654", "claude --resume abc"))
        self.assertIsNone(procinfo.identify(999, "linux", self.proc))
        self.assertEqual(procinfo.starts([4242, 999], "linux", self.proc), {4242: "987654"})


@unittest.skipUnless(sys.platform == "darwin", "macOS ps")
class TestMacLookups(unittest.TestCase):
    def test_identify_and_starts_use_ps(self):
        import subprocess
        me = procinfo.identify(os.getpid(), "darwin")
        self.assertIsNotNone(me)
        self.assertIn("python", me[1].lower())
        gone = subprocess.Popen(["/usr/bin/true"])
        gone.wait()
        self.assertEqual(procinfo.starts([os.getpid(), gone.pid], "darwin"), {os.getpid(): me[0]})
        self.assertEqual(procinfo.starts([gone.pid], "darwin"), {})

    def test_a_ps_error_is_unknown_not_everyone_dead(self):
        self.assertIsNone(procinfo.starts([os.getpid(), 999999], "darwin"))   # "process id too large"


if __name__ == "__main__":
    unittest.main()
