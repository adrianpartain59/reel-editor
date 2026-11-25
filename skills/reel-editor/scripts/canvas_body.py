#!/usr/bin/env python3
"""The body of a canvas reel: the drawn canvas (canvas/scenes.js) with the face cut back in at a few moments.

  canvas_body.py PROJECT preview 13.1,14.5,...   -> work/body_preview.jpg
  canvas_body.py PROJECT render                  -> work/body_final.mp4

Renders the canvas to work/canvas.mp4 first when scenes.js is newer. Reads canvas_reel.json "faces" and "outro"
(references/canvas-reel-schema.md). Captions only on the face, never over the canvas (the canvas already writes the words).
"""
import math, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw
import compose as C
import canvas_lib as L
from canvas_lib import clamp, lerp, eoc, eio, W, H, FPS

DUR_RISE, DUR_IN, DUR_OUT = 0.27, 0.24, 0.22             # canvas rises over the hook; slides back over the face; gives way to the face
HOLD = {}                                                 # the last face frame of each moment, shown under the canvas as it slides back in


def setup(arg):
    global PROJ, REEL, P, N, FACE, OUTRO
    PROJ, REEL = L.project(arg); P = L.part(PROJ, REEL.get("part", "body")); N = P["frames"]; FACE = []; OUTRO = REEL.get("outro")
    for f in REEL.get("faces", []):
        a, b = f["in"], f["out"]; acc = L.ACCENT.get(f.get("accent", "yellow"), f.get("accent")); z0 = f.get("z0", 1.5 if f.get("enter") == "cut" else 1.28)
        if "zoom" in f: Z = L.zooms(f["zoom"])
        else:                                             # settle in, glide, step in on the punch word, glide
            z1 = z0 - (0.2 if f.get("enter") == "cut" else 0.12); e = min(a + 0.23, b); z = [[a, e, z0, z1, "out"]]; t, cur = e, z1
            for p in f.get("punch", []):
                if p > t: z.append([t, p, cur, cur + 0.03 * (p - t), "lin"]); cur += 0.03 * (p - t)
                z.append([p, p + 0.12, cur, cur + 0.16, "back"]); cur += 0.16; t = p + 0.12
            z.append([t, b + 0.1, cur, cur + 0.04 * max(0.1, b - t), "lin"]); Z = L.zooms(z)
        FACE.append({"in": a, "out": b, "enter": f.get("enter", "down"), "back": f.get("back"), "Z": Z, "caps": L.fit_caps(f.get("caps", []), P["words"], a, b), "acc": acc})


def moment(t): return next((f for f in FACE if f["in"] <= t < f["out"]), None)


def face_frame(fr, t, f):
    """fr: the untouched footage frame. Head-tracked, zoomed, captioned; the outro gets the typed comment."""
    z = max(1.0, L.zoom_at(f["Z"], t, 1.12)); fx, fy, fh = P["face"](t); cw, ch = W / z, H / z; x0 = clamp(fx - 540 / z, 0, W - cw); y0 = clamp(fy - 900 / z, 0, H - ch)
    im = fr.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA"); Y, fs = (fy - y0) * z, fh * z
    for a, b, ws in f["caps"]:
        if a <= t < b:
            on = [w for w in ws if t >= w[1] - 0.001]
            if on: k = min(3, int((t - on[-1][1]) * FPS)); C.paste_text(im, C.Captions.cine(tuple(w[0] for w in on), tuple(bool(w[2]) for w in on), f["acc"], 84, 900, k), 540, max(300, Y - 1.06 * fs - 34))
    if OUTRO and t >= OUTRO["t0"]:
        k = clamp((t - OUTRO["t0"]) / 0.25); pill = C.chat_pill_base(820).copy(); d = ImageDraw.Draw(pill); s = fh * 1.5; txt = OUTRO["text"]; cps = OUTRO.get("cps", 0.05)
        pill.paste(fr.crop((int(fx - s / 2), int(fy - s * 0.58), int(fx + s / 2), int(fy + s * 0.42))).resize((88, 88), Image.LANCZOS), (36, 35), C.circle_mask(88)); n = int(max(0, (t - OUTRO["t0"] - OUTRO.get("delay", 0.15)) / cps)); shown = txt[:n]
        f_ = C.font("semibold", 46); d.text((148, 79), shown or "Add a comment", font=f_, fill=(255, 255, 255, 255) if shown else (150, 150, 158, 255), anchor="lm")
        if int(t * 2.5) % 2 == 0 or 0 < n < len(txt): cx = 148 + (f_.getlength(shown) if shown else 0) + 6; d.line([(cx, 54), (cx, 104)], fill=(110, 140, 255, 255), width=4)
        C.paste_text(im, pill, 470, lerp(1390, 1300, C.ease_out_cubic(k)), 1.0, k)
    return im.convert("RGB")


def shift(base, top, dx, dy): out = base.copy(); out.paste(top, (int(dx), int(dy))); return out


