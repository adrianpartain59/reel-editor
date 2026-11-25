#!/usr/bin/env python3
"""Builds a split screen reel (references/split-screen-reel.md): full-frame face for the hook, intro and outro, the drawn canvas over the speaker's
face in the body, Instagram captions with the word the speaker is saying in yellow. Reads PROJECT/split_reel.json and PROJECT/canvas/scenes.js.

  split_reel.py PROJECT words                     every word with its number and time
  split_reel.py PROJECT draft                     a first split of the words into caption lines (paste into "caps" and fix by hand)
  split_reel.py PROJECT caps                      the caption lines as they will show, with warnings
  split_reel.py PROJECT store APP_ID              live App Store facts and icon for the store card -> work/store/
  split_reel.py PROJECT preview 0.2,1.0 [name] [w]   stills -> work/<name>
  split_reel.py PROJECT check                     everything that can be checked before rendering
  split_reel.py PROJECT render                    out/<slug>.mp4, out/<slug>-phone.mp4, work/final_sheet.jpg, and the checks on the finished file
  split_reel.py PROJECT audio                     only redo the sound on the last render

The numbers in here are the style. Change them only when the user asks for a different look.
"""
import difflib, json, math, re, subprocess, sys
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import compose as C
import fx
from common import ASSETS, die, run, whisper_model

W, H, FPS, PH = 1080, 1920, 30, 764
MOVE = 0.36                                              # the canvas slides down (and back up) in this long, the footage with it
YELLOW, SIZE = (255, 212, 59, 255), 70
WFULL, WSPLIT = 700, 900                                 # widest caption line: full shot (clear of the like column), split
CANVAS = ASSETS / "graphic-styles/canvas"
clamp = lambda v, a=0.0, b=1.0: max(a, min(b, v))
lerp = lambda a, b, u: a + (b - a) * u
eio = lambda u: 4 * clamp(u) ** 3 if clamp(u) < .5 else 1 - (-2 * clamp(u) + 2) ** 3 / 2
eoc = lambda u: 1 - (1 - clamp(u)) ** 3
def back(u, s=1.9): u = clamp(u) - 1; return 1 + (s + 1) * u ** 3 + s * u ** 2


def setup(arg):
    global PROJ, R, P, SEG, N, DUR, TRK, HOOK, SPLIT, STORE, FOLLOW, SHOTS, CAPY, SLUG
    PROJ = Path(arg).expanduser().resolve(); f = PROJ / "split_reel.json"
    if not f.exists(): die(f"{f} missing (run canvas_init.py PROJECT split and fill it in)")
    R = json.loads(f.read_text()); P = PROJ / "work/parts" / R.get("part", "body")
    if not (P / "track.json").exists(): die("run split_cut.py first")
    SEG = json.loads((P / "segs.json").read_text()); N, DUR = SEG["frames"], SEG["duration"]; TRK = json.loads((P / "track.json").read_text())["segs"]
    SLUG, HOOK, SPLIT, STORE, FOLLOW = R["slug"], R["hook"], R["split"], R.get("store"), R.get("follow"); CAPY = R.get("cap_y"); SHOTS = R.get("shots") or auto_shots()


# ------------------------------------------------------------------ face track and camera
def face(t):
    for a, b, s in TRK:
        if a <= t + .002 < b + .002: ts = [q[0] for q in s]; return tuple(float(np.interp(t, ts, [q[k] for q in s])) for k in (1, 2, 3))
    s = TRK[-1][2][-1]; return s[1], s[2], s[3]


def seg_at(t): return next((s for s in SEG["segs"] if s["t0"] <= t + .002 < s["t1"]), SEG["segs"][-1])          # .002: a cut at 10.3667 is frame 311, at 10.36667


def over_head(a, b):
    """is anything above the speaker's head in this stretch? (text hook, App Store card, follow card)"""
    o = [(0, HOOK["out"])] + ([(STORE["in"], STORE["out"])] if STORE else []) + ([(FOLLOW["in"], DUR)] if FOLLOW else []); return any(x < b and y > a for x, y in o)


def auto_shots():
    """One slow push per full-frame clip. Wide (1.00) when something sits above the speaker's head, a little tighter when nothing does, so the
    jump cuts change size."""
    out = []
    for s in SEG["segs"]:
        a, b = s["t0"], s["t1"]
        if a >= SPLIT["in"] + MOVE and b <= SPLIT["out"]: continue
        z = 1.0 if over_head(a, b) else 1.03; out.append([a, b + .4, z, z + min(.045, .008 * (b - a)), HOOK.get("face_x", 445) if a < HOOK["end"] - .05 and HOOK.get("cards") else 540])
    return out


@lru_cache(None)
def room(t0):
    """(dx, dy, keep x, keep y) for the shot starting at t0. When the speaker is framed so close that the speaker's hair reaches the thing above the speaker's head, or the speaker's
    cheek the cards, the shot moves down and left and the empty wall above and beside the speaker is stretched to fill: the speaker's face is never touched."""
    sh = next((s for s in SHOTS if abs(s[0] - t0) < .01), None)
    if not sh or R.get("room") is False: return 0, 0, 0, 0
    a, b = sh[0], min(sh[1], DUR - .05); fr = lambda t: (full_cam(t), face(t)); ds = lambda x, y, st: [t for t in np.arange(max(a, x), min(b, y), st) if seg_at(t)["t0"] <= a + .05]
    dx = dy = kx = ky = 0
    if HOOK.get("cards") and a < HOOK["end"] - .05:
        T = card_times(); right = max([(f[0] - c[1]) * c[0] + .46 * f[2] * c[0] for c, f in map(fr, ds(T[0], HOOK["out"], .1))] or [0]); dx = int(clamp(right - 752, 0, 140)) if right > 771 else 0; kx = right - dx + 14
    for x, y, low, k in ([(0.2, HOOK["out"], 226 + 100 * len(HOOK.get("text") or []), .98)] if HOOK.get("text") else []) + ([(STORE["in"], STORE["out"], 464, .90)] if STORE else []) + ([(FOLLOW["in"], DUR, 394, .90)] if FOLLOW else []):
        hair = min([(f[1] - c[2]) * c[0] - k * f[2] * c[0] for c, f in map(fr, ds(x, y, .1))] or [9e9])
        if hair < low + 4 and low + 12 - hair > dy: dy = int(clamp(low + 12 - hair, 0, 130)); ky = hair + dy - 14
    return dx, dy, kx, ky


