#!/usr/bin/env python3
"""One long uncut take with retakes: split it at the pauses and transcribe each utterance alone, so the kept take of every
line can be picked (whisper over the whole file smears retakes together and invents lines).

  utterances.py PROJECT VIDEO [--gap 0.45]     -> PROJECT/work/utter.json, and the list on screen

The kept take of a line is the last complete one before the speaker moves to the next line. Put its [clip, in, out] in selects.json.
"""
import argparse, json
from pathlib import Path
from common import run, whisper_model
import speechmap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("video"); ap.add_argument("--gap", type=float, default=0.45); a = ap.parse_args()
    work = Path(a.project).expanduser().resolve() / "work"; (work / "u").mkdir(parents=True, exist_ok=True); src = str(Path(a.video).expanduser())
    regs, lv = speechmap.regions(src); ut = []
    for s, e in regs:
        if ut and s - ut[-1][1] < a.gap: ut[-1][1] = e
        else: ut.append([s, e])
    model = whisper_model(); full = work / "full16.wav"; run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(full)]); out = []
    for i, (s, e) in enumerate(ut):
        if e - s < 0.25: out.append({"i": i, "a": round(s, 2), "b": round(e, 2), "text": "(short)", "words": []}); continue
        o = max(0, s - 0.25); wav = work / "u" / f"{i:03d}.wav"; stem = str(work / "u" / f"{i:03d}")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{o:.3f}", "-t", f"{e - s + 0.5:.3f}", "-i", str(full), "-af", "apad=pad_dur=0.6", str(wav)])
        run(["whisper-cli", "-m", model, "-f", str(wav), "-ml", "1", "-sow", "-oj", "-of", stem, "-l", "en", "-np"])
        ws = [[x["text"].strip(), round(o + x["offsets"]["from"] / 1000, 2), round(o + x["offsets"]["to"] / 1000, 2)] for x in json.loads(Path(stem + ".json").read_text())["transcription"] if x["text"].strip()]
        out.append({"i": i, "a": round(s, 2), "b": round(e, 2), "text": " ".join(w[0] for w in ws), "words": ws})
    (work / "utter.json").write_text(json.dumps(out, indent=0))
    print(f"{len(out)} utterances, levels {lv}")
    for o in out: print(f"u{o['i']:<3d} {o['a']:7.2f}-{o['b']:7.2f} ({o['b'] - o['a']:5.2f})  {o['text']}")


if __name__ == "__main__": main()
