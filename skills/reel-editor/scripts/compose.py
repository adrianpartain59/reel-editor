#!/usr/bin/env python3
"""Step 4: composite one reel variant frame by frame from PROJECT/plan.json.

  compose.py PROJECT --variant h1                    full render -> work/out/h1/video.mp4 + events.json
  compose.py PROJECT --variant h1 --preview 0.5,2,7  stills only -> work/out/h1/preview/*.jpg + sheet.jpg
  compose.py PROJECT --variant h1 --cover            cover image  -> out/<slug>-h1-cover.jpg

The timeline is the hook part followed by the body part. Every time in plan.json is relative to its own part and
may be a number of seconds or a word reference (w12, w12e, w12+0.1) from work/timeline.txt.
See references/plan-schema.md for every layout, sticker, fx and caption style.
"""
import argparse, os, json, math, random, re, subprocess, sys
from collections import deque
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat, ImageChops, ImageEnhance
from common import load, save, tspec, load_style, W, H, FPS, die, run
import fx

SF = "/System/Library/Fonts/SFNS.ttf"
NYI = "/System/Library/Fonts/NewYorkItalic.ttf"
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"
HAND = "/System/Library/Fonts/Noteworthy.ttc"
PHONE_LAYS = {"fullpw", "phone3d"}               # "fullpw" renders as phone3d when the style says so
# the hook's snap-out intro zoom, on by default
INTRO_DEFAULT = {"from": 1.35, "d": 0.2, "zoom_blur": 0.14, "blur": 7.0, "edge_blur": 18.0}
# Instagram Reels UI covers roughly y<200 (top bar), y>1540 (username, caption, audio) and x>940 below y=1150
SAFE_TOP, SAFE_BOTTOM = 200, 1540
FULL_Y, FULL_H = 300, 1420                      # full-screen phone: its CTA area lands above SAFE_BOTTOM
PHONE_W, PHONE_H = 1260, 2640                   # mockup PNG size (3x)
SCREEN = (63, 63, 1134, 2514, 159)              # screen rect inside the phone PNG (x, y, w, h, radius)
CAPY = {"face": 1480, "split": 960, "fullpw": 250, "phone3d": 250, "video": 250, "broll": 1480, "letterbox": 1430}
CAP_TOP_BAND = 250                              # caption ink top on phones, b-roll and splits (just under TEXT_TOP)
CAP_HEAD = 0.62                                 # face shots: caption ink ends this many face-heights above the face centre
OVERLAY_LAYS = {"split", "fullpw", "phone3d", "video", "broll"}
TEXT_TYPES = {"glow_title", "text", "counter", "hand_note", "chat_pill", "icon"}   # stay lit under a spotlight fx
PHONE_IN = {"rise": "rises in turning towards camera", "side": "swings in from the side", "far": "flies in from far away",
            "drop": "drops from the top and bounces", "flip": "flips round from edge-on"}
PHONE_OUT = {"sink": "sinks and fades", "side": "swings off to the side", "far": "shrinks away into the distance",
             "flip": "flips edge-on"}

# Every cue carries how long it may play (its span: the on-screen motion it belongs to) and a priority. mix.py
# trims each sound to its span, plays one sound at a time, and drops the lower-priority cue when two collide.
# (Without this, scribbles and whooshes run past what is on screen and sounds stack up.)
CUE_SPAN = {"tr": 0.3, "phone_in": 0.4, "phone_out": 0.35, "overlay_enter": 0.4, "overlay_enter_soft": 0.35,
            "overlay_land": 0.3, "overlay_exit": 0.3, "swap": 0.15, "smash": 0.3, "reveal": 0.35, "settle": 0.35,
            "bg_in": 0.4, "drop": 0.7, "punch": 0.45, "title": 0.4, "spotlight": 0.3, "red_x": 0.35, "check": 0.4,
            "circle": 0.45, "hand_note": 0.6, "icon": 0.5, "icon_done": 0.3, "chat_key": 0.07, "chat_send": 0.35,
            "counter": 0.07, "counter_land": 0.4, "star": 0.07, "plan": 0.45, "glitch": 0.3, "letterbox": 0.4}


def cue_span(key):
    k = str(key)
    if k.startswith("title:"): return 0.07 if k[6:] in ("key", "tick") else 0.4
    return CUE_SPAN.get(k.split(":")[0], 0.4)


def cue_prio(key, name):
    """3 drops and impacts, 2.5 titles and punches, 2 transitions, 1.5 stickers, 1 the rest, 0.5 keys and ticks."""
    k, n = str(key), str(name)
    if k == "drop" or "impact" in n or "stamp" in n or "low_hit" in n: return 3.0
    if k.startswith("title:") and k[6:] in ("key", "tick"): return 0.5
    if k.startswith(("title", "punch")): return 2.5
    if k.startswith("tr:"): return 2.0
    if k in ("chat_key", "counter", "star"): return 0.5
    if k in ("red_x", "check", "circle", "hand_note", "icon", "chat_send", "counter_land", "spotlight"): return 1.5
    return 1.0


class Sounds:
    """Resolves sound specs to files. "cat:a|b" = a category of the sound pack (cycling a -> b on each use of the same
    event kind; sfx_lib.Picker rotates files so the same file never plays twice in a row)."""
    def __init__(self, seed=0):
        self.rr, self.cats = {}, set()
        try:
            import sfx_lib, sfx_pack; sfx_pack.ensure(); self.picker = sfx_lib.Picker(seed=seed); self.cats = set(sfx_lib.cats())
        except Exception:
            self.picker = None

    def resolve(self, spec, t, key, span=None):
        # only the sound pack plays: old category and synthesized names map into it via sfx_lib.canon.
        # Sounds marked `fit` (typing, scribble) get the file whose length matches the visual (span), never a cut one.
        import sfx_lib
        if spec.startswith("lib:"): return spec
        def pick(c): return "lib:" + self.picker.pick(c, t, fit=span if sfx_lib.rules(c).get("fit") else None)
        if not spec.startswith("cat:"):
            c = sfx_lib.canon(spec)
            return pick(c) if c and self.picker else None
        opts = spec[4:].split("|"); n = self.rr.get(key, 0); self.rr[key] = n + 1
        for k in range(len(opts)):
            c = sfx_lib.canon(opts[(n + k) % len(opts)])
            if c in self.cats and self.picker: return pick(c)
        return None


# ---------------------------------------------------------------- small helpers
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, u): return a + (b - a) * u
def ease_out_back(u, s=1.9): u -= 1; return 1 + (s + 1) * u ** 3 + s * u ** 2
def ease_out_cubic(u): return 1 - (1 - u) ** 3
def ease_in_out(u): return 0.5 - 0.5 * math.cos(math.pi * clamp(u))


@lru_cache(None)
def font(kind, size):
    if kind == "serif":
        f = ImageFont.truetype(NYI, size); f.set_variation_by_name("Heavy Italic"); return f
    if kind == "hand":
        return ImageFont.truetype(HAND, size, index=1)
    f = ImageFont.truetype(SF, size)
    f.set_variation_by_name({"black": "Black", "heavy": "Heavy", "bold": "Bold", "semibold": "Semibold",
                             "cblack": "Compressed Black", "cheavy": "Compressed Heavy", "regular": "Regular",
                             "xblack": "Expanded Black"}[kind])
    return f


def norm(w): return re.sub(r"[^\w$%']", "", w.lower())


def hexc(h, a=255):
    h = h.lstrip("#"); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def shadowed(im, blur=12, alpha=150, dy=8):
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, alpha), (0, 0), im)
    sh = sh.filter(ImageFilter.GaussianBlur(blur)); out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, dy)); out.alpha_composite(im); return out


def paste_center(dst, im, cx, cy, scale=1.0, alpha=1.0):
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if alpha < 1.0:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    dst.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# HARD RULE, the text safe area. No text's ink may leave this box: Instagram's top bar sits above TEXT_TOP, the username / caption /
# audio line below TEXT_BOTTOM, and the like / comment / share column right of TEXT_RIGHT_LOW from TEXT_COLUMN_Y down.
# paste_text moves (and, for a wide line low on screen, shrinks) every caption, title, punch and text sticker into it.
TEXT_LEFT, TEXT_RIGHT, TEXT_TOP, TEXT_BOTTOM = 40, 1040, 220, 1500
TEXT_RIGHT_LOW, TEXT_COLUMN_Y = 900, 1150


def safe_text_box(im, cx, cy, scale=1.0):
    """(cx, cy, scale) that keep the image's ink inside the text safe area."""
    w, h = im.width * scale, im.height * scale
    bb = im.getbbox() or (0, 0, im.width, im.height)
    def box(cx, cy, s):
        w_, h_ = im.width * s, im.height * s
        return (cx - w_ / 2 + bb[0] * s, cy - h_ / 2 + bb[1] * s, cx - w_ / 2 + bb[2] * s, cy - h_ / 2 + bb[3] * s)
    x0, y0, x1, y1 = box(cx, cy, scale)
    if x1 - x0 > TEXT_RIGHT - TEXT_LEFT: scale *= (TEXT_RIGHT - TEXT_LEFT) / (x1 - x0); x0, y0, x1, y1 = box(cx, cy, scale)
    if y1 - y0 > TEXT_BOTTOM - TEXT_TOP: scale *= (TEXT_BOTTOM - TEXT_TOP) / (y1 - y0); x0, y0, x1, y1 = box(cx, cy, scale)
    if y0 < TEXT_TOP: cy += TEXT_TOP - y0
    elif y1 > TEXT_BOTTOM: cy -= y1 - TEXT_BOTTOM
    x0, y0, x1, y1 = box(cx, cy, scale)
    if x0 < TEXT_LEFT: cx += TEXT_LEFT - x0
    elif x1 > TEXT_RIGHT: cx -= x1 - TEXT_RIGHT
    x0, y0, x1, y1 = box(cx, cy, scale)
    if y1 > TEXT_COLUMN_Y and x1 > TEXT_RIGHT_LOW:           # beside the like / share column
        room = TEXT_RIGHT_LOW - TEXT_LEFT
        if x1 - x0 > room: scale *= room / (x1 - x0); x0, y0, x1, y1 = box(cx, cy, scale)
        cx -= x1 - TEXT_RIGHT_LOW
        x0, y0, x1, y1 = box(cx, cy, scale)
        if x0 < TEXT_LEFT: cx += TEXT_LEFT - x0
    return cx, cy, scale


_CLIP = {}


def clip_frame(r, st, t):
    """The frame of a "clip" sticker at time t: PNG frames in st["src"] (a folder, sorted by name) at st["fps"]
    (30), scaled to st["w"] (900) px wide; holds the last frame once it runs out."""
    p = Path(st["src"]).expanduser(); p = p if p.is_absolute() else r.proj / p
    if p not in _CLIP: _CLIP[p] = sorted(p.glob("*.png"))
    files = _CLIP[p]
    if not files: return None
    i = min(len(files) - 1, max(0, int((t - st["_t0"]) * st.get("fps", FPS))))
    key = (p, i, st.get("w", 900))
    if key not in _CLIP:
        im = Image.open(files[i]).convert("RGBA"); w = st.get("w", 900)
        _CLIP.clear() if len(_CLIP) > 120 else None
        _CLIP[p] = files
        _CLIP[key] = im if im.width == w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    return _CLIP[key]


def paste_text(dst, im, cx, cy, scale=1.0, alpha=1.0):
    """paste_center for anything with words in it: always lands inside the text safe area."""
    cx, cy, scale = safe_text_box(im, cx, cy, scale)
    paste_center(dst, im, cx, cy, scale, alpha)


def pop_scale(t, t0, dur=0.14, s0=0.55):
    u = clamp((t - t0) / dur); return lerp(s0, 1.0, ease_out_back(u, 2.2)) if u < 1 else 1.0


