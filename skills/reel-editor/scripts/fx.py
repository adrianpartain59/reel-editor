"""Effects library for the reel compositor (imported by compose.py). Pure functions on 1080x1920 PIL images.

- TRANSITIONS: shot-to-shot transitions. transition(name, A, B, u, opts) mixes the outgoing shot A and the
  incoming shot B at u in 0..1 across the window; the cut sits at u = 0.5. Each entry lists its default length,
  its sound categories (from the downloaded library, see sfx_lib.py), its energy and what it fits.
- glitch_frame(): authentic digital corruption (slice displacement with per-slice RGB split, datamosh macroblocks
  from older frames, pixel-stretch bands, scanline noise, jitter) in short bursts.
- dim(): the spotlight dim (the frame darkens and desaturates; text drawn after it stays lit).
- bloom() / shine(): multi-layer neon glow and a light sweep across text.
- TITLE_IN / TITLE_OUT + title_anim(): text animation curves (pop, type, scramble, slide, drop, stamp, ...).
- ICONS + neon_icon(): line icons that draw themselves on with a neon glow.
Every effect here is documented with its sound in references/effects.md; the planner picks by name.
"""
import math, random
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageEnhance

W, H = 1080, 1920


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, u): return a + (b - a) * u
def smooth(u): u = clamp(u); return u * u * (3 - 2 * u)
def ease_in(u, p=3): return clamp(u) ** p
def ease_out(u, p=3): return 1 - (1 - clamp(u)) ** p
def ease_in_out(u): return 0.5 - 0.5 * math.cos(math.pi * clamp(u))
def ease_out_back(u, s=1.7): u = clamp(u) - 1; return 1 + (s + 1) * u ** 3 + s * u ** 2
def whip_pos(u):
    """Position 0..1 for a whip: slow start, very fast through the cut, slow landing."""
    v = 2 * clamp(u) - 1; return 0.5 + 0.5 * math.copysign(abs(v) ** 0.42, v)


# ---------------------------------------------------------------- image helpers
def rgba(im): return im if im.mode == "RGBA" else im.convert("RGBA")


