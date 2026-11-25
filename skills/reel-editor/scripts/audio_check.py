#!/usr/bin/env python3
"""Compare the finished reel's audio with the original recording, segment by segment.

  audio_check.py PROJECT --variant h1

For each body segment, takes the same stretch from the source clip (as recorded, both channels) and from the
finished reel, matches their level at 500-2000 Hz, and reports the difference per octave band. A clean edit
stays within about 2 dB everywhere; muffling (mono phase cancellation, over-aggressive denoise, low-pass)
shows up as -4 dB or worse above 4 kHz. Exits 1 if any band above 2 kHz averages worse than -3 dB.
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np

SR = 48000
EDGES = [125, 250, 500, 1000, 2000, 4000, 8000, 12000, 16000]


def pcm(src, ss, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-t", f"{t:.3f}", "-i", str(src), "-map", "0:a:0",
                          "-ar", str(SR), "-ac", "2", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def bands(x):
    """Band power of the stereo pair as heard (L and R power summed), Welch-averaged."""
    n = 4096; w = np.hanning(n); acc = None
    for ch in range(2):
        s = x[:, ch]
        for i in range(0, len(s) - n, n // 2):
            p = np.abs(np.fft.rfft(s[i:i + n] * w)) ** 2
            acc = p if acc is None else acc + p
    f = np.fft.rfftfreq(n, 1 / SR)
    return np.array([10 * np.log10(acc[(f >= a) & (f < b)].sum() + 1e-12) for a, b in zip(EDGES, EDGES[1:])])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--variant", required=True)
    a = ap.parse_args()
    proj = Path(a.project).expanduser().resolve()
    plan = json.loads((proj / "plan.json").read_text()); clips = {c["id"]: c for c in json.loads((proj / "project.json").read_text())["clips"]}
    final = proj / "out" / f"{plan.get('slug', 'reel')}-{a.variant}.mp4"
    hook = json.loads((proj / "work/parts" / f"hook-{a.variant}" / "segs.json").read_text())["duration"]
    segs = json.loads((proj / "work/parts/body/segs.json").read_text())["segs"]
    diffs = []
    for s in segs:
        d = s["t1"] - s["t0"]
        if d < 1.5: continue
        o = bands(pcm(clips[s["clip"]]["file"], s["src_in"], d)); r = bands(pcm(final, hook + s["t0"], d))
        ref = np.mean((r - o)[3:5])                      # 1-2 kHz... level-match on the mid bands
        diffs.append((r - o) - ref)
    D = np.mean(diffs, axis=0)
    labels = [f"{a}-{b}" for a, b in zip(EDGES, EDGES[1:])]
    print("band (Hz)        " + " ".join(f"{l:>11s}" for l in labels))
    print("reel - original  " + " ".join(f"{v:>+10.1f}dB" for v in D))
    worst = min(D[4:])
    ok = worst >= -3.0
    print(f"worst band above 2 kHz: {worst:+.1f} dB -> {'PASS' if ok else 'FAIL (muffled vs the original)'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
