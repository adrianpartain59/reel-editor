#!/usr/bin/env python3
"""Sound and final assembly of a canvas reel: hook + body, the voice, the effects, the beat.

  canvas_sound.py PROJECT                      -> out/<slug>.mp4, out/<slug>-phone.mp4, out/<slug>-sheet.jpg
  canvas_sound.py PROJECT --beat mixkit-403    same with another beat (or --beat none); writes out/<slug>-<beat>.mp4
  canvas_sound.py PROJECT --countup arcade     taps (default), arcade, charge
  canvas_sound.py PROJECT --keys [ids]         does the count-up's scale sit on each beat? prints the shift to use

Hook: whoosh as the card comes and goes, the count-up (pitch follows the graph line), a low hit and a ding on the landing, a pop
per title word. Body: a quiet whoosh on every camera flight and face cut, and the cues the scenes ask for. Beat: nothing under the
count-up, it drops on the landing, cuts at "stop" and returns at "back". Voice: the house chain, -12 LUFS, about -1 dBTP.
Nothing here can be heard by whoever runs it: every number printed is a measurement.
"""
import argparse, json, subprocess, sys
from collections import Counter
from pathlib import Path
import numpy as np
from common import run, ASSETS, MUSIC
import canvas_lib as L
import countup_hook as K

SR, TARGET = 48000, -12.0
import sfx_lib, sfx_pack
sfx_pack.ensure()
LIB, CU = ASSETS / "sfx/lib", ASSETS / "sfx/countup"
CHAIN = json.loads((ASSETS / "styles/cinematic.json").read_text())["mix"]["voice_chain"]
PEAK = {c: sfx_lib.sound(f"{c}_01")["sync"] for c in ("whoosh", "pop", "key", "low_hit", "counting")}     # where in the file the sound happens
DB = {"whoosh": -13.5, "pop": -12.5, "scribble": -13, "counting": -14, "low_hit": -9, "key": -16}     # under the voice's speech level


def pcm(path, ch=2):
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", str(ch), "-ar", str(SR), "-f", "f32le", "-"], text=False).stdout; return np.frombuffer(raw, np.float32).reshape(-1, ch).astype(np.float64)


def hp(x, fc=100.0):
    X = np.fft.rfft(x, axis=0); f = np.fft.rfftfreq(len(x), 1 / SR); return np.fft.irfft(X * (1 / (1 + (fc / np.maximum(f, 1)) ** 4))[:, None], n=len(x), axis=0)


