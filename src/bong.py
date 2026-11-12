#!/usr/bin/python3
"""Synthesize the claude-light 'bong' (a struck-bell tone) as a WAV file."""
import array
import math
import sys
import wave

BASE_HZ = 196.0  # G3: low enough to read as a "bong", not a "ding"
# (ratio to base, loudness, decay seconds): a church-bell partial series
PARTIALS = [
    (0.5, 0.35, 0.90),   # hum
    (1.0, 1.00, 0.55),   # strike
    (1.19, 0.25, 0.35),  # minor third
    (1.5, 0.30, 0.30),   # fifth
    (2.0, 0.45, 0.25),   # nominal
    (2.74, 0.20, 0.15),
    (4.1, 0.10, 0.08),
]


def make(path, seconds=1.8, rate=44100):
    n = int(seconds * rate)
    raw = []
    for i in range(n):
        t = i / float(rate)
        attack = min(1.0, t / 0.004)
        v = sum(a * math.exp(-t / tau) * math.sin(2 * math.pi * BASE_HZ * r * t)
                for r, a, tau in PARTIALS)
        raw.append(v * attack)
    peak = max(abs(x) for x in raw) or 1.0
    samples = array.array("h", (int(x / peak * 0.85 * 32767) for x in raw))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())


if __name__ == "__main__":
    make(sys.argv[1])
