#!/usr/bin/env python3
"""Is everything reel-editor needs on this Mac? Says what is missing and the command that gets it.

  doctor.py
"""
import os, shutil, subprocess, sys
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
bad = 0


def row(ok, what, fix="", optional=False):
    global bad
    bad += (not ok and not optional); print(f"{'ok  ' if ok else ('    ' if optional else 'MISS')}  {what}" + ("" if ok else f"\n        {fix}"))


row(sys.platform == "darwin", "macOS", "reel-editor uses Apple's Vision framework and system fonts, so it only runs on a Mac")
row(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]}", "Python 3.9 or newer")
for m, pip in (("PIL", "pillow"), ("numpy", "numpy")):
    try: __import__(m); row(True, pip)
    except ImportError: row(False, pip, f"{sys.executable} -m pip install {pip}   (add --user or use a venv if pip refuses)")
for t, why in (("ffmpeg", "ffmpeg"), ("ffprobe", "ffmpeg"), ("whisper-cli", "whisper-cpp")): row(bool(shutil.which(t)), t, f"brew install {why}")
try:
    sys.path.insert(0, str(Path(__file__).parent)); import common
    try: m = common.whisper_model(); row(True, f"whisper model: {m}")
    except SystemExit: row(False, "whisper model", "mkdir -p ~/.cache/whisper.cpp && curl -L -o ~/.cache/whisper.cpp/ggml-large-v3-turbo.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin   (1.6 GB)")
except Exception as e: row(False, "scripts/common.py", str(e))
row(Path(CHROME).exists(), "Google Chrome (mockups)", "install Google Chrome")
row(subprocess.run(["xcrun", "--find", "swift"], capture_output=True).returncode == 0, "swift (face detection, person masks)", "xcode-select --install")
row(Path("/System/Library/Fonts/SFNS.ttf").exists(), "SF Pro system font", "expected at /System/Library/Fonts/SFNS.ttf")
row(bool(shutil.which("node")), "node (only for the drawn kinds)", "brew install node", optional=True)
A = Path(__file__).resolve().parent.parent / "assets"
row((A / "graphic-styles/node_modules").exists(), "drawing library (only for the drawn kinds)", "installed by canvas_init.py the first time", optional=True)
row(any((Path.home() / ".cache/reel-editor/music").glob("*.mp3")), "downloaded beats (the synthesized pad plays without them)", "python3 scripts/music_lib.py fetch   (33 MB from mixkit.co, Mixkit's free licence)", optional=True)
pf = Path.home() / ".config/reel-editor/preferences.md"; row(pf.exists(), f"your own rules: {pf}", "optional: your corrections collect here", optional=True)
print("\neverything needed is here" if not bad else f"\n{bad} missing"); sys.exit(1 if bad else 0)
