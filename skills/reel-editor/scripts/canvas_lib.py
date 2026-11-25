"""Shared by the canvas reel scripts (countup_hook, canvas_body, canvas_sound): the project's canvas_reel.json, easing, the head
track, captions fitted to the word times. Spec: references/canvas-reel-schema.md."""
import json, math, re, subprocess, sys
from pathlib import Path
import numpy as np
from common import W, H, FPS, die

GREEN, YELLOW, RED = "#3DDC84", "#FFD43B", "#FF6B6B"
ACCENT = {"green": GREEN, "yellow": YELLOW, "red": RED}
def clamp(v, a=0.0, b=1.0): return max(a, min(b, v))
def lerp(a, b, u): return a + (b - a) * u
def eoc(u): return 1 - (1 - clamp(u)) ** 3
def eio(u): return 0.5 - 0.5 * math.cos(math.pi * clamp(u))
def back(u, s=1.7): u = clamp(u) - 1; return 1 + (s + 1) * u ** 3 + s * u ** 2
def lin(u): return clamp(u)
def ein(u): return clamp(u) ** 2.4
EASE = {"out": eoc, "io": eio, "back": back, "lin": lin, "in": ein}


def project(arg):
    proj = Path(arg).expanduser().resolve(); f = proj / "canvas_reel.json"
    if not f.exists(): die(f"{f} missing (run canvas_init.py PROJECT roadmap and fill it in)")
    return proj, json.loads(f.read_text())


def part(proj, name):
    """{dir, dur, frames, words, face(t) -> (x, y, height)} of a cut part; tracks the head the first time."""
    d = proj / "work/parts" / name
    if not (d / "base.mp4").exists(): die(f"{d}/base.mp4 missing (run cut.py)")
    if not (d / "track.json").exists(): subprocess.run([sys.executable, str(Path(__file__).parent / "track.py"), str(d)], check=True)
    segs = json.loads((d / "segs.json").read_text()); trk = json.loads((d / "track.json").read_text())["segs"]; wf = proj / "work" / f"{name}_words.json"
    if not wf.exists(): wf = d / "words.json"; print(f"note: {name} word times come from cut.py; run seg_words.py for times that don't drift across cuts", file=sys.stderr)
    def face(t):
        for a, b, s in trk:
            if a <= t < b + 1e-6:
                ts = [p[0] for p in s]; return tuple(float(np.interp(t, ts, [p[k] for p in s])) for k in (1, 2, 3))
        s = trk[-1][2][-1]; return s[1], s[2], s[3]
    return {"dir": d, "dur": segs["duration"], "frames": segs["frames"], "words": json.loads(wf.read_text()), "face": face}


NUM = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
def NORM(w): w = re.sub(r"[^a-z0-9%$]", "", w.lower()); return NUM.get(w, w)


def fit_caps(spec, words, t0, t1, hold=0.35):
    """Caption groups -> [(start, end, [(TEXT, time, hot), ...]), ...].
    A group is a string in the order the speaker says it: "THIS KEPT ME", "ALMOST *FOREVER*" (*accent*), "SAME_TIME DAILY" (joined words
    show together). Each word takes the time of the next matching word the speaker says in [t0, t1]. A group already written out as
    [start, end, [[TEXT, time, hot], ...]] passes through."""
    pool = [w for w in words if w[2] > t0 - 0.12 and w[1] < t1 + 0.05]; k = 0; out = []
    for g in spec:
        if isinstance(g, list) and not (len(g) == 3 and isinstance(g[0], (int, float)) and isinstance(g[2], list)): die(f"caps: each group is one string in the order the speaker says it, or [start, end, [[WORD, time], ...]]; got {g!r}")
        if not isinstance(g, str): out.append([g[0], g[1], [(w[0], w[1], w[2] if len(w) > 2 else 0) for w in g[2]]]); continue
        ws = []
        for tok in g.split():
            hot = tok.startswith("*") and tok.endswith("*"); txt = tok.strip("*"); bits = txt.split("_"); at = None
            for b in bits:
                j = next((i for i in range(k, len(pool)) if NORM(pool[i][0]) == NORM(b)), None)
                if j is None: die(f"caption word {b!r} is not said after {pool[k - 1][1] if k else t0:.2f}s (before {t1:.2f}s); whisper heard: " + " ".join(w[0] for w in pool) + ". If it misheard, write the group out as [start, end, [[WORD, time], ...]]")
                if at is None: at = pool[j][1]
                k = j + 1
            ws.append((" ".join(bits), at, 1 if hot else 0))
        out.append([ws[0][1], min(t1, pool[k - 1][2] + hold), ws])
    for a, b in zip(out, out[1:]): a[1] = min(a[1], b[0]) if b[0] > a[0] else a[1]
    return out


def zooms(z): return [(a, b, z0, z1, EASE[e] if isinstance(e, str) else lin) for a, b, z0, z1, e in z]


def zoom_at(Z, t, rest=1.0):
    for a, b, z0, z1, e in Z:
        if a <= t < b: return z0 + (z1 - z0) * e((t - a) / (b - a))
    return rest


def scenes_info(proj, reel):
    if not (proj / reel.get("scenes", "canvas/scenes.js")).exists(): return {"flights": reel.get("flights", []), "cues": reel.get("cues", {}), "frames": None}      # art from another style, already in work/canvas.mp4
    r = subprocess.run(["node", str(proj / reel.get("scenes", "canvas/scenes.js")), "info"], capture_output=True, text=True)
    if r.returncode: die(r.stderr[-1500:])
    return json.loads(r.stdout)


def stamp(im, t):
    """the time on a preview tile"""
    from PIL import ImageDraw
    import compose
    d = ImageDraw.Draw(im); d.rectangle([0, 0, 74, 30], fill=(0, 0, 0)); d.text((8, 4), f"{t:.2f}", font=compose.font("bold", 20), fill=(255, 255, 255)); return im


def h264(extra=()): return ["-c:v", "libx264", *extra, "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
