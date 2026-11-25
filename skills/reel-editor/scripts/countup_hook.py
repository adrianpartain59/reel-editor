#!/usr/bin/env python3
"""The edited hook of a canvas reel: punch zooms on the big words over the speaker's face, a graph that squiggles and then takes off while
the number counts up, and a title card with one marker per step.

  countup_hook.py PROJECT preview 0.1,1.5,2.4,...   -> work/hook_preview.jpg
  countup_hook.py PROJECT render                    -> work/hook_video.mp4

Reads canvas_reel.json "hook" (references/canvas-reel-schema.md) and work/parts/hook-<variant>. One function of time (value / tip_h)
drives the line, the number and the count-up pitch (canvas_sound.py), so they can't drift apart. The camera ends on the full,
untouched frame (z = 1), so the canvas can rise over it; on a short hook the title may hold to the end instead. The squiggle is drawn for effect; it is not data.
"""
import math, random, subprocess, sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import compose as C
import canvas_lib as L
from canvas_lib import clamp, lerp, eoc, eio, back, W, H, FPS

GREENC, WHITE, GREY = (61, 220, 132), (255, 255, 255), (168, 176, 186)
KNOTS = [(0.00, 240), (0.06, 693), (0.10, 547), (0.17, 1240), (0.22, 920), (0.25, 1013), (0.31, 387), (0.36, 640), (0.40, 493), (0.48, 1573), (0.52, 1280), (0.56, 1720), (0.61, 1160), (0.65, 1320), (0.72, 573), (0.77, 960), (0.80, 787), (0.88, 1907), (0.92, 1520), (0.95, 1693), (1.00, 1227)]   # drawn for a landing at 100,000, scaled to yours
X0, X1, XS, BASE, TOP = 92, 846, 0.66, 1462, 404          # px: graph left, right, share of width the squiggle gets, baseline, top of the line
KV, KH = 3.6, 2.7


def setup(proj_arg):
    """Everything the frames need, in module globals (worker processes re-run it)."""
    global PROJ, P, HK, N, CARD_IN, T0, T_SURGE, T1, CARD_OUT, VALUE, SC, PX0, Z, FACE, CAPS, TITLE, UNDER, BLURS, FR
    PROJ, reel = L.project(proj_arg); HK = reel["hook"]; P = L.part(PROJ, "hook-" + HK.get("variant", "main")); N = P["frames"]; FR = PROJ / "work" / "hookframes"
    b = HK["beats"]; CARD_IN, T0, T_SURGE, T1, CARD_OUT = (b[k] for k in ("card_in", "start", "surge", "land", "card_out"))
    VALUE = float(HK["value"]); SC = VALUE / 100000; PX0 = 138 / (1907 * SC); TITLE = HK.get("title"); UNDER = HK.get("under", [])
    Z = L.zooms(HK["zoom"]) if "zoom" in HK else L.zooms(auto_zoom()); FACE = HK.get("face") or auto_face()
    if TITLE and TITLE["out"] < P["dur"] - 0.05 and TITLE["out"] + 0.25 > P["dur"]: print(f"note: the title card leaves at {TITLE['out']} s but the hook ends at {P['dur']:.2f} s; set title.out to {P['dur']:.2f} to hold it to the end", file=sys.stderr)
    CAPS = L.fit_caps(HK.get("caps", []), P["words"], 0, P["dur"] + 0.1); BLURS = HK.get("blur") or [a + 0.055 for a, _, _, _, e in Z if e is back]


def auto_zoom():
    """Snap-out, a push that never stops, a step in on every punch word, a hit on the landing, back out when the card leaves."""
    z, t, cur = [[0.0, 0.20, 1.35, 1.04, "out"]], 0.20, 1.04; dur = P["dur"]
    def glide(to, rate=0.045):
        nonlocal t, cur
        if to > t + 0.02: z.append([t, to, cur, cur + rate * (to - t), "lin"]); cur += rate * (to - t); t = to
    def step(at, d, by, e="back"):
        nonlocal t, cur
        glide(at); z.append([at, at + d, cur, cur + by, e]); cur += by; t = at + d
    ti = TITLE or {}; ev = [(p, "p") for p in HK.get("punch", [])] + [(T1 - 0.02, "land"), (CARD_OUT, "out")] + [(w[1], "p") for w in ti.get("words", [])] + ([(ti["out"] + 0.03, "clear")] if ti else [])
    for at, k in sorted(ev):
        if at < t - 0.01 or at > dur - 0.6: continue
        if k == "p": step(at, 0.12, 0.11)
        elif k == "land": step(at, 0.07, 0.13, "out"); step(t, 0.33, -0.20, "io")
        else: step(at, 0.26, (1.06 if k == "out" else 1.20) - cur, "io")
    if ti and ti["out"] >= dur - 0.05: glide(dur + 0.1); return z                                      # the title holds to the end: the canvas rises over it
    end = max(t + 0.05, dur - 1.0); glide(end); z.append([end, dur + 0.1, cur, 1.0, "io"]); return z


