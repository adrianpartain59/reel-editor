#!/usr/bin/env python3
"""The split screen reel's thumbnail: the speaker's cut-out face with a white edge, the reel's blurred cards beside the speaker, a League
Gothic line on top and one under the speaker's chin. Everything sits in the middle 1080x1440, which is what the Instagram grid shows.

  split_thumb.py PROJECT candidates     -> work/thumb/candidates.jpg: faces numbered in seconds (pick eyes open, mouth mid-word, no blur, no hand)
  split_thumb.py PROJECT make           -> out/thumbnail.jpg (1080x1920), out/thumbnail-youtube.jpg (2160x3840)

split_reel.json "thumb": {"t": 7.2, "top": [["3 HABITS", "yellow"], ["THAT STICK", "white"]], "bottom": "START TODAY"}. The cards come from hook.cards.
"""
import json, subprocess, sys
from PIL import Image, ImageDraw
import split_reel as S
import compose as C
from common import ASSETS, die, run
from segment import SWIFT


def main():
    if len(sys.argv) < 3: die(__doc__)
    S.setup(sys.argv[1]); d = S.PROJ / "work/thumb"; d.mkdir(parents=True, exist_ok=True)
    if sys.argv[2] == "candidates":
        ts = [t for t in (round(.4 * i, 1) for i in range(1, int(S.DUR / .4))) if S.split(t) < .02][:60]; w, h = 230, 300; s = Image.new("RGB", (w * 10, h * -(-len(ts) // 10)))
        for i, t in enumerate(ts): x, y, fh = S.face(t); r = fh; c = S.grab(S.P / "base.mp4", int(t * 30), 1080, 1920); x = min(max(x, r * .77), 1080 - r * .77); c = c.crop((int(x - r * .77), int(y - r), int(x + r * .77), int(y + r))).resize((w, h), Image.LANCZOS); q = ImageDraw.Draw(c); q.rectangle([0, 0, 70, 34], fill=(0, 0, 0)); q.text((8, 4), f"{t:.1f}", font=C.font("bold", 24), fill=(255, 255, 255)); s.paste(c, ((i % 10) * w, (i // 10) * h))
        s.save(d / "candidates.jpg", quality=90); print(d / "candidates.jpg"); return
    T = S.R.get("thumb") or die('split_reel.json has no "thumb"'); im = S.grab(S.P / "base.mp4", int(round(T["t"] * 30)), 1080, 1920); im.save(d / "face.png"); (d / "in").mkdir(exist_ok=True); (d / "m").mkdir(exist_ok=True); im.save(d / "in/face.jpg", quality=95); (d / "seg.swift").write_text(SWIFT); run(["swift", str(d / "seg.swift"), str(d / "m"), str(d / "in/face.jpg")])
    (d / "spec.json").write_text(json.dumps({"frame": str(d / "face.png"), "mask": str(d / "m/face.png"), "face": list(S.face(T["t"])), "top": T["top"], "bottom": T["bottom"], "cards": S.HOOK.get("cards") or [], "out": str(d / "thumb-2x.png")})); run(["node", str(ASSETS / "graphic-styles/canvas/thumb_split.js"), str(d / "spec.json")])
    big = Image.open(d / "thumb-2x.png").convert("RGB"); o = S.PROJ / "out"; o.mkdir(exist_ok=True); big.save(o / "thumbnail-youtube.jpg", quality=88, optimize=True); big.resize((1080, 1920), Image.LANCZOS).save(o / "thumbnail.jpg", quality=93)
    g = big.resize((1080, 1920), Image.LANCZOS); s = Image.new("RGB", (1330, 1000), (60, 60, 60)); s.paste(g.resize((562, 1000)), (0, 0)); s.paste(g.crop((0, 240, 1080, 1680)).resize((750, 1000)), (580, 0)); s.save(d / "check.jpg", quality=88); print(o / "thumbnail.jpg", "| look at", d / "check.jpg")


if __name__ == "__main__": main()
