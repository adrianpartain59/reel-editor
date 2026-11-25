#!/usr/bin/env python3
"""Step 1: ingest raw takes into a reel project.

  ingest.py PROJECT_DIR --hook H1.MOV [--hook H2.MOV ...] --body B1.MOV B2.MOV ... [--slug name]

For every clip: probe it, find the speech (auto threshold from the clip's own noise floor), transcribe the
speech with word timings (silence trimmed first: whisper.cpp squeezes words into a silent lead-in), and find
the face (macOS Vision) so zooms and crops centre on it.

Writes PROJECT/project.json, PROJECT/selects.json (every speech chunk, in order: edit this to drop retakes,
flubs and dead lines), PROJECT/work/transcript.txt (chunk ids + text, read this) and PROJECT/work/clips.jpg.
"""
import argparse, json, statistics, subprocess, tempfile
import speechmap
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import run, save, whisper_model, need_tools, die, SR

SWIFT_FACE = r'''
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
  guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("NONE"); continue }
  let req = VNDetectFaceRectanglesRequest()
  try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
  let faces = (req.results ?? []).sorted { $0.boundingBox.width > $1.boundingBox.width }
  if let f = faces.first { let b = f.boundingBox; print("\(b.midX) \(1 - b.midY) \(b.width) \(b.height)") } else { print("NONE") }
}
'''


def probe(f):
    js = json.loads(run(["ffprobe", "-v", "error", "-show_entries",
                         "format=duration:stream=codec_type,width,height,r_frame_rate:stream_side_data=rotation",
                         "-of", "json", str(f)]).stdout)
    v = next((s for s in js["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in js["streams"] if s["codec_type"] == "audio"), None)
    if not v: die(f"{f}: no video stream")
    if not a: die(f"{f}: no audio stream")
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd: rot = int(sd["rotation"])
    w, h = v["width"], v["height"]
    if abs(rot) in (90, 270): w, h = h, w
    num, den = v["r_frame_rate"].split("/")
    return {"dur": float(js["format"]["duration"]), "w": w, "h": h, "fps": round(float(num) / float(den), 2)}


def pcm(path, sr):
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
              text=False).stdout
    return np.frombuffer(raw, dtype=np.float32)


def speech_chunks(x, sr, pad_in=0.06, pad_out=0.12, merge_gap=0.25, min_len=0.14):
    """Energy-based speech regions with a threshold set from the clip's own noise floor."""
    win = int(0.02 * sr)
    n = len(x) // win
    db = 20 * np.log10(np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-9)
    noise, speech = np.percentile(db, 10), np.percentile(db, 92)
    thr = float(np.clip(noise + 0.28 * (speech - noise), -54, -28))
    on = db > thr
    # smooth: fill 1-2 window dropouts inside words
    for i in range(1, n - 1):
        if not on[i] and on[i - 1] and on[i + 1]: on[i] = True
    regs, i = [], 0
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]: j += 1
            regs.append([i * 0.02, j * 0.02]); i = j
        else:
            i += 1
    regs = [r for r in regs if r[1] - r[0] >= 0.05]
    # A breath or rustle in a very quiet room can clear a noise-floor-relative threshold. Real speech peaks
    # near the clip's speech level; anything that never gets within 18 dB of it is not a line.
    regs = [r for r in regs if db[int(r[0] / 0.02):max(int(r[0] / 0.02) + 1, int(r[1] / 0.02))].max() >= speech - 18]
    dur = len(x) / sr
    padded = [[max(0, a - pad_in), min(dur, b + pad_out)] for a, b in regs]
    merged = []
    for a, b in padded:
        if merged and a - merged[-1][1] < merge_gap: merged[-1][1] = b
        else: merged.append([a, b])
    merged = [m for m in merged if m[1] - m[0] >= min_len]
    return [[round(a, 3), round(b, 3)] for a, b in merged], {"noise_db": round(float(noise), 1),
                                                              "speech_db": round(float(speech), 1), "thr_db": round(thr, 1)}


def owner(w, chunks):
    """Chunk index a word belongs to: the one it overlaps most, else the nearest."""
    best, bo = None, 0.0
    for k, (a, b) in enumerate(chunks):
        o = min(b, w[2]) - max(a, w[1])
        if o > bo: best, bo = k, o
    if best is not None: return best
    return min(range(len(chunks)), key=lambda k: min(abs(chunks[k][0] - w[2]), abs(chunks[k][1] - w[1])))


def cover_words(chunks, words, dur, sdb=None, slv=None):
    """Quiet words (a soft 'do', a trailing 'it') can sit under the threshold. If whisper heard a word that no chunk
    overlaps, stretch the nearest chunk over it so the cut never drops a spoken word, but only over audio that has
    speech-band energy (>= floor + 8 dB): whisper stretches a last word over trailing silence or hum
    (to the clip's end), and following it puts a 1.2 s pause in the reel."""
    chunks = [list(c) for c in chunks]
    def audible(a, b):
        if sdb is None: return True
        i, j = int(a / 0.01), max(int(a / 0.01) + 1, int(b / 0.01))
        return len(sdb[i:j]) and float(sdb[i:j].max()) >= slv["floor"] + 8
    for w in words:
        if not audible(w[1], w[2]): continue
        hit = [c for c in chunks if min(c[1], w[2]) - max(c[0], w[1]) > 0]
        if hit:
            # a chunk that cuts a word short gets stretched to the word's edge (at most 0.3 s)
            c = max(hit, key=lambda c: min(c[1], w[2]) - max(c[0], w[1]))
            if 0 < w[2] + 0.05 - c[1] <= 0.15 and audible(c[1], w[2]): c[1] = min(dur, w[2] + 0.05)
            if 0 < c[0] - (w[1] - 0.03) <= 0.15 and audible(w[1], c[0]): c[0] = max(0, w[1] - 0.03)
            continue
        k = owner(w, chunks)
        if min(abs(chunks[k][0] - w[2]), abs(chunks[k][1] - w[1])) > 0.8: continue
        chunks[k][0] = min(chunks[k][0], max(0, w[1] - 0.05)); chunks[k][1] = max(chunks[k][1], min(dur, w[2] + 0.06))
    chunks.sort(); merged = []
    for a, b in chunks:
        if merged and a <= merged[-1][1] + 0.02: merged[-1][1] = max(merged[-1][1], b)
        else: merged.append([a, b])
    return [[round(a, 3), round(b, 3)] for a, b in merged]


def transcribe(wav16, t_in, t_out, model, tmp):
    """Transcribe only [t_in, t_out] so whisper's first word lands on the first syllable."""
    seg = Path(tmp) / "seg.wav"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t_in:.3f}", "-to", f"{t_out:.3f}", "-i", str(wav16), str(seg)])
    run(["whisper-cli", "-m", model, "-f", str(seg), "-ml", "1", "-sow", "-oj", "-of", str(Path(tmp) / "w"),
         "-l", "en", "-np"])
    js = json.loads((Path(tmp) / "w.json").read_text())
    out = []
    for s in js["transcription"]:
        t = s["text"].strip()
        if not t or t.startswith("["): continue
        out.append([t, round(t_in + s["offsets"]["from"] / 1000, 3), round(t_in + s["offsets"]["to"] / 1000, 3)])
    return out


