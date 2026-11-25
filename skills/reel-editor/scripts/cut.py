#!/usr/bin/env python3
"""Step 2: cut every part (each hook variant, then the body) down to the selected speech.

  cut.py PROJECT_DIR                  every part
  cut.py PROJECT_DIR --part hook-h2   one part only (after changing that part's selects)
  cut.py PROJECT_DIR --audio-only     re-extract voice audio for every part, keeping cuts and words
  cut.py PROJECT_DIR --as-is          keep every select exactly as written and don't grade (a hand-cut raw take, or "just cut
                                      it, unedited"); a pause or a tail left in only prints a warning

Reads selects.json ({"hooks": {"h1": [[clip, in, out], ...]}, "body": [[clip, in, out], ...]}), snaps every
segment to the 30 fps frame grid so audio and video stay locked, renders 1080x1920 graded video + voice per
part, then re-transcribes each part so word timings are on the part's own timeline.

Writes PROJECT/work/parts/<part>/{base.mp4, voice.wav, words.json, segs.json} and PROJECT/work/timeline.txt
(word indices you reference in plan.json as w<index>).
"""
import difflib, json, re, sys, tempfile
from pathlib import Path
from common import run, load, save, whisper_model, W, H, FPS, die
import speechmap

GRADE = "eq=contrast=1.05:saturation=1.10:gamma=1.01,unsharp=5:5:0.35:5:5:0.0,vignette=angle=PI/7"   # cc off

# The CC pass. Per clip: white balance measured from the clip's own neutral
# midtones (gray world on low-saturation pixels, 3 frames), corrected WB_STRENGTH of the way so the room keeps a
# little warmth; then a gentle S-curve for depth, a whisper of teal in the shadows and warmth in the highlights,
# a touch of saturation, the old sharpen and vignette. plan.json "cc": false turns it off, {"wb": 0.5} changes
# how far the white balance goes. Gains are cached in work/cc.json.
WB_STRENGTH = 0.7
CC_LOOK = ("curves=all='0/0 0.08/0.055 0.5/0.5 0.92/0.95 1/1',colorbalance=rs=-0.02:bs=0.03:rh=0.02:bh=-0.01,"
           "eq=saturation=1.06,unsharp=5:5:0.35:5:5:0.0,vignette=angle=PI/7")


def wb_gains(clip, strength):
    """RGB gains that pull the clip's neutral midtones toward grey, `strength` of the way, brightness kept."""
    import numpy as np
    vals = []
    for k in (0.25, 0.5, 0.75):
        raw = run(["ffmpeg", "-v", "error", "-ss", f"{clip['dur'] * k:.2f}", "-i", clip["file"], "-frames:v", "1",
                   "-vf", "scale=270:480:force_original_aspect_ratio=increase,crop=270:480", "-f", "rawvideo",
                   "-pix_fmt", "rgb24", "-"], text=False).stdout
        x = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(float) / 255
        if len(x) == 0: continue
        l = x.mean(1); sat = (x.max(1) - x.min(1)) / (x.max(1) + 1e-6)
        m = x[(l > 0.25) & (l < 0.9) & (sat < 0.35)]
        if len(m) > 500: vals.append(m.mean(0))
    if not vals: return (1.0, 1.0, 1.0)
    m = np.mean(vals, 0); g = 1 + strength * (m.mean() / m - 1); g /= (g * m).mean() / m.mean()
    return tuple(float(v) for v in np.clip(g, 0.85, 1.2).round(3))


def grade_for(proj, cid, clip):
    if AS_IS: return "null"
    plan = proj / "plan.json"
    cc = load(plan).get("cc", {}) if plan.exists() else {}
    if cc is False: return GRADE
    strength = (cc or {}).get("wb", WB_STRENGTH)
    cache = proj / "work" / "cc.json"; got = load(cache) if cache.exists() else {}
    key = f"{cid}:{strength}"
    if key not in got: got[key] = wb_gains(clip, strength); save(cache, got)
    r, g, b = got[key]
    return f"colorchannelmixer=rr={r}:gg={g}:bb={b},{CC_LOOK}"


def out_anchor(clip):
    """Face centre in output pixels after cover-scaling the source to 1080x1920 and centre-cropping."""
    w, h, f = clip["w"], clip["h"], clip["face"]
    s = max(W / w, H / h); ox, oy = (w * s - W) / 2, (h * s - H) / 2
    cx, cy = f["cx"] * w * s - ox, f["cy"] * h * s - oy
    fh = f["fh"] * h * s if f["found"] else 0.0
    return round(cx, 1), round(cy, 1), round(fh, 1)


AS_IS = "--as-is" in sys.argv
_SPEECH = {}


def speech_of(c):
    """(regions, levels) of a source clip, cached; levels from ingest when present."""
    if c["id"] not in _SPEECH:
        lv = c.get("speech_lv") or speechmap.clip_levels(c["file"])
        regs, lv = speechmap.regions(c["file"], lv=lv)
        _SPEECH[c["id"]] = (regs, lv)
    return _SPEECH[c["id"]]


