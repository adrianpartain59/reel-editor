#!/usr/bin/env python3
"""Cut a Split Screen's takes: tight to the first word, with no click, breath or dead air left at the front of a clip.

  split_cut.py PROJECT            selects.json -> work/parts/body, work/body_words.json, work/clip_edges.txt
  split_cut.py PROJECT --as-is    keep selects.json exactly as written (after hand-setting a boundary), still report the edges
  split_cut.py PROJECT --report   only re-measure the edges of the current cut

selects.json: {"hooks": {}, "body": [["b1", in, out], ...]}, one entry per kept take, in speaking order. 2 to 4 minutes: run it in the background.

Why this exists: cut.py's speech map calls any low-pitched sound over its threshold "voiced", so in a take whose room tone sits at
that threshold a lip smack followed by room tone counted as a word and became the
start of the clip. So after the speech map's cut, every clip's start is measured again
against the speaker's speaking level and moved up to the word. The picture is never graded here (cut.py --as-is).
"""
import difflib, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from common import run, load, die, whisper_model

HERE = Path(__file__).resolve().parent
SR, FPS, LEAD = 48000, 30, 0.04          # kept before the first sound of the word


def pcm(path, cache):
    if path not in cache:
        raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], text=False).stdout
        cache[path] = np.frombuffer(raw, np.float32)
    return cache[path]


def levels(x, a, b, hop=0.01, win=0.02):
    ts = np.arange(max(0, a), b, hop); n = int(win * SR)
    return ts, np.array([20 * np.log10(np.sqrt(np.mean(x[int(t * SR): int(t * SR) + n] ** 2) + 1e-18) + 1e-9) if int(t * SR) + n <= len(x) else -99.0 for t in ts])


def edges(x, a, b):
    """(start, end) of the speech inside source seconds a..b, and the speaking level. A start is the first 60 ms that stays within
    10 dB of the speaker's level, walked back through the soft consonant attached to it (30 ms of quiet ends the walk)."""
    ts, e = levels(x, a, b); sp = float(np.percentile(e, 75)); on = e > sp - 10
    j = next((n for n in range(max(1, len(on) - 6)) if on[n:n + 6].mean() > .75), 0); k = next((n for n in range(len(on) - 1, 5, -1) if on[n - 5:n + 1].mean() > .75), len(on) - 1)
    _, f = levels(x, a - 1.5, b + 1.0); thr = max(float(np.percentile(f, 10)) + 8, sp - 30)
    def walk(n, step):
        miss = 0
        while 0 < n < len(e) - 1:
            n += step; miss = 0 if e[n] > thr else miss + 1
            if miss > 3: return n - step * miss
        return n
    return float(ts[walk(j, -1)]), float(ts[walk(k, 1)]) + .02, sp


def clicks(x, a, b, sp):
    """short bursts with quiet on both sides: a lip smack, not a consonant (those touch a vowel)"""
    ts, e = levels(x, a, b, .005, .01); hits = []
    for i, t in enumerate(ts):
        if sp - 28 < e[i] < sp - 6:
            l, r = e[max(0, i - 16):max(0, i - 2)], e[i + 4:i + 24]
            if len(l) > 8 and len(r) > 12 and l.max() < e[i] - 6 and np.percentile(r, 80) < sp - 18 and (not hits or t - hits[-1] > .08): hits.append(float(t))
    return hits