# ---------------------------------------------------------------- project / plan loading
class Reel:
    def __init__(self, proj, variant):
        self.proj = Path(proj).expanduser().resolve()
        self.plan = load(self.proj / "plan.json")
        self.style = load_style(self.plan)
        self.cine = self.style.get("titles") == "glow" or bool(self.style["grade"].get("segment"))
        self.project = load(self.proj / "project.json")
        if variant not in self.plan.get("hooks", {}): die(f"plan.json has no hooks.{variant}")
        self.variant = variant
        self.parts = []
        off = 0.0
        for name, key in [(f"hook-{variant}", ("hooks", variant)), ("body", ("body",))]:
            d = self.proj / "work" / "parts" / name
            segs = load(d / "segs.json"); words = load(d / "words.json")
            spec = self.plan[key[0]][key[1]] if len(key) == 2 else self.plan["body"]
            self.parts.append({"name": name, "dir": d, "off": off, "dur": segs["duration"], "frames": segs["frames"],
                               "segs": segs["segs"], "words": words, "spec": spec})
            off += segs["duration"]
        self.dur = off
        self.nfr = sum(p["frames"] for p in self.parts)
        self.mock = self.proj / "mock"
        self.hist, self.frozen, self.mask, self.view = deque(maxlen=6), {}, None, (0, 0, 1.0)
        self.resolve()

    def T(self, part, v): return tspec(v, part["words"], part["off"])

    def default_outro(self):
        """HARD RULE, the comment outro. Every reel ends on a chat_pill: the comment
        box with the speaker's face, a comment typed in letter by letter, then sent. A plan that has one keeps it; otherwise one
        is added over the last sentence with plan "outro_comment" (text) or a neutral default. "outro_comment": false
        is the only way to leave it out."""
        oc = self.plan.get("outro_comment", True)
        if oc is False or any(st["type"] == "chat_pill" for st in self.stickers): return
        body = self.parts[-1]; ws = body["words"]
        if not ws: return
        k = 0
        for i in range(len(ws) - 1):
            if re.search(r"[.!?]$", ws[i][0]): k = i + 1
        t0 = body["off"] + ws[k][1] + 0.05
        t0 = min(max(t0, self.dur - 4.5), self.dur - 1.6)         # whisper sometimes loses the full stop before the last sentence
        text = oc if isinstance(oc, str) else "trying this today"
        avail = self.dur - t0 - 0.15 - 0.45
        cps = max(0.03, min(0.06, avail / max(1, len(text))))
        self.stickers.append({"type": "chat_pill", "text": text, "y": 1300, "delay": 0.15, "cps": round(cps, 3),
                              "t0": t0, "t1": self.dur, "_t0": t0, "_t1": self.dur, "_auto": True})

    def resolve(self):
        self.shots, self.sections, self.punches, self.stickers, self.fx, self.sfx = [], [], [], [], [], []
        self.drops, self.risers = [], []
        cap_st = self.style["captions"]
        default_sec = [[0, cap_st.get("default", "pop"), cap_st.get("accent", "#FFE14D")]]
        self.words = []  # (clean, raw, start, end) on the global timeline
        for p in self.parts:
            s = p["spec"]; T = lambda v: self.T(p, v)
            fix = s.get("fix", {})
            for i, (w, a, b) in enumerate(p["words"]):
                if f"w{i}" in fix:
                    w = fix[f"w{i}"]
                    if not w: continue          # "" hides a word from the captions (timing refs still work)
                self.words.append((re.sub(r"[.,!;:]", "", w), w, p["off"] + a, p["off"] + b))
            shots = sorted(s.get("shots", [{"t": 0, "lay": "face", "z": 1.0}]), key=lambda x: T(x["t"]))
            if not shots or T(shots[0]["t"]) > p["off"] + 1e-6: shots.insert(0, {"t": 0, "lay": "face", "z": 1.0})
            for sh in shots:
                sh = dict(sh); sh["_t"] = T(sh["t"])
                sh["_swaps"] = [(T(ts), img) for ts, img in sh.get("swaps", [])]
                if sh["lay"] == "fullpw" and self.style["overlays"].get("phone_layout") == "phone3d": sh["lay"] = "phone3d"
                if sh.get("drop"): self.drops.append(sh["_t"])
                self.shots.append(sh)
            for d in s.get("drops", []): self.drops.append(T(d))
            for rz in s.get("risers", []):    # a build under the voice, mixed like the bed (outside the one-at-a-time map)
                self.risers.append({"id": rz["id"], "peak": T(rz["peak"]), "t0": T(rz.get("t0", 0)), "db": rz.get("db", 0)})
            for sec in s.get("sections", default_sec):
                self.sections.append((T(sec[0]), sec[1], sec[2] if len(sec) > 2 else cap_st.get("accent", "#FFE14D")))
            for pu in s.get("punches", []):
                self.punches.append({**pu, "_t0": T(pu["t0"]), "_t1": T(pu["t1"])})
            for st in s.get("stickers", []):
                self.stickers.append({**st, "_t0": T(st["t0"]), "_t1": T(st["t1"])})
            for fx in s.get("fx", []):
                self.fx.append({**fx, "_t": T(fx["t"])})
            if s.get("cta") is not None: die('plan key "cta" is gone: the ding plays only on a tap sticker with "cta": true, a button visibly being clicked')
            for ev in s.get("sfx", []):
                self.sfx.append([round(T(ev[0]), 3), ev[1], ev[2] if len(ev) > 2 else 0])
        self.default_outro()
        self.shots.sort(key=lambda x: x["_t"])
        for i, sh in enumerate(self.shots):
            sh["_end"] = self.shots[i + 1]["_t"] if i + 1 < len(self.shots) else self.dur
        self.sections.sort(key=lambda x: x[0])
        self.rng = random.Random(self.plan.get("seed", 7))
        self.check_shots()
        self.plan_transitions()
        self.plan_variety()
        self.spots = [(st["_t0"], st["_t1"], 0.3 if st["spotlight"] is True else st["spotlight"]) for st in self.stickers if st.get("spotlight")]
        self.spots += [(f["_t"], f["_t"] + f.get("d", 1.2), f.get("level", 0.3)) for f in self.fx if f["type"] == "spotlight"]
        self.spot_fx = [(f["_t"], f["_t"] + f.get("d", 1.2)) for f in self.fx if f["type"] == "spotlight"]
        self.build_groups()
        self.auto_sfx()

    # -------------------------------------------------- intent checks, transitions, variety
    def check_shots(self):
        """Every layout and background has to carry something: an empty letterbox or a background with no content is
        decoration, and the plan is refused."""
        for sh in self.shots:
            if sh["lay"] == "letterbox" and not (sh.get("top") or sh.get("bottom")):
                die(f"letterbox at {sh['_t']:.2f}s has nothing in its bars. Give it 'top' and/or 'bottom' content "
                    "({\"title\": [[text, color, size]], \"label\": ...} or {\"img\": mockup}) or use another layout.")
            bg = sh.get("bg")
            if bg is not None:
                if not isinstance(bg, dict) or not (bg.get("mock") or bg.get("img")):
                    die(f"shot at {sh['_t']:.2f}s: bg must be {{\"mock\": name}} or {{\"img\": path}}: a background has to "
                        "show something the viewer needs (the screen being talked about, a profile, a result)")
                if not bg.get("why"):
                    die(f"shot at {sh['_t']:.2f}s: bg needs a \"why\" (what the background shows the viewer and why now)")
        self.need_mask = any(sh.get("bg") for sh in self.shots) or bool(self.style["grade"].get("segment"))

    def plan_transitions(self):
        TS = self.style.get("transitions", {}); default = TS.get("default", "cut"); pools = TS.get("pools", {})
        avoid = TS.get("avoid_last", 3); used = []; self.trans = []
        def group(sh): return "overlay" if sh["lay"] in OVERLAY_LAYS else "face"
        for i in range(1, len(self.shots)):
            a, b = self.shots[i - 1], self.shots[i]
            spec = b.get("tr", default); spec = {"name": spec} if isinstance(spec, str) else dict(spec)
            name = spec.get("name", "cut")
            short = min(b["_t"] - a["_t"], b["_end"] - b["_t"]) < TS.get("min_shot", 0.9)
            if name == "auto" and short: name = "cut"     # two transitions half a second apart read as noise
            if name == "auto":
                ctx = f"{group(a)}>{group(b)}"; hot = b.get("drop") or b.get("smash")
                pool = pools.get(ctx + ":drop") if hot and pools.get(ctx + ":drop") else pools.get(ctx, pools.get("any", ["cut"]))
                pool = [n for n in pool if n in fx.TRANSITIONS]
                cand = [n for n in pool if n not in used[-avoid:]] or pool
                name = self.rng.choice(cand) if cand else "cut"
            if name not in fx.TRANSITIONS: die(f"unknown transition {name}; have: {', '.join(fx.TRANSITIONS)}")
            used.append(name)
            if name == "cut": continue
            d = min(spec.get("d", fx.TRANSITIONS[name][1]), 0.8 * (b["_t"] - a["_t"]), 0.8 * (b["_end"] - b["_t"]))
            opts = {k: v for k, v in spec.items() if k not in ("name", "d")}
            k_same = sum(1 for x in self.trans if x["name"] == name)
            if name == "whip": opts.setdefault("dir", ["l", "r", "u", "l", "d"][k_same % 5])
            elif name == "slide": opts.setdefault("dir", ["l", "r", "u"][k_same % 3])
            elif name == "wipe": opts.setdefault("dir", ["r", "l", "d"][k_same % 3])
            opts.setdefault("sgn", 1 if k_same % 2 == 0 else -1); opts.setdefault("seed", len(self.trans))
            self.trans.append({"t": b["_t"], "d": d, "name": name, "opts": opts, "a": a, "b": b}); b["_tr"] = name
            a["_exit_by_tr"] = True                      # the transition replaces the outgoing shot's exit animation

    def pick(self, pool_key, used, avoid=3):
        pool = self.style.get("variety", {}).get(pool_key, [])
        cand = [n for n in pool if n not in used[-avoid:]] or pool
        v = self.rng.choice(cand) if cand else None; used.append(v); return v

    def plan_variety(self):
        """Fill in animations the plan left open, rotating through the style's pools so the same move never repeats
        back to back. Explicit choices in the plan always win."""
        u_in, u_out, t_in, t_out, b_in = [], [], [], [], []
        # the camera always moves, subtly: face shots without a `push` alternate a slow push-in
        # and a slow pull-out, so no shot sits still and no two face shots in a row move the same way
        k_face = 0; base = self.style.get("motion", {}).get("push", 0.03)
        for sh in self.shots:
            if sh["lay"] == "face" and "push" not in sh and not sh.get("smash"):
                sh["push"] = base if k_face % 2 == 0 else -base; k_face += 1
        for sh in self.shots:
            if sh["lay"] == "phone3d":
                if "enter_anim" not in sh: sh["enter_anim"] = self.pick("phone_in", u_in) or "rise"
                if "exit_anim" not in sh: sh["exit_anim"] = self.pick("phone_out", u_out) or "sink"
            if sh.get("bg") and "in" not in sh["bg"]: sh["bg"] = {**sh["bg"], "in": self.pick("bg_in", b_in) or "fade"}
        titles = sorted([st for st in self.stickers if st["type"] in ("glow_title", "text")], key=lambda x: x["_t0"])
        for st in titles:
            if "anim" not in st: st["anim"] = self.pick("title_in", t_in) or ("flicker" if st["type"] == "glow_title" else "pop")
            if "out" not in st:
                follow = any(o is not st and abs(o["_t0"] - st["_t1"]) < 0.06 for o in self.stickers)
                st["out"] = "cut" if follow else (self.pick("title_out", t_out) or "fade")
        for pu in self.punches:
            if "anim" not in pu: pu["anim"] = self.pick("title_in", t_in) or "pop"

    # -------------------------------------------------- captions
    def section_at(self, t):
        cur = self.sections[0]
        for s in self.sections:
            if s[0] <= t + 1e-6: cur = s
        return cur

    def build_groups(self):
        cap = self.plan.get("captions", {})
        maxw = {"pop": 3, "box": 4, "serif": 4, "neon": 3, "word": 1, "cine": self.style["captions"].get("max_words", 4),
                **cap.get("max_words", {})}
        self.keywords = {norm(k) for k in cap.get("keywords", [])}
        groups, cur = [], None
        breaks = set()
        # punches (unless keep_captions) and stickers with hide_captions replace the captions while they show
        self.cap_blocks = [p for p in self.punches if not p.get("keep_captions")] + [s for s in self.stickers if s.get("hide_captions")]
        for p in self.parts:
            for v in p["spec"].get("cap_breaks", []): breaks.add(round(self.T(p, v), 3))
        prev_end, prev_raw = None, "."
        for clean, raw, a, b in self.words:
            sec = self.section_at(a)
            gap = (a - prev_end) if prev_end is not None else 0
            sent = prev_raw.endswith((".", "?", "!", ":"))
            prev_end, prev_raw = b, raw
            if sec[1] is None or any(p["_t0"] - 0.01 <= a < p["_t1"] for p in self.cap_blocks):
                cur = None; continue
            if (cur is None or cur["sec"] != sec or len(cur["w"]) >= maxw.get(sec[1], 3) or cur["brk"]
                    or gap > 0.35 or round(a, 3) in breaks):
                cur = {"sec": sec, "w": [], "brk": False, "cap": sent}; groups.append(cur)
            cur["w"].append((clean, a, b)); cur["brk"] = raw.endswith((".", ",", "?", "!"))
        for g in groups: g["t0"] = g["w"][0][1]
        for i, g in enumerate(groups):
            nxt = groups[i + 1]["t0"] if i + 1 < len(groups) else self.dur
            g["t1"] = min(nxt, g["w"][-1][2] + 0.6)
            for p in self.cap_blocks:
                if g["t0"] < p["_t0"] < g["t1"]: g["t1"] = p["_t0"]
            for s in self.sections:
                if g["t0"] < s[0] < g["t1"]: g["t1"] = s[0]
        self.groups = groups

    # -------------------------------------------------- automatic sound design
    def auto_sfx(self):
        """Every visual event gets a sound from the style's table (event kind -> [[sound spec, dt, dB], ...]).
        self.visual records each event, so QA can find anything that moves in silence."""
        raw, self.visual = [], []
        auto_on = {p["name"]: p["spec"].get("auto_sfx", True) for p in self.parts}
        def on(t):
            for p in self.parts:
                if p["off"] - 1e-6 <= t < p["off"] + p["dur"] + 1e-6: return auto_on[p["name"]]
            return True
        tab = self.style["sfx"]
        def put(kind, t, key=None, span=None):
            for name, dt, db in tab.get(kind, []): raw.append([t + dt, name, db, key or kind] + ([span] if span else []))
            return kind in tab                     # a key the style leaves empty is silent on purpose, not missing
        def vis(kind, t, silent=False, sounded=True): self.visual.append({"t": round(t, 3), "kind": kind, "silent": silent, "sound": sounded})
        def cat(c, t, db=0, key=None, span=None): raw.append([t, "cat:" + c, db, key or c] + ([span] if span else [])); return True
        drops = sorted(self.drops)
        for tr in self.trans:
            t = tr["t"]; name = tr["name"]
            if not on(t): vis("tr:" + name, t, silent=True); continue
            if any(abs(t - d) < 0.15 for d in drops): vis("tr:" + name, t, sounded=True); continue   # the drop's hit covers it
            tspan = tr.get("d", 0.3) * 0.5 + 0.12          # the window is centred on the cut: sound ends just after it
            if ("tr:" + name) in tab: ok = put("tr:" + name, t, span=tspan)
            elif "tr" in tab: ok = put("tr", t, key="tr:" + name, span=tspan)   # sound rules: every transition = the whoosh
            elif fx.TRANSITIONS[name][2]: ok = cat("|".join(fx.TRANSITIONS[name][2]), t, 0, "tr:" + name, span=tspan)
            else: ok = False
            vis("tr:" + name, t, sounded=ok)
        for sh in self.shots:
            t = sh["_t"]
            if sh.get("sfx") is False or not on(t): vis("shot:" + sh["lay"], t, silent=True); continue
            via_tr = bool(sh.get("_tr"))
            if sh["lay"] == "phone3d":
                k = f"phone_in:{sh.get('enter_anim', 'rise')}"
                if not via_tr or sh.get("enter_anim") in ("drop", "far"):
                    land = t + sh.get("enter", 0.45) if sh.get("enter_anim") in ("drop",) else t
                    ok = put(k, land) if k in tab else put("overlay_enter_soft" if not sh.get("enter", 0) else "overlay_enter", t)
                    vis(k, t, sounded=ok)
            elif sh["lay"] in OVERLAY_LAYS and sh.get("enter", 0):
                ok = put("overlay_enter", t)
                if sh["lay"] in ("fullpw", "video"): put("overlay_land", t)
                vis("overlay_enter", t, sounded=ok)
            elif sh["lay"] in OVERLAY_LAYS:
                vis("overlay_enter", t, sounded=put("overlay_enter_soft", t))
            if sh["lay"] == "letterbox" and not via_tr: vis("letterbox", t, sounded=put("letterbox", t))
            if sh.get("smash"): vis("smash", t, sounded=put("smash", t))
            if sh.get("settle") and not sh.get("drop") and not via_tr: vis("settle", t, sounded=put("reveal", t))
            if sh.get("bg") and not via_tr:
                prev = [x for x in self.shots if x["_end"] == t]
                if not (prev and prev[0].get("bg") == sh["bg"]): vis("bg_in", t, sounded=put("bg_in:" + sh["bg"].get("in", "fade"), t) or put("bg_in", t))
            ex = sh.get("exit", 0) if not sh.get("_exit_by_tr") else 0
            if ex and sh["lay"] == "phone3d":
                k = f"phone_out:{sh.get('exit_anim', 'sink')}"
                vis(k, sh["_end"] - ex, sounded=put(k, sh["_end"] - ex) if k in tab else put("overlay_exit", sh["_end"] - ex))
            elif ex: vis("overlay_exit", sh["_end"] - ex, sounded=put("overlay_exit", sh["_end"] - ex))
            for ts, _ in sh["_swaps"]:   # swap_sfx false: a riser or montage sound already carries rapid swaps
                vis("swap", ts, sounded=put("swap", ts) if sh.get("swap_sfx", True) else True)
        for d in drops:
            if on(d): vis("drop", d, sounded=put("drop", d))
        for p in self.punches:
            if p.get("sfx") is False or not on(p["_t0"]): vis("punch", p["_t0"], silent=True); continue
            if isinstance(p.get("sfx"), str): raw.append([p["_t0"] - 0.02, p["sfx"], 0, "punch"]); vis("punch", p["_t0"]); continue
            if any(abs(p["_t0"] - d) < 0.15 for d in drops): vis("punch", p["_t0"]); continue
            if self.cine and p.get("anim") in fx.TITLE_SFX: vis("punch", p["_t0"], sounded=self.title_sfx(raw, p, p["_t0"], put, cat))
            else: vis("punch", p["_t0"], sounded=put("punch", p["_t0"]))
        snd = {"red_x": [("thud", 0), ("buzzer", 0.04)], "check": [("ding", 0)], "thought": [("pop", 0)],
               "review_card": [("pop", 0)], "emoji": [("pop", 0)], "banner": [("whoosh_short", 0)],
               "circle": [("tick", 0)], "arrow": [("whoosh_short", 0)], "counter": [("typing", 0)],
               "image": [("pop", 0)], "text": [("pop", 0)]}
        for st in self.stickers:
            typ = st["type"]; t0 = st["_t0"]
            if st.get("spotlight") and on(t0): vis("spotlight", t0, sounded=put("spotlight", t0))
            if st.get("sfx") is False or not on(t0): vis(typ, t0, silent=True); continue
            if isinstance(st.get("sfx"), str): raw.append([t0, st["sfx"], 0, typ]); vis(typ, t0); continue
            if typ in ("glow_title", "text") and self.cine and st.get("anim") in fx.TITLE_SFX:
                vis(typ, t0, sounded=self.title_sfx(raw, st, t0, put, cat)); continue
            if typ == "tap" and st.get("cta"):    # a button visibly clicked for the call to action: the only place the ding plays
                vis("cta", t0, sounded=put("cta", t0)); continue
            if typ == "icon":
                ok = put("icon", t0); put("icon_done", t0 + st.get("draw", 0.55)); vis(typ, t0, sounded=ok); continue
            if typ == "clip":                     # a pop-up graphic moves in and out: the whoosh both ways
                ok = put("overlay_enter", t0); vis(typ, t0, sounded=ok)
                vis("clip_out", st["_t1"] - 0.2, sounded=put("overlay_exit", st["_t1"] - 0.2)); continue
            if typ in tab:
                anim = {"hand_note": st.get("reveal", 0.6), "circle": 0.45, "icon": st.get("draw", 0.55)}.get(typ, 0.4)
                ok = put(typ, t0, span=min(max(0.2, anim), max(0.2, st["_t1"] - t0 if "_t1" in st else anim)))
            else:
                ok = bool(snd.get(typ))
                for name, dt in snd.get(typ, []): raw.append([t0 + dt, name, 0, typ])
            vis(typ, t0, sounded=ok)
            if typ == "counter":
                if "counter" in tab:                # the counting sound runs while the number runs
                    raw.append([t0, tab["counter"][0][0], -2, "counter", st.get("dur", 0.8)])
                if "counter_land" in tab: put("counter_land", t0 + st.get("dur", 0.8))
                else: raw.append([t0 + st.get("dur", 0.8), "shimmer" if not self.cine else "cine_shimmer", 0, "counter_land"])
            if typ == "chat_pill":
                n = len(st.get("text", "")); d0 = t0 + st.get("delay", 0.25); typing = n * st.get("cps", 0.09)
                if tab.get("chat_key"):             # one key per letter
                    key = tab["chat_key"][0]
                    for i in range(n): raw.append([d0 + i * st.get("cps", 0.09), key[0], key[2], "chat_key"])
                elif tab.get("chat_type"):          # one sound for the whole typing run (the pack's counting)
                    for name, dt, db in tab["chat_type"]: raw.append([d0 + dt, name, db, "chat_type", typing])
                put("chat_send", t0 + st.get("delay", 0.25) + n * st.get("cps", 0.09) + 0.15)
        for f in self.fx:
            if f.get("sfx") is False or not on(f["_t"]): vis("fx:" + f["type"], f["_t"], silent=True); continue
            k = "glitch" if f["type"] in ("rgb", "glitch") else f["type"]
            if f["type"] == "spotlight": vis("spotlight", f["_t"], sounded=put("spotlight", f["_t"])); continue
            if k in tab or "fx:" + k in tab: vis("fx:" + f["type"], f["_t"], sounded=put("fx:" + k if "fx:" + k in tab else k, f["_t"]))
            else: vis("fx:" + f["type"], f["_t"], sounded=False)
        raw += [[t, n, db, "plan"] for t, n, db in self.sfx]
        S = Sounds(self.plan.get("seed", 7)); evs = []
        for e in sorted(raw, key=lambda e: e[0]):
            t, spec, db, key = e[:4]
            span = e[4] if len(e) > 4 else cue_span(key)
            name = S.resolve(spec, max(0.0, t), key, span)
            if name: evs.append([round(max(0.0, t), 3), name, db, round(span, 3), cue_prio(key, name), str(key)])
        last, keep = {}, []        # one cue per kind of sound within 0.1 s (a tap on a swap is one click, not two)
        def role(n): return n[4:].rsplit("_", 1)[0].replace("click_mouse", "click").replace("click_ui", "click") if n.startswith("lib:") else n
        for e in sorted(evs):
            rl = role(e[1]); gap = 0.03 if rl in ("key", "tick", "type_key", "ui_tick") else 0.1   # typing and ticks are meant to be fast
            if e[0] - last.get(rl, -9) >= gap: keep.append(e); last[rl] = e[0]
        self.events = keep

    def title_sfx(self, raw, st, t0, put, cat):
        """Sounds that follow a title's animation: a key per typed letter, ticks while scrambling, a hit on landing."""
        anim = st.get("anim"); lines = st.get("lines", [])
        n = sum(len(str(ln[0]).replace(" ", "")) for ln in lines) or 6
        d = st.get("d_in") or fx.TITLE_D.get(anim) or min(0.9, n * 0.045)
        if anim == "type": d = st.get("d_in") or min(0.9, n * 0.045)
        tab = self.style["sfx"]
        if "title:" + anim in tab: return put("title:" + anim, t0)
        if "title" in tab:                       # sound rules: text appearing = the pop; typed text = typing
            if anim == "type":                   # one key press per letter, as each letter lands
                step = max(0.035, d / n); k = 0
                while k * step < d: cat("key", t0 + k * step, -2, "title:key"); k += 1
                return True
            return put("title", t0)
        for c, when in fx.TITLE_SFX.get(anim, []):
            if when == "start": cat(c, t0, -1, "title:" + c)
            elif when == "land": cat(c, t0 + d, 0, "title:" + c)
            elif when == "chars":
                step = max(0.035, d / n); k = 0
                while k * step < d: cat(c, t0 + k * step, -4 if c == "tick" else -2, "title:" + c); k += 1
        return bool(fx.TITLE_SFX.get(anim))

    def anchor(self, t):
        """Face centre (x, y) and face height in output pixels at time t: the smoothed head track when there is one
        (track.py), else the clip's single face position from ingest."""
        for p in self.parts:
            if p["off"] <= t < p["off"] + p["dur"] + 1e-6:
                lt = t - p["off"]
                for i, s in enumerate(p["segs"]):
                    if s["t0"] - 1e-6 <= lt < s["t1"] + 1e-6:
                        tr = p.get("track")
                        if tr and i < len(tr["segs"]) and tr["segs"][i][2]:
                            sm = tr["segs"][i][2]; ts = [x[0] for x in sm]
                            return tuple(float(np.interp(lt, ts, [x[k] for x in sm])) for k in (1, 2, 3))
                        return s["ax"], s["ay"], s["fh"]
        s = self.parts[-1]["segs"][-1]; return s["ax"], s["ay"], s["fh"]

    def trans_at(self, t):
        for tr in self.trans:
            if tr["t"] - tr["d"] / 2 <= t < tr["t"] + tr["d"] / 2: return tr
        return None

    def spot_at(self, t):
        """Spotlight dim at t: (how far into the dim 0..1, dim level)."""
        best = (0.0, 0.3)
        for a, b, lvl in self.spots:
            if a - 0.01 <= t < b:
                k = min(fx.ease_out(clamp((t - a) / 0.22), 2), fx.ease_in_out(clamp((b - t) / 0.28)))
                if k > best[0]: best = (k, lvl)
        return best

    def shot_at(self, t):
        cur = self.shots[0]
        for s in self.shots:
            if s["_t"] <= t + 1e-6: cur = s
        return cur