def zoom(im, z, cx=W / 2, cy=H / 2):
    """Zoom about (cx, cy). z >= 1 crops in; z < 1 shrinks onto black."""
    if abs(z - 1) < 1e-3: return im
    w, h = im.size
    if z > 1:
        cw, ch = w / z, h / z; x0 = clamp(cx - cw / 2, 0, w - cw); y0 = clamp(cy - ch / 2, 0, h - ch)
        return im.resize((w, h), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    s = im.resize((max(1, int(w * z)), max(1, int(h * z))), Image.BILINEAR)
    out = Image.new(im.mode, (w, h), (0, 0, 0, 255) if im.mode == "RGBA" else (0, 0, 0))
    out.paste(s, (int(cx - s.width / 2 + (w / 2 - cx) * z), int(cy - s.height / 2 + (h / 2 - cy) * z))); return out


def zoom_blur(im, z, b, cx=W / 2, cy=H / 2, n=5):
    """Zoom with a radial-ish motion blur: n zoom levels from z to z*(1+b) averaged."""
    out = zoom(im, z, cx, cy)
    if abs(b) < 0.01: return out
    for i in range(1, n):
        out = Image.blend(out, zoom(im, z * (1 + b * i / (n - 1)), cx, cy), 1 / (i + 1))
    return out


def dir_blur(im, k, axis=0):
    """Directional motion blur of about k px along x (axis 0) or y (axis 1), via a resize round trip."""
    if k < 3: return im
    f = max(1.0, k / 2.5); w, h = im.size
    size = (max(4, int(w / f)), h) if axis == 0 else (w, max(4, int(h / f)))
    return im.resize(size, Image.BILINEAR).resize((w, h), Image.BILINEAR)


def soft_blur(im, r):
    """Cheap large gaussian: blur at quarter size."""
    if r < 0.5: return im
    w, h = im.size; s = im.resize((w // 4, h // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(r / 4))
    return s.resize((w, h), Image.BILINEAR)


@lru_cache(None)
def _lut(f):
    return [int(clamp(v * f / 255) * 255) for v in range(256)] * 3


def bright(im, f):
    """Multiply RGB by f (alpha kept)."""
    if abs(f - 1) < 0.01: return im
    f = round(f, 2)
    if im.mode == "RGBA":
        r, g, b, a = im.split(); rgb = Image.merge("RGB", (r, g, b)).point(_lut(f)); rgb.putalpha(a); return rgb
    return im.point(_lut(f))


def white(alpha):
    return Image.new("RGBA", (W, H), (255, 255, 255, int(255 * clamp(alpha))))


def over(base, col, alpha):
    if alpha <= 0.003: return base
    out = base.copy(); out.alpha_composite(Image.new("RGBA", base.size, (*col, int(255 * clamp(alpha))))); return out


# ---------------------------------------------------------------- transitions
def _strip(A, B, p, d):
    """A leaving and B arriving side by side; p = 0..1 travelled; d = direction the content moves."""
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    if d in ("l", "r"):
        s = -1 if d == "l" else 1; off = int(s * p * W)
        out.paste(A, (off, 0)); out.paste(B, (off - s * W, 0))
    else:
        s = -1 if d == "u" else 1; off = int(s * p * H)
        out.paste(A, (0, off)); out.paste(B, (0, off - s * H))
    return out


def tr_cut(A, B, u, o): return B if u >= 0.5 else A


def tr_whip(A, B, u, o):
    d = o.get("dir", "l"); p = whip_pos(u)
    v = (whip_pos(min(1, u + 0.02)) - whip_pos(max(0, u - 0.02))) / 0.04
    out = _strip(A, B, p, d)
    return dir_blur(out, min(0.42 * (W if d in "lr" else H), 0.05 * v * (W if d in "lr" else H)), 0 if d in "lr" else 1)


def tr_slide(A, B, u, o):
    d = o.get("dir", "l"); p = ease_in_out(u) ** 1.0
    out = _strip(A, B, smooth(p), d)
    v = abs(math.sin(math.pi * u))
    out = dir_blur(out, 60 * v, 0 if d in "lr" else 1)
    return zoom(out, 1 + 0.03 * v)


def tr_zoom_in(A, B, u, o):
    cx, cy = o.get("cx", W / 2), o.get("cy", H * 0.42); amt = o.get("amt", 1.0)
    if u < 0.5:
        k = ease_in(u * 2, 3); out = zoom_blur(A, 1 + amt * k, 0.16 * k, cx, cy)
    else:
        k = 1 - ease_out((u - 0.5) * 2, 3); out = zoom_blur(B, 1 + amt * k, 0.16 * k, cx, cy)
    return bright(out, 1 + 0.25 * (1 - abs(2 * u - 1)) ** 3)


def tr_zoom_out(A, B, u, o):
    """A pulls away into the distance (shrinking with blur), B pushes out from inside it."""
    cx, cy = o.get("cx", W / 2), o.get("cy", H * 0.42)
    if u < 0.5:
        k = ease_in(u * 2, 2.5); base = zoom_blur(B, 1.6, 0.0, cx, cy)
        base = bright(soft_blur(base, 30), 0.5)
        s = zoom_blur(A, 1.0, -0.12 * k, cx, cy).resize((max(2, int(W * (1 - 0.55 * k))), max(2, int(H * (1 - 0.55 * k)))), Image.BILINEAR)
        base.alpha_composite(s, (int(cx - s.width * cx / W), int(cy - s.height * cy / H))); return base
    k = 1 - ease_out((u - 0.5) * 2, 3); return zoom_blur(B, 1 + 0.6 * k, 0.15 * k, cx, cy)


def tr_flash(A, B, u, o):
    w = (1 - abs(2 * u - 1)) ** 1.6; base = A if u < 0.5 else B
    col = tuple(o.get("color", (255, 255, 255)))
    return over(bright(base, 1 + 0.7 * w), col, w * o.get("strength", 0.95))


def tr_shutter(A, B, u, o):
    """Camera shutter: black blades close from top and bottom, a beat of black, then they open on B with a flash."""
    if u < 0.42: base, k = A, ease_in(u / 0.42, 2)
    elif u < 0.56: base, k = B, 1.0
    else: base, k = B, 1 - ease_out((u - 0.56) / 0.44, 2.2)
    out = base.copy(); d = ImageDraw.Draw(out); h = int(k * H / 2 + 2)
    tilt = int(60 * k)
    d.polygon([(0, 0), (W, 0), (W, h - tilt), (0, h + tilt)], fill=(0, 0, 0, 255))
    d.polygon([(0, H), (W, H), (W, H - h - tilt), (0, H - h + tilt)], fill=(0, 0, 0, 255))
    if u >= 0.56:
        out = over(out, (255, 255, 255), 0.75 * clamp(1 - (u - 0.56) / 0.22))
    return out


def tr_glitch(A, B, u, o):
    base = A if u < 0.5 else B; other = B if u < 0.5 else A
    amt = o.get("amp", 1.0) * (0.35 + 0.9 * math.sin(math.pi * u))
    return glitch_frame(base, amt, int(o.get("seed", 0) * 997 + u * 1000), other=other, hist=o.get("hist"))


def tr_spin(A, B, u, o):
    s = o.get("sgn", 1)
    def cover(ang):                      # zoom that keeps a rotated 9:16 frame filling the screen
        a = math.radians(abs(ang)); return math.cos(a) + (H / W) * math.sin(a)
    def rot(im, ang, z, blur):
        out = im.rotate(ang, Image.BILINEAR, fillcolor=(0, 0, 0, 255))
        if blur > 0.5:
            for i, w in ((1, 0.5), (2, 0.33)):
                out = Image.blend(out, im.rotate(ang - s * blur * i, Image.BILINEAR, fillcolor=(0, 0, 0, 255)), w)
        return zoom(out, max(z, cover(ang) * 1.02))
    if u < 0.5:
        k = ease_in(u * 2, 3); return rot(A, s * 40 * k, 1 + 0.5 * k, 7 * k)
    k = 1 - ease_out((u - 0.5) * 2, 3); return rot(B, -s * 40 * k, 1 + 0.5 * k, 7 * k)


def _ramp_mask(pos, d, soft=70):
    """L mask 0 -> 255 across a moving edge at pos (0..1) in direction d."""
    n = W if d in "lr" else H
    x = np.arange(n, dtype=np.float32); e = pos * (n + 2 * soft) - soft
    m = np.clip((e - x) / soft + 0.5, 0, 1) if d in ("r", "d") else np.clip((x - (n - e)) / soft + 0.5, 0, 1)
    row = Image.fromarray((m * 255).astype(np.uint8)[None, :] if d in "lr" else (m * 255).astype(np.uint8)[:, None])
    return row.resize((W, H), Image.NEAREST), e


def tr_wipe(A, B, u, o):
    d = o.get("dir", "r"); pos = ease_in_out(u)
    m, e = _ramp_mask(pos, d, o.get("soft", 60))
    out = Image.composite(B, A, m)
    edge = Image.new("L", (W, H), 0); dd = ImageDraw.Draw(edge)
    if d in "lr":
        x = e if d == "r" else W - e; dd.rectangle([x - 4, 0, x + 4, H], fill=255)
    else:
        y = e if d == "d" else H - e; dd.rectangle([0, y - 4, W, y + 4], fill=255)
    return glow_add(out, edge, tuple(o.get("color", (255, 255, 255))), 0.9 * math.sin(math.pi * u))


def tr_iris(A, B, u, o):
    cx, cy = o.get("cx", W / 2), o.get("cy", H * 0.42)
    R = ease_in(u, 1.6) * math.hypot(max(cx, W - cx), max(cy, H - cy)) * 1.05
    m = Image.new("L", (W // 4, H // 4), 0); ImageDraw.Draw(m).ellipse([(cx - R) / 4, (cy - R) / 4, (cx + R) / 4, (cy + R) / 4], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(2)).resize((W, H), Image.BILINEAR)
    out = Image.composite(B, A, m)
    ring = Image.new("L", (W, H), 0); ImageDraw.Draw(ring).ellipse([cx - R, cy - R, cx + R, cy + R], outline=255, width=8)
    return glow_add(out, ring, tuple(o.get("color", (255, 255, 255))), 0.8 * math.sin(math.pi * u))


def tr_blur(A, B, u, o):
    k = 1 - abs(2 * u - 1); base = Image.blend(A, B, smooth((u - 0.3) / 0.4))
    return zoom(soft_blur(base, 60 * k ** 1.3), 1 + 0.05 * k)


def tr_dip(A, B, u, o):
    base = A if u < 0.5 else B; return over(base, tuple(o.get("color", (0, 0, 0))), math.sin(math.pi * u) ** 0.7)


@lru_cache(None)
def _leak():
    """Warm blobs on a 3W-wide strip, fading to black at both ends, so sliding it never shows an edge."""
    yy, xx = np.mgrid[0:H // 8, 0:3 * W // 8].astype(np.float32) * 8
    out = np.zeros(xx.shape + (3,), np.float32)
    for cx, cy, r, col in [(1.5 * W, H * 0.35, 520, (255, 120, 40)), (1.5 * W + 180, H * 0.55, 330, (255, 200, 120)),
                           (1.5 * W - 160, H * 0.7, 600, (255, 60, 30))]:
        k = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r)))[..., None]; out += k * np.array(col, np.float32)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).resize((3 * W, H), Image.BILINEAR)


def tr_light_leak(A, B, u, o):
    base = Image.blend(A, B, smooth((u - 0.35) / 0.3)).convert("RGB")
    lk = _leak(); x = int(lerp(-2.2 * W, -0.6 * W, u))
    layer = lk.crop((-x, 0, -x + W, H))
    layer = layer.point(_lut(round(math.sin(math.pi * u) * 1.4, 2)))
    return ImageChops.screen(base, layer).convert("RGBA")


def tr_pixelate(A, B, u, o):
    k = (1 - abs(2 * u - 1)) ** 1.4; base = A if u < 0.5 else B
    b = 1 + int(o.get("block", 72) * k)
    if b < 2: return base
    return base.resize((max(1, W // b), max(1, H // b)), Image.BILINEAR).resize((W, H), Image.NEAREST)


def tr_tv_off(A, B, u, o):
    """Old TV: A squashes to a glowing line and a dot; B opens back up from the line."""
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    src, k = (A, ease_in(u * 2, 2)) if u < 0.5 else (B, 1 - ease_out((u - 0.5) * 2, 2))
    sy = max(0.004, 1 - k); sx = 1 + 0.12 * k if k < 0.92 else (1.12 * (1 - (k - 0.92) / 0.08 * 0.9))
    im = bright(src, 1 + 1.6 * k).resize((max(2, int(W * sx)), max(2, int(H * sy))), Image.BILINEAR)
    out.alpha_composite(im, (int((W - im.width) / 2), int((H - im.height) / 2)))
    line = Image.new("L", (W, H), 0); ImageDraw.Draw(line).rectangle([(W - im.width) / 2, H / 2 - 3, (W + im.width) / 2, H / 2 + 3], fill=255)
    return glow_add(out, line, (210, 230, 255), 0.9 * k)


def tr_rgb_split(A, B, u, o):
    base = Image.blend(A, B, smooth((u - 0.42) / 0.16)); k = math.sin(math.pi * u) ** 2
    amp = int(o.get("amp", 70) * k)
    r, g, b, a = base.split()
    r = r.transform(base.size, Image.AFFINE, (1, 0, -amp, 0, 1, 0)); b = b.transform(base.size, Image.AFFINE, (1, 0, amp, 0, 1, -amp // 3))
    return zoom(Image.merge("RGBA", (r, g, b, a)), 1 + 0.06 * k)


def tr_strobe(A, B, u, o):
    i = int(u * 8)
    if i % 2: return over(B if i > 3 else A, (255, 255, 255), 0.82)
    return bright(A if i < 4 else B, 1.25 if i in (2, 4) else 1.0)


def tr_luma(A, B, u, o):
    """B appears through its brightest parts first, like light burning through."""
    lum = np.asarray(B.convert("L").resize((W // 4, H // 4), Image.BILINEAR), np.float32) / 255
    th = lerp(1.05, -0.25, smooth(u)); m = np.clip((lum - th) / 0.18, 0, 1)
    mask = Image.fromarray((m * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    return Image.composite(B, A, mask)


def tr_impact(A, B, u, o):
    if u < 0.5: return A
    k = (u - 0.5) * 2; amp = 46 * (1 - k) ** 2
    rng = np.random.default_rng(int(u * 1000))
    out = zoom(B, 1.09 - 0.09 * ease_out(k, 3), W / 2 + rng.normal(0, amp), H / 2 + rng.normal(0, amp))
    return over(out, (255, 255, 255), 0.85 * clamp(1 - k * 3.5))


def tr_card(A, B, u, o):
    """A shrinks into a rounded card and drops away; B is revealed behind it, coming forward."""
    k = ease_in_out(u); base = bright(zoom(B, 1.14 - 0.14 * k), 0.45 + 0.55 * k)
    s = 1 - 0.3 * k; im = A.resize((int(W * s), int(H * s)), Image.BILINEAR)
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], int(70 * k), fill=255)
    im.putalpha(m); y = int((H - im.height) / 2 + ease_in(u, 2.4) * H * 0.95); x = int((W - im.width) / 2)
    rot = o.get("sgn", 1) * 8 * ease_in(u, 2)
    if rot: im = im.rotate(rot, Image.BILINEAR, expand=True); x -= (im.width - int(W * s)) // 2
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 170), (0, 0), im.getchannel("A"))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(24)), (x, y + 30)); base.alpha_composite(im, (x, y))
    return base


def tr_stretch(A, B, u, o):
    """Elastic: A stretches tall and snaps away upward; B drops in and squashes on landing."""
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    if u < 0.5:
        k = ease_in(u * 2, 2.5); im = A.resize((W, int(H * (1 + 0.8 * k))), Image.BILINEAR)
        out.paste(dir_blur(im, 160 * k, 1), (0, int(-H * 1.3 * k ** 1.5)))
    else:
        k = (u - 0.5) * 2; y = int(H * (1 - ease_out(k, 2.6)) * 0.9); sq = 1 + 0.06 * math.sin(math.pi * clamp((k - 0.55) / 0.45))
        im = B.resize((W, int(H / sq)), Image.BILINEAR); out.paste(dir_blur(im, 120 * (1 - k), 1), (0, y + H - im.height))
    return out


# name: (fn, default seconds, sound categories (cycled), energy 1-3, about, fits)
TRANSITIONS = {
    "cut": (tr_cut, 0.0, [], 0, "hard cut", "any"),
    "whip": (tr_whip, 0.3, ["swish", "whoosh"], 2, "whip pan: both shots slide with heavy motion blur (dir l/r/u/d)", "any"),
    "slide": (tr_slide, 0.36, ["swipe", "swish"], 1, "push: new shot pushes the old one off, light blur (dir)", "face>overlay, overlay>overlay"),
    "zoom_in": (tr_zoom_in, 0.36, ["whoosh_heavy", "whoosh"], 3, "zoom-through: punch into the old shot with radial blur, land zoomed in on the new one", "face>face, reveals"),
    "zoom_out": (tr_zoom_out, 0.42, ["reverse", "whoosh"], 2, "old shot pulls away into the distance, new one pushes out", "overlay>face, endings"),
    "flash": (tr_flash, 0.24, ["impact", "shimmer"], 3, "white flash with an exposure bloom at the cut", "reveals, drops"),
    "shutter": (tr_shutter, 0.32, ["shutter"], 2, "camera shutter blades close and open with a flash", "screenshots, 'look at this', proof"),
    "glitch": (tr_glitch, 0.3, ["glitch"], 3, "digital corruption bursts, slices of each shot bleed into the other", "warnings, mistakes, loops"),
    "spin": (tr_spin, 0.34, ["whoosh", "swish"], 3, "rotational whip with zoom and blur", "high-energy moments, rarely"),
    "wipe": (tr_wipe, 0.34, ["swish", "swipe"], 1, "soft linear wipe with a glowing edge (dir)", "lists, before/after"),
    "iris": (tr_iris, 0.4, ["whoosh", "pop"], 2, "circle opens from a point (cx, cy) with a glowing ring", "focus on one thing"),
    "blur": (tr_blur, 0.36, ["whoosh"], 1, "defocus out, refocus in", "calm beats, time skips"),
    "dip": (tr_dip, 0.32, ["reverse"], 1, "dip to black", "section breaks"),
    "light_leak": (tr_light_leak, 0.5, ["shimmer", "whoosh"], 1, "warm film light leak washes across", "story, emotion"),
    "pixelate": (tr_pixelate, 0.3, ["glitch", "tick"], 2, "mosaic out and back", "digital topics, censor-style reveals"),
    "tv_off": (tr_tv_off, 0.4, ["stop", "switch"], 2, "old-TV switch-off to a line, back on", "endings, 'stop doing X'"),
    "rgb_split": (tr_rgb_split, 0.26, ["glitch", "swish"], 2, "chromatic split peaking at the cut", "punchy face>face"),
    "strobe": (tr_strobe, 0.3, ["impact", "glitch"], 3, "fast flashes alternating both shots", "drops, rarely"),
    "luma": (tr_luma, 0.45, ["shimmer"], 1, "new shot burns in through its brightest parts", "different content only (same face looks like a double exposure)"),
    "impact": (tr_impact, 0.3, ["impact"], 3, "hard cut that lands with a flash, shake and zoom punch", "drops, punchlines"),
    "card": (tr_card, 0.45, ["swipe", "whoosh"], 2, "old shot shrinks to a card and falls away, new one comes forward", "face>overlay, story beats"),
    "stretch": (tr_stretch, 0.36, ["swish", "pop"], 2, "elastic: old snaps up, new drops in and squashes", "playful beats"),
}


def transition(name, A, B, u, opts=None):
    if name not in TRANSITIONS: raise KeyError(f"unknown transition {name}; have {', '.join(TRANSITIONS)}")
    return rgba(TRANSITIONS[name][0](rgba(A), rgba(B), clamp(u), opts or {}))


# ---------------------------------------------------------------- glows
def glow_add(base, mask_L, col, strength, radii=(6, 22)):
    """Add a coloured glow (and a bright core) of an L mask onto base."""
    if strength <= 0.01: return base
    out = base.copy()
    for r, k in zip(radii, (1.0, 0.8)):
        g = Image.new("RGBA", base.size, (*col, 0)); g.putalpha(soft_blur(mask_L, r) if r > 8 else mask_L.filter(ImageFilter.GaussianBlur(r)))
        g.putalpha(g.getchannel("A").point(lambda v, s=strength * k: int(min(255, v * s * 2.2))))
        out.alpha_composite(g)
    core = Image.new("RGBA", base.size, (255, 255, 255, 0)); core.putalpha(mask_L.point(lambda v: int(v * clamp(strength))))
    out.alpha_composite(core); return out


def bloom(alpha, col, g=1.0):
    """Neon bloom from an alpha mask: a tight bright glow, a mid glow and a wide soft bloom, in the colour."""
    out = Image.new("RGBA", alpha.size, (0, 0, 0, 0))
    for r, k in ((3, 1.0), (12, 0.85), (34, 0.55)):
        layer = Image.new("RGBA", alpha.size, (*col[:3], 0))
        a = alpha.filter(ImageFilter.GaussianBlur(r)) if r < 20 else soft_blur(alpha, r)
        layer.putalpha(a.point(lambda v, s=k * g: int(min(255, v * s * 1.6))))
        out.alpha_composite(layer)
    return out


def hot_core(col, mix=0.55):
    """Neon tube colour: the hue pushed towards white, so the glyph reads lit, not painted."""
    return tuple(int(c + (255 - c) * mix) for c in col[:3]) + (255,)


def shine(im, u, width=0.12, angle=22, strength=0.85):
    """A diagonal light sweep across im's opaque parts at position u (0..1, may run past)."""
    if not 0 <= u <= 1.2: return im
    w, h = im.size; a = np.asarray(im.getchannel("A"), np.float32) / 255
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = math.radians(angle); proj = (xx * math.cos(t) + yy * math.sin(t)) / (w * math.cos(t) + h * math.sin(t))
    band = np.exp(-((proj - lerp(-0.15, 1.15, u)) / width) ** 2) * a * strength
    arr = np.asarray(im, np.float32).copy(); arr[..., :3] = arr[..., :3] + (255 - arr[..., :3]) * band[..., None]
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


# ---------------------------------------------------------------- glitch
PALETTE = [(0, 255, 140), (255, 0, 200), (255, 230, 0), (0, 160, 255), (255, 255, 255)]


def glitch_frame(img, amt, seed, other=None, hist=None):
    """Digital corruption at strength amt (about 0..1.5). Real glitches come in bursts with clean frames between,
    so the caller varies amt per frame (see glitch_amt)."""
    if amt <= 0.02: return img
    rng = np.random.default_rng(abs(int(seed)) % (2 ** 32))
    a = np.asarray(img.convert("RGB")).copy(); h_, w_ = a.shape[:2]
    o = np.asarray(other.convert("RGB")) if other is not None else None
    # 1) horizontal slices pushed sideways, some with their own RGB split, some bleeding in the other shot
    for _ in range(int(5 + 16 * amt)):
        hh = int(rng.choice([2, 3, 5, 8, 14, 24, 40, 70, 130]) * (0.6 + 0.8 * rng.random()))
        y = int(rng.integers(0, max(1, h_ - hh))); dx = int(rng.normal(0, 70 * amt))
        src = o if (o is not None and rng.random() < 0.35) else a
        band = np.roll(src[y:y + hh], dx, axis=1)
        if rng.random() < 0.6:
            k = int(rng.integers(4, 22) * amt) + 1; band = band.copy()
            band[..., 0] = np.roll(band[..., 0], k, axis=1); band[..., 2] = np.roll(band[..., 2], -k, axis=1)
        a[y:y + hh] = band
    # 2) macroblocks: stale blocks from an older frame (datamosh), smeared blocks, flat quantized blocks
    bs = int(rng.choice([16, 32, 48]))
    for _ in range(int(14 * amt * amt + 5 * amt)):
        bx = int(rng.integers(0, w_ // bs)) * bs; by = int(rng.integers(0, h_ // bs)) * bs
        bw = bs * int(rng.integers(1, 7)); bh = bs * int(rng.integers(1, 3)); m = rng.random()
        if hist and m < 0.4:
            old = hist[int(rng.integers(0, len(hist)))]
            if old.shape == a.shape: a[by:by + bh, bx:bx + bw] = old[by:by + bh, bx:bx + bw]
        elif m < 0.75: a[by:by + bh, bx:bx + bw] = a[by:by + 1, bx:bx + bw]
        else:
            blk = a[by:by + bh, bx:bx + bw]
            if blk.size: a[by:by + bh, bx:bx + bw] = (blk.reshape(-1, 3).mean(0) // 24 * 24).astype(np.uint8)
    # 3) pixel stretch: one row dragged down over a band, across part of the width
    if rng.random() < 0.55 * amt:
        y = int(rng.integers(0, h_ - 300)); hh = int(rng.integers(40, 280)); x0 = int(rng.integers(0, w_ // 2)); x1 = int(rng.integers(x0 + 200, w_ + 1))
        a[y:y + hh, x0:x1] = a[y:y + 1, x0:x1]
    # 4) scanline noise
    for _ in range(int(2 + 4 * amt)):
        y = int(rng.integers(0, h_ - 4)); hh = int(rng.integers(1, 4))
        a[y:y + hh] = rng.integers(0, 256, (hh, w_, 3), dtype=np.uint8) if rng.random() < 0.5 else np.array(PALETTE[int(rng.integers(0, len(PALETTE)))], np.uint8)
    # 5) on hard bursts, a channel swap or a negative over a band
    if amt > 0.85 and rng.random() < 0.35:
        y = int(rng.integers(0, h_ // 2)); hh = int(rng.integers(h_ // 8, h_ // 2))
        a[y:y + hh] = a[y:y + hh][..., [2, 0, 1]] if rng.random() < 0.5 else 255 - a[y:y + hh]
    # 6) whole-frame jitter
    a = np.roll(a, int(rng.normal(0, 10 * amt)), axis=1)
    return Image.fromarray(a).convert("RGBA")


def glitch_rgba(im, amt, seed):
    """Light glitch for a transparent layer (a title): sliced rows pushed sideways with an RGB split, alpha kept."""
    if amt <= 0.02: return im
    rng = np.random.default_rng(abs(int(seed)) % (2 ** 32)); a = np.asarray(im).copy(); h_ = a.shape[0]
    for _ in range(int(3 + 8 * amt)):
        hh = int(rng.integers(3, max(4, h_ // 5))); y = int(rng.integers(0, max(1, h_ - hh))); dx = int(rng.normal(0, 40 * amt))
        band = np.roll(a[y:y + hh], dx, axis=1); k = int(rng.integers(3, 14) * amt) + 1
        band[..., 0] = np.roll(band[..., 0], k, axis=1); band[..., 2] = np.roll(band[..., 2], -k, axis=1); a[y:y + hh] = band
    return Image.fromarray(a, "RGBA")


def glitch_amt(u, frame, seed=0, base=1.0):
    """Burst envelope: mostly strong corrupted frames with an occasional near-clean one, fading at the ends."""
    r = random.Random(frame * 7919 + seed * 31).random()
    env = math.sin(math.pi * clamp(u)) ** 0.5
    return base * env * (0.25 if r < 0.2 else (1.25 if r > 0.8 else 0.85))


# ---------------------------------------------------------------- spotlight dim
def dim(img, k, level=0.3, desat=0.5):
    """k (0..1) of the way into a dim to `level` brightness, with some desaturation."""
    if k <= 0.003: return img
    rgb = img.convert("RGB")
    if desat: rgb = ImageEnhance.Color(rgb).enhance(1 - desat * k)
    return rgb.point(_lut(round(1 - k * (1 - level), 2))).convert("RGBA")


# ---------------------------------------------------------------- title animations
TITLE_IN = {
    "flicker": "neon flicker-on (fast on/off), label typed on",
    "pop": "scale overshoot from 55%",
    "type": "typed on letter by letter (key clicks)",
    "scramble": "random characters resolve into the words, left to right (digital ticks)",
    "slide": "lines slide in from alternate sides with motion blur",
    "drop": "falls from above and lands with a shake (impact)",
    "stamp": "slams down from 2.4x with a shake (stamp)",
    "blur": "comes into focus from a big soft blur",
    "reveal": "wiped on left to right behind a glowing edge",
    "zoom": "flies in from far away (whoosh)",
    "glitch": "glitches into place",
    "rise": "rises 60 px while fading in, each line staggered",
}
TITLE_OUT = {"fade": "fade", "pop": "shrinks away", "slide": "slides off", "blur": "blurs out", "glitch": "glitches out",
             "flicker": "flickers off", "drop": "falls away", "cut": "just disappears"}
# sounds per animation: (category, when) - when: "start", "land" (t0 + d), or "chars" (one per character)
# Only a title that visibly types gets key sounds; the neon buzz reads as a siren.
TITLE_SFX = {"flicker": [("shimmer", "start")], "pop": [("pop", "start")], "type": [("key", "chars")],
             "scramble": [("glitch", "start")], "slide": [("swish", "start")],
             "drop": [("impact", "land")], "stamp": [("stamp", "land")], "blur": [("whoosh", "start")],
             "reveal": [("swish", "start"), ("shimmer", "land")], "zoom": [("whoosh", "start"), ("impact", "land")],
             "glitch": [("glitch", "start")], "rise": [("shimmer", "start")]}
TITLE_D = {"flicker": 0.28, "pop": 0.16, "type": None, "scramble": 0.45, "slide": 0.28, "drop": 0.26, "stamp": 0.16,
           "blur": 0.3, "reveal": 0.34, "zoom": 0.3, "glitch": 0.24, "rise": 0.32}
SCRAMBLE = "#%&@$*+=?/<>0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def title_anim(kind, t, t0, t1, n_chars, out="fade", d_in=None, d_out=0.18, cps=0.045):
    """Animation state for a title at time t. Returns a dict: scale, alpha, dx, dy, blur, rot, reveal (0..1, None
    = no wipe), chars (how many characters are final), scramble (bool), glitch (0..), shake (px), lines_dx (per
    line offsets factor), glow (multiplier)."""
    d = d_in if d_in is not None else (TITLE_D.get(kind) or min(0.9, n_chars * cps))
    if kind == "type": d = d_in if d_in is not None else min(0.9, n_chars * cps)
    u = clamp((t - t0) / max(d, 1e-3)); s = dict(scale=1.0, alpha=1.0, dx=0.0, dy=0.0, blur=0.0, rot=0.0, reveal=None,
                                                  chars=n_chars, scramble=False, glitch=0.0, shake=0.0, lines_dx=0.0, glow=1.0)
    if kind == "flicker":
        fl = t - t0; s["alpha"] = 1.0 if fl > 0.22 else [1, 0.12, 0.9, 0.25, 1, 0.55, 1][min(6, int(fl * 30))]
        s["scale"] = lerp(1.06, 1.0, ease_out(fl / 0.25))
    elif kind == "pop": s["scale"] = lerp(0.55, 1.0, ease_out_back(u, 2.2)); s["alpha"] = clamp(u * 3)
    elif kind == "type": s["chars"] = int(n_chars * u + 0.999) if u < 1 else n_chars
    elif kind == "scramble": s["chars"] = int(n_chars * ease_in_out(u)); s["scramble"] = u < 1; s["alpha"] = clamp(u * 6)
    elif kind == "slide": s["lines_dx"] = (1 - ease_out(u, 4)) * 900; s["blur"] = 0
    elif kind == "drop":
        s["dy"] = -900 * (1 - ease_in(u, 2)) if u < 1 else 0.0; s["alpha"] = clamp(u * 4)
        k = clamp((t - t0 - d) / 0.25); s["shake"] = 22 * (1 - k) ** 2 if t >= t0 + d else 0
        s["scale"] = 1 + 0.06 * math.sin(math.pi * k) if t >= t0 + d else 1.0
    elif kind == "stamp":
        s["scale"] = lerp(2.4, 1.0, ease_in(u, 2)); s["alpha"] = clamp(u * 2.5)
        k = clamp((t - t0 - d) / 0.22); s["shake"] = 26 * (1 - k) ** 2 if t >= t0 + d else 0
    elif kind == "blur": s["blur"] = 26 * (1 - ease_out(u)); s["scale"] = lerp(1.25, 1.0, ease_out(u)); s["alpha"] = clamp(u * 2)
    elif kind == "reveal": s["reveal"] = ease_in_out(u) if u < 1 else None
    elif kind == "zoom": s["scale"] = lerp(0.08, 1.0, ease_out(u, 4)); s["alpha"] = clamp(u * 3); s["blur"] = 8 * (1 - u)
    elif kind == "glitch": s["glitch"] = 1.1 * (1 - u) if u < 1 else 0.0; s["alpha"] = clamp(u * 5)
    elif kind == "rise": s["dy"] = 60 * (1 - ease_out(u)); s["alpha"] = ease_out(u, 2)
    # exit
    if out != "cut" and t > t1 - d_out:
        v = clamp((t - (t1 - d_out)) / d_out)
        if out == "fade": s["alpha"] *= 1 - v
        elif out == "pop": s["scale"] *= lerp(1.0, 0.4, ease_in(v, 2)); s["alpha"] *= 1 - ease_in(v, 2)
        elif out == "slide": s["dx"] -= 1100 * ease_in(v, 3)
        elif out == "blur": s["blur"] += 24 * v; s["alpha"] *= 1 - v; s["scale"] *= 1 + 0.15 * v
        elif out == "glitch": s["glitch"] = max(s["glitch"], 1.2 * v); s["alpha"] *= 1 - ease_in(v, 3)
        elif out == "flicker": s["alpha"] *= [1, 0.1, 0.8, 0.0, 0.5, 0.0][min(5, int(v * 6))]
        elif out == "drop": s["dy"] += 900 * ease_in(v, 2.5); s["alpha"] *= 1 - ease_in(v, 3)
    return s


def scramble_text(text, n_final, seed):
    """First n_final non-space characters final, the rest random glyphs (spaces kept)."""
    r = random.Random(seed); out = []; k = 0
    for ch in text:
        if ch == " ": out.append(ch); continue
        out.append(ch if k < n_final else r.choice(SCRAMBLE)); k += 1
    return "".join(out)


def reveal_mask(im, u, soft=40):
    """Wipe im on left to right (u 0..1) with a glowing edge."""
    w, h = im.size; e = u * (w + soft) - soft / 2
    x = np.arange(w, dtype=np.float32); m = np.clip((e - x) / soft + 0.5, 0, 1)
    a = (np.asarray(im.getchannel("A"), np.float32) * m[None, :]).astype(np.uint8)
    out = im.copy(); out.putalpha(Image.fromarray(a))
    edge = np.exp(-((x - e) / 10) ** 2)[None, :] * (np.asarray(im.getchannel("A"), np.float32) > 0)
    if u < 1:
        glow = Image.new("RGBA", (w, h), (255, 255, 255, 0)); glow.putalpha(Image.fromarray((edge * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)))
        out.alpha_composite(glow); out.alpha_composite(glow)
    return out


# ---------------------------------------------------------------- neon line icons
def _arc(cx, cy, r, a0, a1, n=28, ry=None):
    ry = r if ry is None else ry
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


ICONS = {   # strokes in a unit box, drawn in order
    "check": [[(0.14, 0.54), (0.4, 0.8), (0.88, 0.22)]],
    "cross": [[(0.2, 0.2), (0.8, 0.8)], [(0.8, 0.2), (0.2, 0.8)]],
    "question": [_arc(0.5, 0.33, 0.2, 200, 400) + [(0.5, 0.56), (0.5, 0.66)], _arc(0.5, 0.84, 0.035, 0, 360, 12)],
    "warning": [[(0.5, 0.08), (0.95, 0.88), (0.05, 0.88), (0.5, 0.08)], [(0.5, 0.36), (0.5, 0.62)], _arc(0.5, 0.75, 0.03, 0, 360, 10)],
    "trend_up": [[(0.05, 0.86), (0.36, 0.55), (0.56, 0.7), (0.93, 0.2)], [(0.68, 0.2), (0.93, 0.2), (0.93, 0.45)]],
    "trend_down": [[(0.05, 0.16), (0.36, 0.47), (0.56, 0.32), (0.93, 0.82)], [(0.68, 0.82), (0.93, 0.82), (0.93, 0.57)]],
    "podium": [[(0.03, 0.9), (0.03, 0.62), (0.34, 0.62), (0.34, 0.42), (0.66, 0.42), (0.66, 0.7), (0.97, 0.7), (0.97, 0.9), (0.03, 0.9)]],
    "funnel": [[(0.05, 0.12), (0.95, 0.12), (0.6, 0.55), (0.6, 0.9), (0.4, 0.82), (0.4, 0.55), (0.05, 0.12)]],
    "user": [_arc(0.5, 0.32, 0.18, -90, 270), _arc(0.5, 0.95, 0.36, 180, 360, 24, 0.32)],
    "eye": [_arc(0.5, 0.75, 0.48, 200, 340, 24, 0.5), _arc(0.5, 0.25, 0.48, 20, 160, 24, 0.5), _arc(0.5, 0.5, 0.14, 0, 360)],
    "bell": [_arc(0.5, 0.42, 0.28, 180, 360) + [(0.78, 0.72), (0.9, 0.8), (0.1, 0.8), (0.22, 0.72), (0.22, 0.42)], _arc(0.5, 0.86, 0.08, 0, 180, 10)],
    "lock": [[(0.2, 0.46), (0.8, 0.46), (0.8, 0.92), (0.2, 0.92), (0.2, 0.46)], _arc(0.5, 0.46, 0.2, 180, 360) , [(0.5, 0.62), (0.5, 0.76)]],
    "target": [_arc(0.5, 0.5, 0.44, 0, 360, 36), _arc(0.5, 0.5, 0.28, 0, 360, 28), _arc(0.5, 0.5, 0.1, 0, 360, 14)],
    "heart": [[(0.5 + 0.42 * (16 * math.sin(a) ** 3) / 16, 0.46 - 0.42 * (13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) / 16)
               for a in [math.pi * 2 * k / 48 for k in range(49)]]],
    "phone": [[(0.28, 0.04), (0.72, 0.04), (0.72, 0.96), (0.28, 0.96), (0.28, 0.04)], [(0.44, 0.88), (0.56, 0.88)]],
    "clock": [_arc(0.5, 0.5, 0.44, -90, 270, 36), [(0.5, 0.22), (0.5, 0.5), (0.7, 0.62)]],
    "arrow_right": [[(0.06, 0.5), (0.9, 0.5)], [(0.62, 0.22), (0.9, 0.5), (0.62, 0.78)]],
}


def _len(st): return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(st, st[1:]))


def neon_icon(name, u, col, size=420, width=None, g=1.3):
    """The icon drawn on to fraction u of its total length, with a neon bloom. Returns RGBA (size+pad)."""
    if name not in ICONS: raise KeyError(f"unknown icon {name}; have {', '.join(ICONS)}")
    strokes = ICONS[name]; total = sum(_len(s) for s in strokes); left = clamp(u) * total
    pad = int(size * 0.25); S = size + 2 * pad; width = width or max(7, size // 20)
    mask = Image.new("L", (S, S), 0); d = ImageDraw.Draw(mask)
    P = lambda p: (pad + p[0] * size, pad + p[1] * size)
    for st in strokes:
        if left <= 0: break
        pts = [P(st[0])]
        for a, b in zip(st, st[1:]):
            seg = math.hypot(b[0] - a[0], b[1] - a[1])
            if left >= seg: pts.append(P(b)); left -= seg
            else: f = left / max(seg, 1e-6); pts.append(P((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))); left = 0; break
        if len(pts) > 1: d.line(pts, fill=255, width=width, joint="curve")
        for p in (pts[0], pts[-1]): d.ellipse([p[0] - width / 2, p[1] - width / 2, p[0] + width / 2, p[1] + width / 2], fill=255)
    out = bloom(mask, col, g); core = Image.new("RGBA", (S, S), hot_core(col, 0.6)); core.putalpha(mask)
    out.alpha_composite(core); return out
