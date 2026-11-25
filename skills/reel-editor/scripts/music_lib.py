#!/usr/bin/env python3
"""Downloaded music beds: instrumental beats with a measured beat grid, so the mixer can cut the beat before a
reveal and bring it back on a downbeat (the reveal lands on the "1").

  music_lib.py fetch                    download what library.json lists into ~/.cache/reel-editor/music, analyse new ones
  music_lib.py list [TAG ...]           ids, tempo, grid confidence, steady section, mood tags
  music_lib.py analyse [ID ...]         (re)measure tempo, downbeats and the steady section into library.json
  music_lib.py audition PROJECT --variant V [--ids a,b,c] [--secs 16] [--out FILE.m4a]
                                        the reel's own voice over each beat at its mix level, the id read out first

In a plan or style: "music": {"bed": "track:mixkit-358", "level": -16, "duck": 3}. music.bed() does the cutting.

Analysis (per track, stored in library.json):
- bpm, bar (4 beats), downbeat: tempo from the autocorrelation of an onset envelope (kick/808 + body + hats);
  the downbeat is whichever of the 4 beat positions carries the strongest kick/808 onsets.
- grid_conf: that position's strength over the next strongest. Below 2.0 the grid is not trusted and drops keep
  the beat running (the low end just cuts out before the hit, like the synthesized pad).
- full_from / full_to: the longest run of bars within 4 dB of the track's median level (no breakdowns); the bed
  plays from there and loops it by whole 4-bar phrases.

Licence (references/music-library.md): Mixkit Stock Music Free License. Free in social video posts and online
ads, no attribution. Not allowed: CDs/DVDs, games, broadcast, remixing into a music-only track, claiming it, or
registering it with Content ID or any rights-management service. The files are never handed on inside a
tool, so they are not in this repository: everyone downloads their own copies from Mixkit with `music_lib.py fetch`.
"""
import argparse, json, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
import numpy as np
from common import ASSETS, MUSIC, SR, run, load

ROOT = ASSETS / "music"
LIB = MUSIC
MANIFEST = ROOT / "library.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
_lib = None


def library():
    global _lib
    if _lib is None: _lib = {t["id"]: t for t in json.loads(MANIFEST.read_text())["tracks"]}
    return _lib


def track(tid):
    tid = tid.split(":", 1)[-1]
    if tid not in library(): raise KeyError(f"unknown music track {tid!r} (music_lib.py list)")
    return library()[tid]


def path(tid):
    t = track(tid); return LIB / f"{t['id']}{Path(t['url']).suffix}"


def _save(lib):
    doc = json.loads(MANIFEST.read_text()); doc["tracks"] = list(lib.values())
    MANIFEST.write_text(json.dumps(doc, indent=1) + "\n")


# ---------------------------------------------------------------- analysis

def _onsets(x, sr, hop, lo, hi, n_fft=1024):
    n = len(x) // hop - 8; idx = np.arange(n) * hop
    fr = np.stack([x[i:i + n_fft] if i + n_fft <= len(x) else np.pad(x[i:], (0, i + n_fft - len(x))) for i in idx])
    S = np.abs(np.fft.rfft(fr * np.hanning(n_fft), axis=1)); f = np.fft.rfftfreq(n_fft, 1 / sr)
    b = np.log1p(S[:, (f >= lo) & (f < hi)].sum(1) * 5)
    return np.maximum(0, np.diff(b, prepend=b[0]))


