#!/usr/bin/env python3
"""Synthesize the sound pack: the only sound effects a reel uses. Nothing is sampled or downloaded, so there is nothing
to license and the files can be shared.

  sfx_pack.py            write assets/sfx/lib/<cat>/<cat>_NN.wav + library.json, and the count-up sounds in assets/sfx/countup
  sfx_pack.py --check    measure the pack without writing

assets/sfx/pack.json says what each sound is for, how loud it plays and when it's allowed (audiomap.py enforces it).
To use your own recording of a sound, put the WAV over assets/sfx/lib/<cat>/<cat>_01.wav (48 kHz stereo) and run
`sfx_pack.py --measure`, which re-reads the files' lengths and sync points without replacing them.
"""
import json, sys
from pathlib import Path
import numpy as np
import sfx_cine as C, sfx_lib
from sfx_lib import LIB, SR, write_wav, read_wav, normalize, analyze

SPEC = sfx_lib.ASSETS / "sfx" / "pack.json"
COUNTUP = sfx_lib.ASSETS / "sfx" / "countup"


def _mix(n, *layers):
    """(n, 2) mix of (samples, start seconds, gain) layers, mono or stereo."""
    out = np.zeros((n, 2))
    for x, at, g in layers:
        x = C.st(np.asarray(x, float)); i = int(at * SR); m = min(len(x), n - i); out[i:i + m] += x[:m] * g
    return out


def counting():
    """a fast dry count that speeds up slightly and ends on a firmer tick"""
    n = int(1.46 * SR); out = np.zeros((n, 2)); r = np.random.default_rng(5); t = 0.0; k = 0
    tick = C.ui_tick(); body = C.ui_click()
    while t < 1.36:
        g = r.uniform(0.55, 0.8) * (1.0 if k % 4 else 1.25); out += _mix(n, (tick, t, g), (body, t, 0.10)); t += 0.062 - 0.016 * t / 1.36; k += 1
    return out + _mix(n, (tick, 1.38, 1.3), (body, 1.38, 0.5))


def glitch():
    x = C.cine_glitch(); n = int(0.7 * SR); y = _mix(n, (x, 0.0, 1.0), (x[::-1].copy(), 0.36, 0.55)); y *= np.concatenate([np.ones(n - int(0.3 * SR)), np.linspace(1, 0.05, int(0.3 * SR))])[:, None]; return y


def whoosh():
    """short build, long soft tail, with low body so it reads as air moving rather than hiss"""
    x = C._whoosh(1.0, 320, 4200, 420, 0.24, -0.6, 0.6, 0.75, 1.1, 1); return x[: int(1.5 * SR)]


def riser():
    """metallic swell that peaks at its end and stops"""
    d = 1.72; t = C.T(d); n = len(t); u = t / d; f = 130 * 6 ** (u ** 1.25)
    ring = sum(np.sin(2 * np.pi * np.cumsum(f * m) / SR + p) * a for m, a, p in [(1, 1, 0), (1.5, .5, 1), (2.76, .35, 2), (5.4, .16, 3)])
    air = C.sweep_band(C.noise(n), 300 * 28 ** u, 1.3); sub = np.sin(2 * np.pi * np.cumsum(48 + 40 * u) / SR)
    x = (0.5 * C.sat(ring, 1.3) + 0.8 * air + 0.7 * sub) * u ** 2.4; x[-int(0.2 * SR):] *= np.linspace(1, 0.25, int(0.2 * SR)) ** 0.6
    return C.st(x, 0.12)


def low_hit(): return C.cine_hit()[: int(1.5 * SR)] * np.concatenate([np.ones(int(1.1 * SR)), np.linspace(1, 0, int(0.4 * SR)) ** 1.5])[:, None]


def flash():
    """flash pop, then the capacitor whining back up, faint"""
    n = int(1.55 * SR); t = C.T(0.5); pop_ = C.band(C.noise(len(t)), 900, 15000) * C.env(len(t), 0.0, 0.045) + np.sin(2 * np.pi * 240 * t) * C.env(len(t), 0.001, 0.02) * 0.7
    tw = C.T(1.3); fw = 2600 + 5200 * (tw / 1.3) ** 0.6; whine = np.sin(2 * np.pi * np.cumsum(fw) / SR) * np.clip(tw / 0.1, 0, 1) * np.exp(-tw / 0.55) * 0.10
    return _mix(n, (C.reverb(pop_, 0.8, 0.18, 9000, 500, 0.3, 12), 0.0, 1.0), (whine, 0.12, 1.0))