def speech_only(segs, clips):
    """HARD RULE: a part contains only the parts where the speaker is talking. Every select is intersected with its clip's
    speech map, so a hand-edited select, a whisper word stretched over silence, or a noisy room can never bring a
    pause in. Pauses over SPLIT_GAP inside a select are cut out; a select with no speech is dropped."""
    out = []
    for cid, a, b in segs:
        c = clips.get(cid) or die(f"selects.json: unknown clip {cid}")
        regs, _ = speech_of(c)
        keep = speechmap.tighten(regs, float(a), float(b), c["dur"])
        if not keep: print(f"  dropped {cid} {a}-{b}: no speech in it", flush=True)
        trimmed = (float(b) - float(a)) - sum(k1 - k0 for k0, k1 in keep)
        if trimmed > 0.3: print(f"  {cid} {float(a):.2f}-{float(b):.2f}: cut {trimmed:.2f}s of non-speech", flush=True)
        out += [[cid, k0, k1] for k0, k1 in keep]
    return out


def gate(name, d, out, clips):
    """Refuse a part with a pause in it (speechmap.MAX_GAP inside, MAX_EDGE at either end)."""
    lv = {cid: speech_of(c)[1] for cid, c in clips.items() if any(s["clip"] == cid for s in out)}
    gaps, lead, tail = speechmap.gaps_in_part(d / "voice.wav", out, lv)
    bad = [f"{g:.2f}s of silence at {t:.2f}s" for t, g in gaps]
    if lead > speechmap.MAX_EDGE + 0.05: bad.append(f"{lead:.2f}s before the first word")
    if tail > speechmap.MAX_EDGE + 0.08: bad.append(f"{tail:.2f}s after the last word")
    if bad and AS_IS: print(f"  WARN {name}: " + "; ".join(bad) + " (kept: --as-is)", flush=True); return
    if bad: die(f"part {name} still has non-speech in it: " + "; ".join(bad) + " (check the clip's levels in "
                f"project.json speech_lv; speechmap.py <clip> shows its regions)")
    print(f"  {name}: speech-only check passed (longest pause <= {speechmap.MAX_GAP}s)", flush=True)


def render_part(proj, name, segs, clips, model):
    d = proj / "work" / "parts" / name; (d / "seg").mkdir(parents=True, exist_ok=True)
    for f in (d / "seg").glob("*"): f.unlink()
    segs = [[c, float(a), float(b)] for c, a, b in segs] if AS_IS else speech_only(segs, clips)
    vlist, alist, out, t = [], [], [], 0.0
    for i, (cid, a, b) in enumerate(segs):
        c = clips.get(cid) or die(f"selects.json: unknown clip {cid}")
        a = max(0.0, float(a)); b = min(float(b), c["dur"])
        n = round((b - a) * FPS)
        if n < 3: continue
        dur = n / FPS
        vf = (f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,{grade_for(proj, cid, c)},"
              f"tpad=stop_mode=clone:stop=3")
        vp, ap = d / "seg" / f"{i:02d}.mp4", d / "seg" / f"{i:02d}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", c["file"], "-frames:v", str(n), "-an", "-vf", vf,
             "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-pix_fmt", "yuv420p", str(vp)])
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{dur:.4f}", "-i", c["file"], "-map", "0:a:0",
             "-ac", "2", "-ar", "48000", "-af", f"afade=t=in:d=0.012,afade=t=out:st={max(0, dur - 0.02):.3f}:d=0.02,apad",
             "-t", f"{dur:.4f}", str(ap)])
        ax, ay, fh = out_anchor(c)
        out.append({"clip": cid, "src_in": round(a, 3), "src_out": round(a + dur, 3), "t0": round(t, 4),
                    "t1": round(t + dur, 4), "ax": ax, "ay": ay, "fh": fh})
        vlist.append(f"file '{vp}'"); alist.append(f"file '{ap}'"); t += dur
    if not out: die(f"part {name}: no segments")
    (d / "v.txt").write_text("\n".join(vlist) + "\n"); (d / "a.txt").write_text("\n".join(alist) + "\n")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(d / "v.txt"), "-c", "copy", str(d / "base.mp4")])
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(d / "a.txt"), "-c:a", "pcm_s16le", str(d / "voice.wav")])
    gate(name, d, out, clips)
    with tempfile.TemporaryDirectory() as tmp:
        w16 = Path(tmp) / "v16.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(d / "voice.wav"), "-ac", "1", "-ar", "16000", str(w16)])
        run(["whisper-cli", "-m", model, "-f", str(w16), "-ml", "1", "-sow", "-oj", "-of", str(Path(tmp) / "w"), "-l", "en", "-np"])
        js = json.loads((Path(tmp) / "w.json").read_text())
    words = [[s["text"].strip(), round(s["offsets"]["from"] / 1000, 3), round(s["offsets"]["to"] / 1000, 3)]
             for s in js["transcription"] if s["text"].strip() and not s["text"].strip().startswith("[")]
    words = restore_punctuation(words, segs, clips)
    frames = int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                      "stream=nb_read_frames", "-of", "csv=p=0", str(d / "base.mp4")]).stdout.strip())
    nominal = round(t * FPS)
    if frames != nominal: print(f"warning: {name} has {frames} frames, expected {nominal}", file=sys.stderr)
    save(d / "segs.json", {"duration": round(nominal / FPS, 4), "frames": nominal, "segs": out})
    save(d / "words.json", words)
    return words, nominal / FPS


