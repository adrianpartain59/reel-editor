"""Procedural music beds (synthesized here, so there is nothing to license and nothing for Instagram to mute).

  from music import bed; x = bed("dark_pad", duration, drops=[3.2, 17.9], seed=1)   # (n, 2) float32 at 48 kHz

dark_pad: A-minor i-VI-III-VII (Am F C G), one chord every 2 s (the pace measured on the reference reel),
detuned-saw pad low-passed around 1 kHz, a saturated sub on the root (harmonics so phones hear it), a slow
"breathing" swell on the beat, and a quiet air layer on top. Wide stereo: left and right use different detunes.

Drops: for each time in `drops`, the low end (sub + pad body) cuts out for `drop_len` seconds before it and the
bed comes back full on the beat. The cut is what makes the impact that lands there feel heavy.
mix.py sets the level against the voice and ducks it a little while the speaker speaks.
"""
import numpy as np

SR = 48000
CHORDS = [(55.00, [220.00, 261.63, 329.63]),   # Am   (root A1, pad A3 C4 E4)
          (43.65, [174.61, 220.00, 261.63]),   # F    (F1,  F3 A3 C4)
          (65.41, [196.00, 261.63, 329.63]),   # C    (C2,  G3 C4 E4)
          (49.00, [196.00, 246.94, 293.66])]   # G    (G1,  G3 B3 D4)


def _lp(x, fc, soft=0.5):
    n = len(x); X = np.fft.rfft(x, 2 * n); f = np.fft.rfftfreq(2 * n, 1 / SR)
    g = 1 / (1 + (f / fc) ** (2 / soft)); return np.fft.irfft(X * g)[:n]


def _hp(x, fc): return x - _lp(x, fc, 0.35)


def _saw(freq, n, phase):
    """Band-limited saw by additive synthesis, harmonics up to 5 kHz."""
    t = np.arange(n) / SR; out = np.zeros(n)
    for k in range(1, int(5000 // freq) + 1):
        out += np.sin(2 * np.pi * k * freq * t + phase * k) / k
    return out


def _chord(root, notes, d, rng, side):
    n = int(SR * d); x = np.zeros(n)
    det = [-9, 0, 8] if side == 0 else [-6, 2, 11]          # cents; different per channel = width
    for f in notes:
        for c in det: x += _saw(f * 2 ** (c / 1200), n, rng.uniform(0, 2 * np.pi)) * 0.33
    x = _lp(x, 950)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * root * t)
    sub = np.tanh(2.2 * (sub + 0.25)) - np.tanh(0.55)          # asymmetric clip: 2nd harmonic for phones
    return x * 0.6, sub * 0.32


def track(tid, duration, drops=(), drop_len=0.5, pocket=-4.0, sub=-3.0):
    """A downloaded beat (music_lib) cut to the reel.

    - Starts so the track's own way into its full section lands on the first drop (the hook payoff), when the
      track has enough lead-in; otherwise starts in the full section.
    - Before each drop the beat stops (drop_len, a 40 ms fade) and comes back on a downbeat at the drop, so the
      reveal lands on the "1" with the 808. Each return jumps forward to the next downbeat after where the beat
      would have been, so the track keeps progressing. With an untrusted grid (grid_conf < 2) the beat keeps
      running and only its low end cuts out before the drop, like the pad.
    - Loops the steady section by whole 4-bar phrases if the reel outlasts it.
    - pocket: dB at 2.4 kHz (an octave-wide dip where the voice's consonants live); sub: dB shelf under 90 Hz
      (the 808 stays felt on headphones without pumping the master).
    """
    import subprocess, music_lib
    m = music_lib.track(tid); f = music_lib.path(tid)
    if not f.exists(): raise FileNotFoundError(f"{m['id']} is not downloaded: run music_lib.py fetch")
    af = ",".join(x for x in [f"equalizer=f=2400:t=o:w=1.3:g={pocket}" if pocket else "",
                              f"lowshelf=f=90:g={sub}" if sub else ""] if x) or "anull"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-af", af, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    n = int(SR * duration); bar, db0, lo, hi = m["bar"], m["downbeat"], m["full_from"], m["full_to"]
    grid = m.get("grid_conf", 0) >= 2.0
    span = max(4 * bar, np.floor((hi - lo) / (4 * bar)) * 4 * bar)
    drops = sorted(d for d in drops if 0.3 < d < duration - 0.3)
    pre = 0.015                                                    # start each return just before the downbeat's attack

    def take(pos, k):
        out, fade = [], int(0.004 * SR)
        while k > 0:
            if pos >= lo + span: pos = lo + (pos - lo) % span
            m_ = min(k, max(1, int(round((lo + span - pos) * SR))))
            i0 = int(round(pos * SR)); seg = x[i0:i0 + m_]
            if len(seg) < m_: seg = np.pad(seg, ((0, m_ - len(seg)), (0, 0)))
            if out: seg = seg.copy(); seg[:fade] *= np.linspace(0, 1, min(fade, len(seg)))[:, None]
            out.append(seg); k -= m_; pos += m_ / SR
        return np.concatenate(out)

    def snap(p): return db0 + np.ceil((p - db0) / bar - 1e-6) * bar

    out = np.zeros((n, 2)); cur = lo - drops[0] if drops and lo - drops[0] >= 0 else lo
    bounds = [0.0] + drops + [duration]
    for i in range(len(bounds) - 1):
        t0, t1 = bounds[i], bounds[i + 1]
        if i > 0 and grid: cur = snap(cur) - pre; t0 -= pre
        a, b = max(0, int(round(t0 * SR))), min(n, int(round(t1 * SR)))   # n uses int(): round() can overshoot by one sample
        out[a:b] = take(cur, b - a); cur += t1 - t0
    g = np.ones(n); f40 = int(0.04 * SR)
    for d in drops:
        a, b = int((d - drop_len) * SR), int((d - (pre if grid else 0)) * SR)
        if grid:
            g[a:b] = 0.0; g[a:a + f40] = np.linspace(1, 0, f40)
        else:                                                      # running beat: only the low end drops out
            lp = np.stack([_lp(out[a:b, c], 250) for c in range(2)], 1); out[a:b] -= lp * np.linspace(0, 1, b - a)[:, None] ** 0.3
    out *= g[:, None]
    fi, fo = int(0.01 * SR), int(0.12 * SR)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]; out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return (out / (np.max(np.abs(out)) + 1e-9) * 0.7).astype(np.float32)


