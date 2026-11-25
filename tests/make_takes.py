#!/usr/bin/env python3
"""Make phone-style test takes with nobody in them: a drawn speaker whose mouth follows a macOS `say` voice.

  make_takes.py OUTDIR          HOOK_A.mov, HOOK_B.mov, TAKE_1.mov .. TAKE_4.mov (1080x1920, 30 fps, stereo)

TAKE_2 has a flub and a retake in it, every take has dead air at both ends and a little room noise, so the cutter has
something to cut. Used by tests/run.sh.
"""
import math, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 48000
TAKES = {
    "HOOK_A": "Your onboarding is losing you half your users.",
    "HOOK_B": "Stop putting feature tours in your onboarding.",
    "TAKE_1": "Most onboarding flows open with three swipe screens about features. Nobody reads them.",
    "TAKE_2": "Instead, ask one question. [[slnc 700]] Sorry, let me redo that. [[slnc 800]] Instead, ask them one question about their goal, before you show anything else.",
    "TAKE_3": "Then show them a plan built from their answer, with the date they'll hit their goal.",
    "TAKE_4": "People pay for a plan that feels like theirs. Try it, and tell me your numbers.",
}


def voice(text, tmp):
    f = tmp / "v.aiff"; subprocess.run(["say", "-v", "Samantha", "-r", "185", "-o", str(f), text], check=True)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64); x = x / np.abs(x).max() * 0.5
    x = np.concatenate([np.zeros(int(0.9 * SR)), x, np.zeros(int(0.8 * SR))]); rng = np.random.default_rng(len(text))
    n = rng.standard_normal((len(x), 2)) * 10 ** (-62 / 20); return np.stack([x, x], 1) + n


def background():
    im = Image.new("RGB", (W, H), (196, 190, 180)); d = ImageDraw.Draw(im)
    for y in range(H): d.line([(0, y), (W, y)], fill=(int(206 - 46 * y / H), int(199 - 46 * y / H), int(188 - 46 * y / H)))
    d.rectangle([760, 300, 1010, 900], fill=(120, 108, 92)); d.rectangle([780, 320, 990, 880], fill=(160, 182, 196)); return im.filter(ImageFilter.GaussianBlur(7))


def speaker(bg, t, mouth):
    im = bg.copy(); d = ImageDraw.Draw(im); cx, cy = 540 + 12 * math.sin(t * 1.3), 840 + 7 * math.sin(t * 2.1); skin, dark = (222, 178, 148), (58, 42, 34)
    d.rounded_rectangle([cx - 430, cy + 400, cx + 430, H + 200], 220, fill=(38, 44, 60)); d.rounded_rectangle([cx - 100, cy + 220, cx + 100, cy + 470], 60, fill=(204, 160, 130))
    d.ellipse([cx - 235, cy - 330, cx + 235, cy + 330], fill=skin); d.pieslice([cx - 250, cy - 370, cx + 250, cy + 150], 180, 360, fill=dark); d.ellipse([cx - 205, cy - 190, cx + 205, cy + 240], fill=skin)
    for s in (-1, 1):
        ex = cx + s * 92; d.ellipse([ex - 42, cy - 70, ex + 42, cy - 22], fill=(250, 250, 248))
        if (t % 3.7) > 0.12: d.ellipse([ex - 20, cy - 66, ex + 20, cy - 26], fill=(70, 52, 38)); d.ellipse([ex - 9, cy - 56, ex + 9, cy - 38], fill=(15, 12, 10))
        d.line([(ex - 52, cy - 104), (ex + 52, cy - 110)], fill=dark, width=14)
    d.polygon([(cx - 8, cy - 20), (cx - 40, cy + 78), (cx + 40, cy + 78)], fill=(206, 160, 130)); m = 8 + 62 * mouth
    d.ellipse([cx - 78, cy + 150 - m / 2, cx + 78, cy + 150 + m], fill=(120, 48, 48)); return im


def take(name, text, out):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); x = voice(text, tmp); (tmp / "a.f32").write_bytes(x.astype(np.float32).tobytes()); n = int(len(x) / SR * FPS); bg = background()
        hop = SR // FPS; e = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop, 0] ** 2)) for i in range(n)]); e = np.clip(e / (np.percentile(e, 95) + 1e-9), 0, 1)
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(tmp / "a.f32"),
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out / f"{name}.mov")], stdin=subprocess.PIPE)
        for k in range(n): ff.stdin.write(speaker(bg, k / FPS, float(e[k])).tobytes())
        ff.stdin.close()
        if ff.wait(): sys.exit(f"ffmpeg failed on {name}")
    print(f"{name}.mov {n / FPS:.1f} s")


if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    out = Path(sys.argv[1]).expanduser(); out.mkdir(parents=True, exist_ok=True)
    for k, v in TAKES.items(): take(k, v, out)
