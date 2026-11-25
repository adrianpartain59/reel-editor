#!/usr/bin/env python3
"""The sound library: every sound effect a reel may use, with how loud it plays and when it's allowed.

  sfx_lib.py list [CAT ...]            ids, durations, titles
  sfx_lib.py check                     library.json vs the files on disk
  sfx_lib.py audition [CAT ...] --out FILE.m4a
                                       a spoken catalogue: the id is read out, then the sound plays at its mix level

Use from other scripts:
  import sfx_lib
  p = sfx_lib.Picker(seed=3)           # one per reel
  sid = p.pick("pop", t=4.2)           # never the same file twice in a row, avoids repeats within 8 s
  sfx_lib.path(sid), sfx_lib.sound(sid)["sync"], sfx_lib.offset("pop")

Every file is 48 kHz stereo 16-bit, starts <= 5 ms before its first transient, ends with a 20 ms fade, and is
peak-normalized to -1 dBFS (the mixer sets the real level from `offset`). `sync` is the time inside the file
that should land on the visual event: the transient for hits, keys and pops; the loudest point for whooshes;
the peak at the end for risers.
The sounds are synthesized by sfx_pack.py, so they're yours to use and share. references/sfx-library.md has the
rules and how to swap in your own recordings.
"""
import argparse, json, random, subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np
from common import ASSETS, SR, run

LIB = ASSETS / "sfx" / "lib"
_LIBRARY = None

# The sound pack is the only sound effects a reel may use: twelve categories, each with its own job (assets/sfx/pack.json).
# Older category and sound names, still accepted in plans and styles, resolve to one of the twelve, so nothing else plays.
PACK_CATS = ("counting", "glitch", "whoosh", "riser", "low_hit", "flash", "flash_shutter", "page_flip", "shine", "pop",
             "key", "scribble")
LEGACY = {
    "shutter": "flash_shutter", "click_mouse": "pop", "click_ui": "pop", "click_hard": "pop", "typing": "key", "notif": "pop", "swish": "whoosh", "whoosh_heavy": "whoosh", "impact": "low_hit",
    "reverse": "riser", "swipe": "page_flip", "tick": "counting", "success": "shine", "error": "low_hit",
    "cash": "shine", "switch": "flash", "shimmer": "shine", "stamp": "low_hit", "message": "pop",
    "vibrate": "pop", "stop": "glitch", "neon": "shine",
    # synthesized sounds that used to live in assets/sfx/*.wav
    "boom": "low_hit", "buzzer": "low_hit", "cha_ching": "shine", "cine_boom": "low_hit", "cine_glitch": "glitch",
    "cine_hit": "low_hit", "cine_neon": "shine", "cine_riser": "riser", "cine_shimmer": "shine", "cine_suck": "riser",
    "cine_swish": "whoosh", "cine_tape": "glitch", "cine_whoosh": "whoosh", "cine_whoosh_out": "whoosh",
    "click": "pop", "ding": "shine", "notify": "pop", "scratch": "glitch", "thud": "low_hit", "type_key": "key",
    "ui_click": "pop", "ui_tick": "counting", "whoosh_down": "whoosh", "whoosh_short": "whoosh",
}


def canon(name):
    """A pack category, an old category, an old synthesized sound name or a sound id ("success_07", "lib:pop_01")
    -> one of the pack's categories, or None."""
    n = str(name)[4:] if str(name).startswith("lib:") else str(name)
    for k in (n, n.rsplit("_", 1)[0]):
        if k in PACK_CATS: return k
        if k in LEGACY: return LEGACY[k]
    return None


# ---------------------------------------------------------------- API used by compose.py / mix.py
def library():
    global _LIBRARY
    if _LIBRARY is None:
        f = LIB / "library.json"
        if not f.exists():
            raise FileNotFoundError(f"{f} missing: run `python3 sfx_pack.py`")
        _LIBRARY = json.loads(f.read_text())
        _LIBRARY["_by_id"] = {s["id"]: s for s in _LIBRARY["sounds"]}
    return _LIBRARY


