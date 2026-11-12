import array
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import bong  # noqa: E402


class TestBong(unittest.TestCase):
    def test_writes_a_decaying_bell_tone(self):
        path = os.path.join(tempfile.mkdtemp(), "bong.wav")
        bong.make(path)
        with wave.open(path) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 44100))
            self.assertAlmostEqual(w.getnframes() / 44100.0, 1.8, places=2)
            samples = array.array("h", w.readframes(w.getnframes()))
        head = max(abs(x) for x in samples[: 44100 // 5])
        tail = max(abs(x) for x in samples[-44100 // 5:])
        self.assertGreater(head, 20000)        # loud strike
        self.assertLess(tail, head / 8)        # rings out


if __name__ == "__main__":
    unittest.main()
