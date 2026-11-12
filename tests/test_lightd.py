import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import lightcore as lc  # noqa: E402
import lightd  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "state"))
        self.dead = set()
        self.api_ok = True
        self.probes = 0
        self.w = lightd.Watcher(self.root, alive=lambda s: s["session_id"] not in self.dead,
                                probe=self.probe)

    def probe(self):
        self.probes += 1
        return self.api_ok

    def put(self, sid, state, since=-1000.0, **kw):
        d = {"session_id": sid, "cwd": "/x/" + sid, "state": state, "since": since}
        d.update(kw)
        with open(os.path.join(self.root, "state", sid + ".json"), "w") as f:
            json.dump(d, f)

    def config(self, **kw):
        with open(os.path.join(self.root, "config.json"), "w") as f:
            json.dump(kw, f)

    def display(self):
        with open(os.path.join(self.root, "display.json")) as f:
            return json.load(f)


class TestTickWritesDisplay(Base):
    def test_yellow_session_shows_yellow_ball(self):
        self.put("webapp", "yellow")
        self.w.tick(now=10.0)
        d = self.display()
        self.assertEqual((d["visible"], d["color"], d["detail"]), (True, "yellow", "webapp"))


class TestClickAcknowledges(Base):
    def test_ack_hides_ball_and_survives_restart(self):
        self.put("webapp", "yellow")
        d = self.w.tick(now=10.0)
        with open(os.path.join(self.root, "ack.json"), "w") as f:
            json.dump({"keys": d["keys"]}, f)
        self.assertFalse(self.w.tick(now=11.0)["visible"])
        fresh = lightd.Watcher(self.root, alive=lambda s: True, probe=self.probe)
        self.assertFalse(fresh.tick(now=12.0)["visible"])


class TestCrashCheck(Base):
    def test_dead_mid_turn_goes_red_and_dead_waiting_is_removed(self):
        self.put("work", "running")
        self.put("done", "yellow")
        self.dead.update({"work", "done"})
        d = self.w.tick(now=50.0)
        self.assertEqual((d["color"], d["detail"]), ("red", "work: session crashed"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "state"))), ["work.json"])


class TestApiProbe(Base):
    def test_probe_only_while_working_and_red_after_two_minutes(self):
        self.put("idle", "idle")
        self.w.tick(now=0.0)
        self.assertEqual(self.probes, 0)                 # nothing working: no probe
        self.put("work", "running")
        self.api_ok = False
        for t in range(100, 216, 5):
            d = self.w.tick(now=float(t))
        self.assertFalse(d["visible"])                   # 115 s down: not yet
        d = self.w.tick(now=220.0)
        self.assertEqual((d["color"], d["detail"]), ("red", "API unreachable for 2+ min"))
        self.assertEqual(self.probes, 9)                 # every 15 s, not every tick
        self.api_ok = True
        self.assertFalse(self.w.tick(now=235.0)["visible"])


class TestOffSwitch(Base):
    def test_disabled_in_config_keeps_ball_hidden(self):
        self.put("webapp", "red", reason="session crashed")
        self.config(enabled=False)
        self.assertFalse(self.w.tick(now=1.0)["visible"])


PS = """  101 Wed Nov 11 19:52:26 2026
 4242 Wed Nov  4 01:17:48 2026
"""


class TestProcessAlive(unittest.TestCase):
    def test_same_pid_and_start_time_is_alive(self):
        table = lightd.parse_ps(PS)
        self.assertEqual(table[4242], "Wed Nov  4 01:17:48 2026")
        self.assertTrue(lightd.process_alive({"pid": 4242, "pid_start": "Wed Nov  4 01:17:48 2026"}, table))
        self.assertFalse(lightd.process_alive({"pid": 4242, "pid_start": "Thu Nov  5 09:00:00 2026"}, table))
        self.assertFalse(lightd.process_alive({"pid": 999, "pid_start": "x"}, table))
        self.assertTrue(lightd.process_alive({}, table))     # never identified: can't judge


class TestApiReachable(unittest.TestCase):
    def test_any_http_answer_is_up_and_no_answer_is_down(self):
        import http.server
        import socket
        import threading

        class NotFound(http.server.BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_response(404)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), NotFound)
        threading.Thread(target=srv.handle_request, daemon=True).start()
        self.assertTrue(lightd.api_reachable("http://127.0.0.1:%d/" % srv.server_port, 3))
        srv.server_close()
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]
        s.close()
        self.assertFalse(lightd.api_reachable("http://127.0.0.1:%d/" % closed, 3))


class TestPsFailure(unittest.TestCase):
    def test_no_process_table_means_nobody_is_judged_dead(self):
        self.assertTrue(lightd.process_alive({"pid": 4242, "pid_start": "x"}, None))


class TestSleepWake(Base):
    def test_a_long_gap_between_probes_forgets_the_old_outage(self):
        self.put("work", "running")
        self.api_ok = False
        self.w.tick(now=100.0)                        # failed just before the lid closed
        d = self.w.tick(now=100.0 + 3 * 3600)         # wakes hours later, network not back yet
        self.assertFalse(d["visible"])