def loud100(x):
    m = np.sqrt(np.mean(hp(x) ** 2, axis=1)); w = int(0.1 * SR); n = max(1, len(m) // (w // 4) - 4); return max(20 * np.log10(np.sqrt(np.mean(m[i * (w // 4): i * (w // 4) + w] ** 2)) + 1e-12) for i in range(n))


def lib(c, i=1): return pcm(LIB / c / f"{c}_{i:02d}.wav")


def stretch_pitch(x, semis):
    r = 2 ** (semis / 12); i = np.arange(int(len(x) / r)) * r; return np.stack([np.interp(i, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], 1)


# ---------------------------------------------------------------- the count-up
PENTA = [0, 2, 4, 7, 9]
def degree(k, shift): return 12 * (k // 5) + PENTA[k % 5] + shift                                      # k-th note of C major pentatonic above C5, in semitones


def taps(shift):
    """one tap repitched once per tick, plus a soft marimba body: the pitch is the height of the graph line"""
    src = pcm(CU / "tap.wav", 1)[:, 0]; on = int(np.argmax(np.abs(src) > 0.05)); src = src[max(0, on - 40): on + int(0.09 * SR)]; f_src = 1714.0; out = np.zeros(int((K.T1 - K.T0 + 1.6) * SR)); ticks = []; t = K.T0; hs = K.tip_h(K.T_SURGE)
    while t < K.T1 - 0.012:
        h = K.tip_h(t)
        if t < K.T_SURGE: k = int(round(4 * h / 138)); rate = 13.5; g = 0.52
        else: s = (t - K.T_SURGE) / (K.T1 - K.T_SURGE); k = int(round(2 + 9.2 * ((h - hs) / (K.BASE - K.TOP - hs)) ** 0.62)); rate = 14 + 17 * s; g = 0.56 + 0.44 * s
        ticks.append((t, k, g)); t += 1 / rate
    for t, k, g in ticks:
        f = 523.25 * 2 ** (degree(k, shift) / 12); r = f / f_src; n = int(len(src) / r); tap = np.interp(np.arange(n) * r, np.arange(len(src)), src); tt = np.arange(int(0.16 * SR)) / SR
        body = (np.sin(2 * np.pi * f * tt) + 0.28 * np.sin(2 * np.pi * 3.93 * f * tt) * np.exp(-tt * 40)) * np.exp(-tt * 26) * np.minimum(1, tt / 0.0015); i = int((t - K.T0) * SR); tap = tap / (np.abs(tap).max() + 1e-9)
        out[i: i + len(tap)] += 0.62 * g * tap; out[i: i + len(body)] += 0.42 * g * body
    out = out[: int((K.T1 - K.T0 + 0.25) * SR)]; d = int(0.009 * SR); return np.stack([out + 0.18 * np.concatenate([np.zeros(d), out[:-d]]), out], 1), K.T0


def whole(name, end):
    x = pcm(CU / name, 2); a = np.abs(x).max(1); i0 = int(np.argmax(a > 0.01)); i1 = len(a) - int(np.argmax(a[::-1] > 0.02)); x = x[i0:i1]; return x, end - len(x) / SR


# ---------------------------------------------------------------- cues: (samples, time on the reel, dB vs voice, kind)
def hook_cues(kind, shift):
    cu, t0 = taps(shift) if kind == "taps" else whole("arcade.wav" if kind == "arcade" else "charge.wav", K.T1 + 0.02); ding = pcm(CU / "ding.wav"); ding = stretch_pitch(ding, shift) if shift else ding; ding = ding * np.linspace(1, 0, len(ding))[:, None] ** 0.6; wh, pop = lib("whoosh"), lib("pop")
    return [(wh, K.CARD_IN - PEAK["whoosh"] + 0.06, -12, "whoosh"), (cu, t0, {"taps": -3.0, "arcade": -7.0, "charge": -6.5}[kind], "count-up"), (lib("low_hit"), K.T1 - PEAK["low_hit"], -6, "low_hit"), (ding, K.T1, -13, "ding"), (wh, K.CARD_OUT - PEAK["whoosh"] + 0.12, -12, "whoosh")] + [(pop, w[1] + 0.02 - PEAK["pop"], -9, "pop") for w in (K.TITLE or {}).get("words", [])]


def scribbles():
    out = []
    for f in sorted((LIB / "scribble").glob("*.wav")): x = pcm(f); a = np.abs(x).max(1); out.append((len(x) / SR, int(np.argmax(a > a.max() * 0.05)) / SR, x))
    return out


def body_cues(reel, info, hd):
    c = []; faces = reel.get("faces", []); cuts = [(f["in"], f.get("enter", "down") != "cut") for f in faces] + [(f["out"], True) for f in faces if f.get("back")]
    for t in [0.02] + [t for t, snd in cuts if snd] + [(a + b) / 2 - 0.04 for a, b, *_ in info["flights"] if not any(abs(t - (a + b) / 2) < 0.6 for t, _ in cuts)]: c.append(("whoosh", t))
    for k, v in info["cues"].items(): c += [(k, x) for x in v]
    pool = scribbles(); used = -1; out = []
    for k, x in sorted(c, key=lambda q: q[1][0] if isinstance(q[1], list) else q[1]):
        t, extra = (x[0], x[1] if len(x) > 1 else None) if isinstance(x, list) else (x, None)
        if k == "scribble":
            j = min((i for i in range(len(pool)) if i != used), key=lambda i: abs(pool[i][0] - pool[i][1] - (extra or 0.3))); used = j; out.append((pool[j][2], hd + t - pool[j][1], DB[k], k))
        else: out.append((lib(k), hd + t - PEAK.get(k, 0), extra if extra is not None else DB[k], k))
    o = reel.get("outro"); ks = list(range(1, len(sfx_lib.ids("key")) + 1))
    for n, ch in enumerate(o["text"] if o else ""):
        if ch != " ": out.append((lib("key", ks[(n * 7) % len(ks)]), hd + o["t0"] + o.get("delay", 0.15) + (n + 1) * o.get("cps", 0.05) - 0.004, DB["key"], "key"))
    return out


# ---------------------------------------------------------------- voice, mix, master
def voice(proj, parts, n):
    (proj / "work/v.txt").write_text("".join(f"file '{proj}/work/parts/{p}/voice.wav'\n" for p in parts)); run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(proj / "work/v.txt"), "-af", CHAIN, "-ac", "2", "-c:a", "pcm_f32le", str(proj / "work/voice.wav")])
    v = pcm(proj / "work/voice.wav"); return np.pad(v, ((0, max(0, n - len(v))), (0, 0)))[:n]


def speech_ref(v):
    vm = np.sqrt(np.mean(v ** 2, axis=1)); w = int(0.4 * SR); n = len(vm) // w; d = 20 * np.log10(np.sqrt(np.mean(vm[: n * w].reshape(n, w) ** 2, axis=1)) + 1e-12); return float(np.median(d[d > d.max() - 20]))


def bus(cues, n, ref):
    b = np.zeros((n + 4 * SR, 2))
    for x, t, db, _ in cues: g = ref + db - loud100(x); i = int(round(t * SR)); seg = x[max(0, -i):]; i = max(0, i); b[i: i + len(seg)] += seg[: len(b) - i] * 10 ** (g / 20)
    return b[:n]


def onset(x, t, w=0.12):
    s = np.abs(x[int((t - w) * SR):int((t + w) * SR)]).max(1); return float(np.argmax(s > s.max() * 0.25) / SR - w)


def music(beat, hd, dur, vm, ref, n):
    """nothing before the landing; the first kick of the beat's full section nudged onto the landing and onto the return"""
    import mix as M
    land, back = K.T1, hd + beat["back"] if "back" in beat else None; stop = hd + beat["stop"] if "stop" in beat else None; drops = [land] + ([back] if back else []); cfg = {"bed": f"track:{beat['track']}", "level": beat.get("level", -16), "duck": beat.get("duck", 3), "drop_len": (back - stop) if back else 0.5}
    nudge = 0.0
    for _ in range(2): mus = M.music_bus(cfg, dur, [d + nudge for d in drops], vm, ref, n); nudge = beat["nudge"] if "nudge" in beat else round(nudge - onset(mus, land), 3)
    mus = M.music_bus(cfg, dur, [d + nudge for d in drops], vm, ref, n); k = max(0, int((land + nudge - 0.015) * SR)); f = int(0.004 * SR); mus[:k] = 0; mus[k:k + f] *= np.linspace(0, 1, f)[:, None]; e = int(0.35 * SR); mus[-e:] *= np.linspace(1, 0, e)[:, None]
    db = lambda z, a, c: 20 * np.log10(np.sqrt((M.hp_fft(z[int(a * SR):int(c * SR)], 150.0) ** 2).mean()) + 1e-12)
    print(f"beat {beat['track']}: nudge {nudge * 1000:.0f} ms; first hit {onset(mus, land) * 1000:.0f} ms from the landing" + (f", {onset(mus, back) * 1000:.0f} ms from the return; gap {db(mus, stop + .06, back - .04):.0f} dB" if back else "")); return mus


def loud(args):
    m = subprocess.run(["ffmpeg", "-hide_banner", *args, "-f", "null", "-"], capture_output=True, text=True).stderr; return json.loads(m[m.rindex("{"): m.rindex("}") + 1])


def master(proj, mix, video, final, dur):
    tmp = proj / "work/premix.f32"; mix.astype(np.float32).tofile(tmp); src = ["-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(tmp)]; gain = TARGET - float(loud([*src, "-af", "loudnorm=print_format=json"])["input_i"]); ceil = -2.0
    for _ in range(4):
        lim = f"aresample=192000,alimiter=limit={10 ** (ceil / 20):.3f}:attack=3:release=60:level=false,aresample=48000"
        for _ in range(2):
            got = float(loud([*src, "-af", f"volume={gain:.2f}dB,{lim},loudnorm=print_format=json"])["input_i"])
            if abs(got - TARGET) < 0.15: break
            gain += TARGET - got
        run(["ffmpeg", "-v", "error", "-y", "-i", str(video), *src, "-af", f"volume={gain:.2f}dB,{lim},apad", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-t", f"{dur:.4f}", "-movflags", "+faststart", str(final)])
        js = loud(["-i", str(final), "-vn", "-af", "loudnorm=print_format=json"]); ceil -= max(0, float(js["input_tp"]) + 1.1)
        if float(js["input_tp"]) <= -1.0: break
    print(f"{final.name}: {js['input_i']} LUFS, {js['input_tp']} dBTP")


def concat(proj, files, out):
    """Re-encode with one set of settings, so the hook and the body can't differ in colour or timing."""
    (proj / "work/c.txt").write_text("".join(f"file '{f}'\n" for f in files)); run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(proj / "work/c.txt"), "-vf", "fps=30", *L.h264(("-crf", "16", "-preset", "medium")), "-movflags", "+faststart", str(out)])


def keys(ids):
    """Rough key of each beat's steady section: which shift (semitones) puts the count-up's pentatonic scale on it."""
    A = ASSETS / "music"; tr = json.loads((A / "library.json").read_text()); tr = tr["tracks"] if isinstance(tr, dict) and "tracks" in tr else tr
    for t in tr:
        if ids and t["id"] not in ids: continue
        if not (MUSIC / f"{t['id']}.mp3").exists(): print(f"{t['id']}: not downloaded (music_lib.py fetch)"); continue
        a, b = t["full_from"], min(t["full_to"], t["full_from"] + 40); raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", str(MUSIC / f"{t['id']}.mp3"), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, np.float32); n = 8192; f = np.fft.rfftfreq(n, 1 / 16000); lo = (f >= 110) & (f <= 1400); ch = np.zeros(12)
        for i in range(0, len(x) - n, 4096):
            s = np.abs(np.fft.rfft(x[i:i + n] * np.hanning(n)))
            for k in np.where(lo)[0][2:-2]:
                if s[k] > s[k - 1] and s[k] >= s[k + 1] and s[k] > s[lo].max() * .08: d = .5 * (s[k - 1] - s[k + 1]) / (s[k - 1] - 2 * s[k] + s[k + 1] + 1e-12); ch[int(round(69 + 12 * np.log2((k + d) * 16000 / n / 440))) % 12] += s[k] ** .7
        ch /= ch.sum(); fit = {r if r <= 6 else r - 12: sum(ch[(r + k) % 12] for k in PENTA) for r in range(12)}; near = {r: v for r, v in fit.items() if abs(r) <= 2}; best = max(near, key=near.get); best = 0 if near[0] > near[best] - .03 else best
        print(f"{t['id']} {t['title']}: grid {t['grid_conf']}{' (NOT trusted: cannot cut cleanly)' if t['grid_conf'] < 2 else ''}; scale fit as is {fit[0]:.2f}, use \"shift\": {best} ({near[best]:.2f})")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--beat"); ap.add_argument("--countup", default=None); ap.add_argument("--keys", nargs="*"); a = ap.parse_args()
    if a.keys is not None: keys(a.keys); return
    proj, reel = L.project(a.project); K.setup(a.project); hd = K.P["dur"]; body = L.part(proj, reel.get("part", "body")); dur = hd + body["dur"]; n = int(round(dur * SR)); (proj / "out").mkdir(exist_ok=True); info = L.scenes_info(proj, reel)
    beat = dict(reel.get("beat") or {}) if a.beat != "none" else {}
    if a.beat and a.beat != "none": beat = {**beat, "track": a.beat}; beat.pop("nudge", None) if a.beat != (reel.get("beat") or {}).get("track") else None
    if beat:
        import music_lib
        if not music_lib.path(beat["track"]).exists(): print(f"note: beat {beat['track']} isn't downloaded, so there's no beat (scripts/music_lib.py fetch gets them)"); beat = {}
    shift = beat.get("shift", 0); kind = a.countup or reel["hook"].get("countup", "taps"); v = voice(proj, ["hook-" + reel["hook"].get("variant", "main"), reel.get("part", "body")], n); ref = speech_ref(v); vm = np.sqrt(np.mean(v ** 2, axis=1))
    hc = hook_cues(kind, shift); bc = body_cues(reel, info, hd); fx = bus(hc + bc, n, ref); mus = music(beat, hd, dur, vm, ref, n) if beat.get("track") else np.zeros_like(v)
    reelv = proj / "work/reel.mp4"; src = [proj / "work/hook_video.mp4", proj / "work/body_final.mp4"]
    for f in src:
        if not f.exists(): L.die(f"{f} missing (countup_hook.py render, canvas_body.py render)")
    if not reelv.exists() or reelv.stat().st_mtime < max(f.stat().st_mtime for f in src): concat(proj, src, reelv)
    slug = reel.get("slug", proj.name) + (f"-{a.beat}" if a.beat else "") + (f"-{a.countup}" if a.countup else ""); out = proj / f"out/{slug}.mp4"; master(proj, v + fx + mus, reelv, out, dur)
    vk = int(min(5000, 27.5 * 8000 / dur - 300)); run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-maxrate", f"{vk}k", "-bufsize", f"{vk * 2}k", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(proj / f"out/{slug}-phone.mp4")])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf", "fps=2/3,scale=180:-1,tile=12x6", "-frames:v", "1", str(proj / f"out/{slug}-sheet.jpg")])
    fr = int(run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(out)]).stdout.strip()); want = K.N + body["frames"]
    print(f"{'OK' if fr == want else 'FAIL'} frames {fr} of {want}; {dur:.2f} s; speech {ref:.1f} dBFS; cues {dict(Counter(c[3] for c in hc + bc))}")
    f = lambda z, p, q: 20 * np.log10(np.sqrt((z[int(p * SR):int(q * SR)] ** 2).mean()) + 1e-12); hot = [round(float(t), 1) for t in np.arange(hd, dur - .5, .5) if f(v, t, t + .5) > ref - 12 and f(fx, t, t + .5) > f(v, t, t + .5) - 6]
    print("WARN effects within 6 dB of the voice at " + ", ".join(map(str, hot)) if hot else "OK no body effect comes within 6 dB of the voice while the speaker speaks")


if __name__ == "__main__": main()
