#!/usr/bin/env python3
"""Step 5: sound. Voice clean-up, SFX placed against the voice, master for Instagram, mux.

  mix.py PROJECT --variant h1      -> out/<slug>-h1.mp4 (full quality) and out/<slug>-h1-phone.mp4 (<30 MB)

Levels are measured, not guessed:
- Voice: kept exactly as recorded, in stereo. Only a 70 Hz high-pass (rumble) and gentle linked compression.
  No denoise, no low-pass, no mono fold-down: iPhone stereo comes from two spaced mics whose highs are out of
  phase, so summing them to mono cancels 5-10 dB of the 4-16 kHz clarity band (measured), and a
  spectral denoiser set above the real noise floor strips consonants and adds a watery sound. Opt-in denoise:
  plan.json "audio": {"denoise": true} applies afftdn at the measured noise floor, gently.
- SFX: each cue's loudest 100 ms is placed OFFSET dB under the voice's typical 400 ms speech level, by category,
  plus the cue's own extra dB. So effects sit at a known distance under the voice whatever the file's own level.
- Master: the stereo mix, linear gain to -12 LUFS integrated, true-peak limiter at -1 dBTP. Meta publishes no Reels loudness spec;
  -12 keeps a voice-only reel from sounding quiet next to music reels while leaving headroom for re-encoding.
"""
import argparse, json, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
from common import load, run, load_style, ASSETS, SR, die

TARGET_LUFS = -12.0
# cinematic bank: levels are measured on the phone-audible part (>100 Hz), so a sub hit's 30-60 Hz body does not
# eat its level budget; the sub then adds weight on headphones without making the hit louder on a phone speaker.
OFFSET_CINE = {"cine_hit": -3, "cine_boom": -2, "cine_whoosh": -8, "cine_swish": -10, "cine_whoosh_out": -10,
               "cine_riser": -9, "cine_suck": -9, "cine_glitch": -8, "cine_shimmer": -11, "cine_neon": -11,
               "ui_click": -10, "ui_tick": -14, "type_key": -13, "notif": -8, "cine_tape": -6}
OFFSET = {"pop": -5, "thud": -5, "buzzer": -6, "ding": -5, "cha_ching": -6, "scratch": -7, "boom": -4,
          "glitch": -8, "notify": -6, "shutter": -7, "shimmer": -9, "click": -10, "typing": -10,
          "whoosh": -9, "whoosh_short": -10, "whoosh_down": -10, "riser": -9, "tick": -11}
VOICE_CHAIN = "highpass=f=70,acompressor=threshold=-24dB:ratio=2.5:attack=8:release=120:makeup=2:link=average"


def pcm2(path):
    """Stereo float frames (n, 2)."""
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], text=False).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def win_db(x, win):
    n = len(x) // win
    if n == 0: return np.array([20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)])
    return 20 * np.log10(np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-12)


def read_sfx(f):
    """(n, 2) float: stereo files as they are, mono files duplicated."""
    with wave.open(str(f)) as w:
        ch = w.getnchannels(); x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2") / 32768.0
    return x.reshape(-1, ch) if ch == 2 else np.stack([x, x], 1)


def hp_fft(x, fc=100.0):
    X = np.fft.rfft(x, axis=0); f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X * (1 / (1 + (fc / np.maximum(f, 1)) ** 4))[:, None], n=len(x), axis=0)