def report(proj, clips):
    cache, out, bad = {}, [], 0; segs = load(proj / "work/parts/body/segs.json")["segs"]
    for k, s in enumerate(segs):
        x = pcm(clips[s["clip"]]["file"], cache); a, b = s["src_in"], s["src_out"]; st, en, sp = edges(x, a, b); hs = [h for h in clicks(x, a, b, sp) if h < st - .05 or h > en + .05]
        ts, e = levels(x, st, en); quiet = e < sp - 22; p, n0 = [], None
        for n, q in enumerate(quiet):
            if q and n0 is None: n0 = n
            if not q and n0 is not None:
                if (n - n0) * .01 > .28: p.append(f"{(n - n0) * .01:.2f} s pause at {ts[n0] - a + s['t0']:.2f}")
                n0 = None
        flag = [] if st - a <= .10 else [f"starts {st - a:.2f} s before the word"]
        if b - en > .30: flag.append(f"{b - en:.2f} s after the last word")
        joined = lambda t: any(o is not s and (abs(o["src_out"] - t) < .06 or abs(o["src_in"] - t) < .06) for o in segs)      # cut inside a phrase on purpose: the next clip carries on
        _, pre = levels(x, a - .09, a - .02); _, post = levels(x, b + .02, b + .09)
        if st - a < .015 and len(pre) and pre.min() > sp - 11 and not joined(a): flag.append("may start mid-word (the speaker is already talking before the cut)")
        if b - en < .015 and len(post) and post.min() > sp - 11 and not joined(b): flag.append("may end mid-word")
        flag += [f"click at {h - a + s['t0']:.2f}" for h in hs]; bad += len(flag)
        out.append(f"clip {k:2d}  reel {s['t0']:6.2f}-{s['t1']:6.2f}  raw {a:7.2f}-{b:7.2f}  speech starts {st - a:.2f} s in" + ("   FIX: " + "; ".join(flag) if flag else "") + ("   note: " + "; ".join(p) if p else ""))
    miss = missing(proj); out += ["CHECK the raw take has a word the cut's transcript doesn't: " + m for m in miss]
    (proj / "work/clip_edges.txt").write_text("\n".join(out) + "\n"); print("\n".join(out)); print(f"{bad} problem(s)" if bad else "every clip starts on the word, no stray clicks" + (f"; {len(miss)} word(s) to check" if miss else ", no word lost")); return bad


def words(proj, clips):
    """work/body_words.json [[word, start, end, clip], ...]. Each clip is transcribed alone with whisper's DTW alignment: a word starts as the
    one before it ends, past any silence. (Whisper's plain word times were over 0.15 s off for 85 of 361 words on a test take.)
    Every clip's first word sits on the measured sound."""
    d = proj / "work/parts/body"; model = whisper_model(); preset = re.sub(r"-q\w+$", "", Path(model).stem.replace("ggml-", "")).replace("-", "."); x16 = np.frombuffer(run(["ffmpeg", "-v", "error", "-i", str(d / "voice.wav"), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], text=False).stdout, np.float32); lv = lambda t: 20 * np.log10(np.sqrt(np.mean(x16[int(t * 16000):int(t * 16000) + 320] ** 2) + 1e-18) + 1e-9); out, cache = [], {}
    for k, s in enumerate(load(d / "segs.json")["segs"]):
        with tempfile.TemporaryDirectory() as tmp:
            wav = f"{tmp}/s.wav"; run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['t0']:.4f}", "-t", f"{s['t1'] - s['t0']:.4f}", "-i", str(d / "voice.wav"), "-af", "adelay=250:all=1,apad=pad_dur=0.6", "-ac", "1", "-ar", "16000", wav]); run(["whisper-cli", "-m", model, "-f", wav, "-dtw", preset, "-nfa", "-ojf", "-of", f"{tmp}/s", "-l", "en", "-np"]); js = json.loads(Path(f"{tmp}/s.json").read_bytes().decode("utf-8", "replace"))
        ws = []
        for seg in js["transcription"]:
            for tk in seg["tokens"]:
                if tk["text"].startswith("[_") or not tk["text"].strip(): continue
                t = s["t0"] - .25 + tk["t_dtw"] / 100
                if tk["text"].startswith(" ") or not ws: ws.append([tk["text"].strip(), t, t])
                else: ws[-1][0] += tk["text"]; ws[-1][2] = t
        ws = [w for w in ws if re.search(r"\w", w[0])]
        if not ws: continue
        st, en, _ = edges(pcm(clips[s["clip"]]["file"], cache), s["src_in"], s["src_out"]); last = s["t0"] + en - s["src_in"]; starts = [s["t0"] + max(0, st - s["src_in"])]
        for i in range(1, len(ws)):
            p, e = ws[i - 1][2], ws[i][1]; a = p + .03
            if e - p > .24 + .045 * len(ws[i][0]):                       # a pause in there: start where the sound comes back
                ts = np.arange(p, e - .03, .01); l = np.array([lv(t) for t in ts])
                if len(l) > 4:
                    q = np.convolve(l, np.ones(3) / 3, "same"); m = n = int(q.argmin())
                    while n < len(l) - 1 and l[n] < l[m] + 9: n += 1
                    if q[m] < np.percentile(l, 80) - 14: a = float(ts[n])
            starts.append(min(max(a, starts[-1] + .06), max(starts[-1] + .06, last - .08)))
        for i, w in enumerate(ws): out.append([w[0], round(starts[i], 2), round(max(starts[i] + .05, starts[i + 1] if i + 1 < len(ws) else last), 2), k])
    (proj / "work/body_words.json").write_text(json.dumps(out)); return len(out)