def auto_face():
    """Where the face sits on screen: centre, then left while the graph is up (the line climbs on the right), then centre."""
    f = [[0.0, 540, 880], [CARD_IN - 0.02, 500, 870], [T0 + 0.04, 400, 812], [CARD_OUT - 0.02, 400, 812], [CARD_OUT + 0.28, 540, 850]]
    if TITLE: f += [[TITLE["in"], 540, 850], [TITLE["in"] + 0.16, 540, 800], [TITLE["out"] - 0.02, 540, 800], [TITLE["out"] + 0.14, 540, 900]]
    return f + [[P["dur"] - 0.9, 540, 860], [P["dur"] + 0.2, 540, 860]]


def face_target(t):
    for (a, x0, y0), (b, x1, y1) in zip(FACE, FACE[1:]):
        if a <= t < b:
            u = eio((t - a) / (b - a)); return lerp(x0, x1, u), lerp(y0, y1, u)
    return FACE[-1][1:]


def shake(t):
    d = t - T1
    if not 0 <= d < 0.34: return 0, 0
    a = 20 * (1 - d / 0.34) ** 1.6
    return a * math.sin(d * 92), a * math.cos(d * 117)


def camera(fr, t):
    z = max(1.0, L.zoom_at(Z, t)); fx_, fy_, fh = P["face"](t); tx, ty = face_target(t); sx, sy = shake(t); cw, ch = W / z, H / z
    x0 = clamp(fx_ - (tx + sx) / z, 0, W - cw); y0 = clamp(fy_ - (ty + sy) / z, 0, H - ch)                  # at z = 1 this is the untouched frame
    im = fr.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)); cx, cy = (fx_ - x0) * z, (fy_ - y0) * z
    zb = lambda s: im.resize((W, H), Image.BILINEAR, box=(cx - cx / s, cy - cy / s, cx + (W - cx) / s, cy + (H - cy) / s))
    if t < 0.2:                                            # the house snap-out: zoom blur + soft blur, gone by 0.13 s
        k = (1 - clamp(t / 0.2)) ** 1.5
        if k > 0.03: im = Image.fromarray((sum(np.asarray(zb(1 + 0.14 * k * i / 6), np.float32) for i in range(7)) / 7).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7 * k))
    elif any(abs(t - b) < 0.05 for b in BLURS) or T1 - 0.02 <= t < T1 + 0.08 or CARD_OUT + 0.04 < t < CARD_OUT + 0.20:
        im = Image.blend(im, zb(1.07 if T1 - 0.02 <= t < T1 + 0.08 else 1.035), 0.45)                       # a touch of zoom blur on every punch
    return im, (cx, cy, fh * z)


# ---- the graph: one value function drives the line, the number and the sound
def squig(w):
    for (a, v0), (b, v1) in zip(KNOTS, KNOTS[1:]):
        if a <= w <= b: u = (w - a) / (b - a); return lerp(v0, v1, 0.7 * u + 0.3 * eio(u)) * SC
    return KNOTS[-1][1] * SC


def value(t):
    """the number at time t"""
    if t <= T0: return 0.0 if t < T0 - 0.15 else KNOTS[0][1] * SC * clamp((t - T0 + 0.15) / 0.15)
    if t < T_SURGE: return squig((t - T0) / (T_SURGE - T0))
    s = clamp((t - T_SURGE) / (T1 - T_SURGE)); v0 = KNOTS[-1][1] * SC; return v0 + (VALUE - v0) * (math.exp(KV * s) - 1) / (math.exp(KV) - 1)


