"""Shared helpers for the reel-editor scripts. Python 3.9+, Pillow, numpy, ffmpeg/ffprobe, whisper-cli."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"
CONFIG = Path.home() / ".config" / "reel-editor"          # the user's own: preferences.md, styles/, rooms/
MUSIC = Path.home() / ".cache" / "reel-editor" / "music"  # downloaded beats (outside the skill, so updates keep them)
W, H, FPS, SR = 1080, 1920, 30, 48000
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def die(msg):
    print(f"error: {msg}", file=sys.stderr); sys.exit(1)


def run(args, **kw):
    """Run a command, raise with stderr on failure."""
    r = subprocess.run(args, capture_output=True, text=kw.pop("text", True), **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]} failed ({r.returncode}): {r.stderr[-1500:]}")
    return r


def load(p, default=None):
    p = Path(p)
    if not p.exists():
        if default is not None: return default
        die(f"missing {p}")
    return json.loads(p.read_text())


def save(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1))


def whisper_model():
    """Find a ggml whisper model. Override with REEL_WHISPER_MODEL."""
    env = os.environ.get("REEL_WHISPER_MODEL")
    if env and Path(env).exists(): return env
    names = ["ggml-large-v3-turbo.bin", "ggml-large-v3-turbo-q5_0.bin", "ggml-medium.en.bin", "ggml-small.en.bin", "ggml-base.en.bin"]
    for d in [Path.home() / ".cache/whisper.cpp", Path.home() / ".cache/whisper", Path("/opt/homebrew/share/whisper-cpp"), Path("/usr/local/share/whisper-cpp")]:
        for n in names:
            if (d / n).exists(): return str(d / n)
    try:
        hits = run(["mdfind", "-name", "ggml-"]).stdout.split("\n")
        hits = [h for h in hits if h.endswith(".bin") and "for-tests" not in h and os.path.getsize(h) > 50e6]
        hits.sort(key=lambda h: ("turbo" not in h, "large" not in h))
        if hits: return hits[0]
    except Exception:
        pass
    die("no whisper ggml model found; put ggml-large-v3-turbo.bin in ~/.cache/whisper.cpp (see the README) or set REEL_WHISPER_MODEL")


def need_tools():
    for t in ["ffmpeg", "ffprobe", "whisper-cli"]:
        if not shutil.which(t): die(f"{t} not on PATH (brew install ffmpeg whisper-cpp)")
    if not Path(CHROME).exists(): die("Google Chrome not found (needed to render mockups)")


TSPEC = re.compile(r"^w(\d+)(e?)([+-]\d*\.?\d+)?$")


def tspec(v, words, offset=0.0):
    """Resolve a time spec to absolute seconds.
    number -> seconds within the part; 'w12' -> start of word 12; 'w12e' -> its end; 'w12+0.1' / 'w12e-0.05' -> offset."""
    if isinstance(v, (int, float)): return offset + float(v)
    m = TSPEC.match(str(v).strip())
    if not m: raise ValueError(f"bad time spec {v!r} (use seconds or w<index>[e][+/-sec])")
    i = int(m.group(1))
    if i >= len(words): raise ValueError(f"time spec {v!r}: only {len(words)} words in this part")
    t = words[i][2] if m.group(2) else words[i][1]
    return offset + t + (float(m.group(3)) if m.group(3) else 0.0)


def frames(sec): return round(sec * FPS)


def deep_merge(a, b):
    """b over a, recursively for dicts; lists and scalars in b replace a's."""
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_style(plan):
    """The plan's style preset (assets/styles/<plan.style>.json) with plan.style_overrides on top. The default is
    cinematic, the house style; classic is the original look, only on request."""
    name = plan.get("style", "cinematic")
    p = next((d / f"{name}.json" for d in (CONFIG / "styles", ASSETS / "styles") if (d / f"{name}.json").exists()), None)
    if p is None:
        die(f"unknown style {name!r}; available: {', '.join(sorted({x.stem for d in (CONFIG / 'styles', ASSETS / 'styles') for x in d.glob('*.json')}))}")
    base = load(ASSETS / "styles" / "classic.json") if name != "classic" else {}
    st = deep_merge(deep_merge(base, load(p)), plan.get("style_overrides", {}))
    m = st.get("music") or {}
    if m.get("bed") == "trap":
        # A trap beat under every cinematic reel, picked per reel from the best-measured beats so reels don't all share one; a plan pins one with
        # style_overrides.music.bed = "track:<id>" (references/music-library.md). The beats aren't in the repo (Mixkit's
        # licence doesn't allow it); until `music_lib.py fetch` has been run, the synthesized pad plays instead.
        import zlib
        pool = m.get("trap_pool") or TRAP_POOL
        tid = pool[zlib.crc32(str(plan.get("slug", "reel")).encode()) % len(pool)]
        have = (MUSIC / f"{tid}.mp3").exists()
        m["bed"] = f"track:{tid}" if have else "dark_pad"
        if not have:
            global _NOTED
            if not _NOTED: print(f"note: beat {tid} isn't downloaded, using the synthesized pad (get the beats with scripts/music_lib.py fetch)", file=sys.stderr)
            _NOTED = True
    return st


_NOTED = False
TRAP_POOL = ["mixkit-358", "mixkit-403", "mixkit-369", "mixkit-426"]   # trap-measured, beat grid trusted (>= 2)
