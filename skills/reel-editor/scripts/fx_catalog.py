#!/usr/bin/env python3
"""Contact sheets of the effects library, to choose moves by eye.

  fx_catalog.py OUTDIR [--a FRAME.jpg --b FRAME.jpg]

Writes OUTDIR/fx-transitions-<n>.jpg (every transition at five points across its window, outgoing shot A to
incoming shot B; defaults to two built-in test cards), fx-titles.jpg (every title animation at five moments)
and fx-icons.jpg (every neon icon). Names and sounds: references/effects.md.
"""
import argparse, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).parent))
import fx
from compose import draw_title, font, W, H

LABEL = "/System/Library/Fonts/SFNS.ttf"


def card(text, top, bottom):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H; d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bottom)))
    for x in range(0, W, 120): d.line([(x, 0), (x, H)], fill=(255, 255, 255), width=2)
    d.ellipse([340, 560, 740, 960], fill=(240, 220, 200)); d.text((540, 1300), text, font=font("xblack", 200), fill=(255, 255, 255), anchor="mm")
    return im.convert("RGBA")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("outdir"); ap.add_argument("--a"); ap.add_argument("--b")
    a = ap.parse_args(); out = Path(a.outdir).expanduser(); out.mkdir(parents=True, exist_ok=True)
    A = Image.open(a.a).convert("RGBA").resize((W, H)) if a.a else card("A", (40, 60, 120), (10, 10, 30))
    B = Image.open(a.b).convert("RGBA").resize((W, H)) if a.b else card("B", (150, 60, 40), (30, 10, 10))
    fn = ImageFont.truetype(LABEL, 22); us = [0.15, 0.35, 0.5, 0.62, 0.85]; names = list(fx.TRANSITIONS); per = 8
    for s in range(0, len(names), per):
        grp = names[s:s + per]; sheet = Image.new("RGB", (150 + 5 * 216, len(grp) * 384), "black"); d = ImageDraw.Draw(sheet)
        for i, n in enumerate(grp):
            for j, u in enumerate(us):
                sheet.paste(fx.transition(n, A, B, u, {"cx": 540, "cy": 760}).convert("RGB").resize((216, 384)), (150 + j * 216, i * 384))
            d.text((6, i * 384 + 170), n + "\n" + ", ".join(fx.TRANSITIONS[n][2]), font=fn, fill="yellow")
        sheet.save(out / f"fx-transitions-{s // per + 1}.jpg", quality=80)
    # titles
    lines = (("EASY REASON", "xblack", 116, "#FF3434"), ("TO LEAVE", "xblack", 100, "#FFFFFF"))
    ts = [0.04, 0.1, 0.2, 0.4, 1.0]; anims = list(fx.TITLE_IN)
    sheet = Image.new("RGB", (150 + 5 * 270, len(anims) * 240), "black"); d = ImageDraw.Draw(sheet)
    for i, an in enumerate(anims):
        for j, t in enumerate(ts):
            fr = Image.new("RGBA", (W, 640), (18, 18, 22, 255))
            draw_title(None, fr, lines, {"anim": an, "label": "WARNING", "frame": True, "accent": "#FF3434"}, t, 0.0, 3.0, 540, 320)
            sheet.paste(fr.convert("RGB").resize((270, 160)), (150 + j * 270, i * 240 + 40))
        d.text((6, i * 240 + 100), an, font=fn, fill="yellow")
    sheet.save(out / "fx-titles.jpg", quality=80)
    icons = list(fx.ICONS); cols = 6; rows = (len(icons) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 240, rows * 260), (14, 14, 18)); d = ImageDraw.Draw(sheet)
    for k, n in enumerate(icons):
        im = fx.neon_icon(n, 1.0, (120, 200, 255) if k % 2 else (255, 255, 255), 150)
        sheet.paste(im, ((k % cols) * 240 + 20, (k // cols) * 260), im); d.text(((k % cols) * 240 + 10, (k // cols) * 260 + 232), n, font=fn, fill="yellow")
    sheet.save(out / "fx-icons.jpg", quality=82)
    print(f"wrote catalog sheets to {out}")


if __name__ == "__main__":
    main()
