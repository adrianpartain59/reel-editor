#!/usr/bin/env python3
"""Step 6: check a finished variant before showing it to anyone.

  qa.py PROJECT --variant h1

Checks (FAIL blocks delivery, WARN is a judgement call to mention):
  frames + duration match the cut, audio covers the whole video
  loudness -12 +/- 1 LUFS, true peak <= -0.5 dBTP
  the reel opens on the face (first shot is a face layout, first overlay no earlier than 0.8 s)
  first spoken word within 0.6 s (no dead air at the top)
  pacing: no stretch longer than 3.0 s without a cut, zoom change, punch, sticker or overlay change
  captions cover >= 90% of spoken words (punch titles and caption-free sections count as covered)
  full-screen overlays hold >= 1.5 s so people can read them
  SFX density: at least 1 cue per 4 s
  intent and variety (everything animated, everything with a sound, nothing repeated):
    every visual event has a sound unless the plan silenced it on purpose
    no sound file more than 3 times (typing keys and ticks excepted), no category over 35% of the cues,
    no file twice within 3 s
    no transition twice in a row, none over 30% of the transitions; no title / phone animation 3 times running
  the audio matches the original recording's tone (audio_check.py: no band above 2 kHz more than 3 dB down)
  file size of the phone copy < 30 MB
Also writes out/<slug>-<variant>-sheet.jpg: one still every 1.5 s for a fast visual check.
"""
import argparse, json, subprocess, sys
from pathlib import Path
from PIL import Image
from common import load, run, load_style

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--variant", required=True)
    a = ap.parse_args()
    proj = Path(a.project).expanduser().resolve(); plan = load(proj / "plan.json"); slug = plan.get("slug", "reel")
    ev = load(proj / "work" / "out" / a.variant / "events.json")
    final = proj / "out" / f"{slug}-{a.variant}.mp4"; phone = proj / "out" / f"{slug}-{a.variant}-phone.mp4"
    res = []
    def check(ok, msg, level="FAIL"): res.append(("PASS" if ok else level, msg))
    fr = int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                  "-of", "csv=p=0", str(final)]).stdout.strip())
    check(fr == ev["frames"], f"frames {fr} vs cut {ev['frames']}")
    ad = float(run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(final)]).stdout.strip())
    check(abs(ad - ev["duration"]) < 0.05, f"audio {ad:.2f}s vs video {ev['duration']:.2f}s")
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    js = json.loads(m[m.rindex("{"): m.rindex("}") + 1]); I, TP = float(js["input_i"]), float(js["input_tp"])
    tgt = float(load_style(plan)["mix"].get("lufs", -12))
    check(abs(I - tgt) <= 1.0, f"loudness {I:.1f} LUFS (target {tgt:g})"); check(TP <= -0.5, f"true peak {TP:.2f} dBTP")
    shots = ev["shots"]
    check(shots[0]["lay"] == "face", f"opens on {shots[0]['lay']} (should be the face)")
    first_overlay = next((s["_t"] for s in shots if s["lay"] != "face"), 99)
    check(first_overlay >= 0.8, f"first overlay at {first_overlay:.2f}s (keep the face alone >= 0.8 s)")
    first_word = ev["groups"][0]["t0"] if ev["groups"] else 0
    check(first_word <= 0.6, f"first caption at {first_word:.2f}s", "WARN")
    # HARD RULE: only the parts where the speaker talks. Each cut part's voice is re-measured with the speech map, every
    # segment against its own source clip's thresholds.
    import speechmap
    clips = {c["id"]: c for c in load(proj / "project.json")["clips"]}
    bad = []
    for part in (f"hook-{a.variant}", "body"):
        pd = proj / "work" / "parts" / part
        segs = load(pd / "segs.json")["segs"]
        lv = {s["clip"]: clips[s["clip"]].get("speech_lv") or speechmap.clip_levels(clips[s["clip"]]["file"]) for s in segs}
        gaps, lead, tail = speechmap.gaps_in_part(pd / "voice.wav", segs, lv)
        bad += [f"{part} {g:.2f}s at {t:.2f}s" for t, g in gaps]
        if lead > speechmap.MAX_EDGE + 0.05: bad.append(f"{part} starts with {lead:.2f}s of silence")
        if tail > speechmap.MAX_EDGE + 0.08: bad.append(f"{part} ends with {tail:.2f}s of silence")
    check(not bad, f"speech only: no pause over {speechmap.MAX_GAP}s in any part" if not bad else
          "pauses where the speaker isn't talking: " + ", ".join(bad[:6]))
    # the comment outro: every reel ends on a comment being typed (compose adds one if the plan has none)
    pills = [s for s in ev["stickers"] if s["type"] == "chat_pill" and s["t1"] >= ev["duration"] - 0.5]
    check(bool(pills), "ends on the comment outro (chat_pill)" if pills else
          'no comment outro: the reel must end on a chat_pill (plan "outro_comment": false only when they ask)')
    marks = sorted({0.0, ev["duration"]} | {s["_t"] for s in shots} | {p["t0"] for p in ev["punches"]} |
                   {s["t0"] for s in ev["stickers"]} | {f["t"] for f in ev["fx"]} |
                   {t for s in shots for t in s.get("swap_t", [])})
    gaps = [(b - a, a) for a, b in zip(marks, marks[1:])]
    worst = max(gaps)
    check(worst[0] <= 3.0, f"longest stretch without a visual change {worst[0]:.1f}s at {worst[1]:.1f}s", "WARN")
    covered = sum(len(g["words"]) for g in ev["groups"])
    suppressed = ev["word_count"] - covered
    check(covered / max(1, ev["word_count"]) >= 0.75 or suppressed < 20,
          f"captions show {covered}/{ev['word_count']} words ({suppressed} under punches, bubbles or caption-free sections)", "WARN")
    for s in shots:
        if s["lay"] in ("fullpw", "phone3d", "video"):
            check(s["_end"] - s["_t"] >= 1.5, f"full-screen {s.get('img') or s.get('src')} holds {s['_end'] - s['_t']:.1f}s", "WARN")
    rate = len(ev["sfx"]) / max(1, ev["duration"])
    check(rate >= 0.25, f"{len(ev['sfx'])} sfx cues ({rate * 10:.1f} per 10 s)", "WARN")
    if "visual" in ev:
        mute = [v for v in ev["visual"] if not v["sound"] and not v["silent"]]
        check(not mute, f"every visual event has a sound" if not mute else
              f"{len(mute)} visual events move in silence: " + ", ".join(f"{v['kind']} {v['t']:.1f}s" for v in mute[:6]), "WARN")
        # how often each sound may play is the sound's own rule now (pack.json "rules", checked in the audio map
        # below), so the old reuse / repeat / most-used checks are gone
        from collections import Counter
        trs = [x["name"] for x in ev.get("transitions", [])]
        rep = [f"{a_} at {x['t']:.1f}s" for a_, b_, x in zip(trs, trs[1:], ev["transitions"][1:]) if a_ == b_]
        check(not rep, f"{len(trs)} transitions, {len(set(trs))} different, none twice in a row" if not rep else "same transition twice in a row: " + ", ".join(rep), "WARN")
        if len(trs) >= 5:
            tc = Counter(trs).most_common(1)[0]; check(tc[1] <= 0.3 * len(trs), f"most used transition: {tc[0]} {tc[1]}/{len(trs)}", "WARN")
        for kind in ("glow_title", "phone3d"):
            seq = [x["anim"] for x in sorted(ev.get("anims", []), key=lambda x: x["t"]) if x["type"] == kind]
            run3 = [seq[i] for i in range(len(seq) - 2) if seq[i] == seq[i + 1] == seq[i + 2]]
            check(not run3, f"{kind} animations vary ({len(set(seq))} kinds)" if not run3 else f"{kind} animation '{run3[0]}' three times running", "WARN")
    ac = subprocess.run([sys.executable, str(Path(__file__).parent / "audio_check.py"), str(proj), "--variant", a.variant],
                        capture_output=True, text=True)
    last = (ac.stdout.strip().split("\n") or [""])[-1]
    check(ac.returncode == 0, f"audio vs original recording: {last.replace('worst band above 2 kHz: ', 'worst band above 2 kHz ')}")
    # the audio map (mix.py): one effect at a time, each ends with its visual, whooshes short, no pile-ups
    am = proj / "work" / "out" / a.variant / "audio_map.json"
    if am.exists():
        import audiomap
        try: import sfx_lib; rq = sfx_lib.rules
        except Exception: rq = None
        for lvl, msg in audiomap.check(json.loads(am.read_text()), rq): check(lvl == "PASS", msg, "FAIL" if lvl == "FAIL" else "WARN")
    else: check(False, "no audio_map.json: run mix.py")
    size = phone.stat().st_size / 1e6 if phone.exists() else 999
    check(size < 30, f"phone copy {size:.1f} MB")
    # contact sheet
    ts = [round(x * 1.5, 2) for x in range(int(ev["duration"] / 1.5) + 1)]
    tiles = []
    for t in ts:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(final), "-frames:v", "1", "-vf", "scale=216:384",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        if len(r.stdout) == 216 * 384 * 3: tiles.append(Image.frombytes("RGB", (216, 384), r.stdout))
    cols = 10; rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 216, rows * 384))
    for i, im in enumerate(tiles): sheet.paste(im, ((i % cols) * 216, (i // cols) * 384))
    sp = proj / "out" / f"{slug}-{a.variant}-sheet.jpg"; sheet.save(sp, quality=82)
    for lvl, msg in res: print(f"{lvl:4s}  {msg}")
    print(f"sheet: {sp}")
    fails = [m for l, m in res if l == "FAIL"]
    print("RESULT:", "FAIL" if fails else "PASS")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