def flash_shutter():
    n = int(1.5 * SR); r = np.random.default_rng(17)
    def blade(g, lo):
        t = C.T(0.06); m = len(t); return g * (C.band(r.standard_normal(m), lo, 14000) * C.env(m, 0, 0.007) + 0.5 * np.sin(2 * np.pi * 190 * t) * C.env(m, 0, 0.012))
    return _mix(n, (blade(1.0, 1500), 0.0, 1.0), (blade(0.7, 2200), 0.045, 1.0), (blade(0.9, 1300), 0.115, 1.0), (flash()[: int(1.3 * SR)], 0.02, 0.45))


def page_flip():
    d = 0.52; t = C.T(d); n = len(t); u = t / d; r = np.random.default_rng(23)
    e = np.where(u < 0.28, (u / 0.28) ** 1.5, np.exp(-(u - 0.28) * 5.5)); flut = 0.72 + 0.28 * np.abs(np.sin(2 * np.pi * (26 * u + 9 * u * u)))
    x = C.sweep_band(r.standard_normal(n), 900 + 2600 * np.sin(np.pi * np.clip(u * 1.15, 0, 1)), 1.5) * e * flut
    slap = C.band(r.standard_normal(n), 250, 2500) * np.exp(-np.maximum(t - 0.30, 0) / 0.02) * (t > 0.30) * 0.5
    return C.pan(x + slap, np.linspace(0.35, -0.35, n))


def shine():
    n = int(2.0 * SR); bell = np.zeros(int(1.6 * SR)); t = C.T(1.6)
    for f, a, d in [(1975.5, 1.0, .55), (2637.0, .55, .45), (3951.1, .35, .30), (5919.9, .14, .18)]: bell += a * np.sin(2 * np.pi * f * t) * np.exp(-t / d)
    return _mix(n, (C.reverb(bell * np.clip(t / 0.002, 0, 1), 0.4, 0.14, 12000, 800, 0.25, 14)[: int(1.9 * SR)], 0.05, 0.9), (C.cine_shimmer(), 0.0, 0.5))


def pop():
    t = C.T(0.30); n = len(t); f = 260 + 720 * np.exp(-t * 30); b = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 34)
    return C.st(b + 0.16 * C.band(C.noise(n), 1800, 9000) * np.exp(-t * 320))


def key(k):
    """one laptop key: the press, then the softer release; every file slightly different"""
    r = np.random.default_rng(300 + k); n = int(0.2 * SR); x = np.zeros(n); tone = r.uniform(240, 420)
    for at, g in [(0.0, 1.0), (r.uniform(0.055, 0.085), r.uniform(0.28, 0.45))]:
        i = int(at * SR); m = n - i; t = np.arange(m) / SR
        x[i:] += g * (C.band(r.standard_normal(m), r.uniform(1400, 2200), r.uniform(8000, 12000)) * np.exp(-t / r.uniform(0.0018, 0.0034)) + r.uniform(0.35, 0.6) * np.sin(2 * np.pi * tone * t) * np.exp(-t / r.uniform(0.008, 0.016)))
    return C.st(x, 0.1)


def scribble(d, seed, strokes):
    """a pencil: band-limited paper noise whose level follows the hand's strokes"""
    r = np.random.default_rng(700 + seed); n = int(d * SR); t = np.arange(n) / SR; e = np.zeros(n); at = 0.0
    for k in range(strokes):
        w = d / strokes * r.uniform(0.75, 1.1); c = at + w / 2; e += r.uniform(0.6, 1.0) * np.exp(-((t - c) / (w * 0.36)) ** 4); at += d / strokes
    fc = 2600 + 1500 * np.sin(2 * np.pi * strokes / d / 2 * t + r.uniform(0, 6)); x = C.sweep_band(r.standard_normal(n), fc, 1.6) * e
    grit = 0.75 + 0.25 * C.band(r.standard_normal(n), 30, 180) / 0.1 * 0.02
    edge = int(0.006 * SR); x[:edge] *= np.linspace(0, 1, edge); x[-edge:] *= np.linspace(1, 0, edge); return C.st(x * grit, 0.15)


MAKE = {"counting": [counting], "glitch": [glitch], "whoosh": [whoosh], "riser": [riser], "low_hit": [low_hit], "flash": [flash],
        "flash_shutter": [flash_shutter], "page_flip": [page_flip], "shine": [shine], "pop": [pop],
        "key": [lambda k=k: key(k) for k in range(12)],
        "scribble": [lambda a=a: scribble(*a) for a in [(0.33, 1, 1), (0.36, 2, 2), (0.52, 3, 2), (0.70, 4, 3), (0.72, 5, 4), (0.92, 6, 4), (1.10, 7, 5), (1.85, 8, 8)]]}


