"""Synthesis building blocks for the sound pack (sfx_pack.py): noise, filters, envelopes, reverb, and the heavy "cine"
sounds. Synthesized here (no samples, nothing to license).

Design notes (what makes these sound expensive rather than thin):
- Sub hits are saturated (tanh) so their 80-250 Hz harmonics carry the weight on phone speakers, which cannot
  play the 30-60 Hz fundamental.
- Every transient has a separate crisp layer (high-passed noise, a few ms long) on top of the body.
- Stereo comes from decorrelated reverb tails and moving pans, never from duplicating a mono file.
- Filters are done in the frequency domain (whole-buffer FFT or a short STFT for sweeps), so edges are clean.
"""
import numpy as np

SR = 48000
rng = np.random.default_rng(11)

def T(d): return np.arange(int(SR * d)) / SR


def noise(n): return rng.standard_normal(n)


def band(x, lo=None, hi=None, soft=0.15):
    """Zero-phase band limit with smooth (raised-cosine, +-soft octaves) edges."""
    n = len(x); X = np.fft.rfft(x, 2 * n); f = np.fft.rfftfreq(2 * n, 1 / SR); g = np.ones_like(f)
    if lo:
        a, b = lo * 2 ** -soft, lo * 2 ** soft
        g *= np.clip((np.log2(np.maximum(f, 1)) - np.log2(a)) / (np.log2(b) - np.log2(a)), 0, 1)
    if hi:
        a, b = hi * 2 ** -soft, hi * 2 ** soft
        g *= 1 - np.clip((np.log2(np.maximum(f, 1)) - np.log2(a)) / (np.log2(b) - np.log2(a)), 0, 1)
    return np.fft.irfft(X * g)[:n]


def sweep_band(x, fc, bw_oct=0.9, nfft=1024, hop=256):
    """Time-varying band-pass: fc is an array (Hz) as long as x; Gaussian band of bw_oct octaves (STFT)."""
    n = len(x); w = np.hanning(nfft); pad = np.pad(x, (nfft, nfft)); out = np.zeros(len(pad)); norm = np.zeros(len(pad))
    f = np.fft.rfftfreq(nfft, 1 / SR); lf = np.log2(np.maximum(f, 20))
    fcp = np.pad(fc, (nfft, nfft), mode="edge")
    for i in range(0, len(pad) - nfft, hop):
        c = np.log2(max(fcp[i + nfft // 2], 30))
        g = np.exp(-0.5 * ((lf - c) / (bw_oct / 2)) ** 2)
        out[i:i + nfft] += np.fft.irfft(np.fft.rfft(pad[i:i + nfft] * w) * g) * w; norm[i:i + nfft] += w ** 2
    return (out / np.maximum(norm, 1e-6))[nfft:nfft + n]


def env(n, a, d, shape=1.0):
    """Attack a s (squared ramp), then exponential decay with time constant d s."""
    t = np.arange(n) / SR; e = np.exp(-np.maximum(t - a, 0) / d)
    if a > 0: e *= np.clip(t / a, 0, 1) ** 2
    return e ** shape


def reverb(x, dur=1.4, decay=0.35, lp=6000, hp=180, mix=0.3, seed=0):
    """Stereo convolution reverb with decorrelated noise IRs. Returns (n+tail, 2)."""
    r = np.random.default_rng(100 + seed); n = int(SR * dur); t = np.arange(n) / SR
    out = []
    for ch in range(2):
        ir = r.standard_normal(n) * np.exp(-t / decay); ir = band(ir, hp, lp); ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        L = len(x) + n; y = np.fft.irfft(np.fft.rfft(x, 2 * L) * np.fft.rfft(ir, 2 * L))[:L]
        out.append(y)
    wet = np.stack(out, 1); dry = np.pad(x, (0, n))[:, None] * np.ones((1, 2))
    return dry * (1 - mix) + wet * mix * 2.2


def st(x, width=0.0):
    """Mono -> stereo, optional Haas-free width via a tiny decorrelating all-pass blend."""
    if x.ndim == 2: return x
    if width <= 0: return np.stack([x, x], 1)
    k = int(0.00035 * SR); s = np.roll(x, k) - np.roll(x, -k)
    return np.stack([x + width * s, x - width * s], 1)


def pan(x, p):
    """Equal-power pan; p scalar or array in [-1, 1]."""
    p = np.broadcast_to(p, x.shape); a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1)


def sat(x, drive=2.0, bias=0.0):
    """Soft clip. bias > 0 makes it asymmetric, which adds even harmonics (2nd = an octave up: audible on phones)."""
    return (np.tanh(drive * (x + bias)) - np.tanh(drive * bias)) / np.tanh(drive)


# ---------------------------------------------------------------- sounds
def cine_hit():
    """Trailer-style impact: saturated sub drop + chest thump + crack + stereo room."""
    t = T(2.2); n = len(t)
    f = 33 + 52 * np.exp(-t * 11); sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.55)
    fk = 62 + 110 * np.exp(-t * 28); kick = np.sin(2 * np.pi * np.cumsum(fk) / SR) * env(n, 0.001, 0.09)   # chest punch
    body = band(noise(n), 60, 520) * env(n, 0.001, 0.06) * 1.6 + kick * 0.9
    crack = band(noise(n), 2200, 13000) * env(n, 0.0, 0.009) * 1.1 + np.sin(2 * np.pi * 1400 * t) * env(n, 0, 0.006) * 0.4
    dry = sat(sub * 1.1 + body, 2.6, 0.25) + crack
    wet = reverb(band(body * 0.6 + crack, 200, 7000), 1.6, 0.42, 6500, 250, 1.0, 1)
    out = st(dry) * 1.0; out = np.pad(out, ((0, len(wet) - n), (0, 0))) + wet * 0.35
    return out[: int(SR * 2.4)]


def cine_boom():
    """Bass drop: long distorted 808-style sub with a soft attack click."""
    t = T(3.0); n = len(t)
    f = 28 + 40 * np.exp(-t * 6); sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.004, 1.1)
    click = band(noise(n), 1500, 9000) * env(n, 0, 0.006) * 0.5
    oct2 = np.sin(2 * np.pi * np.cumsum(2 * f) / SR) * env(n, 0.004, 0.7) * 0.35
    x = sat(sub * 1.3 + oct2, 3.0, 0.3) * 0.9 + click
    return np.pad(st(x), ((0, 0), (0, 0)))