def faces(clip, dur, tmp):
    paths = []
    for k, frac in enumerate([0.25, 0.5, 0.75]):
        p = Path(tmp) / f"f{k}.png"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * frac:.2f}", "-i", str(clip), "-frames:v", "1",
             "-vf", "scale=540:-2", str(p)])
        paths.append(str(p))
    sw = Path(tmp) / "face.swift"; sw.write_text(SWIFT_FACE)
    try:
        out = subprocess.run(["swift", str(sw), *paths], capture_output=True, text=True, timeout=120).stdout.split("\n")
        vals = [list(map(float, l.split())) for l in out if l and l != "NONE"]
    except Exception:
        vals = []
    if not vals: return {"cx": 0.5, "cy": 0.45, "fw": 0.0, "fh": 0.0, "found": False}
    med = [statistics.median(v[i] for v in vals) for i in range(4)]
    return {"cx": round(med[0], 4), "cy": round(med[1], 4), "fw": round(med[2], 4), "fh": round(med[3], 4), "found": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--hook", action="append", default=[], help="a hook take (repeat for A/B hook variants)")
    ap.add_argument("--body", nargs="+", default=[], help="body takes, in speaking order")
    ap.add_argument("--slug", default=None)
    a = ap.parse_args()
    need_tools()
    if not a.hook and not a.body: die("give --hook clips (the opening line), --body clips, or both (a Split Screen needs only --body)")
    if not a.body: die("give the body clips with --body")
    proj = Path(a.project).expanduser().resolve(); (proj / "work").mkdir(parents=True, exist_ok=True)
    model = whisper_model()
    clips, lines = [], []
    roles = [("hook", f) for f in a.hook] + [("body", f) for f in a.body]
    for idx, (role, f) in enumerate(roles):
        f = Path(f).expanduser().resolve()
        if not f.exists(): die(f"{f} not found")
        cid = f"{'h' if role == 'hook' else 'b'}{sum(1 for r, _ in roles[:idx] if r == role) + 1}"
        info = probe(f)
        with tempfile.TemporaryDirectory() as tmp:
            wav16 = Path(tmp) / "a16.wav"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(wav16)])
            # the speech map decides the chunks: speech-band energy against this clip's own floor (speechmap.py)
            regs, slv = speechmap.regions(f)
            chunks = speechmap.tighten(regs, 0.0, info["dur"], info["dur"])
            if not chunks: die(f"{f.name}: no speech found")
            x = pcm(f, SR)
            _, lv = speech_chunks(x, SR)          # full-band levels, kept for the denoise option in mix.py
            sdb = speechmap.band_db(speechmap.pcm16(f))
            words = transcribe(wav16, max(0, chunks[0][0] - 0.02), min(info["dur"], chunks[-1][1] + 0.05), model, tmp)
            face = faces(f, info["dur"], tmp)
        chunks = cover_words(chunks, words, info["dur"], sdb, slv)
        ch = []
        for k, (ci, co) in enumerate(chunks):
            ws = [w for w in words if owner(w, chunks) == k]
            ch.append({"id": f"{cid}.{k}", "in": ci, "out": co, "text": " ".join(w[0] for w in ws), "words": len(ws)})
        clips.append({"id": cid, "role": role, "file": str(f), **info, "levels": lv, "speech_lv": slv, "face": face,
                      "words": words, "chunks": ch})
        lines.append(f"== {cid} ({role})  {f.name}  {info['dur']:.1f}s  {info['w']}x{info['h']}@{info['fps']}  "
                     f"face={'yes' if face['found'] else 'NOT FOUND'}  noise {lv['noise_db']} dB / speech {lv['speech_db']} dB")
        for c in ch:
            lines.append(f"  {c['id']:6s} {c['in']:6.2f}-{c['out']:6.2f}  {c['text'] or '(no words: breath or noise, left out of selects.json)'}")
        print("\n".join(lines[-len(ch) - 1:]), flush=True)
    slug = a.slug or proj.name
    save(proj / "project.json", {"slug": slug, "clips": clips})
    hooks = {c["id"]: [[c["id"], k["in"], k["out"]] for k in c["chunks"] if k["words"]] for c in clips if c["role"] == "hook"}
    body = [[c["id"], k["in"], k["out"]] for c in clips if c["role"] == "body" for k in c["chunks"] if k["words"]]
    sel = proj / "selects.json"
    if sel.exists(): print(f"kept existing {sel} (delete it to regenerate)")
    else: save(sel, {"hooks": hooks, "body": body})
    (proj / "work" / "transcript.txt").write_text("\n".join(lines) + "\n")
    contact(proj, clips)
    print(f"\nwrote {proj/'project.json'}, {sel}, {proj/'work/transcript.txt'}, {proj/'work/clips.jpg'}")


def contact(proj, clips):
    tiles = []
    for c in clips:
        p = proj / "work" / f"_t_{c['id']}.png"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{c['dur'] * 0.4:.2f}", "-i", c["file"], "-frames:v", "1",
             "-vf", "scale=270:480:force_original_aspect_ratio=increase,crop=270:480", str(p)])
        im = Image.open(p).convert("RGB"); d = ImageDraw.Draw(im)
        if c["face"]["found"]:
            x, y = c["face"]["cx"] * 270, c["face"]["cy"] * 480
            d.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(255, 0, 0), width=3)
        d.rectangle([0, 0, 120, 30], fill=(0, 0, 0)); d.text((6, 6), c["id"], fill=(255, 255, 255),
                                                               font=ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 18))
        tiles.append(im); p.unlink()
    sheet = Image.new("RGB", (270 * len(tiles), 480))
    for i, t in enumerate(tiles): sheet.paste(t, (i * 270, 0))
    sheet.save(proj / "work" / "clips.jpg", quality=85)


if __name__ == "__main__":
    main()