@lru_cache(None)
def _map(n, keep, d):
    """output -> source along one axis: shifted by d up to keep, then smoothly on to the edge"""
    o = np.arange(n, dtype=float); s = o + d; m = o > keep; u = (o[m] - keep) / (n - 1 - keep); span = n - 1 - keep - d; s[m] = keep + d + span * (u + (d / span) * (u - u * u)); s = np.clip(s, 0, n - 1); i = np.floor(s).astype(int); return i, np.minimum(i + 1, n - 1), (s - i).astype(np.float32)


def make_room(im, dx, dy, kx, ky):
    g = np.asarray(im).astype(np.float32)
    if dy: i, j, f = _map(H, H - 1 - int(ky), dy); g = g[::-1]; g = (g[i] * (1 - f)[:, None, None] + g[j] * f[:, None, None])[::-1]
    if dx: i, j, f = _map(W, int(kx), dx); g = g[:, i] * (1 - f)[None, :, None] + g[:, j] * f[None, :, None]
    return Image.fromarray(g.round().astype(np.uint8))


def shot_t0(t): return next((x[0] for x in reversed(SHOTS) if x[0] <= t + .001), SHOTS[0][0])


def split(t): return eio((t - SPLIT["in"]) / MOVE) if t < SPLIT["in"] + MOVE else 1 - eio((t - SPLIT["out"]) / MOVE)


def full_cam(t):
    fx_, fy, fh = face(t); f = None
    for a, b, z0, z1, tx in SHOTS:
        if a <= t + .002 < b: z = lerp(z0, z1, clamp((t - a) / (b - a))); f = (z, clamp(fx_ - tx / z, 0, W - W / z), clamp(fy - 1000 / z, 0, H - H / z))
    return f


def camera(t):
    """(zoom, x0, y0): output pixel = (source - (x0, y0)) * zoom. In the split the speaker's hair sits just under the seam."""
    fx_, fy, fh = face(t); s = split(t); f = full_cam(t); g = seg_at(t); zs = 1.0 + 0.006 * max(0, t - g["t0"]); sp = (zs, clamp(fx_ - 540 / zs, 0, W - W / zs), fy - (824 + 0.90 * fh * zs) / zs)
    if f is None or s >= 1: return sp
    return f if s <= 0 else tuple(lerp(p, q, s) for p, q in zip(f, sp))


def footage(fr, t):
    z, x0, y0 = camera(t); s = split(t); top = int(round(PH * s)); out = Image.new("RGB", (W, H), (18, 18, 18)); ya = y0 + top / z; yb = y0 + H / z
    if ya < 0: top2 = int(math.ceil(-y0 * z)); ya = y0 + top2 / z; top = max(top, top2)
    yb = min(yb, H); h = int(round((yb - ya) * z)); out.paste(fr.resize((W, min(h, H - top)), Image.BICUBIC, box=(x0, ya, x0 + W / z, yb)), (0, top))
    if s < 1:
        dx, dy, kx, ky = room(shot_t0(t)); dx, dy = int(round(dx * (1 - s))), int(round(dy * (1 - s)))
        if dx or dy: out = make_room(out, dx, dy, int(kx), int(ky))
    return out, s


# ------------------------------------------------------------------ captions
def words():
    """[[shown, start, end], ...]. "times" moves a word (by number), "add" puts back one whisper lost, "join" turns a run of words into one (or
    drops some), "fix" shows a word differently (one word may become two)."""
    raw = [w[:3] for w in json.loads((PROJ / f"work/{R.get('part', 'body')}_words.json").read_text())]; tm = {int(k.lstrip("w")): v for k, v in R.get("times", {}).items()}
    for k, v in tm.items(): raw[k][1] = v
    for q, at in R.get("add", []): raw.append([q, at, at + .2])
    raw.sort(key=lambda w: w[1]); out, i, nz = [], 0, lambda s: re.sub(r"[^\w$%'-]", "", s.lower())
    while i < len(raw):
        hit = next((j for j in R.get("join", []) if [nz(x) for x in j[:-1]] == [nz(w[0]) for w in raw[i:i + len(j) - 1]]), None)
        if hit: out.append([hit[-1], raw[i][1], raw[i + len(hit) - 2][2]]); i += len(hit) - 1
        else: t, a, b = raw[i]; out.append([R.get("fix", {}).get(t, R.get("fix", {}).get(t.rstrip(".,?!"), t)), a, max(b, a + .05)]); i += 1
    return out


@lru_cache(None)
def fnt(): return C.font("semibold", SIZE)
def in_split(t): return SPLIT["in"] + .25 < t < SPLIT["out"] + .2


@lru_cache(None)
def groups():
    ws, gs, k = words(), [], 0
    for line in R["caps"]:
        toks, n, g = line.split(), 0, []
        while n < len(toks):
            if k >= len(ws): die(f"caps: {line!r} runs past the last word")
            w = ws[k]; want = w[0].split(); got = toks[n:n + len(want)]
            if [C.norm(x) for x in got] != [C.norm(x) for x in want]: die(f"caps: in {line!r} the speaker says {w[0]!r} (word {k}, {w[1]:.2f} s) where the caption has {' '.join(got)!r}. Every word appears once, in order; use fix or join for a mishearing")
            g.append([" ".join(got), w[1], w[2]]); n += len(want); k += 1
        gs.append({"w": g, "split": in_split(g[0][1])})
    if k < len(ws): die(f"caps stop before {ws[k][0]!r} at {ws[k][1]:.2f} s")
    for i, g in enumerate(gs):
        nx = gs[i + 1]["w"][0][1] if i + 1 < len(gs) else DUR; g["t0"], g["t1"] = g["w"][0][1], min(nx, g["w"][-1][2] + .5); t = [w[0] for w in g["w"]]; t[-1] = t[-1].rstrip(".,;:"); g["txt"] = t; g["px"] = fnt().getlength(" ".join(t))
    return gs