def _whoosh(d, f0, fpk, f1, peak_at=0.6, pan0=-0.7, pan1=0.7, air=1.0, body=0.6, seed=0):
    t = T(d); n = len(t); u = t / d
    fc = np.where(u < peak_at, f0 * (fpk / f0) ** (u / peak_at), fpk * (f1 / fpk) ** ((u - peak_at) / (1 - peak_at)))
    e = np.where(u < peak_at, (u / peak_at) ** 2.2, np.exp(-((u - peak_at) / (1 - peak_at)) * 3.2))
    hi = sweep_band(noise(n), fc, 1.1) * air
    lo = band(noise(n), 60, 380) * body
    mono = (hi + lo) * e
    p = pan0 + (pan1 - pan0) * np.clip(u / (peak_at + 0.15), 0, 1)
    out = pan(mono, p)
    wet = reverb(band(mono, 400, 9000), 0.9, 0.22, 8000, 400, 1.0, seed)
    return np.pad(out, ((0, len(wet) - n), (0, 0))) + wet * 0.28


def cine_whoosh(): return _whoosh(0.62, 350, 5200, 1600, 0.58)
def cine_swish(): return _whoosh(0.26, 900, 8000, 3000, 0.5, -0.4, 0.5, 1.0, 0.25, 2)


def cine_whoosh_out():
    x = _whoosh(0.5, 6000, 2400, 300, 0.25, 0.6, -0.6, 0.9, 0.7, 3); return x


def cine_riser():
    """Tension build into a cut: rising filtered noise + two detuned rising tones, stops dead at the end."""
    d = 1.5; t = T(d); n = len(t); u = t / d
    fc = 250 * (40 ** u); nz = sweep_band(noise(n), fc, 1.4)
    f = 110 * (8 ** (u ** 1.3)); tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + np.sin(2 * np.pi * np.cumsum(f * 1.012) / SR)
    x = (nz * 1.0 + 0.35 * band(sat(tone, 1.5), 150, 6000)) * u ** 2.6
    out = st(x, 0.0); w = reverb(x * 0.5, 0.6, 0.15, 9000, 500, 1.0, 4)[: n]
    out = out + w * 0.3; out[-int(0.006 * SR):] *= np.linspace(1, 0, int(0.006 * SR))[:, None]
    return out


def cine_suck():
    """Reverse cymbal swell (pre-reveal 'suck back')."""
    d = 0.9; t = T(d); n = len(t)
    cym = band(noise(n), 3500, 16000) * env(n, 0, 0.28) + 0.4 * band(noise(n), 800, 4000) * env(n, 0, 0.15)
    wet = reverb(cym, 1.0, 0.3, 14000, 1500, 0.6, 5)
    return wet[::-1][: int(SR * 1.0)].copy()