def analyse_file(f):
    sr, hop = 22050, 128
    raw = run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], text=False).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64); fps = sr / hop
    lo = _onsets(x, sr, hop, 30, 150); mid = _onsets(x, sr, hop, 150, 5000); hi = _onsets(x, sr, hop, 5000, 11000)
    o = lo / (lo.std() + 1e-9) + mid / (mid.std() + 1e-9) + hi / (hi.std() + 1e-9); o = o - o.mean()
    ac = np.correlate(o, o, "full")[len(o) - 1:]; ax = np.arange(len(ac))
    bpm = max(np.arange(55, 181, 0.25), key=lambda b: sum(np.interp(fps * 60 / b * k, ax, ac) for k in (1, 2, 3, 4, 8)))
    period = fps * 60 / bpm; ox = np.arange(len(o))
    ph = max(np.arange(0, period, 0.25), key=lambda p: np.interp(np.arange(p, len(o) - 1, period), ox, o).sum())
    beats = np.arange(ph, len(o) - 1, period)
    lv = np.interp(beats, np.arange(len(lo)), lo)
    sc = np.array([lv[k::4].mean() for k in range(4)]); k = int(np.argmax(sc)); s2 = np.sort(sc)[-2]
    bar = 4 * period / fps; db0 = beats[k] / fps
    # bar levels from the first downbeat; the longest run within 4 dB of the median is the steady section
    starts = np.arange(db0, len(x) / sr - bar, bar)
    lev = np.array([10 * np.log10(np.mean(x[int(s * sr):int((s + bar) * sr)] ** 2) + 1e-12) for s in starts])
    ok = lev > np.median(lev) - 4; best, cur = (0, 0), None
    for i, v in enumerate(list(ok) + [False]):
        if v and cur is None: cur = i
        if not v and cur is not None:
            if i - cur > best[1] - best[0]: best = (cur, i)
            cur = None
    return {"duration": round(len(x) / sr, 2), "bpm": float(bpm), "bar": round(bar, 4), "downbeat": round(db0, 4),
            "grid_conf": round(float(sc[k] / (s2 + 1e-9)), 2), "full_from": round(float(starts[best[0]]), 4),
            "full_to": round(float(starts[best[0]] + (best[1] - best[0]) * bar), 4), **trap_measures(f)}


