import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import lightcore as lc  # noqa: E402


def ev(name, **kw):
    p = {"hook_event_name": name, "session_id": "s1", "cwd": "/Users/x/dev/webapp"}
    p.update(kw)
    return p


def running():
    return {"session_id": "s1", "cwd": "/Users/x/dev/webapp", "state": lc.RUNNING, "since": 1.0}


class TestStop(unittest.TestCase):
    def test_stop_turns_session_yellow(self):
        s = lc.apply_event(running(), ev("Stop"), now=10.0)
        self.assertEqual(s["state"], lc.YELLOW)
        self.assertEqual(s["since"], 10.0)


class TestUserPrompt(unittest.TestCase):
    def test_prompt_clears_yellow_to_running(self):
        s = dict(running(), state=lc.YELLOW)
        s = lc.apply_event(s, ev("UserPromptSubmit"), now=20.0)
        self.assertEqual(s["state"], lc.RUNNING)
        self.assertEqual(s["since"], 20.0)


class TestQuestion(unittest.TestCase):
    def test_ask_user_question_turns_green(self):
        s = lc.apply_event(running(), ev("PreToolUse", tool_name="AskUserQuestion"), now=30.0)
        self.assertEqual(s["state"], lc.GREEN)


class TestToolActivity(unittest.TestCase):
    def test_tool_use_after_answer_clears_to_running(self):
        for name in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            s = dict(running(), state=lc.GREEN)
            s = lc.apply_event(s, ev(name, tool_name="Bash"), now=40.0)
            self.assertEqual(s["state"], lc.RUNNING, name)


class TestNotification(unittest.TestCase):
    def test_permission_and_input_prompts_turn_green(self):
        for kind in ("permission_prompt", "elicitation_dialog", "worker_permission_prompt", "agent_needs_input"):
            s = lc.apply_event(running(), ev("Notification", notification_type=kind), now=50.0)
            self.assertEqual(s["state"], lc.GREEN, kind)

    def test_idle_reminder_changes_nothing(self):
        before = dict(running(), state=lc.YELLOW, since=5.0)
        s = lc.apply_event(before, ev("Notification", notification_type="idle_prompt"), now=65.0)
        self.assertEqual((s["state"], s["since"]), (lc.YELLOW, 5.0))


class TestStopFailure(unittest.TestCase):
    def test_api_error_ending_turn_turns_red(self):
        s = lc.apply_event(running(), ev("StopFailure", error="overloaded"), now=60.0)
        self.assertEqual(s["state"], lc.RED)
        self.assertEqual(s["reason"], "API error: overloaded")


class TestSubagentEvents(unittest.TestCase):
    def test_subagent_tool_use_does_not_clear_main_yellow(self):
        before = dict(running(), state=lc.YELLOW, since=5.0)
        s = lc.apply_event(before, ev("PreToolUse", tool_name="Bash", agent_id="a1"), now=70.0)
        self.assertEqual((s["state"], s["since"]), (lc.YELLOW, 5.0))


class TestStopWithBackgroundWork(unittest.TestCase):
    def test_stop_with_running_background_task_is_background_not_working(self):
        tasks = [{"id": "b1", "type": "local_bash", "status": "running"}]
        s = lc.apply_event(running(), ev("Stop", background_tasks=tasks), now=80.0)
        self.assertEqual(s["state"], lc.BACKGROUND)
        self.assertEqual(lc.alerts([s], api_down_since=0.0, now=999.0), [])   # not "working"
        self.assertIsNone(lc.check_alive(s, alive=False, now=90.0))           # exit = quiet close

    def test_stop_with_only_finished_tasks_is_yellow(self):
        tasks = [{"id": "b1", "type": "local_bash", "status": "completed"}]
        s = lc.apply_event(running(), ev("Stop", background_tasks=tasks), now=80.0)
        self.assertEqual(s["state"], lc.YELLOW)