# ---------------------------------------------------------------- assets
class Assets:
    def __init__(self, reel): self.r = reel; self.streams = {}

    @lru_cache(None)
    def phone(self, name, width):
        p = self.r.mock / f"{name}.png"
        if not p.exists(): die(f"mockup {p} not found (render it with mockups.py)")
        im = Image.open(p).convert("RGBA")
        return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)

    @lru_cache(None)
    def frame_png(self, width):
        p = self.r.mock / "frame.png"
        if not p.exists(): die("video layout needs mock/frame.png (mockups.py ... frame)")
        im = Image.open(p).convert("RGBA")
        return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)

    @lru_cache(None)
    def screen(self, name):
        """The screen of a mockup without the phone around it (for backgrounds and letterbox bars)."""
        p = self.r.mock / f"{name}.png"
        if not p.exists(): die(f"mockup {p} not found (render it with mockups.py)")
        x, y, w, h, _ = SCREEN; return Image.open(p).convert("RGB").crop((x, y + 120, x + w, y + h - 40))

    @lru_cache(None)
    def bg_src(self, key):
        """Contextual background, prepared once: cover-fit with 12% spare for drift, then blur / saturation / dim."""
        spec = json.loads(key)
        if spec.get("mock"): im = self.screen(spec["mock"])
        else:
            pth = Path(spec["img"]).expanduser(); pth = pth if pth.is_absolute() else self.r.proj / pth
            if not pth.exists(): die(f"bg image {pth} not found")
            im = Image.open(pth).convert("RGB")
        k = max(W * 1.12 / im.width, H * 1.12 / im.height); im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
        if spec.get("blur", 0): im = im.filter(ImageFilter.GaussianBlur(spec["blur"]))
        im = ImageEnhance.Color(im).enhance(spec.get("sat", 0.85))
        return ImageEnhance.Brightness(im).enhance(spec.get("dim", 0.42))

    @lru_cache(None)
    def screen_mask(self, w, h, r):
        m = Image.new("L", (w * 2, h * 2), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], r * 2, fill=255)
        return m.resize((w, h), Image.LANCZOS)

    def stream_frame(self, sh, t, size):
        """Sequential reader for b-roll / screen recordings; one ffmpeg pipe per shot."""
        key = id(sh)
        w, h = size
        if key not in self.streams:
            src = Path(sh["src"]).expanduser()
            if not src.is_absolute(): src = self.r.proj / src
            if not src.exists(): die(f"b-roll {src} not found")
            vf = f"fps={FPS},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            proc = subprocess.Popen(["ffmpeg", "-v", "quiet", "-ss", str(sh.get("src_in", 0)), "-i", str(src), "-vf", vf,
                                     "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.streams[key] = {"p": proc, "n": -1, "last": Image.new("RGB", (w, h))}
        s = self.streams[key]
        want = int((t - sh["_t"]) * FPS * sh.get("speed", 1.0))
        while s["n"] < want:
            buf = s["p"].stdout.read(w * h * 3)
            if len(buf) < w * h * 3: break        # source ran out: hold the last frame
            s["last"] = Image.frombytes("RGB", (w, h), buf); s["n"] += 1
        return s["last"]