WEAK = set("or and the a an to of not that is are with like for in on at your you're my be as than if so but because their how from about this these it's we you i they're there's just has have i'm i'd called number".split())


def draft():
    """thoughts of two to five words: broken at sentence ends and where the screen splits, never after "to" or "the" when it can be helped"""
    ws, out, cl = words(), [], []
    def lines(c):
        n, sp = len(c), in_split(c[0][1]); lim = WSPLIT if sp else WFULL; best, bk = [0.0] + [1e18] * n, [0] * (n + 1)
        for j in range(1, n + 1):
            for i in range(max(0, j - 5), j):
                t = [w[0] for w in c[i:j]]; px = fnt().getlength(" ".join(t)); d = (c[j][1] if j < n else c[-1][2]) - c[i][1]
                v = best[i] + (1e6 if px > lim and j - i > 1 else 0) + .4 * (j - i - 3.3) ** 2 + (4 if C.norm(t[-1]) in WEAK and j < n else 0) + (6 if j - i == 1 and n > 1 else 0) + (8 if d < .35 else 0) - (1.5 if t[-1][-1] == "," else 0) + (4 if any(x[-1] == "," for x in t[:-1]) else 0)
                if v < best[j]: best[j], bk[j] = v, i
        j, cut = n, []
        while j: cut.append((bk[j], j)); j = bk[j]
        return [" ".join(w[0] for w in c[i:k]).rstrip(".,") for i, k in reversed(cut)]
    for i, w in enumerate(ws):
        cl.append(w); nx = ws[i + 1] if i + 1 < len(ws) else None
        g0, g1 = seg_at(w[1] + .02), seg_at(nx[1] + .02) if nx else None                            # a jump of more than half a second in the raw take is a new line of the speaker's
        if not nx or w[0][-1] in ".?!" or in_split(nx[1]) != in_split(cl[0][1]) or (g1 is not g0 and not 0 <= g1["src_in"] - g0["src_out"] < .5): out += lines(cl); cl = []
    print(json.dumps(out, indent=1, ensure_ascii=False))


def caps():
    for g in groups():
        lim = WSPLIT if g["split"] else WFULL; d = g["t1"] - g["t0"]; warn = ([f"TOO WIDE {g['px']:.0f} px, max {lim}"] if g["px"] > lim else []) + (["on screen under 0.25 s, join it to a neighbour"] if d < .25 else []) + (["one line for 6+ words"] if len(g["w"]) > 5 else [])
        print(f"{g['t0']:6.2f}-{g['t1']:6.2f} {'split' if g['split'] else 'full '} {g['px']:4.0f}  {' '.join(g['txt'])}" + ("   <-- " + "; ".join(warn) if warn else ""))


@lru_cache(None)
def cap_img(gi, j, k, hard=False):
    """White SF Pro Semibold (the speaker's Instagram caption look), the word the speaker is saying in yellow, a soft shadow; deeper under the chin, where the speaker's
    shirt can be light."""
    g = groups()[gi]; f = fnt(); t = g["txt"]; lw = f.getlength(" ".join(t)); pad = 44; cw, ch = int(lw) + pad * 2, int(SIZE * 1.2) + pad * 2; txt = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(txt); x = (cw - lw) / 2
    for n, w in enumerate(t): d.text((x, pad), w, font=f, fill=YELLOW if n == j else (255, 255, 255, 255)); x += f.getlength(w + " ")
    a = txt.getchannel("A"); out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    for o, bl, dy in (((150, 16, 0), (235, 7, 2), (255, 3, 2)) if hard else ((95, 15, 0), (185, 4, 3))): sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); sh.paste((0, 0, 0, o), (0, 0), a); out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(bl)), (0, dy))
    out.alpha_composite(txt); al = [.35, .7, 1][k]
    if al < 1: out.putalpha(out.getchannel("A").point(lambda v: int(v * al)))
    return out


@lru_cache(None)
def chin_y(t0):
    """one steady caption height per full-frame shot: just under the lowest the speaker's chin gets"""
    sh = next((s for s in SHOTS if abs(s[0] - t0) < .01), SHOTS[-1]); lo = 0
    for t in np.arange(sh[0], min(sh[1], DUR) - .05, .2):
        if split(t) > .05 or seg_at(t)["t0"] > sh[0] + .05: continue
        c = full_cam(t); fx_, fy, fh = face(t); lo = max(lo, (fy - c[2]) * c[0] + .5 * fh * c[0])
    return clamp(lo + room(sh[0])[1] + 42, 1385, 1452)


def cap_y(t):
    """(y, alpha, full shot?). It fades across the move instead of sliding over the speaker's face."""
    s = split(t)
    if CAPY: full = [y for a, y in CAPY if a <= t + .001][-1]
    else: full = chin_y(shot_t0(t))
    return (PH + 12 if s > .5 else full), clamp((abs(2 * s - 1) - .35) / .4), s <= .5


def captions(im, t):
    for gi, g in enumerate(groups()):
        if g["t0"] <= t < g["t1"]:
            j = max([i for i, w in enumerate(g["w"]) if w[1] <= t + .001] or [0]); y, al, full = cap_y(t)
            if al > 0: C.paste_center(im, cap_img(gi, j, min(2, int((t - g["t0"]) * FPS + .001)), full), 540, y, 1.0, al)
            return