def tip_h(t):
    """height of the tip above the baseline, px (its own curve, so it always climbs while the scale zooms out)"""
    if t < T_SURGE: return value(t) * PX0
    s = clamp((t - T_SURGE) / (T1 - T_SURGE)); h0 = KNOTS[-1][1] * SC * PX0; return h0 + (BASE - TOP - h0) * (math.exp(KH * s) - 1) / (math.exp(KH) - 1)


def gx(t):
    if t < T_SURGE: return X0 + (X1 - X0) * XS * clamp((t - T0) / (T_SURGE - T0))
    return X0 + (X1 - X0) * (XS + (1 - XS) * clamp((t - T_SURGE) / (T1 - T_SURGE)))


def path(t):
    """The line so far, on the scale in force at t: early wiggles flatten as the scale zooms out."""
    tt = min(t, T1); sc = tip_h(tt) / max(1e-6, value(tt)); pts = []; u = T0
    while u < tt: pts.append((gx(u), BASE - (value(u) * sc if u < T_SURGE else min(value(u) * sc, tip_h(tt))))); u += 0.008
    pts.append((gx(tt), BASE - tip_h(tt))); return pts


@lru_cache(None)
def font(kind, size): return C.font(kind, size)


@lru_cache(600)
def number_img(txt, size, col):
    """Tabular digits, so the number doesn't jitter while it rolls."""
    f = font("cblack", size); dw = max(f.getlength(d) for d in "0123456789"); widths = [dw if c.isdigit() else f.getlength(c) for c in txt]; asc = f.getbbox("$0")[3]; pad = 24
    im = Image.new("RGBA", (int(sum(widths)) + pad * 2, asc + pad * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = pad
    for c, w in zip(txt, widths): d.text((x + (w - f.getlength(c)) / 2, pad), c, font=f, fill=(*col, 255)); x += w
    return im


@lru_cache(None)
def card_img(grid=True):
    w, h = 872, 392; s = 2
    m = Image.new("L", (w * s, h * s), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w * s - 1, h * s - 1], 46 * s, fill=255); m = m.resize((w, h), Image.LANCZOS)
    body = Image.new("RGBA", (w, h), (15, 17, 20, 236)); body.putalpha(ImageChops.multiply(body.getchannel("A"), m))
    edge = Image.new("L", (w * s, h * s), 0); ImageDraw.Draw(edge).rounded_rectangle([1, 1, w * s - 2, h * s - 2], 46 * s, outline=255, width=3); edge = edge.resize((w, h), Image.LANCZOS).point(lambda v: int(v * 0.16))
    body.alpha_composite(Image.merge("RGBA", [Image.new("L", (w, h), 255)] * 3 + [edge]))
    pad = 70; out = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0)); sh = Image.new("RGBA", out.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 170), (pad, pad + 16), m)
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(30))); out.alpha_composite(body, (pad, pad)); d = ImageDraw.Draw(out)
    for y in (1462, 1400, 1338) if grid else (): d.line([(pad + X0 - 48, pad + y - 1112), (pad + w - 46, pad + y - 1112)], fill=(255, 255, 255, 22), width=2)
    return out, pad


def put(dst, im, cx, cy, sc=1.0, al=1.0):
    if al <= 0.01: return
    if abs(sc - 1) > 1e-3: im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.BICUBIC)
    if al < 1: im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * al)))
    x, y = round(cx - im.width / 2), round(cy - im.height / 2); box = (max(0, -x), max(0, -y), min(im.width, W - x), min(im.height, H - y))
    if box[0] >= box[2] or box[1] >= box[3]: return
    dst.alpha_composite(im.crop(box), (x + box[0], y + box[1]))


def mixc(a, b, u): return tuple(int(lerp(x, y, clamp(u))) for x, y in zip(a, b))