# ---------------------------------------------------------------- caption rendering
class Captions:
    def __init__(self, reel): self.r = reel

    @lru_cache(None)
    def render(self, gi, active, k=3):
        g = self.r.groups[gi]; style, accent = g["sec"][1], g["sec"][2]
        kws = self.r.keywords
        words = [w for w, _, _ in g["w"]]
        if style == "cine":
            return self.cine(tuple(re.sub('["“”]', "", w).upper() for w in words[:active + 1]),
                             tuple(norm(w) in kws for w in words[:active + 1]), accent,
                             self.r.style["captions"].get("size", 84), last_k=k)
        if style in ("pop", "word"):
            f = font("black", 96) if style == "pop" else font("cblack", 190)
            words = [w.upper() for w in words]; sp, stroke = 26, (10 if style == "pop" else 12)
        elif style == "box":
            f = font("heavy", 70); sp, stroke = 20, 0
            words = [w[:1].upper() + w[1:] if i == 0 and g.get("cap") else w for i, w in enumerate(words)]
        elif style == "neon":
            f = font("black", 92); sp, stroke = 24, 0; words = [w.upper() for w in words]
        else:
            f = font("serif", 88); sp, stroke = 24, 0
        widths = [f.getbbox(w, stroke_width=stroke)[2] - f.getbbox(w, stroke_width=stroke)[0] for w in words]
        asc, desc = f.getmetrics(); lh = asc + desc
        lines, line, lw = [], [], 0
        for i, wd in enumerate(widths):
            add = wd + (sp if line else 0)
            if line and lw + add > 900: lines.append(line); line, lw = [], 0; add = wd
            line.append(i); lw += add
        lines.append(line)
        padx, pady = (34, 18) if style == "box" else (30, 20)
        lws = [sum(widths[i] for i in ln) + sp * (len(ln) - 1) for ln in lines]
        cw = max(lws) + padx * 2 + 60; ch = len(lines) * (lh + 10) + pady * 2 + 60
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
        if style == "box":
            for li, ln in enumerate(lines):
                y0 = 30 + li * (lh + 10); x0 = (cw - lws[li]) // 2 - padx
                d.rounded_rectangle([x0, y0, x0 + lws[li] + padx * 2, y0 + lh + pady], radius=22, fill=(255, 255, 255, 250))
        for li, ln in enumerate(lines):
            x = (cw - lws[li]) // 2; y = 30 + li * (lh + 10) + (pady // 2 if style == "box" else 0)
            for i in ln:
                w = words[i]; hot = i == active or (norm(w) in kws and i <= active)
                if style in ("pop", "word"):
                    col = hexc(accent) if (hot or style == "word" and norm(w) in kws) else (255, 255, 255, 255)
                    d.text((x, y), w, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                elif style == "box":
                    if hot:
                        d.rounded_rectangle([x - 10, y - 4, x + widths[i] + 10, y + lh - 2], radius=14, fill=hexc(accent))
                        d.text((x, y), w, font=f, fill=(255, 255, 255, 255))
                    else:
                        d.text((x, y), w, font=f, fill=(17, 17, 17, 255))
                elif style == "neon":
                    col = hexc(accent)
                    gd.text((x, y), w, font=f, fill=col if hot else (*col[:3], 120))
                    d.text((x, y), w, font=f, fill=(255, 255, 255, 255) if not hot else col)
                else:
                    gd.text((x + 3, y + 5), w, font=f, fill=(0, 0, 0, 200))
                    d.text((x, y), w, font=f, fill=hexc(accent) if hot else (255, 255, 255, 255))
                x += widths[i] + sp
        if style in ("neon", "serif"):
            glow = glow.filter(ImageFilter.GaussianBlur(10 if style == "neon" else 7))
            if style == "neon": glow.alpha_composite(glow)
            glow.alpha_composite(im); im = glow
        return im

    @staticmethod
    @lru_cache(None)
    def cine(words, hot, accent, size, maxw=930, last_k=3):
        """Heavy wide caps, white with a slight top-to-bottom falloff, soft shadow, keywords in the accent with a
        neon bloom. Only the words said so far are passed in, so the line builds word by word and re-centres; the
        newest word pops in over 3 frames (last_k 0..3: 82% -> 100%, fading up; growing from smaller, because growing past 100% crowds the next word)."""
        f = font("xblack", size); sp = int(size * 0.28)
        wd = [f.getbbox(w)[2] - f.getbbox(w)[0] for w in words]
        lines, cur, lw = [], [], 0
        for i, x in enumerate(wd):
            add = x + (sp if cur else 0)
            if cur and lw + add > maxw: lines.append(cur); cur, lw = [], 0; add = x
            cur.append(i); lw += add
        lines.append(cur)
        lh = int(size * 1.06)
        lws = [sum(wd[i] for i in ln) + sp * (len(ln) - 1) for ln in lines]
        pad = 90; cw = max(lws) + pad * 2; ch = lh * len(lines) + pad * 2
        txt = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
        glow = Image.new("L", (cw, ch), 0); gd = ImageDraw.Draw(glow)
        ac = hexc(accent); last = len(words) - 1
        sc, al = [0.82, 0.93, 0.99, 1.0][last_k], [0.45, 0.8, 0.95, 1.0][last_k]
        for li, ln in enumerate(lines):
            x = (cw - lws[li]) // 2; y = pad + li * lh - int(size * 0.12)
            for i in ln:
                col = fx.hot_core(ac, 0.18) if hot[i] else (255, 255, 255, 255)
                if i == last and last_k < 3:            # the newest word pops in
                    fw = font("xblack", int(size * sc)); bw = fw.getbbox(words[i])
                    wi = Image.new("RGBA", (bw[2] + 20, bw[3] + 20), (0, 0, 0, 0))
                    ImageDraw.Draw(wi).text((10 - bw[0], 10), words[i], font=fw, fill=(*col[:3], int(255 * al)))
                    cxw = x + wd[i] / 2; cyw = y + f.getbbox(words[i])[1] + (f.getbbox(words[i])[3] - f.getbbox(words[i])[1]) / 2
                    txt.alpha_composite(wi, (int(cxw - (bw[2] - bw[0]) / 2 - 10), int(cyw - (bw[1] + bw[3]) / 2 - 10)))
                else:
                    d.text((x, y), words[i], font=f, fill=col)
                    if hot[i]: gd.text((x, y), words[i], font=f, fill=255)
                x += wd[i] + sp
        # top-to-bottom falloff inside each line (metallic white), applied to RGB only
        grad = Image.new("L", (1, ch), 255)
        for y in range(ch):
            k = ((y - pad) % lh) / lh if y >= pad else 0
            grad.putpixel((0, y), int(255 - 50 * clamp(k)))
        grad = grad.resize((cw, ch))
        r_, g_, b_, a_ = txt.split()
        txt = Image.merge("RGBA", [ImageChops.multiply(c, grad) for c in (r_, g_, b_)] + [a_])
        out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        halo = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); halo.paste((0, 0, 0, 120), (0, 0), a_)
        out.alpha_composite(halo.filter(ImageFilter.GaussianBlur(34)))
        sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); sh.paste((0, 0, 0, 215), (0, 0), a_)
        out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (0, 5))
        if any(hot[:last] if last_k < 3 else hot): out.alpha_composite(fx.bloom(glow, ac, 0.9))
        out.alpha_composite(txt)
        return out

    @lru_cache(None)
    def punch(self, key):
        lines, rot = json.loads(key)
        if self.r.cine:
            im = glow_lines(tuple(tuple(l) for l in lines), rot); bb = im.getbbox() or (0, 0, im.width, im.height)
            k = 1000 / max(1, bb[2] - bb[0])
            return im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS) if k < 1 else im
        rendered = []
        for text, kind, size, col in lines:
            f = font(kind, size); st = max(6, size // 22)
            bb = f.getbbox(text, stroke_width=st)
            li = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
            ImageDraw.Draw(li).text((10 - bb[0], 10 - bb[1]), text, font=f, fill=hexc(col), stroke_width=st,
                                    stroke_fill=(0, 0, 0, 255))
            rendered.append(li)
        w = max(r.width for r in rendered); h = sum(r.height for r in rendered) - 10 * (len(rendered) - 1)
        im = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0)); y = 30
        for r in rendered:
            im.alpha_composite(r, ((im.width - r.width) // 2, y)); y += r.height - 10
        return shadowed(im).rotate(rot, resample=Image.BICUBIC, expand=True)


@lru_cache(None)
def backing(w, h):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=min(28, h // 3), fill=(0, 0, 0, 150))
    return im


# ---------------------------------------------------------------- stickers
@lru_cache(None)
def red_x(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); m = int(size * 0.135)
    for wdt, col in [(int(size * 0.21), (255, 255, 255, 255)), (int(size * 0.15), hexc("#FF3B30"))]:
        d.line([m, m, size - m, size - m], fill=col, width=wdt); d.line([size - m, m, m, size - m], fill=col, width=wdt)
    return shadowed(im, 14, 140, 10)


@lru_cache(None)
def check(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    pts = [(size * 0.16, size * 0.55), (size * 0.40, size * 0.78), (size * 0.86, size * 0.24)]
    for wdt, col in [(int(size * 0.20), (255, 255, 255, 255)), (int(size * 0.14), hexc("#34C759"))]:
        d.line(pts, fill=col, width=wdt, joint="curve")
    return shadowed(im, 14, 140, 10)


def star_poly(cx, cy, r):
    return [(cx + (r if k % 2 == 0 else r * 0.45) * math.cos(-math.pi / 2 + k * math.pi / 5),
             cy + (r if k % 2 == 0 else r * 0.45) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]


@lru_cache(None)
def thought(text, side):
    f = font("semibold", 58); bb = f.getbbox(text); tw = bb[2] - bb[0]
    pw, ph = tw + 76, 58 + 64
    im = Image.new("RGBA", (pw + 40, ph + 50), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x0, y0 = 20, 10
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph // 2, fill=(233, 233, 235, 255))
    tx = x0 + 34 if side == "l" else x0 + pw - 34; dx = -14 if side == "l" else 14
    d.ellipse([tx - 14, y0 + ph + 4, tx + 14, y0 + ph + 30], fill=(233, 233, 235, 255))
    d.ellipse([tx - 6 + dx, y0 + ph + 34, tx + 6 + dx, y0 + ph + 46], fill=(233, 233, 235, 255))
    d.text((x0 + 38 - bb[0], y0 + 32 - bb[1]), text, font=f, fill=(20, 20, 20, 255))
    return shadowed(im, 10, 120, 6)


@lru_cache(None)
def review_card(lines, name, src, nstars):
    fq = font("serif", 50); lh = 64
    cw = 900; chh = 150 + lh * len(lines) + 60
    im = Image.new("RGBA", (cw + 40, chh + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 14, 20 + cw, 14 + chh], radius=40, fill=(255, 255, 255, 255))
    for k in range(5):
        d.polygon(star_poly(80 + k * 66, 76, 30), fill=hexc("#F5A623") if k < nstars else (225, 225, 225, 255))
    d.text((440, 54), src, font=font("semibold", 36), fill=(140, 140, 140, 255))
    for i, l in enumerate(lines): d.text((56, 128 + i * lh), l, font=fq, fill=(20, 20, 20, 255))
    d.text((56, 128 + len(lines) * lh + 12), name, font=font("bold", 34), fill=(120, 120, 120, 255))
    return shadowed(im, 14, 120, 8)


@lru_cache(None)
def emoji(ch, size):
    f = ImageFont.truetype(EMOJI, 160)
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0)); ImageDraw.Draw(im).text((20, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox() or (0, 0, 200, 200))
    return shadowed(im.resize((size, round(im.height * size / im.width)), Image.LANCZOS), 8, 110, 6)


@lru_cache(None)
def banner(text, bg, fg, size):
    f = font("heavy", size); bb = f.getbbox(text); tw, th = bb[2] - bb[0], bb[3] - bb[1]
    im = Image.new("RGBA", (tw + 90, th + 70), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, tw + 80, th + 60], radius=(th + 50) // 2, fill=hexc(bg))
    d.text((45 - bb[0], 35 - bb[1]), text, font=f, fill=hexc(fg))
    return shadowed(im, 12, 130, 8)


# ---------------------------------------------------------------- cinematic-style stickers
def _glow_from(alpha, col, blur, strength=255):
    g = Image.new("RGBA", alpha.size, (0, 0, 0, 0)); g.paste((*col[:3], strength), (0, 0), alpha)
    return g.filter(ImageFilter.GaussianBlur(blur))


def _line_img(text, kind, size, col, n=None):
    """One title line on a canvas sized for the whole text; with n, only the first n non-space characters are
    drawn (in place), so typing on never re-centres the line."""
    f = font(kind, size); bb = f.getbbox(text)
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * size // 2, bb[3] - bb[1] + size), (0, 0, 0, 0))
    shown = text
    if n is not None:
        k = 0; shown = ""
        for ch in text:
            if ch != " ":
                if k >= n: break
                k += 1
            shown += ch
    if shown: ImageDraw.Draw(im).text((size // 2 - bb[0], size // 2 - bb[1]), shown, font=f, fill=col)
    return im


@lru_cache(None)
def glow_lines(lines, rot=0, frame_first=False, label=None, label_n=None, accent=None, shown=None):
    """Stacked title lines, no outline: coloured lines are lit neon (a whitened hot core inside a three-layer bloom
    of their colour), white lines get a soft shadow and a faint bloom of the accent.
    lines: ((text, kind, size, '#hex'), ...). Optional small label above (typed on: label_n chars shown) and a
    neon frame around the first coloured line. shown = non-space characters visible (typewriter), None = all."""
    parts = []; left = shown
    if label:
        parts.append(("label", _line_img(label[:label_n if label_n is not None else len(label)] or " ", "xblack", 44, (255, 255, 255, 255))))
    for text, kind, size, col in lines:
        c = hexc(col); white = c[0] > 230 and c[1] > 230 and c[2] > 230; n = None
        if left is not None: cnt = len(text.replace(" ", "")); n = min(cnt, left); left -= n
        parts.append(("line", _line_img(text, kind, size, c if white else fx.hot_core(c, 0.28), n), c, white))
    w = max(p[1].width for p in parts) + 160; gap = -26
    h = sum(p[1].height for p in parts) + gap * (len(parts) - 1) + 160
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0)); y = 80; first_box = None; first_white = True
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0)); glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for p in parts:
        im = p[1]; x = (w - im.width) // 2
        layer.alpha_composite(im, (x, y))
        if p[0] == "line":
            col, white = p[2], p[3]; a = Image.new("L", (w, h), 0); a.paste(im.getchannel("A"), (x, y))
            gc = hexc(accent) if (white and accent) else col
            if not white or accent: glow.alpha_composite(fx.bloom(a, gc, 0.4 if white else 1.0))
            bb = im.getbbox()
            if bb and (first_box is None or (first_white and not white)):
                first_box = (x + bb[0] - 26, y + bb[1] - 16, x + bb[2] + 26, y + bb[3] + 16); first_col = col
                first_white = white
        y += im.height + gap
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0)); sh.paste((0, 0, 0, 200), (0, 0), layer.getchannel("A"))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)), (0, 6))
    out.alpha_composite(glow)
    if frame_first and first_box:
        fr = Image.new("L", (w, h), 0); ImageDraw.Draw(fr).rectangle(first_box, outline=255, width=5)
        out.alpha_composite(fx.bloom(fr, first_col, 0.9))
        core = Image.new("RGBA", (w, h), fx.hot_core(first_col, 0.35)); core.putalpha(fr); out.alpha_composite(core)
    out.alpha_composite(layer)
    return out.rotate(rot, resample=Image.BICUBIC, expand=True) if rot else out


@lru_cache(None)
def hand_text(text, n, size):
    f = font("hand", size); words = text.split(" "); shown = " ".join(words[:n])
    bb = f.getbbox(text)
    im = Image.new("RGBA", (bb[2] - bb[0] + 60, bb[3] - bb[1] + 60), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((30 - bb[0], 30 - bb[1]), shown, font=f, fill=(255, 255, 255, 255))
    return shadowed(im, 8, 200, 3)


def draw_curve_arrow(out, p0, p1, bend, u, col=(255, 255, 255, 255), width=7):
    """Hand-drawn curved arrow from p0 to p1, drawn on (u 0..1). bend: control-point offset as a fraction of length."""
    u = ease_out_cubic(clamp(u))
    if u <= 0: return
    (x0, y0), (x1, y1) = p0, p1; mx, my = (x0 + x1) / 2, (y0 + y1) / 2; L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / (L + 1e-6), (x1 - x0) / (L + 1e-6); cx, cy = mx + nx * bend * L, my + ny * bend * L
    pts = [((1 - s) ** 2 * x0 + 2 * (1 - s) * s * cx + s ** 2 * x1, (1 - s) ** 2 * y0 + 2 * (1 - s) * s * cy + s ** 2 * y1)
           for s in [k / 40 * u for k in range(41)]]
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    d.line(pts, fill=col, width=width, joint="curve")
    if u > 0.85:
        (ax, ay), (bx, by) = pts[-3], pts[-1]; ang = math.atan2(by - ay, bx - ax)
        for s in (-1, 1): d.line([(bx, by), (bx - 34 * math.cos(ang + s * 0.55), by - 34 * math.sin(ang + s * 0.55))], fill=col, width=width)
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 170), (0, 0), layer.getchannel("A"))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)), (0, 3)); out.alpha_composite(layer)