class TestLifecycle(unittest.TestCase):
    def test_session_start_is_idle(self):
        s = lc.apply_event(None, ev("SessionStart", source="startup"), now=1.0)
        self.assertEqual(s["state"], lc.IDLE)
        self.assertEqual(s["cwd"], "/Users/x/dev/webapp")

    def test_compact_restart_keeps_state(self):
        s = lc.apply_event(running(), ev("SessionStart", source="compact"), now=2.0)
        self.assertEqual(s["state"], lc.RUNNING)

    def test_session_end_forgets_session(self):
        self.assertIsNone(lc.apply_event(running(), ev("SessionEnd"), now=3.0))


def sess(sid, state, since=-1000.0, cwd="/Users/x/dev/webapp", **kw):
    d = {"session_id": sid, "cwd": cwd, "state": state, "since": since}
    d.update(kw)
    return d


class TestDisplayColour(unittest.TestCase):
    def test_worst_colour_wins_and_idle_is_ignored(self):
        sessions = [sess("a", lc.GREEN), sess("b", lc.YELLOW), sess("c", lc.IDLE), sess("d", lc.RUNNING)]
        d = lc.compute_display(lc.alerts(sessions), acked=set(), prev=None)
        self.assertTrue(d["visible"])
        self.assertEqual(d["color"], lc.YELLOW)
        self.assertEqual(len(d["keys"]), 2)


class TestAlertId(unittest.TestCase):
    def show(self, sessions, acked=(), prev=None):
        return lc.compute_display(lc.alerts(sessions), acked=set(acked), prev=prev)

    def test_bong_only_on_appear_or_colour_change(self):
        d1 = self.show([sess("a", lc.YELLOW)])
        self.assertEqual(d1["alert_id"], 1)
        d2 = self.show([sess("a", lc.YELLOW), sess("b", lc.YELLOW)], prev=d1)
        self.assertEqual(d2["alert_id"], 1)          # joined, same colour: silent
        d3 = self.show([sess("a", lc.RED), sess("b", lc.YELLOW)], prev=d2)
        self.assertEqual(d3["alert_id"], 2)          # escalated: bong
        hidden = self.show([sess("a", lc.RED)], acked=d3["keys"], prev=d3)
        self.assertFalse(hidden["visible"])         # clicked away
        self.assertEqual(hidden["alert_id"], 2)
        d4 = self.show([sess("a", lc.RED), sess("c", lc.GREEN)], acked=d3["keys"], prev=hidden)
        self.assertEqual((d4["color"], d4["alert_id"]), (lc.GREEN, 3))   # new thing: bong


class TestDeEscalation(unittest.TestCase):
    def test_dropping_a_level_recolours_without_bong(self):
        d1 = lc.compute_display(lc.alerts([sess("a", lc.RED), sess("b", lc.YELLOW)]), set(), None)
        d2 = lc.compute_display(lc.alerts([sess("b", lc.YELLOW)]), set(), d1)
        self.assertEqual((d2["color"], d2["alert_id"]), (lc.YELLOW, d1["alert_id"]))


class TestLabel(unittest.TestCase):
    def label(self, sessions):
        d = lc.compute_display(lc.alerts(sessions), set(), None)
        return d["headline"], d["detail"]

    def test_headline_and_detail_per_colour(self):
        self.assertEqual(
            self.label([sess("a", lc.YELLOW, cwd="/x/api"), sess("b", lc.YELLOW, cwd="/x/webapp"),
                        sess("c", lc.GREEN, cwd="/x/other")]),
            ("WAITING FOR YOU", "api · webapp"))
        self.assertEqual(self.label([sess("c", lc.GREEN, cwd="/x/other")]),
                         ("QUESTION FOR YOU", "other"))
        self.assertEqual(
            self.label([sess("a", lc.RED, cwd="/x/webapp", reason="API error: overloaded")]),
            ("ERROR", "webapp: API error: overloaded"))


