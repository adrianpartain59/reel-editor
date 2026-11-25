#!/usr/bin/env python3
"""Word times good enough to draw to: every kept segment is transcribed alone, behind 0.25 s of silence, and offset by its
place in the part. Transcribing the whole part drifts across cuts (0.76 s at one jump cut of the roadmap reel).

  seg_words.py PROJECT [PART ...]      -> PROJECT/work/<part>_words.json  [[word, start, end, segment], ...]   (default: every part)
"""
import json, sys, tempfile
from pathlib import Path
from common import run, load, whisper_model

LEAD = 0.25


def main():
    proj = Path(sys.argv[1]).expanduser().resolve(); parts = sys.argv[2:] or [p.name for p in sorted((proj / "work/parts").iterdir()) if (p / "segs.json").exists()]; model = whisper_model()
    for part in parts:
        d = proj / "work/parts" / part; out = []
        for i, s in enumerate(load(d / "segs.json")["segs"]):
            with tempfile.TemporaryDirectory() as tmp:
                wav = f"{tmp}/s.wav"; run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['t0']:.4f}", "-t", f"{s['t1'] - s['t0']:.4f}", "-i", str(d / "voice.wav"), "-af", f"adelay={int(LEAD * 1000)}:all=1,apad=pad_dur=0.6", "-ac", "1", "-ar", "16000", wav])
                run(["whisper-cli", "-m", model, "-f", wav, "-ml", "1", "-sow", "-oj", "-of", f"{tmp}/s", "-l", "en", "-np"]); js = json.loads(Path(f"{tmp}/s.json").read_text())["transcription"]
            for w in js:
                t = w["text"].strip()
                if not t or t.startswith("["): continue
                a = s["t0"] + w["offsets"]["from"] / 1000 - LEAD; b = s["t0"] + w["offsets"]["to"] / 1000 - LEAD; out.append([t, round(max(s["t0"], a), 2), round(min(s["t1"], max(a, b)), 2), i])
        (proj / "work" / f"{part}_words.json").write_text(json.dumps(out)); print(f"{part}: {len(out)} words -> work/{part}_words.json")
        seg = None
        for w, a, b, i in out: print(("\n" if i != seg else "") + f"{a:6.2f} {w}", end="  "); seg = i
        print()


if __name__ == "__main__": main()