# ---- the step roadmap's count-up: a pitched tap per tick, two whole alternatives, and the landing's ding
def tap():
    """a small wooden tap at 1714 Hz; canvas_sound.py repitches it per tick"""
    t = C.T(0.12); n = len(t); return C.st(np.sin(2 * np.pi * 1714 * t) * np.exp(-t * 60) + 0.4 * np.sin(2 * np.pi * 1714 * 2.76 * t) * np.exp(-t * 120) + 0.25 * C.band(C.noise(n), 3000, 12000) * np.exp(-t * 500))


def arcade():
    out = np.zeros(int(1.5 * SR)); k = 0; at = 0.0
    while at < 1.3:
        t = C.T(0.07); f = 523.25 * 2 ** ((k * 2) / 12 / 1.6); i = int(at * SR); s = np.sign(np.sin(2 * np.pi * f * t)) * np.exp(-t * 34); out[i:i + len(s)] += s[: len(out) - i]; at += 0.068; k += 1
    return C.st(C.band(out, 120, 7000))


def charge():
    t = C.T(1.5); u = t / 1.5; f = 120 * 9 ** u; x = C.sat(np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.6 * np.sin(2 * np.pi * np.cumsum(f * 1.008) / SR), 1.8) * (0.2 + 0.8 * u ** 1.6) * (0.7 + 0.3 * np.sin(2 * np.pi * (8 + 14 * u) * t))
    x[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR)); return C.st(C.band(x, 100, 8000), 0.1)


def ding():
    t = C.T(1.8); x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, a, d in [(1046.5, 1, .6), (2093.0, .5, .42), (3140, .25, .25), (4186, .12, .16)]); return C.reverb(x * np.clip(t / 0.002, 0, 1), 0.5, 0.16, 12000, 600, 0.22, 15)[: len(t)]


COUNT = {"tap": tap, "arcade": arcade, "charge": charge, "ding": ding}


def _meta(c, sid, x, rule):
    a = analyze(x, rule); return {"id": sid, "cat": c["cat"], "file": f"{c['cat']}/{sid}.wav", **{k: a[k] for k in ("dur", "sync", "level_db", "centroid_hz", "low_ratio", "rise_db")}, "title": c["title"], "tags": [], "source": "synth"}


def build(write=True, measure=False):
    spec = json.loads(SPEC.read_text()); cats, sounds = {}, []
    for c in spec["sounds"]:
        rule = dict(sync=c["sync"], min=0.01, max=8.0, cap=False); cats[c["cat"]] = {k: c[k] for k in ("offset", "about", "usage", "rules")}
        files = sorted((LIB / c["cat"]).glob("*.wav")) if measure else MAKE[c["cat"]]
        for k, m in enumerate(files):
            sid = f"{c['cat']}_{k + 1:02d}"
            if measure: x = read_wav(m).astype(np.float32); sid = m.stem
            else:
                y = C.st(np.asarray(m(), float)); x, why = normalize(y / (np.abs(y).max() + 1e-9) * 0.9, rule)
                if x is None: raise SystemExit(f"{sid}: {why}")
                if write: write_wav(LIB / c["cat"] / f"{sid}.wav", x)
            s = _meta(c, sid, x, rule); sounds.append(s); print(f"{sid:18s} {s['dur']:.2f}s  sync {s['sync']:.3f}  centre {s['centroid_hz']:5d} Hz  low {s['low_ratio']:.2f}  level {s['level_db']:.1f} dB")
    if not write: return
    if not measure:
        for k, f in COUNT.items(): y = C.st(np.asarray(f(), float)); write_wav(COUNTUP / f"{k}.wav", (y / np.abs(y).max() * 0.89).astype(np.float32))
    (LIB / "library.json").write_text(json.dumps({"version": 3, "generated": "sfx_pack.py", "categories": cats, "sounds": sounds}, indent=1) + "\n"); print(f"{len(sounds)} sounds in {len(cats)} categories")


def ensure():
    """mix.py and compose.py call this: synthesize the pack if it isn't there."""
    if not (LIB / "library.json").exists(): build()


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv: print(__doc__)
    else: build(write="--check" not in sys.argv, measure="--measure" in sys.argv)