def sound(sid):
    by = library()["_by_id"]
    if sid not in by:                        # an id from the old library: the pack sound in its place
        c = canon(sid)
        if c is None: raise KeyError(f"unknown sound {sid!r}")
        sid = ids(c)[0]
    return by[sid]


def path(sid):
    return LIB / sound(sid)["file"]


def cats():
    return sorted(library()["categories"])


def ids(cat, tags=None):
    cat = cat if cat in library()["categories"] else (canon(cat) or cat)
    if cat not in library()["categories"]:
        raise KeyError(f"unknown sfx category {cat!r}; categories: {', '.join(cats())}")
    out = [s["id"] for s in library()["sounds"] if s["cat"] == cat]
    if tags:
        tags = {tags} if isinstance(tags, str) else set(tags)
        out = [i for i in out if tags & set(sound(i)["tags"])]
    return out


def rules(cat):
    """Usage rules for a category (pack.json "rules"): events, must, where, min_gap, max, background, fit."""
    c = canon(cat) or cat
    return library()["categories"].get(c, {}).get("rules", {})


def offset(cat):
    return float(library()["categories"][canon(cat) or cat]["offset"])


class Picker:
    """Rotates through a category so a reel never hears the same file twice in a row.

    pick(cat, t): among the category's files (narrowed by `tags` when any match), never the previous pick in
    that category; then prefer files not used within `gap` seconds of t; then the least used; ties broken by a
    fixed shuffle seeded by (seed, cat), so the same plan always gets the same sounds."""

    def __init__(self, seed=0, gap=8.0):
        self.seed, self.gap = seed, gap
        self.last, self.uses, self.count = {}, [], {}

    def pick(self, cat, t, tags=None, fit=None):
        pool = ids(cat, tags) if tags else []
        if not pool: pool = ids(cat)
        if fit and len(pool) > 1:              # the file whose length matches the visual best (sounds are never cut)
            best = min(pool, key=lambda s: abs(sound(s)["dur"] - fit))
            self.last[cat] = best; self.uses.append((best, t)); self.count[best] = self.count.get(best, 0) + 1
            return best
        if not pool: raise KeyError(f"sfx category {cat!r} is empty")
        order = {sid: k for k, sid in enumerate(random.Random(f"{self.seed}:{cat}").sample(pool, len(pool)))}
        cand = [s for s in pool if s != self.last.get(cat)] or pool
        near = {s for (u, tu) in self.uses if abs(tu - t) < self.gap for s in [u]}
        best = min(cand, key=lambda s: (s in near, self.count.get(s, 0), order[s]))
        self.last[cat] = best; self.uses.append((best, t)); self.count[best] = self.count.get(best, 0) + 1
        return best