def music_bus(M, duration, drops, vm, ref, n_total):
    """The style's music bed (n_total, 2) at `level` dB under the voice's speech level, ducked `duck` dB while the speaker
    speaks. A downloaded beat ("track:<id>") is levelled on what a phone speaker plays (above 150 Hz), since its
    808 sub carries most of its energy and a phone reproduces none of it."""
    from music import bed
    trk = M["bed"].startswith("track:")
    kw = {"pocket": M.get("pocket", -4.0), "sub": M.get("sub", -3.0)} if trk else {}
    mus = bed(M["bed"], duration, drops=drops, seed=M.get("seed", 1), drop_len=M.get("drop_len", 0.5), **kw).astype(np.float64)
    mus = np.pad(mus, ((0, max(0, n_total - len(mus))), (0, 0)))[:n_total]
    meas = hp_fft(mus, 150.0) if trk else mus
    w = win_db(np.sqrt(np.mean(meas ** 2, axis=1)), int(0.4 * SR))
    lvl = float(np.median(w[w > w.max() - 30] if trk else w))        # a beat's cut gaps are not its level
    mus *= 10 ** ((ref + M.get("level", -15) - lvl) / 20)
    # duck a little under speech: smoothed voice activity -> up to `duck` dB down
    act = (win_db(vm, int(0.05 * SR)) > ref - 14).astype(float)
    k = np.ones(6) / 6; act = np.convolve(act, k, mode="same")
    env = np.repeat(act, int(0.05 * SR))[:n_total]; env = np.pad(env, (0, n_total - len(env)))
    mus *= (10 ** (-M.get("duck", 2.5) * env / 20))[:, None]
    return mus


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--variant", required=True)
    a = ap.parse_args()
    proj = Path(a.project).expanduser().resolve(); plan = load(proj / "plan.json")
    style = load_style(plan); target = float(style["mix"].get("lufs", TARGET_LUFS))
    od = proj / "work" / "out" / a.variant; ev = load(od / "events.json")
    if not (od / "video.mp4").exists(): die("run compose.py first")
    import sfx_pack; sfx_pack.ensure()
    parts = [proj / "work" / "parts" / f"hook-{a.variant}" / "voice.wav", proj / "work" / "parts" / "body" / "voice.wav"]
    clipmap = {c["id"]: c for c in load(proj / "project.json")["clips"]}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "l.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        chain = style["mix"].get("voice_chain", VOICE_CHAIN)
        if plan.get("audio", {}).get("denoise"):
            floor = max(c["levels"]["noise_db"] for c in load(proj / "project.json")["clips"])
            chain = f"afftdn=nf={max(-80, floor - 2):.0f}:nr=8:tn=1," + chain
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "l.txt"), "-af", chain,
             "-ac", "2", "-c:a", "pcm_f32le", str(tmp / "voice.wav")])
        v2 = pcm2(tmp / "voice.wav")
        n_total = int(round(ev["duration"] * SR)); v2 = np.pad(v2, ((0, max(0, n_total - len(v2))), (0, 0)))[:n_total]
        vm = np.sqrt(np.mean(v2 ** 2, axis=1))                       # per-sample level across both channels
        vw = win_db(vm, int(0.4 * SR)); ref = float(np.median(vw[vw > vw.max() - 20]))
        # Sound effects go through the audio map: trimmed to their visual, one at a time, whooshes short.
        import audiomap, speechmap
        try: import sfx_lib
        except Exception: sfx_lib = None
        cache = {}
        def load_sfx(name):
            if name in cache: return cache[name]
            if sfx_lib is None: return None
            # only the sound pack plays: any other name maps to its pack sound
            try: meta = sfx_lib.sound(name[4:] if name.startswith("lib:") else name)
            except KeyError: cache[name] = None; return None
            lib = True; f = sfx_lib.LIB / meta["file"]
            if not f.exists(): cache[name] = None; return None
            x = read_sfx(f); cine = name in OFFSET_CINE or lib
            meas = hp_fft(x) if cine else x
            pk = float(win_db(np.sqrt(np.mean(meas ** 2, axis=1)), int(0.1 * SR)).max())
            full = float(win_db(np.sqrt(np.mean(x ** 2, axis=1)), int(0.1 * SR)).max())
            off = sfx_lib.offset(meta["cat"]) if lib else (OFFSET_CINE.get(name, -8) if cine else OFFSET.get(name, -8))
            cache[name] = (x, meta.get("sync", 0.0) if lib else 0.0, meta.get("cat") if lib else name)
            levels[name] = (pk, full, off)
            return cache[name]
        levels = {}
        def gain_of(p):
            pk, full, off = levels[p["name"]]
            return min(ref + off + p["extra_db"] - pk, ref + 4 - full)   # the sub body never peaks 4 dB over the voice
        hook_end = ev.get("hook_end", 0.0)
        placed, dropped = audiomap.schedule(ev["sfx"], SR, load_sfx, rules_of=sfx_lib.rules if sfx_lib else (lambda c: {}), hook_end=hook_end, duration=ev["duration"])
        bus = np.zeros((n_total + 3 * SR, 2))
        bus[: n_total + 3 * SR] += audiomap.render(placed, n_total + 3 * SR, SR, gain_of)
        used = [p["name"] for p in placed]
        # Risers: a build under the voice that peaks on a word (plan "risers"). Mixed like the bed, not through the
        # audio map, so the cues on top don't cut it: the build is the point. Fades in from t0, stops just after the peak.
        riser_info = []
        for rz in ev.get("risers", []):
            got = load_sfx("lib:" + rz["id"])
            if got is None: print(f"riser {rz['id']} not in the library; skipped"); continue
            x, sync, _ = got; pk, full, off = levels["lib:" + rz["id"]]
            # rules: a riser plays only in the hook, once, whole (never trimmed or faded in early)
            if riser_info: print(f"riser {rz['id']} at {rz['peak']:.2f}s skipped: one riser a reel"); continue
            if rz["peak"] > hook_end + 0.01: print(f"riser {rz['id']} at {rz['peak']:.2f}s skipped: risers only play in the hook"); continue
            start = rz["peak"] - sync
            if start < 0: print(f"riser {rz['id']} skipped: it would have to start before the reel"); continue
            seg = x.copy()
            g = min(ref + off + rz.get("db", 0) - pk, ref + 4 - full)
            i0 = int(round(start * SR)); bus[i0: i0 + len(seg)] += seg * 10 ** (g / 20)
            riser_info.append(f"{rz['id']} {start:.2f}-{rz['peak']:.2f}s")
            used.append("lib:" + rz["id"])
        speech = []
        for part, off_t in ((f"hook-{a.variant}", 0.0), ("body", None)):
            pdir = proj / "work" / "parts" / part
            sg = load(pdir / "segs.json")
            if off_t is None: off_t = hook_dur
            else: hook_dur = sg["duration"]
            lv = {s["clip"]: clipmap[s["clip"]].get("speech_lv") or speechmap.clip_levels(clipmap[s["clip"]]["file"]) for s in sg["segs"]}
            regs_, _ = speechmap.part_regions(pdir / "voice.wav", sg["segs"], lv)
            speech += [[a_ + off_t, b_ + off_t] for a_, b_ in regs_]
        bed_info = ""
        if style.get("music", {}).get("bed"):
            M = style["music"]
            bus[:n_total] += music_bus(M, ev["duration"], ev.get("drops", []), vm, ref, n_total)
            name = M["bed"]
            if name.startswith("track:"):
                import music_lib; t = music_lib.track(name); name = f"{t['title']} by {t['artist']} ({t['id']})"
            bed_info = f"; music bed {name} at {M.get('level', -15)} dB under the voice, {len(ev.get('drops', []))} drops"
        mus_info = {"bed": style.get("music", {}).get("bed"), "level_db": style.get("music", {}).get("level")} if style.get("music", {}).get("bed") else None
        audiomap.write(od / "audio_map.json", od / "audio_map.txt", ev["duration"], speech, placed, dropped, mus_info, hook_end)
        if dropped: print(f"audio map: {len(placed)} effects placed, {len(dropped)} dropped (one at a time, no pile-ups)")
        mix = (v2 + bus[:n_total]).astype(np.float32); mix.tofile(tmp / "premix.f32")
        src = ["-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(tmp / "premix.f32")]
        m = subprocess.run(["ffmpeg", "-hide_banner", *src, "-af", f"loudnorm=I={target}:TP=-1:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
        js = json.loads(m[m.rindex("{"): m.rindex("}") + 1])
        gain = target - float(js["input_i"])
        # ceiling -2 dBFS (oversampled): AAC encoding overshoots ~1 dB, so the encoded file lands near -1 dBTP.
        # The overshoot depends on the material (a trap beat's 808 pushed it to 1.55 dB, landing at -0.45 dBTP), so
        # the encoded file is measured and, if it is over -1 dBTP, re-mastered with the ceiling lowered by the excess.
        # The limiter shaves a little loudness, so measure after it once and correct the gain.
        slug = plan.get("slug", "reel"); (proj / "out").mkdir(exist_ok=True)
        final = proj / "out" / f"{slug}-{a.variant}.mp4"
        ceil = -2.0
        for _ in range(3):
            lim = f"aresample=192000,alimiter=limit={10 ** (ceil / 20):.3f}:attack=3:release=60:level=false,aresample=48000"
            for _ in range(2):
                m2 = subprocess.run(["ffmpeg", "-hide_banner", *src, "-af", f"volume={gain:.2f}dB,{lim},loudnorm=print_format=json",
                                     "-f", "null", "-"], capture_output=True, text=True).stderr
                got = float(json.loads(m2[m2.rindex("{"): m2.rindex("}") + 1])["input_i"])
                if abs(got - target) < 0.15: break
                gain += target - got
            af = f"volume={gain:.2f}dB,{lim},apad"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(od / "video.mp4"), *src, "-af", af, "-map", "0:v", "-map", "1:a",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-t", f"{ev['duration']:.4f}",
                 "-movflags", "+faststart", str(final)])
            m3 = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(final), "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                                capture_output=True, text=True).stderr
            tp = float(json.loads(m3[m3.rindex("{"): m3.rindex("}") + 1])["input_tp"])
            if tp <= -1.0: break
            ceil -= tp + 1.0 + 0.1; print(f"encoded true peak {tp:.2f} dBTP; limiter ceiling lowered to {ceil:.2f} dBFS")
    phone = proj / "out" / f"{slug}-{a.variant}-phone.mp4"
    vk = int(min(5000, 27.5 * 8000 / ev["duration"] - 300))     # kbit/s so video + 256k audio stay under ~28 MB
    run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-maxrate", f"{vk}k",
         "-bufsize", f"{vk * 2}k", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(phone)])
    nlib = len({u for u in used if u.startswith("lib:")})
    rz_info = f"; riser {', '.join(riser_info)}" if riser_info else ""
    print(f"voice speech level {ref:.1f} dBFS; {len(used)} sfx cues ({nlib} different library sounds){bed_info}{rz_info}; master gain {gain:+.2f} dB")
    print(f"wrote {final}\nwrote {phone}")


if __name__ == "__main__":
    main()