def cine_glitch():
    """Digital stutter: chopped crushed noise, square blips at random pitches, panned per chunk."""
    d = 0.42; n = int(SR * d); out = np.zeros((n, 2)); i = 0; r = np.random.default_rng(21)
    while i < n:
        L = int(SR * r.uniform(0.012, 0.045)); seg_t = np.arange(L) / SR; kind = r.integers(0, 4)
        if kind == 0: s = np.sign(np.sin(2 * np.pi * r.uniform(180, 1800) * seg_t))
        elif kind == 1: s = np.repeat(r.standard_normal(L // 8 + 1), 8)[:L]
        elif kind == 2: s = np.round(np.sin(2 * np.pi * r.uniform(60, 400) * seg_t) * 3) / 3
        else: s = np.zeros(L)
        s = s * r.uniform(0.4, 1.0); p = r.uniform(-0.9, 0.9)
        seg = pan(s, p); out[i:i + L] += seg[: max(0, min(L, n - i))]; i += L
    out[:, 0] = band(out[:, 0], 150, 12000); out[:, 1] = band(out[:, 1], 150, 12000)
    return out


def cine_shimmer():
    d = 1.4; n = int(SR * d); x = np.zeros(n); r = np.random.default_rng(31)
    for k in range(22):
        s0 = r.uniform(0, 0.5); f = r.uniform(2800, 9000); tt = T(0.6)
        seg = np.sin(2 * np.pi * f * tt) * np.exp(-tt * r.uniform(7, 14)) * r.uniform(0.3, 1)
        i = int(SR * s0); x[i:i + len(seg)] += seg[: n - i]
    x *= np.linspace(1, 0.5, n)
    return reverb(x, 1.2, 0.35, 14000, 1500, 0.45, 6)[: int(SR * 1.8)]


def cine_neon():
    """Neon sign flickering on: mains buzz with harmonics + electric crackles, steadying."""
    d = 0.55; t = T(d); n = len(t); u = t / d
    buzz = sum(np.sin(2 * np.pi * 120 * k * t) / k for k in range(1, 14))
    gate = np.ones(n); r = np.random.default_rng(41)
    for _ in range(6):
        a = int(SR * r.uniform(0, 0.22)); gate[a:a + int(SR * r.uniform(0.01, 0.04))] = 0
    crackle = band(noise(n), 2500, 12000) * (r.random(n) > 0.997) * 6
    x = band(sat(buzz * 0.5, 2.0), 100, 7000) * gate * env(n, 0.005, 0.35, 0.6) + crackle * (1 - u)
    return reverb(x, 0.5, 0.12, 8000, 300, 0.25, 7)[: n]


def ui_click():
    t = T(0.05); n = len(t)
    x = np.sin(2 * np.pi * 2900 * t) * env(n, 0, 0.004) * 0.7 + band(noise(n), 3000, 15000) * env(n, 0, 0.0018) * 1.2 \
        + np.sin(2 * np.pi * 420 * t) * env(n, 0, 0.008) * 0.35
    return st(x)


def ui_tick():
    t = T(0.03); n = len(t)
    return st(band(noise(n), 3500, 14000) * env(n, 0, 0.0012) + np.sin(2 * np.pi * 5200 * t) * env(n, 0, 0.002) * 0.4)


def type_key():
    t = T(0.11); n = len(t); x = np.zeros(n)
    for start, amp in [(0.0, 1.0), (0.045, 0.55)]:
        i = int(start * SR); m = n - i; tt = np.arange(m) / SR
        x[i:] += amp * (band(noise(m), 1800, 11000) * np.exp(-tt / 0.0025) + 0.5 * np.sin(2 * np.pi * 310 * tt) * np.exp(-tt / 0.01))
    return st(x)


def notif():
    """Own two-note glass ping (not any platform's sound)."""
    d = 1.0; n = int(SR * d); x = np.zeros(n)
    for s0, f in [(0.0, 1760.0), (0.11, 2349.3)]:
        tt = T(0.8); seg = sum(a * np.sin(2 * np.pi * f * m * tt) for m, a in [(1, 1), (2.0, 0.25), (3.01, 0.08)]) * np.exp(-tt * 6)
        i = int(SR * s0); x[i:i + len(seg)] += seg[: n - i]
    return reverb(x, 0.8, 0.2, 12000, 600, 0.3, 8)[: n]


def cine_tape():
    """Tape-stop: the bed pitch-dives out (use right before a hard reveal)."""
    d = 0.7; t = T(d); n = len(t); u = t / d
    f = 98 * (1 - u) ** 1.5 + 8; x = sat(np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR), 1.6)
    return st(band(x, 30, 3000) * (1 - u) ** 0.7)