def bed(kind, duration, drops=(), seed=1, drop_len=0.5, chord_len=2.0, **kw):
    if kind.startswith("track:"): return track(kind[6:], duration, drops=drops, drop_len=drop_len, **kw)
    if kind not in ("dark_pad",): raise ValueError(f"unknown music bed {kind!r}")
    rng = np.random.default_rng(seed); n = int(SR * duration) + SR
    pad = np.zeros((n, 2)); low = np.zeros((n, 2)); xf = int(0.35 * SR)
    k = 0; i = 0; cache = {}
    while i < n:
        root, notes = CHORDS[k % len(CHORDS)]; L = int(SR * chord_len)
        for ch in range(2):
            key = (k % len(CHORDS), ch)
            if key not in cache: cache[key] = _chord(root, notes, chord_len + 0.35, rng, ch)
            p, s = cache[key]
            e = np.ones(len(p)); e[:xf] = np.linspace(0, 1, xf) ** 0.5; e[-xf:] = np.linspace(1, 0, xf) ** 0.5
            seg = slice(i, min(n, i + len(p))); m = seg.stop - seg.start
            body = _lp(p, 280); pad[seg, ch] += (p - body)[:m] * e[:m]; low[seg, ch] += (body + s)[:m] * e[:m]
        i += L; k += 1
    t = np.arange(n) / SR
    breathe = 1 - 0.18 * (0.5 - 0.5 * np.cos(2 * np.pi * (t % 1.0)))     # gentle swell, 60 bpm
    low *= breathe[:, None]
    air = np.stack([_hp(rng.standard_normal(n), 5000), _hp(rng.standard_normal(n), 5000)], 1)
    air *= (0.012 * (1 + 0.5 * np.sin(2 * np.pi * t / 7.0)))[:, None]
    # drops: low end out for drop_len before each drop time, back on the hit
    g = np.ones(n)
    for d in drops:
        a, b = int((d - drop_len) * SR), int(d * SR)
        if b <= 0 or a >= n: continue
        a = max(a, 0); f = int(0.03 * SR)
        g[a:b] = 0.0; g[a:min(a + f, b)] = np.linspace(1, 0, min(a + f, b) - a)
    hp_dip = 1 - 0.45 * (1 - g)                                            # the top thins out a little too
    out = low * g[:, None] + pad * hp_dip[:, None] + air
    out = out[: int(SR * duration)]
    fade = int(0.6 * SR); out[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))[:, None]; out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return (out / (np.max(np.abs(out)) + 1e-9) * 0.7).astype(np.float32)


if __name__ == "__main__":
    import sys, wave
    x = bed("dark_pad", float(sys.argv[1]) if len(sys.argv) > 1 else 12.0, drops=[6.0])
    with wave.open(sys.argv[2] if len(sys.argv) > 2 else "bed.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype("<i2").tobytes())
    print("wrote", x.shape)