def missing(proj):
    """words whisper heard in the raw take, inside a kept clip, that the cut's own transcript doesn't have"""
    u = proj / "work/utter.json"
    if not u.exists(): return []
    raw = [w for o in load(u) for w in o["words"]]; mine = load(proj / "work/body_words.json"); nz = lambda t: re.sub(r"[^\w$%']", "", t.lower()); out = []
    for k, s in enumerate(load(proj / "work/parts/body/segs.json")["segs"]):
        a = [w for w in raw if s["src_in"] - .02 < (w[1] + w[2]) / 2 < s["src_out"] + .02 and nz(w[0])]; b = [nz(w[0]) for w in mine if w[3] == k]
        for op, i0, i1, j0, j1 in difflib.SequenceMatcher(None, [nz(w[0]) for w in a], b, autojunk=False).get_opcodes():
            near = [nz(w[0]) for w in mine if w[3] == k + 1][:2] + [nz(w[0]) for w in mine if w[3] == k - 1][-2:]                  # whisper's raw times bleed a word over the cut: it's in the clip next door
            if op == "delete": out += [f"clip {k}: {w[0]!r} (raw {w[1]:.2f}, reel {w[1] - s['src_in'] + s['t0']:.2f})" for w in a[i0:i1] if nz(w[0]) not in near]
    return out


def main():
    if len(sys.argv) < 2: die(__doc__)
    proj = Path(sys.argv[1]).expanduser().resolve(); clips = load(proj / "project.json")["clips"]; clips = clips if isinstance(clips, dict) else {c["id"]: c for c in clips}; cut = [sys.executable, str(HERE / "cut.py"), str(proj)]
    if "--report" in sys.argv: sys.exit(1 if report(proj, clips) else 0)
    if "--as-is" not in sys.argv:
        if not (proj / "selects.rough.json").exists(): shutil.copy(proj / "selects.json", proj / "selects.rough.json")
        import cut as K                                                  # its speech map only: one pass, no throwaway graded render
        cache, sel = {}, []
        for cid, a, b in K.speech_only(load(proj / "selects.json")["body"], clips):
            x = pcm(clips[cid]["file"], cache); st, en, _ = edges(x, a, b); up = int(max(0, st - LEAD - a) * FPS); sel.append([cid, round(a + up / FPS if up >= 2 else a, 3), round(en + .14 if b - en > .30 else b, 3)])
            if up >= 2: print(f"  raw {a:.2f}: start moved up {up / FPS:.2f} s to the word", flush=True)
        (proj / "selects.json").write_text(json.dumps({"hooks": {}, "body": sel}))
    print("cutting, transcribing, tracking the head...", flush=True)
    subprocess.run(cut + ["--as-is"], check=True, capture_output=True); (proj / "work/parts/body/track.json").unlink(missing_ok=True); n = words(proj, clips); subprocess.run([sys.executable, str(HERE / "track.py"), str(proj / "work/parts/body")], check=True, capture_output=True)
    seg = load(proj / "work/parts/body/segs.json"); print(f"body: {seg['duration']:.2f} s, {len(seg['segs'])} clips, {n} words"); report(proj, clips)


if __name__ == "__main__": main()
