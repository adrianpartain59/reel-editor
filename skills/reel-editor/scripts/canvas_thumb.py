#!/usr/bin/env python3
"""The "Face and line" thumbnail: the speaker's cut-out face with a white edge on the dark ground, the green
line climbing behind the speaker, from -> to at the top, the title under the speaker's chin.

  canvas_thumb.py PROJECT candidates                 -> work/thumb/candidates.jpg: a face every 0.4 s, numbered in seconds
  canvas_thumb.py PROJECT make --t 3.4 --from '0' --to '1M' --title 'THE 10-STEP ROADMAP' [--part hook-main]
                                                     -> out/thumbnail.jpg (1080x1920), out/thumbnail-youtube.jpg (2160x3840)

Pick a frame with eyes open, mouth mid-word and no motion blur. Everything that matters sits in the middle 1080x1440, which is what
the Instagram grid shows.
"""
import argparse, json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
from common import ASSETS, run, die
import canvas_lib as L
from segment import SWIFT
import compose as C


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("cmd", choices=["candidates", "make"]); ap.add_argument("--part", default="hook-main"); ap.add_argument("--t", type=float); ap.add_argument("--from", dest="frm", default="$0"); ap.add_argument("--to"); ap.add_argument("--title"); a = ap.parse_args()
    proj = Path(a.project).expanduser().resolve(); P = L.part(proj, a.part); d = proj / "work/thumb"; d.mkdir(parents=True, exist_ok=True); grab = lambda t, f: run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(P["dir"] / "base.mp4"), "-frames:v", "1", str(f)])
    if a.cmd == "candidates":
        ts = [round(0.4 * i, 1) for i in range(1, int(P["dur"] / 0.4))][:40]; w, h = 230, 300; s = Image.new("RGB", (w * 10, h * -(-len(ts) // 10)))
        for i, t in enumerate(ts):
            grab(t, d / "c.png"); x, y, fh = P["face"](t); im = Image.open(d / "c.png").convert("RGB"); r = fh * 1.0; c = im.crop((int(x - r * .77), int(y - r), int(x + r * .77), int(y + r))).resize((w, h), Image.LANCZOS); q = ImageDraw.Draw(c); q.rectangle([0, 0, 70, 34], fill=(0, 0, 0)); q.text((8, 4), f"{t:.1f}", font=C.font("bold", 24), fill=(255, 255, 255)); s.paste(c, ((i % 10) * w, (i // 10) * h))
        s.save(d / "candidates.jpg", quality=90); print(d / "candidates.jpg"); return
    if a.t is None or not a.to or not a.title: die("make needs --t, --to and --title")
    grab(a.t, d / "face.png"); (d / "in").mkdir(exist_ok=True); (d / "m").mkdir(exist_ok=True); Image.open(d / "face.png").convert("RGB").save(d / "in/face.jpg", quality=95); (d / "seg.swift").write_text(SWIFT); run(["swift", str(d / "seg.swift"), str(d / "m"), str(d / "in/face.jpg")])
    x, y, fh = P["face"](a.t); (proj / "out").mkdir(exist_ok=True); spec = {"frame": str(d / "face.png"), "mask": str(d / "m/face.png"), "face": [x, y, fh], "from": a.frm, "to": a.to, "title": a.title, "out": str(d / "thumb-2x.png")}; (d / "spec.json").write_text(json.dumps(spec))
    run(["node", str(ASSETS / "graphic-styles/canvas/thumb_face_line.js"), str(d / "spec.json")]); im = Image.open(d / "thumb-2x.png").convert("RGB"); im.save(proj / "out/thumbnail-youtube.jpg", quality=88, optimize=True); im.resize((1080, 1920), Image.LANCZOS).save(proj / "out/thumbnail.jpg", quality=92); print(proj / "out/thumbnail.jpg", f"{(proj / 'out/thumbnail-youtube.jpg').stat().st_size // 1024} KB for YouTube (limit 2 MB)")


if __name__ == "__main__": main()