# ------------------------------------------------------------------ hook: cards popping up with blurred names, and the text hook
def card_times(): n = len(HOOK.get("cards") or []); return [HOOK.get("first", .86) + i * HOOK.get("every", .18) for i in range(n)]


@lru_cache(None)
def cards():
    names = HOOK.get("cards") or []
    if not names: return []
    d = PROJ / "work/cards"; d.mkdir(parents=True, exist_ok=True); (d / "names.json").write_text(json.dumps(names)); run(["node", str(CANVAS / "panel_engine.js"), "cards", str(d / "names.json"), str(d)]); out = []
    for i in range(len(names)):
        c = Image.open(d / f"card{i + 1}.png").convert("RGBA"); n = Image.open(d / f"name{i + 1}.png").convert("RGBA").filter(ImageFilter.GaussianBlur(19)); n.putalpha(n.getchannel("A").point(lambda v: min(255, int(v * 2.3)))); c.alpha_composite(n); out.append(c.resize((c.width // 2, c.height // 2), Image.LANCZOS))
    return out


def hook_cards(im, t):
    T, o0 = card_times(), HOOK["out"]
    if not T or not T[0] <= t < o0 + .4: return
    n = len(T); pitch = min(147, 735 / n); k = min(1, pitch / 147); y0 = 806 - pitch * (n - 1) / 2 if n != 5 else 512       # beside the speaker's face, under the text hook
    for i in range(n):
        u = (t - T[i]) / .2; o = clamp((t - o0 - i * .03) / .18)
        if u <= 0 or o >= 1: continue
        s = (lerp(.3, 1, back(u, 2.4)) if u < 1 else 1) * k; a = clamp((t - T[i]) / .06) * (1 - o); c = cards()[i]; w, h = int(c.width * s), int(c.height * s); r = c.resize((w, h), Image.BILINEAR)
        if a < 1: r.putalpha(r.getchannel("A").point(lambda v: int(v * a)))
        im.alpha_composite(r, (int(896 - w / 2 + 120 * eio(o)), int(y0 + i * pitch + math.sin((t - T[i]) * 1.7 + i) * 3 - h / 2)))


@lru_cache(None)
def hook_text():
    """Black SF Pro Bold on white; the background hugs each line and the corners between lines are rounded, as Instagram draws it."""
    L = HOOK["text"]; S = 3; size = 74; f = C.font("bold", size * S); lh = 100; px, r, pad = 30, 22, 40; ws = [f.getlength(l) / S for l in L]; w = int(max(ws) + px * 2 + pad * 2); h = lh * len(L) + pad * 2; m = Image.new("L", (w * S, h * S), 0); d = ImageDraw.Draw(m)
    for i, lw in enumerate(ws): d.rounded_rectangle([(w / 2 - lw / 2 - px) * S, (pad + i * lh) * S, (w / 2 + lw / 2 + px) * S, (pad + (i + 1) * lh + (1 if i < len(ws) - 1 else 0)) * S], r * S, fill=255)
    for i in range(len(ws) - 1): n = min(ws[i], ws[i + 1]) / 2 + px; d.rectangle([(w / 2 - n) * S, (pad + (i + 1) * lh - r) * S, (w / 2 + n) * S, (pad + (i + 1) * lh + r) * S], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(7 * S)).point(lambda v: 255 if v > 127 else 0).filter(ImageFilter.GaussianBlur(1.2)); im = Image.new("RGBA", m.size, (0, 0, 0, 0)); sh = Image.new("RGBA", m.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 70), (0, 0), m); im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9 * S)), (0, 4 * S)); im.paste((255, 255, 255, 255), (0, 0), m); d = ImageDraw.Draw(im)
    for i, l in enumerate(L): d.text((w * S / 2, (pad + i * lh + lh / 2) * S), l, font=f, fill=(12, 12, 12, 255), anchor="mm")
    return im.resize((w, h), Image.LANCZOS)


def text_hook(im, t):
    o = clamp((t - HOOK["out"]) / .2)                                    # on screen from the first frame, up and out with the cards
    if HOOK.get("text") and o < 1: C.paste_center(im, hook_text(), 540, 226 + 50 * len(HOOK["text"]) - 50 * eio(o), 1.0, 1 - o)