@lru_cache(None)
def notify_card(app, title, body, color):
    """A generic dark lock-screen notification (own design, fictional app)."""
    cw, chh = 980, 196
    im = Image.new("RGBA", (cw + 40, chh + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 14, 20 + cw, 14 + chh], radius=46, fill=(38, 38, 44, 238))
    ic = Image.new("RGBA", (96, 96), (0, 0, 0, 0)); ImageDraw.Draw(ic).rounded_rectangle([0, 0, 95, 95], radius=24, fill=hexc(color))
    ImageDraw.Draw(ic).text((48, 50), app[:1].upper(), font=font("heavy", 54), fill=(255, 255, 255, 255), anchor="mm")
    im.alpha_composite(ic, (50, 14 + (chh - 96) // 2))
    d.text((172, 40), app.upper(), font=font("semibold", 30), fill=(170, 170, 178, 255))
    d.text((cw - 20, 40), "now", font=font("regular", 30), fill=(150, 150, 158, 255), anchor="ra")
    d.text((172, 82), title, font=font("bold", 40), fill=(255, 255, 255, 255))
    d.text((172, 134), body, font=font("regular", 36), fill=(214, 214, 220, 255))
    return shadowed(im, 18, 160, 10)


@lru_cache(None)
def chat_pill_base(width=880):
    h = 118; im = Image.new("RGBA", (width + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 20, 20 + width, 20 + h], radius=h // 2, fill=(28, 28, 34, 225), outline=(255, 255, 255, 40), width=2)
    bx = 20 + width - h // 2 - 4; by = 20 + h // 2
    d.ellipse([bx - 44, by - 44, bx + 44, by + 44], fill=hexc("#6B5CFF"))
    d.line([(bx, by + 22), (bx, by - 20)], fill=(255, 255, 255, 255), width=8)
    d.line([(bx - 18, by - 2), (bx, by - 22), (bx + 18, by - 2)], fill=(255, 255, 255, 255), width=8, joint="curve")
    return shadowed(im, 16, 150, 8)


@lru_cache(None)
def tap_dot(size=96):
    """Glowing blue touch indicator."""
    s = size * 3; im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = s // 2
    d.ellipse([c - size * 0.62, c - size * 0.62, c + size * 0.62, c + size * 0.62], fill=(70, 140, 255, 255))
    glow = im.filter(ImageFilter.GaussianBlur(size * 0.35))
    core = Image.new("RGBA", (s, s), (0, 0, 0, 0)); cd = ImageDraw.Draw(core)
    cd.ellipse([c - size * 0.5, c - size * 0.5, c + size * 0.5, c + size * 0.5], fill=(90, 160, 255, 235))
    cd.ellipse([c - size * 0.3, c - size * 0.3, c + size * 0.3, c + size * 0.3], fill=(190, 220, 255, 240))
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0)); out.alpha_composite(glow); out.alpha_composite(glow); out.alpha_composite(core)
    return out


def draw_circle(out, cx, cy, w, h, col, u):
    """Hand-drawn ellipse that draws itself on (u: 0..1)."""
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    n = 60; end = int(n * 1.12 * clamp(u))
    pts = []
    for k in range(end + 1):
        a = -math.pi * 0.6 + 2 * math.pi * 1.12 * k / n
        wob = 1 + 0.03 * math.sin(k * 0.9)
        pts.append((cx + w / 2 * wob * math.cos(a), cy + h / 2 * wob * math.sin(a)))
    if len(pts) > 1:
        d.line(pts, fill=(255, 255, 255, 255), width=20, joint="curve"); d.line(pts, fill=hexc(col), width=12, joint="curve")
    out.alpha_composite(layer)


def draw_arrow(out, x1, y1, x2, y2, col, u):
    u = ease_out_cubic(clamp(u)); xe, ye = lerp(x1, x2, u), lerp(y1, y2, u)
    d = ImageDraw.Draw(out); ang = math.atan2(ye - y1, xe - x1)
    for wdt, c in [(26, (255, 255, 255, 255)), (16, hexc(col))]:
        d.line([(x1, y1), (xe, ye)], fill=c, width=wdt)
        if u > 0.6:
            L = 60 + (wdt - 16)
            for s in (-1, 1):
                d.line([(xe, ye), (xe - L * math.cos(ang + s * 0.5), ye - L * math.sin(ang + s * 0.5))], fill=c, width=wdt)


# ---------------------------------------------------------------- layouts
@lru_cache(None)
def panel_bg():
    im = Image.new("RGB", (W, 960)); d = ImageDraw.Draw(im)
    for y in range(960): c = int(18 + 14 * y / 960); d.line([0, y, W, y], fill=(c, c, c + 6))
    return im.convert("RGBA")


@lru_cache(None)
def circle_mask(s):
    m = Image.new("L", (s * 3, s * 3), 0); ImageDraw.Draw(m).ellipse([0, 0, s * 3 - 1, s * 3 - 1], fill=255)
    return m.resize((s, s), Image.LANCZOS)


def zoom_crop(fr, cx, cy, z, ow, oh):
    cw, ch = ow / z, oh / z
    x0 = clamp(cx - cw / 2, 0, W - cw); y0 = clamp(cy - ch / 2, 0, H - ch)
    return fr.resize((ow, oh), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def blurred_bg(fr, dark=0.6):
    bg = fr.resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
    return Image.blend(bg, Image.new("RGB", (W, H), (10, 10, 12)), dark).convert("RGBA")


def face_bubble(out, fr, ax, ay, fh, x, y, s=260):
    # an int (Pillow's resize needs integer sizes), and at most W so the crop box (win^2 / W) stays inside the frame
    win = int(min(W, max(560, fh * 2.0))) if fh else 700
    face = zoom_crop(fr, ax, ay, W / win, win, win).resize((s, s), Image.BICUBIC)
    ring = Image.new("RGBA", (s + 16, s + 16), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([0, 0, s + 15, s + 15], fill=(255, 255, 255, 255))
    out.alpha_composite(ring, (x - 8, y - 8)); out.paste(face, (x, y), circle_mask(s))


# ---------------------------------------------------------------- cinematic grade (dark set)
@lru_cache(None)
def mask_lut(lo=0.66, hi=0.96):
    """Vision gives posters and drawn figures on the wall ~0.5-0.75 and the person ~1.0: keep only what it is sure of."""
    return [int(255 * (lambda x: x * x * (3 - 2 * x))(clamp((v / 255 - lo) / (hi - lo)))) for v in range(256)]


class Grader:
    """tone(): the default, a whole-frame grade of the real room. relight() (grade.segment, only when asked
    for a dark set) relights a talking-head frame into a dark set: the person (Vision mask) stays, slightly warmer and more
    contrasty with a highlight roll-off and a light fall-off down the body; the room becomes a dark, blurred,
    desaturated backdrop with a soft warm light pool behind the head. Vignette + grain are screen-space (finish)."""

    def __init__(self, g):
        self.g = g; self.cache = {}; self.t = 0.0; self.set = bool(g.get("segment"))
        c, warm, k = g.get("subject_contrast", 1.1), g.get("subject_warm", 0.03), g.get("highlight_rolloff", 0.82)
        def tone(v, mul):
            x = (v / 255 - 0.45) * c + 0.45
            if x > k: x = k + (1 - k) * (1 - math.exp(-(x - k) / (1 - k))) * 0.9
            return int(clamp(x * mul) * 255)
        self.lut_subj = [tone(v, 1 + warm) for v in range(256)] + [tone(v, 1.0) for v in range(256)] + [tone(v, 1 - warm) for v in range(256)]
        # Vision gives half-confidence (~0.5-0.75) to people-like things on the wall (posters, art); a smoothstep
        # from 0.66 to 0.96 drops them while the person (~1.0) and most of the hair edge stay
        lo, hi = g.get("mask_lo", 0.66), g.get("mask_hi", 0.96)
        self.lut_mask = [int(255 * (lambda x: x * x * (3 - 2 * x))(clamp((v / 255 - lo) / (hi - lo)))) for v in range(256)]
        tint, dark = g.get("bg_tint", [1, 1, 1]), g.get("bg_dark", 0.2)
        self.lut_bg = sum(([int(clamp(v / 255 * dark * tint[ch]) * 255) for v in range(256)] for ch in range(3)), [])
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.46) / (H * 0.62)) ** 2)
        v = 1 - g.get("vignette", 0.5) * np.clip(r - 0.35, 0, 1) ** 1.6
        self.vig = Image.fromarray((np.clip(v, 0, 1) * 255).astype(np.uint8)).convert("RGB")
        rng = np.random.default_rng(3); amp = g.get("grain", 4.0)
        self.grain = []
        for _ in range(6):
            n = rng.normal(0, amp, (H // 2, W // 2)).astype(np.float32)
            p = Image.fromarray(np.clip(n, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR).convert("RGB")
            m = Image.fromarray(np.clip(-n, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR).convert("RGB")
            self.grain.append((p, m))

    def pool(self, ax, ay):
        key = ("pool", int(ax // 24), int(ay // 24))
        if key not in self.cache:
            lp = self.g.get("light_pool", {}); col = lp.get("color", [255, 196, 140]); a = lp.get("alpha", 0.16); R = lp.get("radius", 0.62) * W
            yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
            k = np.exp(-(((xx - ax) ** 2 + (yy - ay) ** 2) / (R * R)))[..., None] * a * np.array(col, np.float32)
            self.cache[key] = Image.fromarray(np.clip(k, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        return self.cache[key]

    def falloff(self, chin):
        key = ("fall", int(chin // 8))
        if key not in self.cache:
            f = self.g.get("body_falloff", 0.42); y = np.arange(H, dtype=np.float32)
            col = 1 - f * np.clip((y - chin - 20) / 520, 0, 1) ** 0.8
            self.cache[key] = Image.fromarray((np.repeat(col[:, None], W, 1) * 255).astype(np.uint8)).convert("RGB")
        return self.cache[key]

    def bokeh(self, t):
        """Out-of-focus set lights: a few soft warm discs drifting slowly, behind the person only."""
        key = ("bokeh", int(t * 10))
        if key not in self.cache:
            if len(self.cache) > 400: self.cache = {k: v for k, v in self.cache.items() if k[0] != "bokeh"}
            b = self.g["bokeh"]; rng = np.random.default_rng(b.get("seed", 5))
            im = Image.new("RGB", (W // 4, H // 4)); d = ImageDraw.Draw(im)
            for i in range(b.get("count", 10)):
                x0, y0 = rng.uniform(0, W / 4), rng.uniform(0, H / 4 * 0.75); r = rng.uniform(8, 22)
                sp, ph = rng.uniform(1.5, 4.0), rng.uniform(0, 6.3)
                x = (x0 + sp * t) % (W / 4 + 40) - 20; y = y0 + 3 * math.sin(t * 0.4 + ph)
                col = [255, 170, 90] if rng.random() < 0.75 else [255, 225, 190]
                a = rng.uniform(0.35, 1.0) * b.get("alpha", 0.22) * (0.85 + 0.15 * math.sin(t * 1.3 + ph))
                d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(c * a) for c in col))
            self.cache[key] = im.filter(ImageFilter.GaussianBlur(2.5)).resize((W, H), Image.BILINEAR)
        return self.cache[key]

    def relight(self, fr, mask, ax, ay, fh):
        g = self.g
        small = fr.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(g.get("bg_blur", 7)))
        small = ImageEnhance.Color(small).enhance(g.get("bg_sat", 0.45))
        bg = small.resize((W, H), Image.BILINEAR).point(self.lut_bg)
        bg = ImageChops.add(bg, self.pool(ax, ay - 0.35 * (fh or 300)))
        if self.g.get("bokeh"): bg = ImageChops.add(bg, self.bokeh(self.t))
        subj = ImageChops.multiply(fr.point(self.lut_subj), self.falloff(ay + 0.5 * (fh or 300)))
        m = mask.point(self.lut_mask).filter(ImageFilter.GaussianBlur(1.2)).resize((W, H), Image.BILINEAR)
        return Image.composite(subj, bg, m)

    def tone(self, fr):
        """Whole-frame grade, the real room kept: contrast, a touch of warmth, highlight roll-off."""
        return fr.point(self.lut_subj)

    def finish(self, out, n):
        rgb = ImageChops.multiply(out.convert("RGB"), self.vig)
        p, m = self.grain[n % len(self.grain)]
        return ImageChops.subtract(ImageChops.add(rgb, p), m).convert("RGBA")


def view_crop(fr, cx, cy, z, ow=W, oh=H):
    """zoom_crop that also returns the source box, so overlays can find the face on screen."""
    z = max(z, ow / W, oh / H)                  # never ask for more than the frame has
    cw, ch = ow / z, oh / z
    x0 = clamp(cx - cw / 2, 0, W - cw); y0 = clamp(cy - ch / 2, 0, H - ch)
    return fr.resize((ow, oh), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)), (x0, y0, z)


# ---------------------------------------------------------------- 3D phone
def _project(w, h, ry, rx, f=2600):
    """Corners of a w x h card rotated ry (yaw) and rx (pitch) degrees, projected; returns fn(px, py) -> (x, y)
    in a frame centred on (0, 0)."""
    a, b = math.radians(ry), math.radians(rx)
    def P(px, py):
        X, Y, Z = (px - 0.5) * w, (py - 0.5) * h, 0.0
        X, Z = X * math.cos(a) + Z * math.sin(a), -X * math.sin(a) + Z * math.cos(a)
        Y, Z = Y * math.cos(b) - Z * math.sin(b), Y * math.sin(b) + Z * math.cos(b)
        s = f / (f + Z); return X * s, Y * s
    return P


def _persp_coeffs(dst, src):
    """PIL PERSPECTIVE coefficients mapping output (dst) points to input (src) points."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


class PhoneRect(tuple):
    """(x, y, w, h) bounding box plus .map(px, py) -> screen point, for stickers in phone space."""
    def __new__(cls, box, fn): o = super().__new__(cls, box); o.fn = fn; return o
    def map(self, px, py): return self.fn(px, py)


@lru_cache(None)
def phone_backdrop_glow(color):
    yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
    k = np.exp(-(((xx - W / 2) / (W * 0.55)) ** 2 + ((yy - H * 0.5) / (H * 0.42)) ** 2))[..., None] * 0.22 * np.array(color, np.float32)
    return Image.fromarray(np.clip(k, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)


def render_phone3d(A, img, base, t, st, end, sh):
    """Dark backdrop (the shot's own frame, blurred and dimmed) with the mockup floating in 3D. It enters by
    sh["enter_anim"] (rise / side / far / drop / flip), keeps drifting (yaw eases, slight push) and leaves by
    sh["exit_anim"] (sink / side / far / flip) unless a transition takes it out."""
    out = base.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
    out = ImageEnhance.Brightness(out).enhance(0.32)
    out = ImageChops.add(out, phone_backdrop_glow(tuple(sh.get("glow", [70, 120, 255]))))
    out = out.convert("RGBA")
    enter = sh.get("enter", 0.45); ex = 0 if sh.get("_exit_by_tr") else sh.get("exit", 0)
    mode, xmode = sh.get("enter_anim", "rise"), sh.get("exit_anim", "sink")
    k = clamp((t - st) / enter) if enter else 1.0; ue = ease_out_cubic(k)
    u = clamp((t - st) / max(end - st, 1e-3))
    y0, y1 = sh.get("yaw", [14, 5]); p0, p1 = sh.get("pitch", [7, 3])
    ry = lerp(y0, y1, ease_in_out(u)); rx = lerp(p0, p1, ease_in_out(u))
    alpha, dy, dx, sc = 1.0, 0.0, 0.0, 1.0
    side = 1 if int(st * 10) % 2 == 0 else -1
    if mode == "rise": ry += (1 - ue) * 26; rx += (1 - ue) * 10; alpha = ue; dy = (1 - ue) * 260
    elif mode == "side": dx = side * (1 - ue) * 1000; ry += side * (1 - ue) * 55; alpha = clamp(k * 2.5)
    elif mode == "far": sc = lerp(0.12, 1.0, ease_out_cubic(k) ** 0.8); ry += (1 - ue) * 20; alpha = clamp(k * 3)
    elif mode == "drop": dy = -(1 - ease_out_back(k, 1.25)) * 1500 if k < 1 else 0.0; rx -= (1 - ue) * 14
    elif mode == "flip": ry += (1 - ue) * 78; alpha = clamp(k * 4)
    if ex and t >= end - ex:
        ux = clamp((t - (end - ex)) / ex); e = ease_in_out(ux)
        if xmode == "sink": alpha *= 1 - ux; dy -= 180 * e; ry -= 12 * ux
        elif xmode == "side": dx -= side * 1100 * ease_in(ux, 2.4); ry -= side * 40 * ux
        elif xmode == "far": sc *= lerp(1.0, 0.1, ease_in(ux, 2)); alpha *= 1 - ease_in(ux, 3)
        elif xmode == "flip": ry -= 78 * e; alpha *= 1 - ease_in(ux, 3)
    ry = max(-80, min(80, ry))
    ph_h = int(sh.get("ph", 1380) * (1 + sh.get("push", 0.04) * u) * sc); ph_w = max(8, round(ph_h * PHONE_W / PHONE_H))
    ph = A.phone(img, ph_w)
    P = _project(ph.width, ph.height, ry, rx); cx, cy = W / 2 + sh.get("dx", 0) + dx, sh.get("cy", 980) + dy
    corners = [P(0, 0), P(1, 0), P(1, 1), P(0, 1)]
    dst = [(cx + x, cy + y) for x, y in corners]
    src = [(0, 0), (ph.width, 0), (ph.width, ph.height), (0, ph.height)]
    layer = ph.transform((W, H), Image.PERSPECTIVE, _persp_coeffs(dst, src), Image.BICUBIC)
    a = layer.getchannel("A")
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow.paste((0, 0, 0, 200), (0, 0), a.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(10)).resize((W, H)))
    if alpha < 1:
        layer.putalpha(a.point(lambda v: int(v * alpha))); shadow.putalpha(shadow.getchannel("A").point(lambda v: int(v * alpha)))
    out.alpha_composite(shadow, (0, 40)); out.alpha_composite(layer)
    xs, ys = [p[0] for p in dst], [p[1] for p in dst]
    rect = PhoneRect((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), lambda px, py: (cx + P(px, py)[0], cy + P(px, py)[1]))
    return out, rect


@lru_cache(None)
def edge_mask():
    """L mask: 0 over the middle, rising to 255 at the frame's edges and corners (for edge-only blur)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.42) / (H / 2)) ** 2)
    return Image.fromarray((np.clip((d - 0.45) / 0.6, 0, 1) ** 1.3 * 255).astype(np.uint8))


def face_zoom(r, sh, t, st):
    """Zoom for a face shot: base z, constant push, settle-on-reveal, smash-in, classic bounce."""
    M = r.style["motion"]; z = sh.get("z", 1.0)
    if getattr(r, "tracking", False): z = max(z, M.get("track_zoom", 1.12))   # room for the frame to follow the head
    iz = getattr(r, "intro", None)              # hook "intro_zoom": the reel opens zoomed in and snaps out in a split second
    if iz and t < iz.get("d", 0.2):
        z *= 1 + (iz.get("from", 1.35) - 1) * (1 - ease_out_cubic(clamp(t / iz.get("d", 0.2))))
    push = sh.get("push", M.get("push", 0.03))
    # push > 0 zooms in over the shot; push < 0 pulls out (starts that much tighter and eases back to z)
    if M.get("push_mode") == "per_second":
        z *= 1 + (push * (t - st) if push >= 0 else -push * max(0.0, sh["_end"] - t))
    else:
        u = clamp((t - st) / max(sh["_end"] - st, 1e-3)); z *= 1 + (push * u if push >= 0 else -push * (1 - u))
    if sh.get("settle"):
        s = M.get("settle", 0.14) if sh["settle"] is True else sh["settle"]
        z *= 1 + s * (1 - ease_out_cubic(clamp((t - st) / M.get("settle_d", 1.1))))
    blur = 0.0
    if sh.get("smash"):
        k = clamp((t - st) / 0.24); z = lerp(max(1.0, z * 0.62), z, ease_out_cubic(k)); blur = (1 - k) * 0.08
    z *= 1 + sh.get("bounce", M.get("bounce", 0.045)) * max(0.0, 1 - (t - st) / 0.12)
    return z, blur


def bg_frame(r, A, sh, t, st, end):
    """The contextual background for this frame (drifting slowly), or None."""
    bg = sh["bg"]; src = A.bg_src(json.dumps({k: v for k, v in bg.items() if k not in ("in", "out", "why")}, sort_keys=True))
    u = clamp((t - st) / max(end - st, 1e-3)); zz = 1 + bg.get("push", 0.05) * u
    cw, ch = W / zz, H / zz; cx = src.width / 2; cy = src.height * bg.get("focus", 0.5) + bg.get("scroll", 0) * u
    cy = clamp(cy, ch / 2, src.height - ch / 2)
    return src.resize((W, H), Image.BILINEAR, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))


def cutout_over_bg(r, A, face, sh, t, st, end, view):
    """The speaker cut out (Vision mask) in front of the shot's contextual background. The background comes in and
    goes out by sh["bg"]["in"] (fade / zoom / slide / drop), unless the neighbouring shot keeps the same one."""
    if r.mask is None: return face
    x0, y0, z = view; cw, ch = W / z, H / z
    m = r.mask.resize((W, H), Image.BILINEAR, box=(x0 / 2, y0 / 2, (x0 + cw) / 2, (y0 + ch) / 2))
    m = m.point(mask_lut(r.style["grade"].get("mask_lo", 0.66), r.style["grade"].get("mask_hi", 0.96))).filter(ImageFilter.GaussianBlur(1.2))
    bg = sh["bg"]; same = lambda o: o is not None and o.get("bg") == bg
    prev = next((x for x in r.shots if abs(x["_end"] - st) < 1e-6), None); nxt = next((x for x in r.shots if abs(x["_t"] - end) < 1e-6), None)
    di, do = bg.get("enter", 0.4), bg.get("exit", 0.3)
    k_in = 1.0 if same(prev) or sh.get("_tr") else clamp((t - st) / di)
    k_out = 1.0 if same(nxt) or sh.get("_exit_by_tr") else clamp((end - t) / do)
    back = bg_frame(r, A, sh, t, st, end)
    mode = bg.get("in", "fade"); k = min(ease_out_cubic(k_in), ease_in_out(k_out))
    room = face.convert("RGB")
    if mode == "zoom": back = fx.zoom(back, 1 + 0.3 * (1 - k)); layer = Image.blend(room, back, k)
    elif mode in ("slide", "drop"):
        layer = room.copy(); off = int((1 - k) * H) * (1 if mode == "slide" else -1); layer.paste(back, (0, off))
    else: layer = Image.blend(room, back, k)
    # a soft dark halo around the speaker separates them from the background
    halo = m.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    layer = ImageChops.multiply(layer, Image.merge("RGB", [halo.point(lambda v: 255 - int(v * 0.45 * k))] * 3))
    return Image.composite(room, layer, m).convert("RGBA")


def bar_content(r, A, out, c, t, st, end, cy, hmax):
    """Something useful in a letterbox bar: a neon title or a screen, animated in."""
    k = clamp((t - st - c.get("delay", 0.12)) / 0.35)
    if k <= 0: return
    if c.get("title"):
        lines = tuple((ln[0], ln[3] if len(ln) > 3 else "xblack", ln[2] if len(ln) > 2 else 96, ln[1]) for ln in c["title"])
        lab = c.get("label"); n_lab = int(len(lab) * clamp(k * 1.4)) if lab else None
        im = glow_lines(lines, 0, c.get("frame", False), lab, n_lab, c.get("accent"))
        bb = im.getbbox() or (0, 0, im.width, im.height); f = min(1.0, 1000 / max(1, bb[2] - bb[0]), hmax / max(1, bb[3] - bb[1]))
        paste_center(out, im, 540, cy + 40 * (1 - ease_out_cubic(k)), f, ease_out_cubic(k))
    elif c.get("img"):
        sc = A.screen(c["img"]); hh = int(hmax * 0.95); im = sc.resize((round(sc.width * hh / sc.height), hh), Image.LANCZOS).convert("RGBA")
        m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], 28, fill=255); im.putalpha(m)
        paste_center(out, shadowed(im, 16, 160, 8), 540 + (1 - ease_out_cubic(k)) * 700, cy, 1.0, clamp(k * 2))


def render_shot(r, A, fr, t, sh):
    """One shot's picture at time t, before stickers and captions. Returns (image, phone_rect, view)."""
    st, end = sh["_t"], sh["_end"]
    u = clamp((t - st) / max(end - st, 1e-3))
    ax, ay, fh = r.anchor(t)
    ey = ay - 0.12 * fh if fh else ay          # aim a little above the face centre (eyes)
    bounce = 1 + sh.get("bounce", r.style["motion"].get("bounce", 0.045)) * max(0.0, 1 - (t - st) / 0.12)
    lay = sh["lay"]; phone_rect = None; view = (0, 0, 1.0)
    img = sh.get("img")
    for ts, nm in sh["_swaps"]:
        if t >= ts: img = nm
    ex_ok = not sh.get("_exit_by_tr")
    if lay == "face":
        z, blur = face_zoom(r, sh, t, st)
        out, view = view_crop(fr, ax, ey, z)
        if blur > 0.005:                       # zoom motion blur while smashing in
            for k in (1, 2):
                im, _ = view_crop(fr, ax, ey, z * (1 - blur * k / 2)); out = Image.blend(out, im, 0.33)
        iz = getattr(r, "intro", None)
        if iz and t < iz.get("d", 0.2):          # intro snap-out: zoom blur that streaks the edges, a soft blur over all
            k = 1 - ease_out_cubic(clamp(t / iz.get("d", 0.2)))
            zb = iz.get("zoom_blur", 0.14) * k
            for i in range(1, 6):              # stacked zoom levels: the further from the face, the longer the streak
                im, _ = view_crop(fr, ax, ey, z * (1 + zb * i / 5)); out = Image.blend(out, im, 1 / (i + 1))
            gb = iz.get("blur", 7.0) * k * k
            if gb > 0.3: out = out.filter(ImageFilter.GaussianBlur(gb))
            eb = iz.get("edge_blur", 18.0) * k
            if eb > 0.5: out = Image.composite(out.filter(ImageFilter.GaussianBlur(eb)), out, edge_mask())
        out = out.convert("RGBA")
        if sh.get("bg"): out = cutout_over_bg(r, A, out, sh, t, st, end, view)
    elif lay == "phone3d":
        out, phone_rect = render_phone3d(A, img, fr, t, st, end, sh)
    elif lay == "letterbox":
        bh = sh.get("bh", 608); cyb = sh.get("cy", 900)
        bg = fr.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
        out = ImageEnhance.Brightness(bg).enhance(0.3).convert("RGBA")
        k = ease_out_cubic(clamp((t - st) / 0.3))           # bars close in from the full frame
        z = sh.get("z", 1.0) * (1 + r.style["motion"].get("push", 0.03) * 0.6 * (t - st))
        bhk = int(lerp(H, bh, k)); win, _ = view_crop(fr, ax, ay - 0.08 * (fh or 0), z, W, bhk)
        out.paste(win, (0, int(lerp(H / 2, cyb, k) - bhk / 2)))
        d = ImageDraw.Draw(out); ly = int(cyb + bh / 2 + 26)
        if k > 0.95:
            d.line([(60, ly), (W - 60, ly)], fill=(255, 255, 255, 60), width=4)
            d.line([(60, ly), (60 + (W - 120) * u, ly)], fill=(255, 255, 255, 230), width=4)
        if sh.get("top"): bar_content(r, A, out, sh["top"], t, st, end, (SAFE_TOP + cyb - bh / 2) / 2, cyb - bh / 2 - SAFE_TOP - 30)
        if sh.get("bottom"): bar_content(r, A, out, sh["bottom"], t, st, end, (ly + 20 + SAFE_BOTTOM) / 2, SAFE_BOTTOM - ly - 50)
        view = None
    elif lay == "split":
        out = Image.new("RGBA", (W, H))
        zf = sh.get("zf", 1.0) * (1 + 0.03 * u) * bounce
        win_h = 960 / zf
        out.paste(zoom_crop(fr, ax, ey + win_h * 0.06, zf, W, 960), (0, 0))
        panel = panel_bg().copy()
        ph = A.phone(img, sh.get("pw", 660))
        if "py" in sh: y0, y1 = sh["py"]
        else:
            # focus = fraction of the phone's height to centre in the panel's safe area (panel y 290 = screen y 1250)
            foc = sh.get("focus", 0.3); foc = foc if isinstance(foc, list) else [foc, foc]
            y0, y1 = [min(30, 290 - f * ph.height) for f in foc]
        enter = sh.get("enter", 0)
        if enter:
            ue = clamp((t - st) / enter); py = lerp(960, y0, ease_out_back(ue, 1.2)) if ue < 1 else lerp(y0, y1, ease_in_out(u))
        else:
            py = lerp(y0, y1, ease_in_out(u))
        px = int((W - ph.width) / 2)
        panel.alpha_composite(ph, (px, int(py)))
        phone_rect = (px, 960 + py, ph.width, ph.height)
        ex = sh.get("exit", 0) if ex_ok else 0
        if ex and t >= end - ex:
            ux = clamp((t - (end - ex)) / ex); out = zoom_crop(fr, ax, ey, 1.0, W, H).convert("RGBA")
            pdy = int(960 + 980 * ux ** 2.2); out.alpha_composite(panel, (0, pdy)); phone_rect = None
        else:
            out.paste(panel, (0, 960))
            ImageDraw.Draw(out).line([0, 959, W, 959], fill=(255, 255, 255, 60), width=3)
    elif lay in ("fullpw", "video"):
        out = blurred_bg(fr)
        ue = clamp((t - st) / sh.get("enter", 0.3)) if sh.get("enter", 0.3) else 1.0
        py = lerp(H + 20, FULL_Y, ease_out_back(ue, 1.1))
        ex = sh.get("exit", 0) if ex_ok else 0
        if ex and t >= end - ex:
            ux = clamp((t - (end - ex)) / ex); out = zoom_crop(fr, ax, ey, 1.0, W, H).convert("RGBA")
            py = FULL_Y + (H + 20 - FULL_Y) * ux ** 2.2
        sc = 1 + sh.get("push", 0.025) * u
        pw = int(FULL_H * PHONE_W / PHONE_H * sc); phh = int(FULL_H * sc)
        if lay == "fullpw":
            php = A.phone(img, pw)
        else:
            s = pw / PHONE_W; sx, sy, sw, shh, sr = [int(v * s) for v in SCREEN]
            php = Image.new("RGBA", (pw, round(PHONE_H * s)), (0, 0, 0, 0))
            vid = A.stream_frame(sh, t, (sw, shh)).convert("RGBA")
            php.paste(vid, (sx, sy), A.screen_mask(sw, shh, sr)); php.alpha_composite(A.frame_png(pw))
        x = int((W - php.width) / 2); y = int(py - (php.height - FULL_H) / 2)
        out.alpha_composite(php, (x, y)); phone_rect = (x, y, php.width, php.height)
        if sh.get("bubble"): face_bubble(out, fr, ax, ey, fh, W - 300, FULL_Y + 40)
    elif lay == "broll":
        out = A.stream_frame(sh, t, (W, H)).convert("RGBA")
        if sh.get("bubble", True): face_bubble(out, fr, ax, ey, fh, W - 300, 260)
    else:
        die(f"unknown layout {lay}")
    return out, phone_rect, view


def compose_frame(r, A, fr, t):
    """The shot (or a transition between two shots) at time t. Both shots of a transition are rendered from the
    same source frame, so a transition mixes two framings of the same moment."""
    tr = r.trans_at(t)
    if tr:
        u = (t - (tr["t"] - tr["d"] / 2)) / tr["d"]
        Ai, Ap, Av = render_shot(r, A, fr, t, tr["a"]); Bi, Bp, Bv = render_shot(r, A, fr, t, tr["b"])
        view = Bv if u >= 0.5 else Av; opts = dict(tr["opts"]); opts["hist"] = r.hist
        if view:                                   # centre zooms and irises on the face as it is on screen
            ax, ay, fh = r.anchor(t); x0, y0, z = view
            opts.setdefault("cx", clamp((ax - x0) * z, 100, W - 100)); opts.setdefault("cy", clamp((ay - y0) * z, 300, H - 300))
        out = fx.transition(tr["name"], Ai, Bi, u, opts)
        r.view = view
        return out, (tr["b"] if u >= 0.5 else tr["a"]), (Bp if u >= 0.5 else Ap)
    sh = r.shot_at(t)
    out, prect, r.view = render_shot(r, A, fr, t, sh)
    return out, sh, prect


def sticker_xy(st, phone_rect, default):
    if st.get("space") == "phone":
        if not phone_rect: return None
        if hasattr(phone_rect, "map"): return phone_rect.map(st.get("px", 0.5), st.get("py", 0.5))
        x, y, w, h = phone_rect
        return x + st.get("px", 0.5) * w, y + st.get("py", 0.5) * h
    return st.get("x", default[0]), st.get("y", default[1])


@lru_cache(maxsize=256)
def icon_img(name, u, col, size, g):
    return fx.neon_icon(name, u, col, size, g=1.3 * g)


def draw_title(r, out, lines, st, t, t0, t1, x, y):
    """A neon title (glow_title, cinematic text sticker or punch) with its in/out animation (st["anim"], st["out"]),
    an optional typed-on label, a light sweep after it lands (st["shine"], default on) and auto-fit to 1000 px."""
    anim = st.get("anim", "flicker"); n = sum(len(str(l[0]).replace(" ", "")) for l in lines) or 1
    S = fx.title_anim(anim, t, t0, t1, n, st.get("out", "fade"), st.get("d_in"))
    d_in = st.get("d_in") or fx.TITLE_D.get(anim) or min(0.9, n * 0.045)
    lab = st.get("label"); n_lab = None
    if lab: n_lab = len(lab) if st.get("hold_label") else int(len(lab) * clamp((t - t0 - 0.06) / 0.28))
    shown = S["chars"] if anim == "type" else None
    if S["scramble"]:
        left = S["chars"]; nl = []
        for i, l in enumerate(lines):
            c = len(str(l[0]).replace(" ", "")); f_ = min(c, left); left -= f_
            nl.append((fx.scramble_text(l[0], f_, int(t * FPS) * 13 + i),) + tuple(l[1:]))
        lines = tuple(nl)
    im = glow_lines(lines, st.get("rot", 0), st.get("frame", False), lab, n_lab, st.get("accent"), shown)
    if S["reveal"] is not None: im = fx.reveal_mask(im, S["reveal"])
    if S["glitch"] > 0.02: im = fx.glitch_rgba(im, S["glitch"], int(t * FPS) + 3)
    if S["blur"] > 0.5: im = im.filter(ImageFilter.GaussianBlur(S["blur"]))
    if st.get("shine", True) and anim not in ("glitch", "scramble"):
        us = (t - t0 - d_in - 0.05) / 0.5
        if 0 <= us <= 1.2: im = fx.shine(im, us)
    bb = im.getbbox() or (0, 0, im.width, im.height); fit = min(1.0, 1000 / max(1, bb[2] - bb[0]))
    side = 1 if int(t0 * 10) % 2 else -1
    if S["lines_dx"] > 1: im = fx.dir_blur(im, S["lines_dx"] * 0.1, 0)
    dx, dy = S["dx"] + side * S["lines_dx"], S["dy"]
    if S["shake"] > 0.5:
        rs = np.random.default_rng(int(t * FPS)); dx += rs.normal(0, S["shake"]); dy += rs.normal(0, S["shake"])
    paste_text(out, im, x + dx, y + dy, fit * S["scale"], S["alpha"])


def draw_sticker(r, C, out, st, t, lay, phone_rect):
    """One sticker at time t, drawn into out."""
    typ = st["type"]; t0 = st["_t0"]
    # simple out-animation: shrink + fade over the last 0.12 s unless "hold_out": true
    k_out = 1.0 if st.get("hold_out") else clamp((st["_t1"] - t) / 0.12)
    sc_in = pop_scale(t, t0, 0.14, 0.55) * (0.7 + 0.3 * k_out)
    if typ in ("red_x", "check"):
        xy = sticker_xy(st, phone_rect, (540, 900 if lay != "split" else 1440))
        if xy is None: return
        sc = lerp(1.9, 1.0, ease_out_cubic(clamp((t - t0) / 0.1)))
        paste_center(out, (red_x if typ == "red_x" else check)(st.get("size", 520)), *xy, sc, k_out)
    elif typ == "thought":
        paste_text(out, thought(st["text"], st.get("side", "l")), st.get("x", 470), st.get("y", 1330), sc_in, k_out)
    elif typ == "review_card":
        n = sum(1 for k in range(st.get("stars", 5)) if t >= t0 + 0.1 + 0.08 * k)
        card = review_card(tuple(st["lines"]), st.get("name", ""), st.get("src", "App Store review"), n)
        paste_text(out, card, st.get("x", 540), st.get("y", 1400), pop_scale(t, t0, 0.18, 0.6), k_out)
    elif typ == "emoji":
        xy = sticker_xy(st, phone_rect, (540, 700))
        if xy is None: return
        im = emoji(st["char"], st.get("size", 220))
        rot = st.get("rot", 0) + (6 * math.sin((t - t0) * 9) if st.get("wiggle", True) else 0)
        paste_center(out, im.rotate(rot, resample=Image.BICUBIC, expand=True), *xy, sc_in, k_out)
    elif typ == "banner":
        im = banner(st["text"], st.get("bg", "#FFFFFF"), st.get("fg", "#111111"), st.get("size", 56))
        yy = lerp(st.get("y", 330) - 80, st.get("y", 330), ease_out_back(clamp((t - t0) / 0.25), 1.4))
        paste_text(out, im, st.get("x", 540), yy, 1.0, clamp((t - t0) / 0.1) * k_out)
    elif typ == "circle":
        if st.get("space") == "phone":
            if not phone_rect: return
            x, y, w, h = phone_rect
            cx, cy = sticker_xy(st, phone_rect, (0, 0)); cw, ch = st.get("pw", 0.4) * w, st.get("ph", 0.08) * h
        else:
            cx, cy, cw, ch = st["x"], st["y"], st.get("w", 400), st.get("h", 160)
        draw_circle(out, cx, cy, cw, ch, st.get("color", "#FF3B30"), (t - t0) / 0.3)
    elif typ == "arrow":
        draw_arrow(out, st["x1"], st["y1"], st["x2"], st["y2"], st.get("color", "#FFE14D"), (t - t0) / 0.25)
    elif typ == "counter":
        u = ease_out_cubic(clamp((t - t0) / st.get("dur", 0.8)))
        v = lerp(st.get("from", 0), st["to"], u); dec = st.get("decimals", 0)
        txt = f"{st.get('prefix', '')}{v:,.{dec}f}{st.get('suffix', '')}"
        key = json.dumps([[[txt, "cblack", st.get("size", 220), st.get("color", "#4CD964")]], st.get("rot", 0)])
        paste_text(out, C.punch(key), st.get("x", 540), st.get("y", 800), sc_in, k_out)
    elif typ == "image":
        p = Path(st["path"]).expanduser(); p = p if p.is_absolute() else r.proj / p
        im = Image.open(p).convert("RGBA"); w = st.get("w", 400)
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        paste_center(out, im, st.get("x", 540), st.get("y", 700), sc_in, k_out)
    elif typ == "clip":
        # an animated graphic that pops up over the shot instead of taking the whole
        # screen: a folder of RGBA PNG frames played from t0
        im = clip_frame(r, st, t)
        if im is None: return
        u_in = clamp((t - t0) / 0.28); u_out = clamp((st["_t1"] - t) / 0.2)
        sc = lerp(0.55, 1.0, ease_out_back(u_in, 1.6)) * lerp(0.86, 1.0, ease_out_cubic(u_out))
        paste_text(out, im, st.get("x", 540), st.get("y", 1150), sc, clamp(u_in * 3) * u_out)
    elif typ == "text" and not r.cine:
        key = json.dumps([st["lines"], st.get("rot", 0)])
        paste_text(out, C.punch(key), st.get("x", 540), st.get("y", 700), sc_in, k_out)
    elif typ == "tap":
        xy = sticker_xy(st, phone_rect, (540, 960))
        if xy is None: return
        k = clamp((t - t0) / 0.12); sc = lerp(1.6, 1.0, ease_out_cubic(k))
        a = k * clamp((st["_t1"] - t) / 0.18)
        ring = clamp((t - t0) / 0.4)
        if ring < 1:
            lay_r = Image.new("RGBA", out.size, (0, 0, 0, 0)); rr = 40 + 90 * ease_out_cubic(ring)
            ImageDraw.Draw(lay_r).ellipse([xy[0] - rr, xy[1] - rr, xy[0] + rr, xy[1] + rr], outline=(120, 175, 255, int(200 * (1 - ring))), width=5)
            out.alpha_composite(lay_r)
        paste_center(out, tap_dot(st.get("size", 96)), *xy, sc, a)
    elif typ == "glow_title" or (typ == "text" and r.cine):
        if typ == "glow_title":
            lines = tuple((ln[0], ln[3] if len(ln) > 3 else "xblack", ln[2] if len(ln) > 2 else 120, ln[1]) for ln in st["lines"])
        else:
            lines = tuple(tuple(ln) for ln in st["lines"])
        draw_title(r, out, lines, st, t, t0, st["_t1"], st.get("x", 540), st.get("y", 760 if typ == "glow_title" else 700))
    elif typ == "icon":
        k = (t - t0) / st.get("draw", 0.55); col = hexc(st.get("color", "#FFFFFF"))
        u = 1.0 if k >= 1 else round(fx.ease_in_out(k) * 30) / 30
        g = 1.0 if k < 1 else round(1 + 0.15 * math.sin((t - t0) * 7), 2)
        im = icon_img(st["name"], u, col, st.get("size", 420), g)
        paste_center(out, im, st.get("x", 540), st.get("y", 760), lerp(0.9, 1.0, ease_out_cubic(clamp(k))), k_out)
    elif typ == "hand_note":
        n_w = len(st["text"].split(" ")); rev = st.get("reveal", 0.6)
        n = max(1, min(n_w, 1 + int((t - t0 - 0.2) / max(rev / n_w, 1e-3)))) if t >= t0 + 0.2 else 0
        if "arrow" in st:
            a0, a1 = st["arrow"]
            if st.get("space") == "phone" and phone_rect and hasattr(phone_rect, "map"): a1 = phone_rect.map(*a1)
            draw_curve_arrow(out, tuple(a0), tuple(a1), st.get("bend", 0.25), (t - t0) / 0.25)
        if n: paste_text(out, hand_text(st["text"], n, st.get("size", 66)), st.get("x", 540), st.get("y", 700), 1.0, k_out)
    elif typ == "notify":
        card = notify_card(st.get("app", "App"), st.get("title", ""), st.get("body", ""), st.get("color", "#1f9d6b"))
        yy = st.get("y", 300); k = clamp((t - t0) / 0.35)
        y = lerp(-card.height, yy, ease_out_back(k, 1.3)) if k < 1 else yy
        if t > st["_t1"] - 0.25: y = lerp(yy, -card.height, ease_in_out((t - (st["_t1"] - 0.25)) / 0.25))
        paste_center(out, card, 540, y)
    elif typ == "chat_pill":
        base = chat_pill_base(st.get("w", 880)); yy = st.get("y", 1300)
        k = clamp((t - t0) / 0.25); y = lerp(yy + 90, yy, ease_out_cubic(k))
        pill = base.copy(); d = ImageDraw.Draw(pill); h0 = 20; hh = 118
        if getattr(r, "_face", None) is not None:
            fc = r._face.resize((88, 88)); pill.paste(fc, (20 + 16, h0 + 15), circle_mask(88))
        txt = st.get("text", ""); n = int(max(0.0, (t - t0 - st.get("delay", 0.25)) / st.get("cps", 0.09)))
        shown = txt[:min(len(txt), n)]
        f = font("semibold", 50); d.text((20 + 128, h0 + hh // 2), shown or st.get("placeholder", ""), font=f,
                                         fill=(255, 255, 255, 255) if shown else (150, 150, 158, 255), anchor="lm")
        if int(t * 2.5) % 2 == 0 or (0 < n < len(txt)):
            cx = 20 + 128 + (f.getlength(shown) if shown else 0) + 6
            d.line([(cx, h0 + 34), (cx, h0 + hh - 34)], fill=(110, 140, 255, 255), width=4)
        paste_text(out, pill, 540, y, 1.0, k * k_out)


def overlays(r, C, out, t, sh, phone_rect):
    """Stickers, punch titles and captions. Under a spotlight the frame (and every sticker that isn't lit) dims,
    then the lit ones, punch titles and captions are drawn on top at full brightness."""
    lay = sh["lay"]
    k, lvl = r.spot_at(t); lit = []
    all_text = any(a <= t < b for a, b in r.spot_fx)
    for st in r.stickers:
        if not (st["_t0"] <= t < st["_t1"]): continue
        if k > 0 and (st.get("spotlight") or (all_text and st["type"] in TEXT_TYPES)): lit.append(st); continue
        draw_sticker(r, C, out, st, t, lay, phone_rect)
    if k > 0: out.paste(fx.dim(out, k, lvl), (0, 0))
    for st in lit: draw_sticker(r, C, out, st, t, lay, phone_rect)
    for pu in r.punches:
        if pu["_t0"] <= t < pu["_t1"]:
            cy = pu.get("y") or (960 if lay == "split" else (380 if lay in ("fullpw", "video") else 1330))
            if r.cine:
                draw_title(r, out, tuple(tuple(ln) for ln in pu["lines"]), {**pu, "out": pu.get("out", "cut")}, t, pu["_t0"], pu["_t1"], pu.get("x", 540), cy)
            else:
                key = json.dumps([pu["lines"], pu.get("rot", 0)])
                paste_text(out, C.punch(key), pu.get("x", 540), cy, pop_scale(t, pu["_t0"], 0.12, 0.4))
            if not pu.get("keep_captions"): return
    if lay in OVERLAY_LAYS and not r.style["captions"].get("on_overlays", True) and not sh.get("captions"): return
    for gi, g in enumerate(r.groups):
        if g["t0"] <= t < g["t1"]:
            active = 0
            for i, (_, a, _) in enumerate(g["w"]):
                if a <= t: active = i
            if g["sec"][1] == "cine":
                wk = g["w"][active][1]; im = C.render(gi, active, min(3, max(0, int((t - wk) * FPS))))
                if lay == "letterbox" and sh.get("bottom") and sh.get("top"): break   # both bars carry their own text
                paste_text(out, im, 540, caption_cy(r, sh, lay, t, im), 1.0)
                break
            im = C.render(gi, active); sc = pop_scale(t, g["t0"], 0.12, 0.7)
            cy = caption_cy(r, sh, lay, t, im)
            if g["sec"][1] != "box":
                bb = im.getbbox() or (0, 0, im.width, im.height)
                bw, bh = bb[2] - bb[0], bb[3] - bb[1]
                region = out.crop((int(540 - bw / 2), int(cy - bh / 2), int(540 + bw / 2), int(cy + bh / 2))).convert("L")
                if ImageStat.Stat(region).mean[0] > 150:
                    paste_center(out, backing(bw + 36, bh + 18), 540, cy + (bb[1] + bb[3] - im.height) / 2, sc)
            paste_text(out, im, 540, cy, sc)
            break


def caption_cy(r, sh, lay, t, im):
    """Where a caption group sits (its centre y). Captions go at the TOP of the frame: on a
    face shot the caption's ink ends just inside the top of the head, following the head track; on phones, b-roll
    and splits it sits in the top band, above the phone. A shot's "capy" still overrides. paste_text keeps it inside
    the text safe area either way."""
    bb = im.getbbox() or (0, 0, im.width, im.height)
    ink_mid = (bb[1] + bb[3]) / 2 - im.height / 2           # ink centre relative to the image centre
    ink_h = bb[3] - bb[1]
    if sh.get("capy"): return sh["capy"] - ink_mid
    if lay == "letterbox":
        cyb, bh = sh.get("cy", 900), sh.get("bh", 608)
        if not sh.get("top"): return (TEXT_TOP + cyb - bh / 2) / 2 - ink_mid
        return (cyb + bh / 2 + TEXT_BOTTOM) / 2 - ink_mid
    if lay == "face" and r.view:
        ax, ay, fh = r.anchor(t); x0, y0, z = r.view
        head_top = (ay - CAP_HEAD * (fh or 300) - y0) * z     # a little inside the top of the hair
        return max(TEXT_TOP, head_top - ink_h) + ink_h / 2 - ink_mid
    return CAP_TOP_BAND + ink_h / 2 - ink_mid


FX_BASE = {"bw"}           # applied to the picture before stickers and captions (text stays in colour)
FX_D = {"flash": 0.12, "invert": 0.07, "freeze": 0.7, "pulse": 0.22, "spotlight": 1.2}


def apply_fx(r, out, t, stage="post"):
    for e in r.fx:
        typ = e["type"]
        if (typ in FX_BASE) != (stage == "base") or typ == "spotlight": continue
        t0, d = e["_t"], e.get("d", FX_D.get(typ, 0.25))
        if not (t0 <= t < t0 + d): continue
        u = (t - t0) / d
        if typ == "flash":
            a = int(255 * e.get("strength", 0.85) * (1 - u) ** 2)
            out.alpha_composite(Image.new("RGBA", out.size, (*hexc(e.get("color", "#FFFFFF"))[:3], a)))
        elif typ == "shake":
            amp = e.get("amp", 16) * (1 - u); k = (t - t0) * 60
            dx, dy = int(amp * math.sin(k * 2.3)), int(amp * math.cos(k * 3.1))
            z = out.resize((int(W * 1.04), int(H * 1.04)), Image.BILINEAR)
            out.paste(z.crop((int(W * 0.02) - dx, int(H * 0.02) - dy, int(W * 0.02) - dx + W, int(H * 0.02) - dy + H)), (0, 0))
        elif typ == "rgb":
            amp = int(e.get("amp", 14) * (1 - u) + 2)
            rch, g, b, a = out.split()
            rch = rch.transform(out.size, Image.AFFINE, (1, 0, -amp, 0, 1, 0)); b = b.transform(out.size, Image.AFFINE, (1, 0, amp, 0, 1, 0))
            out.paste(Image.merge("RGBA", (rch, g, b, a)), (0, 0))
        elif typ == "glitch":                    # authentic: corruption bursts, datamosh blocks from recent frames
            n = int(round(t * FPS)); amt = fx.glitch_amt(u, n, e.get("seed", 0), e.get("amp", 1.0))
            if r.hist and random.Random(n * 3 + 1).random() < 0.18:     # a stutter: an older frame flashes back
                old = Image.fromarray(r.hist[0]).convert("RGBA"); out.paste(fx.glitch_frame(old, amt, n + 5, hist=list(r.hist)), (0, 0))
            else: out.paste(fx.glitch_frame(out, amt, n, hist=list(r.hist)), (0, 0))
        elif typ == "glitch_lite":
            rng = np.random.default_rng(int(t * FPS) + 7); amp = e.get("amp", 1.0) * (1 - 0.5 * u)
            src = out.copy(); rch, gch, bch, ach = src.split(); k = int(22 * amp)
            src = Image.merge("RGBA", (rch.transform(out.size, Image.AFFINE, (1, 0, -k, 0, 1, 0)), gch,
                                       bch.transform(out.size, Image.AFFINE, (1, 0, k, 0, 1, 0)), ach))
            for _ in range(int(rng.integers(7, 13))):
                y0 = int(rng.integers(0, H - 40)); hh = int(rng.integers(20, 180)); dx = int(rng.integers(-140, 140) * amp)
                band_ = src.crop((0, y0, W, y0 + hh)); src.paste(band_, (dx, y0))
            out.paste(src, (0, 0))
        elif typ == "dip":
            a = int(255 * e.get("strength", 1.0) * math.sin(math.pi * u))
            out.alpha_composite(Image.new("RGBA", out.size, (0, 0, 0, a)))
        elif typ in ("zoom", "pulse"):
            zz = 1 + (e.get("to", 1.15 if typ == "zoom" else 1.07) - 1) * math.sin(math.pi * u)
            cx, cy = e.get("x", 540), e.get("y", 900)
            out.paste(zoom_crop(out.convert("RGB"), cx, cy, zz, W, H).convert("RGBA"), (0, 0))
        elif typ == "invert":
            rgb = ImageChops.invert(out.convert("RGB")); out.paste(rgb.convert("RGBA"), (0, 0))
        elif typ == "bw":
            k = min(fx.ease_out(clamp((t - t0) / 0.15), 2), clamp((t0 + d - t) / 0.15))
            g = ImageEnhance.Color(out.convert("RGB")).enhance(1 - k).convert("RGBA"); out.paste(g, (0, 0))
        elif typ == "freeze":                   # photo snap: the frame freezes into a white-bordered print
            key = id(e)
            if key not in r.frozen: r.frozen[key] = out.copy()
            snap = r.frozen[key]; k = ease_out_cubic(clamp((t - t0) / 0.2))
            back = ImageEnhance.Brightness(fx.soft_blur(snap.convert("RGB"), 26)).enhance(0.45).convert("RGBA")
            s_ = lerp(1.0, e.get("scale", 0.8), k); pw, ph = int(W * s_), int(H * s_); b = int(22 * k)
            card = Image.new("RGBA", (pw + 2 * b, ph + 2 * b), (255, 255, 255, 255)); card.paste(snap.resize((pw, ph), Image.BILINEAR), (b, b))
            card = shadowed(card, 24, 170, 14).rotate(e.get("rot", -3) * k, Image.BICUBIC, expand=True)
            back.alpha_composite(card, ((W - card.width) // 2, (H - card.height) // 2))
            back.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(220 * clamp(1 - (t - t0) / 0.14)))))
            out.paste(back, (0, 0))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project"); ap.add_argument("--variant", required=True)
    ap.add_argument("--preview", default=None); ap.add_argument("--cover", action="store_true")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("REEL_WORKERS", 0)) or None,
                    help="processes for the full render (default: CPU cores - 2, at most 10; 1 = serial)")
    ap.add_argument("--range", default=None, help=argparse.SUPPRESS)     # worker: frames F0:F1 of the full render
    ap.add_argument("--out", default=None, help=argparse.SUPPRESS)       # worker: where its chunk goes
    a = ap.parse_args()
    r = Reel(a.project, a.variant); A = Assets(r); C = Captions(r)
    if r.plan.get("track", r.style["motion"].get("track", True)):   # head tracking, on by default
        from track import track_part
        for p in r.parts: p["track"] = track_part(p["dir"])
        r.tracking = True
    iz = r.plan["hooks"][a.variant].get("intro_zoom", True)   # on by default; false turns it off
    # True must become a NON-empty dict: the readers test `if iz`, and an empty {} is falsy, which silently turned the
    # default off (only plans that spelled the dict out got the zoom)
    r.intro = (dict(INTRO_DEFAULT) if iz is True else {**INTRO_DEFAULT, **iz}) if iz else None
    # background replacement: OPT-IN ONLY, when plan.json has "room"; builds room.mp4 per part once
    import room as roomlib
    r.room = roomlib.ensure(r.proj)
    od = r.proj / "work" / "out" / a.variant; od.mkdir(parents=True, exist_ok=True)
    full = not a.preview and not a.cover and not a.range
    workers = a.workers or 1     # parallel is opt-in (--workers N): 10 workers measured no faster on an M-series Mac, not yet diagnosed
    if full and workers > 1 and r.nfr > 300:
        save_events(r, od)
        return render_parallel(r, a, od, workers)
    if not a.range: save_events(r, od)
    render_frames(r, A, C, a, od)


def render_parallel(r, a, od, workers):
    """Full render split across processes (a full render uses one core otherwise). Frames don't
    depend on each other except the glitch effect's 6-frame history, so each worker renders a contiguous chunk, warming
    up on the frames just before it, and encodes its own file; the chunks are joined without re-encoding."""
    import time
    t_start = time.time()
    if r.need_mask:                               # segment once here, never in N workers at the same time
        from segment import segment_part
        for p in r.parts: segment_part(p["dir"])
    cd = od / "chunks"; cd.mkdir(exist_ok=True)
    for f in cd.glob("*"): f.unlink()
    n = min(workers, max(1, r.nfr // 120)); edges = [round(i * r.nfr / n) for i in range(n + 1)]
    procs = []
    for i in range(n):
        f = cd / f"c{i:02d}.mp4"
        cmd = [sys.executable, str(Path(__file__).resolve()), str(r.proj), "--variant", a.variant,
               "--range", f"{edges[i]}:{edges[i + 1]}", "--out", str(f)]
        procs.append((subprocess.Popen(cmd, stdout=subprocess.DEVNULL), f))
    print(f"rendering {r.nfr} frames in {n} processes", flush=True)
    bad = [i for i, (p, _) in enumerate(procs) if p.wait() != 0]
    if bad: die(f"render workers failed: chunks {bad} (run with --workers 1 to see the error)")
    lst = cd / "list.txt"; lst.write_text("".join(f"file '{f}'\n" for _, f in procs))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
         "-movflags", "+faststart", str(od / "video.mp4")])
    got = int(run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                   "stream=nb_read_packets", "-of", "csv=p=0", str(od / "video.mp4")]).stdout.strip() or 0)
    if got != r.nfr: die(f"joined video has {got} frames, expected {r.nfr}")
    print(f"wrote {od/'video.mp4'} ({r.nfr} frames, {r.dur:.2f}s) in {time.time() - t_start:.0f}s on {n} processes")


def save_events(r, od):
    save(od / "events.json", {"duration": r.dur, "frames": r.nfr, "sfx": r.events, "drops": sorted(r.drops), "risers": r.risers,
                              "hook_end": r.parts[0]["dur"],
                              "style": r.style.get("name", "classic"),
                              "shots": [{**{k: v for k, v in s.items() if not k.startswith("_s")}, "swap_t": [ts for ts, _ in s["_swaps"]]} for s in r.shots],
                              "groups": [{"t0": g["t0"], "t1": g["t1"], "words": [w for w, _, _ in g["w"]]} for g in r.groups],
                              "punches": [{"t0": p["_t0"], "t1": p["_t1"]} for p in r.punches],
                              "stickers": [{"type": s["type"], "t0": s["_t0"], "t1": s["_t1"]} for s in r.stickers],
                              "fx": [{"type": f["type"], "t": f["_t"]} for f in r.fx], "word_count": len(r.words),
                              "transitions": [{"t": round(tr["t"], 3), "name": tr["name"], "d": round(tr["d"], 3)} for tr in r.trans],
                              "visual": r.visual,
                              "anims": [{"t": round(x["_t0"], 3), "type": x["type"], "anim": x.get("anim"), "out": x.get("out")} for x in r.stickers if x.get("anim")]
                                       + [{"t": round(x["_t"], 3), "type": "phone3d", "anim": x.get("enter_anim"), "out": x.get("exit_anim")} for x in r.shots if x["lay"] == "phone3d"]})


def render_frames(r, A, C, a, od):
    want = None
    if a.preview: want = sorted({round(float(x) * FPS) for x in a.preview.split(",")})
    if a.cover:
        cv = r.plan["hooks"][a.variant].get("cover") or r.plan.get("cover") or die("plan.json has no cover")
        part = r.parts[0] if cv.get("part", "hook") == "hook" else r.parts[1]
        want = [round(tspec(cv.get("t", 0.5), part["words"], part["off"]) * FPS)]
    if want is not None: (od / "preview").mkdir(exist_ok=True)
    wr = None
    f0, f1 = (int(x) for x in a.range.split(":")) if a.range else (0, r.nfr)
    if want is None:
        wr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(a.out or od / "video.mp4")], stdin=subprocess.PIPE)
    n = 0; stills = []
    gs = r.style["grade"]
    G = Grader(gs) if (gs.get("segment") or gs.get("tone")) else None
    r.hist = deque(maxlen=6); r.frozen = {}; r.mask = None
    keep_hist = any(f["type"] == "glitch" for f in r.fx) or any(tr["name"] == "glitch" for tr in r.trans)
    has_chat = any(s["type"] == "chat_pill" for s in r.stickers)
    MW, MH = 540, 960
    warm = 6 if keep_hist else 0                  # a worker's chunk renders (and discards) these frames first: glitch history
    s0 = max(0, f0 - warm)
    for p in r.parts:
        if n + p["frames"] <= s0: n += p["frames"]; continue      # a part wholly before this chunk
        if n >= f1: break
        k0 = max(0, s0 - n)                       # first frame of this part to decode; seek straight to it
        ss = ["-ss", f"{max(0.0, k0 / FPS - 0.0005):.4f}"] if k0 else []
        src = p["dir"] / ("room.mp4" if getattr(r, "room", False) else "base.mp4")
        rd = subprocess.Popen(["ffmpeg", "-v", "quiet", *ss, "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        mk = None
        if r.need_mask:
            from segment import segment_part
            mpath = segment_part(p["dir"])        # no-op when the mask is up to date
            mk = subprocess.Popen(["ffmpeg", "-v", "quiet", *ss, "-i", str(mpath), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        last = None; mlast = None; n += k0
        for k in range(k0, p["frames"]):
            if n >= f1: break
            buf = rd.stdout.read(W * H * 3)
            if len(buf) == W * H * 3: last = buf
            elif last is None: die(f"{p['name']}: could not read frames")
            if mk:
                mb = mk.stdout.read(MW * MH)
                if len(mb) == MW * MH: mlast = mb
            if want is not None and n not in want:
                n += 1
                if n > want[-1]: break
                continue
            t = n / FPS
            fr = Image.frombytes("RGB", (W, H), last)
            r.mask = Image.frombytes("L", (MW, MH), mlast) if mlast else None
            if G and G.set and r.mask is not None:
                fax, fay, ffh = r.anchor(t); G.t = t
                fr = G.relight(fr, r.mask, fax, fay, ffh)
            elif G: fr = G.tone(fr)
            if has_chat:
                fax, fay, ffh = r.anchor(t); s = max((ffh or 300) * 1.9, 320)
                r._face = fr.crop((int(fax - s / 2), int(fay - s * 0.55), int(fax + s / 2), int(fay + s * 0.45)))
            out, sh, prect = compose_frame(r, A, fr, t)
            if a.cover:
                cv = r.plan["hooks"][a.variant].get("cover") or r.plan["cover"]
                out = Image.alpha_composite(out, Image.new("RGBA", out.size, (0, 0, 0, 70)))
                title = C.punch(json.dumps([cv["lines"], cv.get("rot", -3)]))
                # default: just above the head, inside the 3:4 profile-grid crop (y 240-1680)
                cax, cay, cfh = r.anchor(t); head_top = (cay - 0.62 * cfh) if cfh else 700
                y = cv.get("y") or max(240 + title.height / 2, min(head_top - title.height / 2 + 60, 900))
                paste_center(out, title, 540, y)
            else:
                apply_fx(r, out, t, "base"); overlays(r, C, out, t, sh, prect); apply_fx(r, out, t)
            if G: out = G.finish(out, n)
            if keep_hist: r.hist.append(np.asarray(out.convert("RGB")))
            if wr:
                if n >= f0: wr.stdin.write(out.convert("RGB").tobytes())
            else:
                f = (r.proj / "out" / f"{r.plan.get('slug', 'reel')}-{a.variant}-cover.jpg") if a.cover else od / "preview" / f"{t:06.2f}.jpg"
                f.parent.mkdir(parents=True, exist_ok=True); out.convert("RGB").save(f, quality=90); stills.append(f)
            if wr and n % 150 == 0: print(f"frame {n}/{r.nfr}", flush=True)
            n += 1
        rd.stdout.close(); rd.kill()
        if mk: mk.stdout.close(); mk.kill()
        if want is not None and n > want[-1]: break
    if wr:
        wr.stdin.close(); wr.wait()
        if not a.range: print(f"wrote {od/'video.mp4'} ({r.nfr} frames, {r.dur:.2f}s)")
    elif stills and not a.cover:
        ims = [Image.open(s).resize((270, 480)) for s in stills]; cols = min(8, len(ims)); rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 270, rows * 480))
        for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 270, (i // cols) * 480))
        sheet.save(od / "sheet.jpg", quality=85); print(f"sheet: {od/'sheet.jpg'}")
    else: print(f"cover: {stills[0]}")


if __name__ == "__main__":
    main()