def draw_line(out, t, dx, dy, al):
    pts = [(x + dx, y + dy) for x, y in path(t)]
    if len(pts) < 3: return
    g = clamp((t - T_SURGE) / 0.35); col = mixc((236, 240, 244), GREENC, g); lw = lerp(8, 13, g); y0 = max(0, int(min(p[1] for p in pts)) - 110); y1 = min(H, int(max(p[1] for p in pts)) + 90); s = 2
    m = Image.new("L", (W * s, (y1 - y0) * s), 0); d = ImageDraw.Draw(m); q = [(x * s, (y - y0) * s) for x, y in pts]; d.line(q, fill=255, width=int(lw * s), joint="curve")
    for x, y in (q[0], q[-1]): d.ellipse([x - lw * s / 2, y - lw * s / 2, x + lw * s / 2, y + lw * s / 2], fill=255)
    m = m.resize((W, y1 - y0), Image.LANCZOS)
    if g < 1:                                              # fill under the line, inside the card only
        poly = q + [(q[-1][0], (BASE + dy - y0) * s), (q[0][0], (BASE + dy - y0) * s)]; fm = Image.new("L", (W, y1 - y0), 0); ImageDraw.Draw(fm).polygon([(x / s, y / s) for x, y in poly], fill=255)
        ImageDraw.Draw(fm).rectangle([0, 0, W, max(0, 1300 + dy - y0)], fill=0); grad = Image.linear_gradient("L").resize((W, y1 - y0)).point(lambda v: int(70 - v * 0.2)); fm = ImageChops.multiply(fm, grad)
        lay = Image.new("RGBA", (W, y1 - y0), (*col, 0)); lay.putalpha(fm.point(lambda v: int(v * al * (1 - g)))); out.alpha_composite(lay, (0, y0))
    for r, k in ((34, 0.75 * g), (12, 0.35 + 0.5 * g)):
        gl = m.resize((W // 2, (y1 - y0) // 2)).filter(ImageFilter.GaussianBlur(r / 2)).resize((W, y1 - y0)); gl = gl.point(lambda v: int(min(255, v * 1.7) * k * al)); lay = Image.new("RGBA", gl.size, (*col, 0)); lay.putalpha(gl); out.alpha_composite(lay, (0, y0))
    lay = Image.new("RGBA", m.size, (*mixc(col, WHITE, 0.18), 0)); lay.putalpha(m.point(lambda v: int(v * al))); out.alpha_composite(lay, (0, y0))
    x, y = pts[-1]; r = lerp(13, 19, g) + (10 * (1 - clamp((t - T1) / 0.25)) if t >= T1 else 2.5 * math.sin(t * 34))          # the tip: a dot while it draws, a hard pulse when it lands
    dot = Image.new("RGBA", (240, 240), (0, 0, 0, 0)); dd = ImageDraw.Draw(dot); dd.ellipse([120 - r * 2.1, 120 - r * 2.1, 120 + r * 2.1, 120 + r * 2.1], fill=(*col, 90)); dot = dot.filter(ImageFilter.GaussianBlur(9)); dd = ImageDraw.Draw(dot)
    dd.ellipse([120 - r, 120 - r, 120 + r, 120 + r], fill=(*WHITE, 255)); dd.ellipse([120 - r * .62, 120 - r * .62, 120 + r * .62, 120 + r * .62], fill=(*col, 255)); put(out, dot, x, y, 1, al)
    if T1 <= t < T1 + 0.7: burst(out, x, y, t - T1)


def burst(out, x, y, d):
    u = d / 0.7; lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); R = 34 + 250 * eoc(u); a = int(220 * (1 - u) ** 2)
    dr.ellipse([x - R, y - R, x + R, y + R], outline=(*GREENC, a), width=max(1, int(12 * (1 - u)))); rng = random.Random(5)
    for _ in range(46):
        an = rng.uniform(0, 2 * math.pi); sp = rng.uniform(120, 560); sz = rng.uniform(6, 15); px = x + math.cos(an) * sp * eoc(u); py = y + math.sin(an) * sp * eoc(u) + 420 * u * u; tail = 26 * (1 - u)
        c = GREENC if rng.random() < 0.7 else WHITE; dr.line([(px - math.cos(an) * tail, py - math.sin(an) * tail), (px, py)], fill=(*c, int(255 * (1 - u) ** 1.3)), width=max(1, int(sz * (1 - u * 0.6))))
    out.alpha_composite(lay)


def text_img(words, size, kind="heavy"):
    f = font(kind, size); sp = f.getlength(" "); w = sum(f.getlength(t) for t, _ in words) + sp * (len(words) - 1); im = Image.new("RGBA", (int(w) + 20, int(size * 1.35)), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = 10
    for t, c in words: d.text((x, 4), t, font=f, fill=(*c, 255)); x += f.getlength(t) + sp
    return im


def shown_number(v): return HK.get("prefix", "") + format(int(v), ",") + HK.get("suffix", "")


def graph(out, t):
    if not CARD_IN <= t < CARD_OUT + 0.3: return
    sx, sy = shake(t); sx, sy = -sx * 0.8, -sy * 0.8; uo = clamp((t - CARD_OUT) / 0.26); ui = clamp((t - CARD_IN) / 0.24); dy = lerp(220, 0, back(ui, 1.5)) + 560 * uo ** 2; al = clamp(ui * 2.2) * (1 - clamp(uo * 1.15))
    img, pad = card_img(t < T1); put(out, img, 484 + sx, 1308 + dy + sy, 1 + 0.02 * max(0, 1 - abs(t - T1 - 0.05) / 0.12), al)
    if t >= T0: draw_line(out, t, sx, sy + dy, al)
    k = clamp((t - T1) / 0.2); kb = back(k, 2.4) if k < 1 else 1.0; col = mixc(WHITE, GREENC, clamp((t - T1) / 0.08))          # landing: white -> green, 132 px -> 160 px with a hit of overshoot
    big = min(160, int(160 * 724 / max(1, number_img(shown_number(VALUE), 160, GREENC).width - 48))); small = min(132, big); size = small if t < T1 else big; txt = shown_number(VALUE if t >= T1 else value(t))
    lab = text_img([(HK.get("label", ""), GREY)], 38, "semibold"); put(out, lab, 92 + lab.width / 2 - 10 + sx, 1154 + dy + sy, 1, al)
    ni = number_img(txt, size, col); sc = 1.0 if t < T1 else lerp(small / big, 1.0, kb); x = 92 - 24 * sc + ni.width * sc / 2; y = (1178 if t < T1 else lerp(1178, 1170, k)) + (ni.height * sc) / 2 - 24 * sc
    if t >= T1:                                             # glow under the landed number
        gl = Image.new("RGBA", ni.size, (*GREENC, 0)); gl.putalpha(ni.getchannel("A")); gl = gl.filter(ImageFilter.GaussianBlur(20)); put(out, gl, x + sx, y + dy + sy, sc, al * (0.35 + 0.5 * (1 - clamp((t - T1) / 0.4))))
    put(out, ni, x + sx, y + dy + sy, sc, al)
    ws = [(w[0], w[1], len(w) > 2 and w[2]) for w in UNDER]; shown = [w for w in ws if t >= w[1]]                              # the line under the number, word by word with the voice
    if shown:
        full = text_img([(w, GREENC if h else WHITE) for w, _, h in ws], 58); f = font("heavy", 58); upto = f.getlength(" ".join(w[0] for w in shown)) + 22; pt = full.crop((0, 0, int(min(full.width, upto)), full.height))
        u = clamp((t - shown[-1][1]) / 0.1); put(out, pt, 82 + pt.width / 2 + sx, 1388 + dy + sy + 8 * (1 - eoc(u)), 1, al)


def markers(out, t):
    """The title on the same card, word by word, with one marker per step lighting along a dotted line."""
    if not TITLE: return
    a, b, n = TITLE["in"], TITLE["out"], TITLE.get("count", 0)
    if not a <= t < b + 0.2: return
    ui = clamp((t - a) / 0.2); uo = clamp((t - b) / 0.2); al = clamp(ui * 2.4) * (1 - clamp(uo * 1.2)); dy = lerp(180, 0, back(ui, 1.6)) + 420 * uo ** 2; img, pad = card_img(False); put(out, img, 484, 1290 + dy, 1, al)
    f = font("cblack", 176); ws = [(w[0], f.getlength(w[0]), w[1], GREENC if len(w) > 2 and w[2] else WHITE) for w in TITLE["words"]]; sp = 44; tot = sum(w[1] for w in ws) + sp * (len(ws) - 1); k = min(1.0, 770 / tot); x = 484 - tot * k / 2
    for txt, w, t0, c in ws:
        if t >= t0: u = clamp((t - t0) / 0.15); put(out, number_img(txt, 176, c), x + w * k / 2, 1244 + dy, k * lerp(1.45, 1.0, eoc(u)), al * clamp(u * 3))
        x += (w + sp) * k
    if n < 2: return
    dx = min(744 / (n - 1), 150); x0 = 484 - dx * (n - 1) / 2; y = 1400; n_on = clamp((t - TITLE.get("from", a + 0.1)) / (TITLE.get("to", b - 0.18) - TITLE.get("from", a + 0.1))) * n
    d = Image.new("RGBA", (W, 40), (0, 0, 0, 0)); dd = ImageDraw.Draw(d); xx = x0
    while xx < x0 + dx * (n - 1) * clamp((n_on - 0.5) / (n - 1)): dd.ellipse([xx - 4, 16, xx + 4, 24], fill=(255, 255, 255, int(150 * al))); xx += 15
    put(out, d, W / 2, y + dy)
    for i in range(n):
        u = clamp(n_on - i)
        if u > 0: put(out, mark_img(i, n), x0 + dx * i, y + dy, lerp(0.3, 1.0, back(u, 2.2)), al)


@lru_cache(None)
def mark_img(i, n):
    s = 3; m = Image.new("RGBA", (58 * s, 58 * s), (0, 0, 0, 0)); md = ImageDraw.Draw(m); md.rounded_rectangle([0, 0, 58 * s - 1, 58 * s - 1], 9 * s, fill=(255, 255, 255, 255) if i < n - 1 else (*GREENC, 255))
    md.text((29 * s, 29 * s), str(i + 1), font=font("black", 32 * s), fill=(17, 18, 20, 255), anchor="mm"); return m.resize((58, 58), Image.LANCZOS)


def captions(out, t, face):
    for a, b, ws in CAPS:
        if not a <= t < b: continue
        on = [w for w in ws if t >= w[1] - 0.001]
        if not on: return
        k = min(3, int((t - on[-1][1]) * FPS)); im = C.Captions.cine(tuple(w[0] for w in on), tuple(bool(w[2]) for w in on), L.GREEN, 84, 900, k); C.paste_text(out, im, 540, max(300, face[1] - 1.06 * face[2] - 34))


def frame(n):
    t = n / FPS; im, face = camera(Image.open(FR / f"{n + 1:04d}.png").convert("RGB"), t)
    d = clamp((t - CARD_IN) / 0.3) * (1 - clamp((t - CARD_OUT) / 0.25)); s = clamp((t - T_SURGE) / 0.8)                          # the room dims while the graph is up, so the line reads
    if d > 0: im = im.point(lambda v: int(v * (1 - d * (0.16 + 0.16 * s))))
    out = im.convert("RGBA")
    if T1 <= t < T1 + 0.16: out.alpha_composite(Image.new("RGBA", (W, H), (*mixc(GREENC, WHITE, 0.8), int(58 * (1 - (t - T1) / 0.16) ** 2))))
    graph(out, t); markers(out, t); captions(out, t, face); return out.convert("RGB")


def job(n): frame(n).save(PROJ / "work/hookout" / f"{n:04d}.png", compress_level=1); return n


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    setup(sys.argv[1]); base = P["dir"] / "base.mp4"
    if len(list(FR.glob("*.png"))) < N or FR.stat().st_mtime < base.stat().st_mtime:
        FR.mkdir(parents=True, exist_ok=True); [f.unlink() for f in FR.glob("*.png")]; subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base), str(FR / "%04d.png")], check=True)
    if sys.argv[2] == "preview":
        ts = [float(x) for x in sys.argv[3].split(",")]; w, h = 360, 640; cols = min(6, len(ts)); sheet = Image.new("RGB", (w * cols, h * math.ceil(len(ts) / cols)))
        with Pool(8, setup, (sys.argv[1],)) as p: ims = p.map(frame, [min(N - 1, round(t * FPS)) for t in ts])
        for i, im in enumerate(ims): sheet.paste(L.stamp(im.resize((w, h), Image.LANCZOS), ts[i]), ((i % cols) * w, (i // cols) * h))
        sheet.save(PROJ / "work/hook_preview.jpg", quality=88); print(PROJ / "work/hook_preview.jpg"); return
    od = PROJ / "work/hookout"; od.mkdir(exist_ok=True); [f.unlink() for f in od.glob("*.png")]
    with Pool(8, setup, (sys.argv[1],)) as p:
        for _ in p.imap_unordered(job, range(N), chunksize=4): pass
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i", str(od / "%04d.png"), "-vf", "scale=out_color_matrix=bt709:out_range=tv", *L.h264(("-crf", "12", "-preset", "fast")), str(PROJ / "work/hook_video.mp4")], check=True); print(PROJ / "work/hook_video.mp4")


if __name__ == "__main__": main()