class TestCrash(unittest.TestCase):
    def test_process_gone_mid_turn_is_a_crash(self):
        for state in (lc.RUNNING, lc.GREEN):
            s = lc.check_alive(sess("a", state), alive=False, now=90.0)
            self.assertEqual((s["state"], s["reason"], s["since"]), (lc.RED, "session crashed", 90.0), state)

    def test_process_gone_while_idle_or_waiting_is_a_close(self):
        for state in (lc.IDLE, lc.YELLOW):
            self.assertIsNone(lc.check_alive(sess("a", state), alive=False, now=90.0), state)

    def test_live_process_changes_nothing(self):
        s = sess("a", lc.RUNNING)
        self.assertEqual(lc.check_alive(s, alive=True, now=90.0), s)


class TestApiOutage(unittest.TestCase):
    def test_unreachable_two_minutes_while_working_is_red(self):
        down = lc.track_api(None, ok=False, now=100.0)
        down = lc.track_api(down, ok=False, now=219.0)
        self.assertEqual(down, 100.0)
        working = [sess("a", lc.RUNNING)]
        self.assertEqual(lc.alerts(working, down, now=219.0), [])          # 119 s: not yet
        got = [(a["color"], a["text"]) for a in lc.alerts(working, down, now=220.0)]
        self.assertEqual(got, [(lc.RED, "API unreachable for 2+ min")])

    def test_no_alarm_when_idle_or_recovered(self):
        self.assertEqual(lc.alerts([sess("a", lc.IDLE)], 100.0, now=500.0), [])
        self.assertIsNone(lc.track_api(100.0, ok=True, now=500.0))


class TestInteractive(unittest.TestCase):
    def test_headless_command_lines_are_not_interactive(self):
        self.assertTrue(lc.is_interactive("claude"))
        self.assertTrue(lc.is_interactive("claude --plugin-dir /a/b --effort xhigh --resume e528"))
        self.assertFalse(lc.is_interactive("claude -p hi"))
        self.assertFalse(lc.is_interactive("claude --print --model x"))
        self.assertFalse(lc.is_interactive("claude --output-format stream-json --input-format stream-json"))


class TestHeadlessIgnored(unittest.TestCase):
    def test_headless_sessions_raise_nothing(self):
        quiet = [sess("a", lc.YELLOW, interactive=False), sess("b", lc.RUNNING, interactive=False)]
        self.assertEqual(lc.alerts(quiet, api_down_since=0.0, now=999.0), [])


class TestLateEvents(unittest.TestCase):
    def test_a_late_tool_event_cannot_undo_a_newer_stop(self):
        s = lc.apply_event(running(), ev("Stop"), now=100.0)
        s = lc.apply_event(s, ev("PostToolUse", tool_name="Bash"), now=99.5)   # started earlier, landed later
        self.assertEqual(s["state"], lc.YELLOW)


class TestFirstSeenViaSubagent(unittest.TestCase):
    def test_new_session_seen_first_through_a_subagent_is_idle_and_named(self):
        s = lc.apply_event(None, ev("PostToolUse", tool_name="Bash", agent_id="a1"), now=5.0)
        self.assertEqual((s["session_id"], s["state"]), ("s1", lc.IDLE))


class TestTranscriptPath(unittest.TestCase):
    def test_session_remembers_its_transcript(self):
        s = lc.apply_event(None, ev("UserPromptSubmit", transcript_path="/t/s1.jsonl"), now=1.0)
        self.assertEqual(s["transcript_path"], "/t/s1.jsonl")


class TestGracePeriod(unittest.TestCase):
    def colours(self, state, now):
        return [a["color"] for a in lc.alerts([sess("a", state, since=100.0)], now=now)]

    def test_waiting_alerts_hold_two_minutes_errors_do_not(self):
        for state in (lc.YELLOW, lc.GREEN):
            self.assertEqual(self.colours(state, now=219.0), [], state)     # you may still be here
            self.assertEqual(self.colours(state, now=220.0), [state], state)  # 2 min unanswered
        self.assertEqual(self.colours(lc.RED, now=100.0), [lc.RED])          # errors: at once