# ------------------------------------------------------------------ the App Store page, when the speaker names the app
def store_fetch(app_id):
    d = PROJ / "work/store"; d.mkdir(parents=True, exist_ok=True); j = json.loads(run(["curl", "-s", "-m", "25", f"https://itunes.apple.com/lookup?id={app_id}&country=us"]).stdout)["results"]
    if not j: die(f"no US App Store app {app_id}")
    r = j[0]; n = r.get("userRatingCount", 0); facts = {"id": app_id, "name": r["trackName"], "genre": r["primaryGenreName"], "rating": round(r.get("averageUserRating", 0), 2), "ratings": n, "count": f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n // 1000}K" if n >= 1000 else str(n)}
    run(["curl", "-s", "-m", "25", "-o", str(d / "icon.png"), r["artworkUrl512"].replace("512x512bb", "1024x1024bb")]); (d / "facts.json").write_text(json.dumps(facts, indent=1)); print(json.dumps(facts))


@lru_cache(None)
def store_img():
    """The top of the app's page as an iPhone lays it out: live icon, name, category, rating. The subtitle and the screenshots stay out."""
    f = PROJ / "work/store/facts.json"
    if not f.exists(): die(f"run: split_reel.py PROJECT store {STORE['app']}")
    F = json.loads(f.read_text()); S, w, h, pad = 3, 960, 244, 40; im = Image.new("RGBA", ((w + 2 * pad) * S, (h + 2 * pad) * S), (0, 0, 0, 0)); sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); box = [pad * S, pad * S, (pad + w) * S, (pad + h) * S]
    ImageDraw.Draw(sh).rounded_rectangle([box[0], box[1] + 8 * S, box[2], box[3] + 8 * S], 46 * S, fill=(0, 0, 0, 140)); im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18 * S))); d = ImageDraw.Draw(im); d.rounded_rectangle(box, 46 * S, fill=(28, 28, 30, 255))
    ic = Image.open(PROJ / "work/store/icon.png").convert("RGB").resize((184 * S, 184 * S), Image.LANCZOS); m = Image.new("L", ic.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, ic.width - 1, ic.height - 1], 42 * S, fill=255); im.paste(ic, ((pad + 30) * S, (pad + 30) * S), m)
    x = pad + 244; T = lambda s, yy, kind, size, col, xx=None: d.text(((xx if xx is not None else x) * S, (pad + yy) * S), s, font=C.font(kind, size * S), fill=col, anchor="lm")
    T("APP STORE", 44, "semibold", 25, (152, 152, 159, 255), x)
    nm = STORE.get("name", F["name"]); sz = 50
    while C.font("bold", sz * S).getlength(nm) > 690 * S: sz -= 2
    T(nm, 94, "bold", sz, (255, 255, 255, 255)); T(F["genre"], 142, "regular", 34, (152, 152, 159, 255)); T(f"{F['rating']:.1f}", 198, "bold", 40, (255, 255, 255, 255)); sx = x + 76
    for layer in (0, 1):
        pts = Image.new("L", im.size, 0); q = ImageDraw.Draw(pts)
        for i in range(5): cx, cy = sx + 22 + i * 44, pad + 198; q.polygon([((cx + math.cos(-math.pi / 2 + k * math.pi / 5) * (19 if k % 2 == 0 else 8.2)) * S, (cy + math.sin(-math.pi / 2 + k * math.pi / 5) * (19 if k % 2 == 0 else 8.2)) * S) for k in range(10)], fill=255)
        if layer: q.rectangle([(sx + F["rating"] * 44) * S, 0, im.width, im.height], fill=0)
        im.paste((255, 159, 10, 255) if layer else (84, 84, 90, 255), (0, 0), pts)
    cnt = f"{F['count']} Ratings"; cnt = cnt if sx + 238 + C.font("regular", 34 * S).getlength(cnt) / S < pad + w - 30 - 168 - 14 else F["count"]; T(cnt, 198, "regular", 34, (152, 152, 159, 255), sx + 238); bx, by = pad + w - 30 - 84, pad + 184; d.rounded_rectangle([(bx - 84) * S, (by - 37) * S, (bx + 84) * S, (by + 37) * S], 37 * S, fill=(10, 132, 255, 255)); d.text((bx * S, by * S), "Get", font=C.font("bold", 38 * S), fill=(255, 255, 255, 255), anchor="mm")
    return im.resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)


def store_card(im, t):
    if not STORE or not STORE["in"] - .001 <= t < STORE["out"] + .2: return
    u = (t - STORE["in"] + 1 / FPS) / .24; o = clamp((t - STORE["out"]) / .18); s = (lerp(.45, 1, back(u, 2.2)) if u < 1 else 1) * (1 - .12 * eio(o)); C.paste_center(im, store_img(), 540, 342 + 30 * (1 - eoc(u)) - 30 * eio(o), s, clamp((t - STORE["in"] + 1 / FPS) / .07) * (1 - o))


# ------------------------------------------------------------------ outro: the follow card
CWD, CHT = 800, 164


@lru_cache(None)
def avatar():
    t = FOLLOW.get("photo", FOLLOW["tap"] + .74); S = 4; fr = grab(P / "base.mp4", int(round(t * FPS)), W, H); x, y, fh = face(t); r = fh * .80; im = fr.crop((int(x - r), int(y - r * 1.08), int(x + r), int(y + r * .92))).resize((104, 104), Image.LANCZOS); out = Image.new("RGBA", (124, 124), (0, 0, 0, 0)); yy, xx = np.mgrid[0:124 * S, 0:124 * S] / (124 * S); u = np.clip((xx + (1 - yy)) / 2, 0, 1)
    st = np.array([[254, 218, 117], [250, 126, 30], [214, 41, 118], [150, 47, 191]], float); q = u * 3; i0 = np.clip(q.astype(int), 0, 2); k = (q - i0)[..., None]; ring = Image.fromarray((st[i0] * (1 - k) + st[i0 + 1] * k).astype(np.uint8)).convert("RGBA"); m = Image.new("L", (124 * S, 124 * S), 0); d = ImageDraw.Draw(m); d.ellipse([0, 0, 124 * S - 1, 124 * S - 1], fill=255); d.ellipse([5 * S, 5 * S, 119 * S, 119 * S], fill=0); ring.putalpha(m); out.alpha_composite(ring.resize((124, 124), Image.LANCZOS))
    mm = Image.new("L", (104 * S, 104 * S), 0); ImageDraw.Draw(mm).ellipse([0, 0, 104 * S - 1, 104 * S - 1], fill=255); out.paste(im, (10, 10), mm.resize((104, 104), Image.LANCZOS)); return out