def arrive(kind, under, over, u):
    """the canvas slides in over what was there: up (after the hook), left or right (after a face moment)"""
    dx, dy = {"up": (0, H), "left": (-W, 0), "right": (W, 0)}[kind]; e = eoc(u); return shift(under, over, dx * (1 - e), dy * (1 - e))


def leave(kind, under, over, u):
    """the canvas gives way to the face: down (drops away), through (zooms past), shrink (becomes a card and fades)"""
    if kind == "down": return shift(under, over, 0, H * eio(u))
    if kind == "through":
        s = 1 + 0.9 * u * u; w, h = int(W / s), int(H / s); z = over.crop(((W - w) // 2, (H - h) // 2, (W - w) // 2 + w, (H - h) // 2 + h)).resize((W, H), Image.BILINEAR); return Image.blend(z, under, clamp(u * 1.15))
    if kind == "shrink":
        s = 1 - 0.55 * eio(u); w, h = int(W * s), int(H * s); out = under.copy(); card = over.resize((w, h), Image.BILINEAR); m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], int(90 * eio(u)), fill=int(255 * (1 - clamp((u - 0.45) / 0.55)))); out.paste(card, ((W - w) // 2, int((H - h) / 2 - 120 * u)), m); return out
    return under


def frame(t, canvas, foot):
    f = moment(t)
    if t < DUR_RISE: return arrive("up", HOLD.get("hook") or foot, canvas, (t + 1 / FPS) / DUR_RISE)
    if f:
        im = face_frame(foot, t, f); return leave(f["enter"], im, canvas, (t - f["in"] + 0.5 / FPS) / DUR_OUT) if f["enter"] != "cut" and t - f["in"] < DUR_OUT else im
    for f in FACE:
        if f["back"] and f["out"] <= t < f["out"] + DUR_IN: return arrive(f["back"], HOLD.get(f["out"]) or canvas, canvas, (t - f["out"] + 0.5 / FPS) / DUR_IN)
    return canvas


def stream(path):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, bufsize=W * H * 3 * 2)
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3: return
        yield b


def canvas_video():
    js = PROJ / REEL.get("scenes", "canvas/scenes.js"); mp4 = PROJ / "work/canvas.mp4"
    if not js.exists():
        if mp4.exists(): return mp4
        L.die(f"{js} missing (copy assets/graphic-styles/canvas/starter.scenes.js), or put finished art in work/canvas.mp4")
    if not mp4.exists() or mp4.stat().st_mtime < js.stat().st_mtime:
        info = L.scenes_info(PROJ, REEL)
        if info["frames"] != N: L.die(f"scenes.js dur is {info['dur']} s ({info['frames']} frames) but the body is {P['dur']} s ({N} frames)")
        print("rendering the canvas ..."); subprocess.run(["node", str(js), "render", str(mp4)], check=True)
    return mp4


def len_s(f): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout)


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    setup(sys.argv[1]); mp4 = canvas_video(); want = None; hv, ti = PROJ / "work/hook_video.mp4", REEL.get("hook", {}).get("title")
    if ti and hv.exists():                                # a hook that ends on its title card: rise over that, not over the bare footage
        raw = subprocess.run(["ffmpeg", "-v", "error", "-sseof", "-0.2", "-i", str(hv), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if len(raw) >= W * H * 3 and ti["out"] >= len_s(hv) - 0.05: HOLD["hook"] = Image.frombytes("RGB", (W, H), raw[-W * H * 3:])
    if sys.argv[2] == "preview": want = sorted({min(N - 1, round(float(x) * FPS)) for x in sys.argv[3].split(",")}); tiles = []
    else: ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "30", "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv", *L.h264(("-crf", "12", "-preset", "fast")), str(PROJ / "work/body_final.mp4")], stdin=subprocess.PIPE)
    for n, (cb, fb) in enumerate(zip(stream(mp4), stream(P["dir"] / "base.mp4"))):
        t = n / FPS; last = [f["out"] for f in FACE if abs(t - (f["out"] - 1 / FPS)) < 0.5 / FPS]; near = t < 0.3 or moment(t) or any(f["back"] and f["out"] <= t < f["out"] + DUR_IN for f in FACE)
        if want is not None and n not in want and not last: continue
        if not near and want is None: ff.stdin.write(cb); continue
        im = frame(t, Image.frombytes("RGB", (W, H), cb), Image.frombytes("RGB", (W, H), fb))
        if last: HOLD[last[0]] = im
        if want is None: ff.stdin.write(im.tobytes())
        elif n in want: tiles.append(L.stamp(im.resize((270, 480), Image.LANCZOS), t))
    if want is None: ff.stdin.close(); ff.wait(); print(PROJ / "work/body_final.mp4"); return
    cols = min(8, len(tiles)); s = Image.new("RGB", (270 * cols, 480 * math.ceil(len(tiles) / cols)))
    for i, im in enumerate(tiles): s.paste(im, ((i % cols) * 270, (i // cols) * 480))
    s.save(PROJ / "work/body_preview.jpg", quality=88); print(PROJ / "work/body_preview.jpg")


if __name__ == "__main__": main()