class TestTranscriptInterrupted(unittest.TestCase):
    def write(self, *entries):
        path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        with open(path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        return path

    def test_reads_the_last_message_skipping_bookkeeping(self):
        tool = {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use"}]}}
        esc = {"type": "user", "message": {"role": "user",
                                            "content": [{"type": "text", "text": "[Request interrupted by user]"}]}}
        esc_tool = {"type": "user", "message": {"role": "user",
                                                 "content": "[Request interrupted by user for tool use]"}}
        self.assertTrue(lightd.transcript_interrupted(self.write(tool, esc, {"type": "last-prompt"},
                                                                 {"type": "cost-state"})))
        self.assertTrue(lightd.transcript_interrupted(self.write(tool, esc_tool)))
        self.assertFalse(lightd.transcript_interrupted(self.write(esc, tool)))
        self.assertFalse(lightd.transcript_interrupted("/no/such/file.jsonl"))


class TestEscThenClose(Base):
    def test_interrupted_session_that_exits_is_not_a_crash(self):
        t = os.path.join(self.root, "t.jsonl")
        with open(t, "w") as f:
            f.write(json.dumps({"type": "user", "message": {"content": "[Request interrupted by user]"}}) + "\n")
        self.put("esc", "running", transcript_path=t)
        self.dead.add("esc")
        d = self.w.tick(now=50.0)
        self.assertFalse(d["visible"])
        self.assertEqual(os.listdir(os.path.join(self.root, "state")), [])


class TestSoundSwitch(Base):
    def test_sound_off_in_config_keeps_the_ball_but_drops_the_sound(self):
        self.put("webapp", "yellow")
        self.assertTrue(self.w.tick(now=1.0)["sound"])
        self.config(sound=False)
        d = self.w.tick(now=2.0)
        self.assertEqual((d["visible"], d["sound"]), (True, False))
        self.assertFalse(self.display()["sound"])


class TestConfigDrivesDisplay(Base):
    def test_delay_size_and_message_come_from_config(self):
        self.put("webapp", "yellow", since=95.0, message="Run the ! line?")
        d = self.w.tick(now=100.0)
        self.assertFalse(d["visible"])                       # default 120 s delay not up
        self.config(grace_seconds=0, size=7)
        d = self.w.tick(now=101.0)
        self.assertEqual((d["visible"], d["size"], d["message"]), (True, 7, ""))   # message off by default
        self.config(grace_seconds=0, size=7, show_message=True)
        self.assertEqual(self.w.tick(now=102.0)["message"], "Run the ! line?")


class TestTrayDot(Base):
    def test_tray_shows_the_worst_state_at_once_ball_waits(self):
        self.put("webapp", "yellow", since=95.0)
        self.put("ci", "running")
        d = self.w.tick(now=100.0)
        self.assertEqual((d["visible"], d["tray"]), (False, "yellow"))
        self.put("webapp", "idle")
        self.assertEqual(self.w.tick(now=101.0)["tray"], "")


class TestDisplayCarriesSettings(Base):
    def test_menu_reads_settings_from_the_display(self):
        self.config(size=3, sound=False)
        d = self.w.tick(now=1.0)
        self.assertEqual(d["config"], dict(lc.DEFAULT_CONFIG, size=3, sound=False))


class TestEmptyLookupMeansGone(unittest.TestCase):
    def test_empty_answer_is_dead_but_no_answer_is_unknown(self):
        s = {"pid": 4242, "pid_start": "x"}
        self.assertFalse(lightd.process_alive(s, {}))      # asked about 4242: nothing alive
        self.assertTrue(lightd.process_alive(s, None))     # the lookup itself failed: never cry crash


class TestBallCommand(unittest.TestCase):
    def test_each_os_starts_its_own_ball(self):
        self.assertEqual(lightd.ball_command("darwin", "/h/.claude-light", "/usr/bin/python3"),
                         ["/h/.claude-light/bin/ball", "/h/.claude-light/display.json", "/h/.claude-light/bong.wav"])
        self.assertEqual(lightd.ball_command("linux", "/h/.claude-light", "/usr/bin/python3"),
                         ["/usr/bin/python3", "/h/.claude-light/linux/ball.py",
                          "/h/.claude-light/display.json", "/h/.claude-light/bong.wav"])
        win = lightd.ball_command("win32", r"C:\Users\x\.claude-light", r"C:\Py\pythonw.exe")
        self.assertEqual(win[:6], ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-File"])
        self.assertEqual(win[6:], [r"C:\Users\x\.claude-light\windows\ball.ps1",
                                   r"C:\Users\x\.claude-light\display.json",
                                   r"C:\Users\x\.claude-light\bong.wav", r"C:\Py\pythonw.exe"])


class TestStatusLine(Base):
    def test_display_carries_one_status_sentence(self):
        self.put("webapp", "yellow", since=95.0)
        self.assertEqual(self.w.tick(now=100.0)["status"], "A session is waiting (ball after the delay)")
        self.assertEqual(self.w.tick(now=300.0)["status"], "A session is waiting: webapp")
        self.put("webapp", "idle")
        self.assertEqual(self.w.tick(now=301.0)["status"], "All quiet")
        self.config(enabled=False)
        self.assertEqual(self.w.tick(now=302.0)["status"], "claude-light is off")


if __name__ == "__main__":
    unittest.main()