def follow_img(t):
    S, tap = 2, FOLLOW["tap"]; im = Image.new("RGBA", ((CWD + 80) * S, (CHT + 80) * S), (0, 0, 0, 0)); sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); rr = lambda d, b, r, f: d.rounded_rectangle(b, r, fill=f); rr(ImageDraw.Draw(sh), [40 * S, 48 * S, (40 + CWD) * S, (48 + CHT) * S], 44 * S, (0, 0, 0, 130)); im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18 * S)))
    d = ImageDraw.Draw(im); rr(d, [40 * S, 40 * S, (40 + CWD) * S, (40 + CHT) * S], 44 * S, (24, 24, 26, 250)); im.alpha_composite(avatar().resize((124 * S, 124 * S), Image.LANCZOS), (60 * S, 60 * S)); u = eoc((t - FOLLOW["line_at"]) / .25) if FOLLOW.get("line") else 0; d = ImageDraw.Draw(im); d.text((206 * S, lerp(122, 98, u) * S), FOLLOW["name"], font=C.font("bold", 43 * S), fill=(255, 255, 255, 255), anchor="lm")
    if u > 0: d.text((206 * S, 150 * S), FOLLOW["line"], font=C.font("semibold", 34 * S), fill=(255, 212, 59, int(255 * u)), anchor="lm")
    done = t >= tap + .10; k = 1 - .10 * math.sin(math.pi * clamp((t - tap + .06) / .24)); bw, bh = 232 * k, 88 * k; bx, by = 40 + CWD - 140, 40 + CHT / 2; rr(d, [(bx - bw / 2) * S, (by - bh / 2) * S, (bx + bw / 2) * S, (by + bh / 2) * S], int(24 * S * k), (58, 58, 62, 255) if done else (0, 149, 246, 255)); d.text((bx * S, by * S), "Following" if done else "Follow", font=C.font("bold", int(40 * S * k)), fill=(255, 255, 255, 255), anchor="mm"); v = clamp((t - tap + .30) / .28)
    if v > 0 and t < tap + .35: a = int(150 * min(1, v * 2) * (1 - clamp((t - tap - .1) / .25))); r = lerp(64, 34, eoc(v)) * (1 + .9 * clamp((t - tap - .04) / .25)); o = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(o).ellipse([(bx - r) * S, (by - r) * S, (bx + r) * S, (by + r) * S], fill=(255, 255, 255, a)); im.alpha_composite(o)
    return im


def follow_card(im, t):
    if not FOLLOW or t < FOLLOW["in"]: return
    u = (t - FOLLOW["in"]) / .28; s = lerp(.6, 1, back(u, 1.8)) if u < 1 else 1; al = clamp((t - FOLLOW["in"]) / .1); c = follow_img(t); w, h = int(c.width / 2 * s), int(c.height / 2 * s); r = c.resize((w, h), Image.LANCZOS)
    if al < 1: r.putalpha(r.getchannel("A").point(lambda v: int(v * al)))
    im.alpha_composite(r, (int(540 - w / 2), int(312 - h / 2 - 60 * (1 - eoc(u)))))


# ------------------------------------------------------------------ one frame
def frame(fr, panel, t):
    im, s = footage(fr, t)
    if t < .2:                                                           # the snap-out every reel opens with
        u = eoc((t + .5 / FPS) / .2); z = lerp(1.35, 1, u); w, h = W / z, H / z; im = im.resize((W, H), Image.BICUBIC, box=((W - w) / 2, (H - h) * .45, (W + w) / 2, (H - h) * .45 + h)); b = clamp(1 - t / .13)
        if b > 0: im = fx.zoom_blur(im.filter(ImageFilter.GaussianBlur(16 * b)), 1.0, .12 * b)
    im = im.convert("RGBA")
    if s > 0 and panel is not None: im.paste(panel, (0, int(round(PH * s)) - PH))
    hook_cards(im, t); text_hook(im, t); store_card(im, t); captions(im, t); follow_card(im, t); return im.convert("RGB")


def grab(path, n, w, h): return Image.frombytes("RGB", (w, h), run(["ffmpeg", "-v", "error", "-ss", f"{max(0, (n - .5) / FPS):.4f}", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], text=False).stdout)


def panel_span(): a = math.floor((SPLIT["in"] - .05) * FPS) / FPS; b = math.ceil((SPLIT["out"] + MOVE + .2) * FPS) / FPS; return a, b, int(round((b - a) * FPS))


def panel_video():
    sc = PROJ / R.get("scenes", "canvas/scenes.js"); out = PROJ / "work/panel.mp4"; a, b, n = panel_span(); key = f"{a:.4f} {b:.4f} {max(sc.stat().st_mtime, (CANVAS / 'panel_engine.js').stat().st_mtime)}"; mark = PROJ / "work/panel.key"
    if not out.exists() or not mark.exists() or mark.read_text() != key: run(["node", str(sc), "render", str(out), f"{a:.4f}", f"{b:.4f}"]); mark.write_text(key)
    return out


def panel_n(t): a, b, n = panel_span(); k = int(round((t - a) * FPS)); return k if 0 <= k < n else None


def panel_still(t):
    """one panel frame without rendering the whole panel (previews while the scenes are being drawn)"""
    d = PROJ / "work/pv"; d.mkdir(exist_ok=True); f = d / "p.mp4"; run(["node", str(PROJ / R.get("scenes", "canvas/scenes.js")), "render", str(f), f"{t:.5f}", f"{t + 1 / FPS:.5f}"]); return grab(f, 0, W, PH)