def trap_measures(f):
    """What makes it trap: busy hi-hat patterns with rolls over a ringing, sliding 808.

    hat_rate: hi-hat hits per second (onsets in 6-15 kHz). hat_rolls: bursts of 3+ hits less than 80 ms apart, per
    10 s (rolls, 32nds, triplet runs). sub_share: median share of 28-130 Hz in each 50 ms frame. slides: 808 glides
    per minute (the sub's pitch moving 2+ semitones within 200 ms while it rings).
    A trap beat here: hat_rolls >= 3 and sub_share >= 0.3. Plenty of beats tagged trap measure 0 rolls."""
    sr = 44100; x = np.frombuffer(run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                                      text=False).stdout, np.float32).astype(np.float64)
    N, H = 512, 128; fps = sr / H
    fr = np.lib.stride_tricks.sliding_window_view(np.pad(x, (0, N)), N)[::H][: len(x) // H]
    S = np.abs(np.fft.rfft(fr * np.hanning(N), axis=1)); fq = np.fft.rfftfreq(N, 1 / sr)
    e = np.log1p(S[:, (fq >= 6000) & (fq < 15000)].sum(1) * 20); flux = np.maximum(0, np.diff(e, prepend=e[0]))
    w = int(0.5 * fps); pad = np.pad(flux, (w, w), mode="edge")
    med = np.median(np.lib.stride_tricks.sliding_window_view(pad, 2 * w)[::8], axis=1).repeat(8)[: len(flux)]
    thr = med + 0.35 * np.percentile(flux, 99)
    pk = np.where((flux[1:-1] > thr[1:-1]) & (flux[1:-1] >= flux[:-2]) & (flux[1:-1] > flux[2:]))[0] + 1
    t = []
    for i in pk:
        if not t or i / fps - t[-1] > 0.025: t.append(i / fps)
    short = np.diff(t) < 0.08; rolls, r = 0, 0
    for s in short:
        r = r + 1 if s else 0; rolls += r == 3
    x2 = x[::2]; sr2 = sr // 2; N2, H2 = 8192, int(0.05 * sr2)
    fr2 = np.lib.stride_tricks.sliding_window_view(x2, N2)[::H2]
    P = np.abs(np.fft.rfft(fr2 * np.hanning(N2), axis=1)) ** 2; f2 = np.fft.rfftfreq(N2, 1 / sr2)
    band = (f2 >= 28) & (f2 < 130); sub = P[:, band]; tot = P[:, (f2 >= 28) & (f2 < 8000)].sum(1) + 1e-12
    loud = sub.sum(1) > np.percentile(sub.sum(1), 40); st = 12 * np.log2(f2[band][np.argmax(sub, axis=1)] / 55.0)
    slides, i = 0, 0
    while i < len(st) - 4:
        if loud[i:i + 5].all() and abs(st[i + 4] - st[i]) >= 2 and np.all(np.abs(np.diff(st[i:i + 5])) < 2.5): slides += 1; i += 5
        else: i += 1
    d = len(x) / sr
    return {"hat_rate": round(len(t) / d, 2), "hat_rolls": round(rolls / d * 10, 2),
            "sub_share": round(float(np.median(sub.sum(1) / tot)), 2), "slides": round(slides / d * 60, 1)}


# ---------------------------------------------------------------- commands

def http_get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r: return r.read()
        except Exception as e:
            if i == 2: raise
            time.sleep(2 * (i + 1))


def cmd_fetch(a):
    LIB.mkdir(parents=True, exist_ok=True); lib = library(); got = 0
    for t in lib.values():
        f = path(t["id"])
        if not f.exists():
            f.write_bytes(http_get(t["url"])); got += 1; print(f"downloaded {t['id']} {t['title']}")
        if "bar" not in t: t.update(analyse_file(f))
    _save(lib); print(f"{got} downloaded, {len(lib)} tracks in {LIB}")


def cmd_analyse(a):
    lib = library()
    for tid in a.ids or list(lib):
        t = track(tid); t.update(analyse_file(path(tid))); print(tid, {k: t[k] for k in ("bpm", "bar", "downbeat", "grid_conf", "full_from", "full_to")})
    _save(lib)


def cmd_list(a):
    for t in library().values():
        if a.tags and not set(a.tags) & set(t.get("tags", [])): continue
        have = "ok" if path(t["id"]).exists() else "missing"
        print(f"{t['id']:<13} {t['title'][:20]:<20} {t.get('bpm', 0):>5.1f} bpm  grid {t.get('grid_conf', 0):>4.1f}  "
              f"full {t.get('full_from', 0):5.1f}-{t.get('full_to', 0):5.1f}s  rolls/10s {t.get('hat_rolls', 0):4.1f}  "
              f"808 {t.get('sub_share', 0):.2f} slides/min {t.get('slides', 0):4.1f}  {have:<7} {','.join(t.get('tags', []))}")


def cmd_audition(a):
    sys.path.insert(0, str(Path(__file__).parent))
    import mix
    proj = Path(a.project).expanduser().resolve(); plan = load(proj / "plan.json")
    from common import load_style
    M = dict(load_style(plan).get("music", {})); ev = load(proj / "work" / "out" / a.variant / "events.json")
    ids = a.ids.split(",") if a.ids else [t for t in library() if library()[t].get("pick")] or list(library())[:4]
    parts = [proj / "work" / "parts" / f"hook-{a.variant}" / "voice.wav", proj / "work" / "parts" / "body" / "voice.wav"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); (tmp / "l.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "l.txt"), "-af", mix.VOICE_CHAIN,
             "-ac", "2", "-t", str(a.secs), "-c:a", "pcm_f32le", str(tmp / "v.wav")])
        v = mix.pcm2(tmp / "v.wav").astype(np.float64); n = int(a.secs * SR); v = np.pad(v, ((0, max(0, n - len(v))), (0, 0)))[:n]
        vm = np.sqrt(np.mean(v ** 2, axis=1)); vw = mix.win_db(vm, int(0.4 * SR)); ref = float(np.median(vw[vw > vw.max() - 20]))
        drops = [d for d in ev.get("drops", []) if d < a.secs]; out = []
        for k, tid in enumerate(ids):
            t = track(tid); M2 = dict(M, bed=f"track:{t['id']}", level=M.get("level", -18) if M.get("bed", "").startswith("track:") else -18)
            f = tmp / f"say{k}.aiff"; subprocess.run(["say", "-r", "190", "-o", str(f), f"{t['title']}."], check=True)
            s = mix.pcm2(f).astype(np.float64) * 0.6
            mus = mix.music_bus(M2, a.secs, drops, vm, ref, n)
            out += [s, np.zeros((int(0.3 * SR), 2)), v + mus, np.zeros((int(0.8 * SR), 2))]
        y = np.concatenate(out); y = y / (np.abs(y).max() + 1e-9) * 0.9
        y.astype(np.float32).tofile(tmp / "a.f32")
        run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(tmp / "a.f32"),
             "-af", "loudnorm=I=-14:TP=-1", "-c:a", "aac", "-b:a", "192k", str(Path(a.out).expanduser())])
    print(f"wrote {a.out}: {', '.join(track(i)['title'] for i in ids)}")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("fetch")
    p = sp.add_parser("list"); p.add_argument("tags", nargs="*")
    p = sp.add_parser("analyse"); p.add_argument("ids", nargs="*")
    p = sp.add_parser("audition"); p.add_argument("project"); p.add_argument("--variant", required=True)
    p.add_argument("--ids"); p.add_argument("--secs", type=float, default=16.0)
    p.add_argument("--out", default=str(Path.home() / "Downloads" / "reel-music-audition.m4a"))
    a = ap.parse_args()
    {"fetch": cmd_fetch, "list": cmd_list, "analyse": cmd_analyse, "audition": cmd_audition}[a.cmd](a)


if __name__ == "__main__":
    main()