def restore_punctuation(words, segs, clips):
    """whisper sometimes returns a long part with no punctuation, which breaks caption grouping and sentence
    capitals. The per-clip transcripts from ingest keep theirs, so copy punctuation (and casing) across by
    aligning the two word sequences. Timings always stay the part's own."""
    punct = sum(1 for w in words if re.search(r"[.,?!]$", w[0]))
    if not words or punct >= len(words) / 25: return words
    ref = []
    for cid, a, b in segs:
        for w, s0, s1 in clips[cid]["words"]:
            if a - 0.05 <= (s0 + s1) / 2 <= b + 0.05: ref.append(w)
    norm = lambda w: re.sub(r"[^\w$%']", "", w.lower())
    sm = difflib.SequenceMatcher(a=[norm(w[0]) for w in words], b=[norm(w) for w in ref], autojunk=False)
    out = [list(w) for w in words]
    for i, j, n in sm.get_matching_blocks():
        for k in range(n): out[i + k][0] = ref[j + k]
    print(f"  restored punctuation from the per-clip transcripts ({punct} -> "
          f"{sum(1 for w in out if re.search(r'[.,?!]$', w[0]))} marks)", flush=True)
    return out


def listing(name, words, dur):
    lines, cur = [f"## {name}  ({dur:.2f}s, {len(words)} words)"], []
    for i, (w, a, b) in enumerate(words):
        cur.append(f"w{i}:{w}")
        if re.search(r"[.?!,]$", w) or len(cur) >= 10:
            lines.append(f"  [{words[i - len(cur) + 1][1]:6.2f}] " + " ".join(cur)); cur = []
    if cur: lines.append(f"  [{words[len(words) - len(cur)][1]:6.2f}] " + " ".join(cur))
    return lines


def audio_only(proj, clips):
    """Re-extract every part's voice.wav from its segs.json (same cuts, same timing), e.g. after an audio fix."""
    for d in sorted((proj / "work" / "parts").iterdir()):
        segs = load(d / "segs.json")["segs"]; lst = []
        for i, s in enumerate(segs):
            dur = s["t1"] - s["t0"]; ap = d / "seg" / f"{i:02d}.wav"
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['src_in']:.3f}", "-t", f"{dur:.4f}", "-i", clips[s["clip"]]["file"],
                 "-map", "0:a:0", "-ac", "2", "-ar", "48000", "-af",
                 f"afade=t=in:d=0.012,afade=t=out:st={max(0, dur - 0.02):.3f}:d=0.02,apad", "-t", f"{dur:.4f}", str(ap)])
            lst.append(f"file '{ap}'")
        (d / "a.txt").write_text("\n".join(lst) + "\n")
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(d / "a.txt"), "-c:a", "pcm_s16le", str(d / "voice.wav")])
        print(f"{d.name}: voice re-extracted ({len(segs)} segments)")


def main():
    if len(sys.argv) < 2: die(__doc__)
    proj = Path(sys.argv[1]).expanduser().resolve()
    if "--audio-only" in sys.argv:
        audio_only(proj, {c["id"]: c for c in load(proj / "project.json")["clips"]}); return
    p = load(proj / "project.json"); sel = load(proj / "selects.json")
    clips = {c["id"]: c for c in p["clips"]}
    model = whisper_model()
    lines = []
    parts = [(f"hook-{h}", segs) for h, segs in sel["hooks"].items()] + [("body", sel["body"])]
    only = sys.argv[sys.argv.index("--part") + 1] if "--part" in sys.argv else None
    if only:
        parts = [p for p in parts if p[0] == only] or die(f"no part {only}")
    for name, segs in parts:
        words, dur = render_part(proj, name, segs, clips, model)
        lines += listing(name, words, dur) + [""]
        print(f"{name}: {dur:.2f}s, {len(words)} words", flush=True)
    if only:   # keep the other parts' listings, replace this one
        old = (proj / "work" / "timeline.txt").read_text().split("## ") if (proj / "work" / "timeline.txt").exists() else []
        keep = ["## " + b.rstrip() + "\n" for b in old if b.strip() and not b.startswith(only + " ")]
        lines = [l for b in keep for l in b.split("\n")] + lines
    (proj / "work" / "timeline.txt").write_text("\n".join(lines))
    print(f"wrote {proj/'work/timeline.txt'}")


if __name__ == "__main__":
    main()
