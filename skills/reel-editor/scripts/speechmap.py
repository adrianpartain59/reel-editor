#!/usr/bin/env python3
"""The speech map: where the speaker is talking, measured the same way by ingest, cut, mix and QA.

Speech is detected from the speech band (300-7600 Hz), never full-band energy: room hum, fans and AC sit below
300 Hz and full-band thresholds counted them as speech (a 1.2 s hum tail at -31 dB passed a
-31.5 dB threshold and became a visible pause in the reel). Thresholds come from each SOURCE clip (its own floor
and speech level), so a noisy clip and a quiet clip are judged on their own terms, and QA on the cut part reuses
the clip's thresholds per segment.

Loud enough is not enough: a reel can open on a breath or a lip smack. On one test take a breath sat 23-30 dB under the speaker's speech level, above
the floor threshold, and a 50 ms gap before "I" got filled as if it were inside a word, so the breath opened the
reel. Every 10 ms frame is now classed by its SHAPE as well as its level:

  voiced     energy mostly below 1 kHz (vowels, m, n, l: >= 75% of the 80-7600 Hz energy), or speech-level loud
             with at least 45% below 1 kHz (bright vowels like "I")
  fricative  s / f / sh: bright (spectral centre >= 3.5 kHz) and within 24 dB of the speech level
  loud       within 18 dB of the speech level (plosive bursts, stressed syllables)
  breath, lip smack, click, rustle: none of these. Measured breaths: 23-30 dB under speech, 23-54% below 1 kHz,
             centre 1.6-3.5 kHz, never voiced.

A run of voiced / fricative / loud frames (20 ms dropouts allowed) is speech only if it holds at least 40 ms of
voiced frames: every word has a vowel, a breath or a click has none. A consonant-only run within HOLE of a word
joins it ("ex-S-pect"), and a word may trail up to TAIL_EXT over the floor (final t / k releases); nothing ever
extends before a word. Runs closer than HOLE are one region.

Hard rule this enforces (cut.py dies, qa.py fails): no non-speech stretch longer than MAX_GAP inside a cut part,
and no lead-in / tail longer than MAX_EDGE. Natural pauses longer than SPLIT_GAP are cut down to PAD_OUT + PAD_IN.

  speechmap.py FILE [--ss A --to B] [--frames]   speech regions and the gaps between them (--frames: per-frame classes)
"""
import json, subprocess, sys
import numpy as np

SR = 16000
HOP = 0.01                     # 10 ms frames
PAD_IN, PAD_OUT = 0.04, 0.07   # kept before / after each speech region
HOLE = 0.15                    # gaps shorter than this between speech runs are part of the word (stop closures)
SPLIT_GAP = 0.20               # a pause longer than this is cut out (down to PAD_OUT + PAD_IN = 0.11 s)
MAX_GAP = 0.25                 # QA / cut gate: longest non-speech run allowed inside a part
MAX_EDGE = 0.15                # QA / cut gate: longest non-speech before the first / after the last word
CORE_DB = 18                   # "loud": within this many dB of the clip's speech level
FRIC_DB, FRIC_CEN = 24, 3500   # fricative: within FRIC_DB of speech level and spectral centre above FRIC_CEN Hz
LOW_VOICED, LOW_LOUD = 0.75, 0.45
DROPOUT = 2                    # frames of dropout allowed inside one run
VOICED_MIN = 4                 # frames (40 ms) of voiced energy a run needs to count as speech
TAIL_EXT = 0.12                # after a word, keep up to this much more while the level stays over the floor