def preview(ts, name="preview.jpg", w=360):
    h = w * 16 // 9; cols = min(7, len(ts)); sheet = Image.new("RGB", (cols * (w + 8), ((len(ts) + cols - 1) // cols) * (h + 8)), (70, 70, 70))
    for k, t in enumerate(ts): n = min(N - 1, int(round(t * FPS))); t = n / FPS; im = frame(grab(P / "base.mp4", n, W, H), panel_still(t) if split(t) > 0 else None, t); ImageDraw.Draw(im).text((20, 60), f"{t:.2f}", fill=(0, 255, 255), font=C.font("bold", 40)); sheet.paste(im.resize((w, h), Image.LANCZOS), ((k % cols) * (w + 8), (k // cols) * (h + 8)))
    sheet.save(PROJ / "work" / name, quality=90); print(PROJ / "work" / name)


# ------------------------------------------------------------------ sound: the speaker's voice, one pop per pop-in, nothing else
def loud(args): e = subprocess.run(["ffmpeg", "-hide_banner", *args, "-f", "null", "-"], capture_output=True, text=True).stderr; return json.loads(e[e.rindex("{"):e.rindex("}") + 1])


def add_pops(pre, db=-9.0):
    at = R.get("pops", [STORE["in"]] if STORE else [])
    if not at: return
    rd = lambda f: np.frombuffer(run(["ffmpeg", "-v", "error", "-i", str(f), "-ar", "48000", "-ac", "2", "-f", "f32le", "-"], text=False).stdout, np.float32).reshape(-1, 2).copy(); x = rd(pre); import sfx_pack; sfx_pack.ensure(); p = rd(ASSETS / "sfx/lib/pop/pop_01.wav"); r = lambda z, w: 20 * np.log10(np.sqrt(np.mean(z[: len(z) // w * w].reshape(-1, w, 2) ** 2, axis=(1, 2))) + 1e-9); lv = r(x, 19200); sp = float(np.median(lv[lv > lv.max() - 20])); p *= 10 ** ((sp + db - float(r(p, 2400).max())) / 20)
    for t in at: i = int(round((t - .007) * 48000)); n = min(len(p), len(x) - i); x[i:i + n] += p[:n]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", "48000", "-ac", "2", "-i", "-", "-c:a", "pcm_f32le", pre + ".tmp.wav"], input=x.tobytes(), check=True); Path(pre + ".tmp.wav").replace(pre)


def audio():
    silent = PROJ / "work/silent.mp4"; chain = json.loads((ASSETS / "styles/cinematic.json").read_text())["mix"]["voice_chain"]; pre = str(PROJ / "work/voice_pre.wav"); run(["ffmpeg", "-v", "error", "-y", "-i", str(P / "voice.wav"), "-af", chain, "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", pre]); add_pops(pre); gain = -12 - float(loud(["-i", pre, "-af", "loudnorm=print_format=json"])["input_i"]); ceil = -1.6; (PROJ / "out").mkdir(exist_ok=True); out = PROJ / f"out/{SLUG}.mp4"
    for _ in range(5):
        lim = f"aresample=192000,alimiter=limit={10 ** (ceil / 20):.3f}:attack=3:release=60:level=false,aresample=48000"
        for _ in range(4):
            got = float(loud(["-i", pre, "-af", f"volume={gain:.2f}dB,{lim},loudnorm=print_format=json"])["input_i"])
            if abs(got + 12) < .15: break
            gain += -12 - got
        run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", pre, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", f"volume={gain:.2f}dB,{lim},apad", "-shortest", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)]); tp = float(loud(["-i", str(out), "-vn", "-af", "loudnorm=print_format=json"])["input_tp"])
        if tp <= -1.0: break
        ceil -= tp + 1.15
    run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-c:v", "libx264", "-preset", "medium", "-b:v", "3400k", "-maxrate", "4200k", "-bufsize", "8000k", "-c:a", "copy", "-movflags", "+faststart", str(PROJ / f"out/{SLUG}-phone.mp4")])


def render():
    pv = panel_video(); a, b, n_p = panel_span(); src = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(P / "base.mp4"), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, bufsize=W * H * 3); pan = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(pv), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, bufsize=W * PH * 3)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-profile:v", "high", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", str(PROJ / "work/silent.mp4")], stdin=subprocess.PIPE)
    for n in range(N):
        t = n / FPS; raw = src.stdout.read(W * H * 3)
        if len(raw) < W * H * 3: die(f"base.mp4 ended at frame {n} of {N}")
        panel = Image.frombytes("RGB", (W, PH), pan.stdout.read(W * PH * 3)) if panel_n(t) is not None else None; enc.stdin.write(frame(Image.frombytes("RGB", (W, H), raw), panel, t).tobytes())
        if n % 300 == 0: print(f"{n} / {N}", flush=True)
    enc.stdin.close(); enc.wait(); src.kill(); pan.kill(); audio(); qa()