class TestConfig(unittest.TestCase):
    def test_defaults_types_and_clamping(self):
        self.assertEqual(lc.normalize_config(None), lc.DEFAULT_CONFIG)
        c = lc.normalize_config({"size": 42, "grace_seconds": -5, "sound": "no", "enabled": False,
                                 "show_message": True, "junk": 1})
        self.assertEqual(c, {"enabled": False, "sound": True, "grace_seconds": 0, "size": 10,
                             "show_message": True})
        self.assertEqual(lc.normalize_config({"size": 0, "grace_seconds": 30.5})["size"], 1)


class TestGraceFromSettings(unittest.TestCase):
    def test_delay_is_a_setting(self):
        s = [sess("a", lc.YELLOW, since=100.0)]
        self.assertEqual(len(lc.alerts(s, now=100.0, grace=0)), 1)        # immediate
        self.assertEqual(lc.alerts(s, now=350.0, grace=300), [])           # 5 min not yet up


class TestAgentMessage(unittest.TestCase):
    def test_waiting_states_keep_what_claude_said_and_running_clears_it(self):
        s = lc.apply_event(running(), ev("Stop", last_assistant_message="Done. Run the ! line?"), now=10.0)
        self.assertEqual(s["message"], "Done. Run the ! line?")
        q = {"questions": [{"question": "Which account owns the repo?", "options": []}]}
        s = lc.apply_event(running(), ev("PreToolUse", tool_name="AskUserQuestion", tool_input=q), now=11.0)
        self.assertEqual(s["message"], "Which account owns the repo?")
        s = lc.apply_event(running(), ev("Notification", notification_type="permission_prompt",
                                         message="Claude needs your permission to use Bash"), now=12.0)
        self.assertEqual(s["message"], "Claude needs your permission to use Bash")
        s = lc.apply_event(s, ev("PostToolUse", tool_name="Bash"), now=13.0)
        self.assertNotIn("message", s)


class TestDisplayMessage(unittest.TestCase):
    def test_display_carries_newest_message_of_the_shown_colour(self):
        sessions = [sess("a", lc.YELLOW, since=-900.0, message="old ask"),
                    sess("b", lc.YELLOW, since=-800.0, message="newer ask"),
                    sess("c", lc.GREEN, since=-700.0, message="a question")]
        d = lc.compute_display(lc.alerts(sessions, now=0.0), set(), None)
        self.assertEqual((d["color"], d["message"]), (lc.YELLOW, "newer ask"))
        d = lc.compute_display(lc.alerts([sess("a", lc.YELLOW)], now=0.0), set(), None)
        self.assertEqual(d["message"], "")


class TestTailText(unittest.TestCase):
    def test_keeps_the_end_cut_on_a_word(self):
        self.assertEqual(lc.tail_text("short ask?", 280), "short ask?")
        long = "alpha beta gamma delta epsilon. Do you want me to merge it?"
        out = lc.tail_text(long, 40)
        self.assertTrue(out.startswith("…"), out)
        self.assertTrue(out.endswith("Do you want me to merge it?"), out)
        self.assertLessEqual(len(out), 41)
        self.assertNotIn("…lon", out)                       # never starts mid-word
        self.assertEqual(lc.tail_text("one\n\n**two**  `three`", 280), "one two three")   # plain text


class TestDisplayMessageTrimmed(unittest.TestCase):
    def test_long_reply_is_trimmed_for_the_ball(self):
        msg = "word " * 200 + "Shall I publish it?"
        d = lc.compute_display(lc.alerts([sess("a", lc.YELLOW, message=msg)], now=0.0), set(), None)
        self.assertTrue(d["message"].startswith("…") and d["message"].endswith("Shall I publish it?"))
        self.assertLessEqual(len(d["message"]), 281)


if __name__ == "__main__":
    unittest.main()