def pcm16(path, ss=None, to=None):
    a = ["ffmpeg", "-v", "error"]
    if ss is not None: a += ["-ss", f"{ss:.3f}"]
    if to is not None: a += ["-to", f"{to:.3f}"]
    a += ["-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(a, capture_output=True, check=True).stdout, dtype=np.float32)


def feats(x):
    """Per 10 ms frame (30 ms Hann window): speech-band level in dB, spectral centre (Hz) of the speech band, and the
    share of 80-7600 Hz energy that sits below 1 kHz."""
    hop, win = int(HOP * SR), int(0.03 * SR)
    if len(x) < win: x = np.pad(x, (0, win - len(x)))
    n = (len(x) - win) // hop + 1
    X = np.lib.stride_tricks.sliding_window_view(x, win)[::hop][:n] * np.hanning(win)
    P = np.abs(np.fft.rfft(X, axis=1)) ** 2; f = np.fft.rfftfreq(win, 1 / SR)
    band = (f >= 300) & (f <= 7600)
    pb = P[:, band].sum(1)
    db = 10 * np.log10(pb / win + 1e-12)
    cen = (P[:, band] * f[band]).sum(1) / (pb + 1e-12)
    low = P[:, (f >= 80) & (f < 1000)].sum(1) / (P[:, (f >= 80) & (f <= 7600)].sum(1) + 1e-12)
    return db, cen, low


def band_db(x):
    """Speech-band level per 10 ms frame (for callers that only need the level)."""
    return feats(x)[0]


def levels(db):
    """Floor, speech level and threshold for one source clip."""
    floor, speech = float(np.percentile(db, 10)), float(np.percentile(db, 95))
    thr = floor + max(10.0, 0.33 * (speech - floor))
    return {"floor": round(floor, 2), "speech": round(speech, 2), "thr": round(thr, 2)}


def classify(db, cen, low, lv):
    """Frame masks: voiced (proves a word is there), cons (s / f / sh or a loud burst: a consonant), above (over the
    clip's floor threshold)."""
    above = db > lv["thr"]
    loud = db >= lv["speech"] - CORE_DB
    voiced = (above & (low >= LOW_VOICED)) | (loud & (low >= LOW_LOUD))
    fric = (db >= lv["speech"] - FRIC_DB) & (cen >= FRIC_CEN)
    return {"voiced": voiced, "cons": fric | loud, "above": above}


def runs(mask, dropout=0):
    """[[i, j), ...] runs of True frames, bridging dropouts of up to `dropout` frames."""
    idx = np.flatnonzero(mask)
    if not len(idx): return []
    out = [[int(idx[0]), int(idx[0]) + 1]]
    for k in idx[1:]:
        if k - out[-1][1] <= dropout: out[-1][1] = int(k) + 1
        else: out.append([int(k), int(k) + 1])
    return out


def speech_runs(m):
    """Frame runs where the speaker is talking, from classify()'s masks:
    1. anchors: runs of voiced / consonant frames holding at least VOICED_MIN voiced frames (a word has a vowel);
    2. a consonant-only run (the "s" of "expect", a "t" burst) within HOLE of an anchor joins it;
    3. after each region's last frame, extend up to TAIL_EXT through frames over the floor (soft final t / k / p
       releases and fading "s" sit under the consonant level). Nothing extends BEFORE a word: that is where the
       breath and the lip smack live.
    Regions closer than HOLE merge."""
    voiced, cons, above = m["voiced"], m["cons"], m["above"]
    cand = voiced | cons
    rs = runs(cand, DROPOUT)
    anchor = [voiced[i:j].sum() >= VOICED_MIN for i, j in rs]
    hole, n = int(round(HOLE / HOP)), len(voiced)
    keep = []
    for k, (i, j) in enumerate(rs):
        if anchor[k]: keep.append([i, j]); continue
        if cons[i:j].sum() < 2: continue
        near = any(anchor[q] and (0 <= i - rs[q][1] <= hole or 0 <= rs[q][0] - j <= hole) for q in range(len(rs)))
        if near: keep.append([i, j])
    out = []
    for i, j in keep:
        if out and i - out[-1][1] <= hole: out[-1][1] = j
        else: out.append([i, j])
    ext = int(round(TAIL_EXT / HOP))
    for r in out:
        j = r[1]
        while j < n and j - r[1] < ext and above[j]: j += 1
        r[1] = j
    return out


def frames_to_regions(m):
    """Speech regions in seconds from classify()'s masks."""
    return [[round(i * HOP, 3), round(j * HOP + 0.02, 3)] for i, j in speech_runs(m)]


def regions(path, ss=None, to=None, lv=None):
    """Speech regions [[a, b], ...] in seconds relative to ss, plus the levels used."""
    db, cen, low = feats(pcm16(path, ss, to))
    lv = lv or levels(db)
    return frames_to_regions(classify(db, cen, low, lv)), lv


def clip_levels(path):
    return levels(band_db(pcm16(path)))


def tighten(regs, a, b, dur):
    """Speech regions inside [a, b] -> the segments to keep: padded, pauses over SPLIT_GAP split out."""
    inside = [[max(a, r0), min(b, r1)] for r0, r1 in regs if r1 > a and r0 < b]
    out = []
    for r0, r1 in inside:
        s0, s1 = max(0.0, r0 - PAD_IN), min(dur, r1 + PAD_OUT)
        if out and r0 - out[-1][2] <= SPLIT_GAP: out[-1][1] = s1; out[-1][2] = r1
        else: out.append([s0, s1, r1])
    return [[round(s0, 3), round(s1, 3)] for s0, s1, _ in out]


def part_regions(voice_wav, segs, clip_lv):
    """Speech regions of a cut part, each segment judged with its own source clip's thresholds; also its length."""
    db, cen, low = feats(pcm16(voice_wav)); t = np.arange(len(db)) * HOP
    masks = {k: np.zeros(len(db), bool) for k in ("voiced", "cons", "above")}
    for s in segs:
        sel = (t >= s["t0"]) & (t < s["t1"])
        got = classify(db[sel], cen[sel], low[sel], clip_lv[s["clip"]])
        for k in masks: masks[k][sel] = got[k]
    return frames_to_regions(masks), len(db) * HOP


def gaps_in_part(voice_wav, segs, clip_lv):
    """Non-speech runs in a cut part. Returns (gaps, lead, tail): gaps = [[t, length], ...] longer than MAX_GAP."""
    regs, dur = part_regions(voice_wav, segs, clip_lv)
    if not regs: return [[0.0, dur]], dur, 0.0
    gaps = [[round(regs[k][1], 2), round(regs[k + 1][0] - regs[k][1], 2)] for k in range(len(regs) - 1)
            if regs[k + 1][0] - regs[k][1] > MAX_GAP]
    return gaps, round(regs[0][0], 2), round(max(0.0, dur - regs[-1][1]), 2)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    ss = float(a[a.index("--ss") + 1]) if "--ss" in a else None
    to = float(a[a.index("--to") + 1]) if "--to" in a else None
    db, cen, low = feats(pcm16(a[0], ss, to)); lv = clip_levels(a[0])
    print(json.dumps(lv))
    m = classify(db, cen, low, lv)
    if "--frames" in a:
        for i in range(len(db)):
            tag = "V" if m["voiced"][i] else ("c" if m["cons"][i] else ("." if m["above"][i] else " "))
            print(f"{(ss or 0) + i * HOP:7.2f} {tag} {db[i]:6.1f} dB  centre {cen[i]:5.0f}  low {low[i]:4.2f}")
        sys.exit(0)
    regs = frames_to_regions(m)
    for k, (r0, r1) in enumerate(regs):
        gap = f"   gap {regs[k + 1][0] - r1:.2f}s" if k + 1 < len(regs) else ""
        print(f"{(ss or 0) + r0:7.2f} - {(ss or 0) + r1:7.2f}{gap}")