# ------------------------------------------------------------------ checks
def check():
    bad, note = [], []; say = bad.append
    for g in groups():
        lim = WSPLIT if g["split"] else WFULL
        if g["px"] > lim: say(f"caption {' '.join(g['txt'])!r} is {g['px']:.0f} px wide, max {lim} ({'split' if g['split'] else 'full shot'})")
        if g["t1"] - g["t0"] < .25: say(f"caption {' '.join(g['txt'])!r} shows for {g['t1'] - g['t0']:.2f} s")
    if HOOK.get("text"):
        wd = max(C.font("bold", 74).getlength(l) for l in HOOK["text"]) + 60
        if wd > 1000: say(f"text hook is {wd:.0f} px wide, max 1000; break it into another line")
        if len(HOOK["text"]) > 2: say("text hook over two lines; it will reach the speaker's hair")
    else: say("no text hook")
    T = card_times()
    if T and T[-1] > 2.4: say(f"the last hook card lands at {T[-1]:.2f} s; all of them by about 2 s")
    for nm, a, b in (("text hook", 0, HOOK["out"]), *(((("App Store card"), STORE["in"], STORE["out"]),) if STORE else ()), *((("follow card", FOLLOW["in"], DUR),) if FOLLOW else ())):
        if max(split(a + .01), split(min(b, DUR - .05) - .01)) > .02: say(f"the {nm} ({a:.2f}-{b:.2f}) runs into the split; move it or the split")
    for sh in SHOTS:
        dx, dy, _, _ = room(sh[0])
        if dx or dy: note.append(f"shot at {sh[0]:.2f}: made {dx} px of room beside the speaker and {dy} px above by stretching the wall; look at it")
        if dx >= 140 or dy >= 130: say(f"shot at {sh[0]:.2f}: the speaker is framed too close for the cards or the thing above the speaker's head; drop the cards (\"cards\": [], face_x 540)")
    if SPLIT["in"] < HOOK["out"] + .2: say("the split starts before the hook is off the screen")
    if SPLIT["in"] - HOOK["end"] > 9: say(f"{SPLIT['in'] - HOOK['end']:.1f} s of plain face between the hook and the canvas: start the split earlier, with cells that have no number (head(c, t, null, ...)) for what the speaker says before point one")
    for g in groups():
        for e, nm in ((SPLIT["in"], "open"), (SPLIT["out"], "close")):
            if e + .02 < g["t0"] < e + MOVE * .5: say(f"caption {' '.join(g['txt'])!r} starts {g['t0'] - e:.2f} s into the split's {nm}, so it flashes in the wrong place: move split.{'in' if nm == 'open' else 'out'} to {g['t0'] - .23:.2f}")
    if FOLLOW and not FOLLOW.get("name"): say("follow.name is empty: the display name shown on the follow card")
    if FOLLOW and DUR - FOLLOW["in"] < 2.2: say(f"the follow card is up for {DUR - FOLLOW['in']:.1f} s; start it earlier, at least 2.2 s before the end")
    if FOLLOW and DUR - FOLLOW["tap"] < .9: say("the follow tap is under 0.9 s from the end, so \"Following\" is hardly seen; tap earlier")
    if FOLLOW and FOLLOW["tap"] < FOLLOW["in"] + .4: say("the follow tap comes before the card has landed")
    if not FOLLOW: say("no follow card")
    inf = subprocess.run(["node", str(PROJ / R.get("scenes", "canvas/scenes.js")), "info"], capture_output=True, text=True)
    if not inf.returncode:
        cs = json.loads(inf.stdout)["cells"]
        if not SPLIT["in"] - .3 < cs[0][1] < SPLIT["in"] + 1.2: say(f"canvas: the first cell is at {cs[0][1]} s and the split opens at {SPLIT['in']:.2f}")
        for q, at in cs:
            if not SPLIT["in"] - .3 < at < SPLIT["out"]: say(f"canvas: cell {q} at {at} s is outside the split ({SPLIT['in']:.2f}-{SPLIT['out']:.2f})")
        if cs[-1][0] != "recap": say("canvas: no recap")
        elif SPLIT["out"] - cs[-1][1] < 1.2: say(f"canvas: the recap gets {SPLIT['out'] - cs[-1][1]:.1f} s; give it at least 1.2")
        if SPLIT["out"] - cs[-1][1] > 8: say(f"canvas: the last cell at {cs[-1][1]} s has to carry {SPLIT['out'] - cs[-1][1]:.1f} s; draw what the speaker says there")
    r = subprocess.run(["node", str(PROJ / R.get("scenes", "canvas/scenes.js")), "check"], capture_output=True, text=True); bad += [l.replace("WARN ", "canvas: ") for l in r.stdout.splitlines() if l.startswith("WARN")] + ([r.stderr[-300:]] if r.returncode else [])
    e = (PROJ / "work/clip_edges.txt"); bad += [l for l in e.read_text().splitlines() if "FIX" in l] if e.exists() else ["no clip_edges.txt: run split_cut.py"]
    print("\n".join(["FIX  " + b for b in bad] + ["note " + n for n in note]) + ("" if bad else ("\n" if note else "") + "OK captions, cards, headroom, canvas and clip starts all pass")); return not bad


def qa():
    out = PROJ / f"out/{SLUG}.mp4"; nf = int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)]).stdout.strip().rstrip(",")); j = loud(["-i", str(out), "-vn", "-af", "loudnorm=print_format=json"]); print(f"frames {nf} of {N}; {j['input_i']} LUFS, peak {j['input_tp']} dB; phone copy {(PROJ / f'out/{SLUG}-phone.mp4').stat().st_size / 1e6:.1f} MB")
    w, h, c = 230, 409, 12; ts = [i * DUR / 48 + .2 for i in range(48)]; s = Image.new("RGB", (c * w, 4 * h))
    for k, t in enumerate(ts): s.paste(grab(out, min(N - 1, int(t * FPS)), W, H).resize((w, h), Image.BILINEAR), ((k % c) * w, (k // c) * h))
    s.save(PROJ / "work/final_sheet.jpg", quality=88); run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-ac", "1", "-ar", "16000", str(PROJ / "work/final16.wav")]); tx = subprocess.run(["whisper-cli", "-m", whisper_model(), "-f", str(PROJ / "work/final16.wav"), "-l", "en", "-np", "-nt"], capture_output=True, text=True).stdout; nz = lambda q: [C.norm(x) for x in q.split() if C.norm(x)]; want, got = nz(" ".join(w[0] for w in words())), nz(tx)
    miss = [" ".join(want[a:b]) for op, a, b, _, _ in difflib.SequenceMatcher(None, want, got, autojunk=False).get_opcodes() if op == "delete" and b - a > 2]; print("transcript: " + ("every line heard" if not miss else "not heard (re-run whisper on that window before believing it): " + " | ".join(miss))); print(PROJ / "work/final_sheet.jpg", "<- look at it")


def main():
    if len(sys.argv) < 3: die(__doc__)
    if sys.argv[2] == "store":
        global PROJ; PROJ = Path(sys.argv[1]).expanduser().resolve(); return store_fetch(int(sys.argv[3]))
    setup(sys.argv[1]); cmd, a = sys.argv[2], sys.argv[3:]
    if cmd == "words":
        raw = json.loads((PROJ / f"work/{R.get('part', 'body')}_words.json").read_text()); seg = None
        for i, w in enumerate(raw): print(("\n" if w[3] != seg else "") + f"w{i}:{w[0]}@{w[1]:.2f}", end="  "); seg = w[3]
        print()
    elif cmd == "preview": preview([float(x) for x in a[0].split(",")], *(a[1:2]), **({"w": int(a[2])} if len(a) > 2 else {}))
    elif cmd == "audio": audio(); qa()
    elif cmd in ("draft", "caps", "check", "render", "qa"): globals()[cmd]()
    else: die(__doc__)


if __name__ == "__main__": main()
