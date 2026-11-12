import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import fsutil  # noqa: E402


class TestWriteJson(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "x.json")

    def test_retries_while_another_process_holds_the_file(self):
        busy = [2]

        def locked_then_free(src, dst):
            if busy[0]:
                busy[0] -= 1
                raise PermissionError("in use by another process")   # what Windows says
            os.replace(src, dst)

        fsutil.write_json(self.path, {"a": 1}, replace=locked_then_free, sleep=lambda s: None)
        with open(self.path) as f:
            self.assertEqual(json.load(f), {"a": 1})

    def test_gives_up_after_its_tries_and_leaves_no_temp_file(self):
        def always_locked(src, dst):
            raise PermissionError("in use")

        with self.assertRaises(PermissionError):
            fsutil.write_json(self.path, {"a": 1}, replace=always_locked, sleep=lambda s: None, tries=3)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), [])


if __name__ == "__main__":
    unittest.main()