# ---------------------------------------------------------------- audio helpers
def decode(f):
    """Any audio file -> (n, 2) float32 at 48 kHz."""
    raw = run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], text=False).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def write_wav(f, x):
    f.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1, 1) * 32767).round().astype("<i2")
    with wave.open(str(f), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def read_wav(f):
    with wave.open(str(f)) as w:
        ch = w.getnchannels(); x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2") / 32768.0
    return x.reshape(-1, ch) if ch == 2 else np.stack([x, x], 1)


def env(x, ms=5, hop_ms=1):
    """RMS envelope across both channels, `ms` window, `hop_ms` hop. Returns (values, hop in samples)."""
    m = np.mean(x ** 2, axis=1); w = max(1, int(SR * ms / 1000)); h = max(1, int(SR * hop_ms / 1000))
    c = np.concatenate([[0.0], np.cumsum(m)])
    starts = np.arange(0, max(1, len(m) - w + 1), h)
    return np.sqrt((c[starts + w] - c[starts]) / w + 1e-20), h


def db(v):
    return 20 * np.log10(np.maximum(v, 1e-10))


def normalize(x, rule):
    """Trim to the first transient, trim the tail, fade, peak -1 dBFS. Returns (x, notes) or (None, reason)."""
    if len(x) < int(0.01 * SR): return None, "empty"
    clipped = float(np.mean(np.abs(x) >= 0.999))
    if clipped > 0.005: return None, f"clipped ({clipped * 100:.1f}% of samples at full scale)"
    e, h = env(x, 2, 1); pk = e.max()
    if pk < 1e-4: return None, "silent"
    above = np.nonzero(e > pk * 10 ** ((-45 if rule["sync"] == "end" else -30) / 20))[0]
    start = max(0, above[0] * h - int(0.005 * SR))
    tail = np.nonzero(e > pk * 10 ** (-50 / 20))[0]
    end = min(len(x), tail[-1] * h + int(0.02 * SR) + int(0.002 * SR))
    x = x[start:end]
    notes = []
    dur = len(x) / SR
    if dur > rule["max"]:
        if not rule.get("cap"): return None, f"too long ({dur:.2f} s > {rule['max']} s)"
        x = x[: int(rule["max"] * SR)]; notes.append(f"tail cut at {rule['max']} s")
    if len(x) / SR < rule["min"]: return None, f"too short ({len(x) / SR:.2f} s < {rule['min']} s)"
    fi = min(len(x) // 4, int(0.001 * SR)); x[:fi] *= np.linspace(0, 1, fi)[:, None]
    fo = min(len(x) // 3, int(0.02 * SR) if not notes else int(0.25 * SR))
    x[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    x = x / max(np.abs(x).max(), 1e-9) * 10 ** (-1 / 20)
    return x.astype(np.float32), notes


def analyze(x, rule):
    e, h = env(x, 5, 1); pk_i = int(np.argmax(e)); pk = e[pk_i]
    if rule["sync"] in ("hit", "first"):
        i = int(np.nonzero(e >= pk * (0.5 if rule["sync"] == "hit" else 0.1))[0][0]); back = 0
        while i > 0 and back < 20 and e[i - 1] < e[i] and e[i - 1] > pk * 0.05: i -= 1; back += 1
        sync = i * h / SR
    else:
        e20, h20 = env(x, 20, 2); sync = int(np.argmax(e20)) * h20 / SR + 0.01
    # sharpness: the biggest rise of the 1 ms envelope over any 5 ms in the first 80 ms after the onset (dB).
    # A click or key jumps 25-40 dB in a few ms; a sound that fades in rises a few dB per 5 ms.
    # 10 ms of silence in front, so a file whose transient is its first sample still shows the jump.
    e1, _ = env(np.concatenate([np.zeros((int(0.01 * SR), 2), x.dtype), x]), 1, 1); d1 = db(e1); p1 = d1.max()
    d1 = np.maximum(d1, p1 - 60)
    i0 = int(np.nonzero(d1 >= p1 - 30)[0][0]); seg = d1[max(0, i0 - 6): i0 + 80]
    rise = float((seg[5:] - seg[:-5]).max()) if len(seg) > 6 else 0.0
    m = np.mean(x ** 2, axis=1); w = int(0.1 * SR)
    c = np.concatenate([[0.0], np.cumsum(m)])
    if len(m) > w:
        st = np.arange(0, len(m) - w + 1, int(0.01 * SR)); lv = np.sqrt(((c[st + w] - c[st]) / w).max())
    else:
        lv = np.sqrt(m.mean())
    mono = x.mean(1); X = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) ** 2; f = np.fft.rfftfreq(len(mono), 1 / SR)
    centroid = float((X * f).sum() / max(X.sum(), 1e-20)); low = float(X[f < 150].sum() / max(X.sum(), 1e-20))
    e10, h10 = env(x, 10, 10); active = float(np.mean(e10 > e10.max() * 10 ** (-40 / 20)))
    return dict(dur=round(len(x) / SR, 3), sync=round(sync, 3), level_db=round(float(db(lv)), 1),
                centroid_hz=int(centroid), low_ratio=round(low, 3), rise_db=round(rise, 1),
                peak_at=round(pk_i * h / SR, 3), active=round(active, 2))


# ---------------------------------------------------------------- commands
def cmd_list(a):
    L = library()
    for c in (a.cats or cats()):
        meta = L["categories"][c]
        print(f"\n{c}  (offset {meta['offset']} dB) {meta.get('about', '')}")
        for s in L["sounds"]:
            if s["cat"] == c:
                print(f"  {s['id']:16} {s['dur']:5.2f}s sync {s['sync']:.3f}  {s['source']:6} {s['title'][:44]:44} {','.join(s['tags'])}")


def cmd_check(a):
    L = library(); bad = 0
    for s in L["sounds"]:
        f = LIB / s["file"]
        if not f.exists(): print(f"missing file {f}"); bad += 1; continue
        with wave.open(str(f)) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SR, 2, 2):
                print(f"wrong format {f}"); bad += 1
            elif abs(w.getnframes() / SR - s["dur"]) > 0.01:
                print(f"duration mismatch {f}"); bad += 1
        if s["cat"] not in L["categories"]: print(f"{s['id']}: unknown category"); bad += 1
    listed = {LIB / s["file"] for s in L["sounds"]}
    for f in LIB.rglob("*.wav"):
        if f not in listed: print(f"unlisted file {f}"); bad += 1
    ids_ = [s["id"] for s in L["sounds"]]
    if len(ids_) != len(set(ids_)): print("duplicate ids"); bad += 1
    print(f"{len(L['sounds'])} sounds, {len(L['categories'])} categories: " + ("OK" if not bad else f"{bad} problems"))
    return bad


def cmd_audition(a):
    L = library(); sel = a.cats or cats()
    out = Path(a.out).expanduser()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); parts = []
        def say(text, k):
            f = tmp / f"say{k}.aiff"; subprocess.run(["say", "-r", "200", "-o", str(f), text], check=True)
            return decode(f)
        voice_ref = None; k = 0
        gap = lambda s: np.zeros((int(s * SR), 2), np.float32)
        for c in sel:
            v = say(f"{c.replace('_', ' ')}.", k); k += 1
            if voice_ref is None:
                vv = env(v, 400, 50)[0]; voice_ref = float(db(np.median(vv[vv > vv.max() * 0.1])))
            parts += [gap(0.5), v, gap(0.5)]
            for s in [s for s in L["sounds"] if s["cat"] == c]:
                n = s["id"].rsplit("_", 1)[1].lstrip("0") or "0"
                parts += [say(n, k) * 0.7, gap(0.25)]; k += 1
                x = read_wav(LIB / s["file"]).astype(np.float32)
                g = voice_ref + L["categories"][c]["offset"] + 4 - s["level_db"]
                parts += [x * 10 ** (g / 20), gap(0.4)]
        y = np.concatenate(parts); y = y / max(1.0, np.abs(y).max() / 0.95)
        (tmp / "a.f32").write_bytes(y.astype(np.float32).tobytes())
        run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(tmp / "a.f32"),
             "-c:a", "aac", "-b:a", "192k", str(out)])
    print(f"wrote {out} ({len(y) / SR / 60:.1f} min, {sum(1 for s in L['sounds'] if s['cat'] in sel)} sounds)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("list"); p.add_argument("cats", nargs="*")
    sp.add_parser("check")
    p = sp.add_parser("audition"); p.add_argument("cats", nargs="*"); p.add_argument("--out", default=str(Path.home() / "Downloads" / "reel-sfx-audition.m4a"))
    a = ap.parse_args()
    r = {"list": cmd_list, "check": cmd_check, "audition": cmd_audition}[a.cmd](a)
    sys.exit(1 if r else 0)


if __name__ == "__main__":
    main()
