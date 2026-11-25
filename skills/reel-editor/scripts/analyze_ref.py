#!/usr/bin/env python3
"""Break down a reference reel (a video whose production style the user wants to learn from) into measurements.

  analyze_ref.py VIDEO OUTDIR [--start 4.85 --end 44.75]

--start/--end trim a screen recording to the reel itself (scrub past the app UI and any loop restart).
Writes to OUTDIR:
  sheets/s_<t>.jpg     4 fps contact sheets, 8 s each, timestamped: read every one
  key/<t>.jpg          full-res stills at the visual events found below: fonts, glow, layout detail
  spec_mid.png         spectrogram of the mid channel (voice + everything) with the words under it
  spec_side.png        spectrogram of L-R: music and stereo SFX without the centred voice
  summary.md           the numbers: pace, pauses, loudness, music-bed level, SFX onsets, hard cuts, zoom
                       moves (face size per 0.1 s), brightness
The interpretation is yours: look at the sheets and spectrograms, then write assets/styles/<name>.json and
references/looks/<name>.md (see references/looks/README.md for the procedure).
"""
import argparse, json, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import run, whisper_model, SR

FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
SWIFT_FACE = r'''
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
  autoreleasepool {
  guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("NONE"); return }
  let req = VNDetectFaceRectanglesRequest()
  try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
  let faces = (req.results ?? []).sorted { $0.boundingBox.width > $1.boundingBox.width }
  if let f = faces.first { let b = f.boundingBox; print("\(b.midX) \(1 - b.midY) \(b.width) \(b.height)") } else { print("NONE") }
  }
}
'''


def sheets(frames, fps, out, span=8, cols=8):
    fn = ImageFont.truetype(FONT, 26); out.mkdir(parents=True, exist_ok=True)
    for a in range(0, int(len(frames) / fps) + 1, span):
        sel = [(i / fps, f) for i, f in enumerate(frames) if a <= i / fps < a + span]
        if not sel: continue
        w, h = Image.open(sel[0][1]).size; rows = (len(sel) + cols - 1) // cols
        S = Image.new("RGB", (cols * w, rows * h)); d = ImageDraw.Draw(S)
        for k, (t, f) in enumerate(sel):
            x, y = (k % cols) * w, (k // cols) * h
            S.paste(Image.open(f), (x, y)); d.rectangle([x, y, x + 92, y + 32], fill="black"); d.text((x + 4, y + 2), f"{t:.2f}", font=fn, fill="yellow")
        S.save(out / f"s_{a:02d}.jpg", quality=85)


def spectrogram(sig, words, path, rng=55, pxs=60):
    n = 2048; hop = 240; win = np.hanning(n)
    fr = np.lib.stride_tricks.sliding_window_view(sig, n)[::hop] * win
    S = np.abs(np.fft.rfft(fr, axis=1)) ** 2; f = np.fft.rfftfreq(n, 1 / SR)
    edges = np.geomspace(30, 20000, 241)
    rows = np.stack([S[:, (f >= a) & (f < b)].mean(1) if ((f >= a) & (f < b)).any() else S[:, np.argmin(abs(f - a))]
                     for a, b in zip(edges, edges[1:])], 1)
    db = 10 * np.log10(rows + 1e-12); top = np.percentile(db, 99.5); db = np.clip((db - top + rng) / rng, 0, 1)
    t = len(sig) / SR
    im = Image.fromarray((db.T[::-1] * 255).astype(np.uint8)).resize((int(t * pxs), 420))
    a = np.asarray(im).astype(float) / 255
    im = Image.fromarray((np.stack([np.clip(a * 3, 0, 1), np.clip(a * 3 - 1, 0, 1), np.clip(a * 3 - 2, 0, 1)], 2) * 255).astype(np.uint8))
    C = Image.new("RGB", (im.width, im.height + 60)); C.paste(im, (0, 0)); d = ImageDraw.Draw(C)
    fn = ImageFont.truetype(FONT.replace(" Bold", ""), 13)
    for s in range(int(t) + 1):
        d.line([(s * pxs, 0), (s * pxs, im.height)], fill=(80, 80, 255)); d.text((s * pxs + 2, im.height + 2), str(s), font=fn, fill="white")
    for k, (a0, _, w) in enumerate(words): d.text((a0 * pxs, im.height + 18 + (k % 3) * 13), w, font=fn, fill=(200, 255, 200))
    for hz in [50, 100, 200, 500, 1000, 2000, 5000, 10000]:
        y = int((1 - np.log(hz / 30) / np.log(20000 / 30)) * im.height); d.text((2, y), str(hz), font=fn, fill="cyan")
    C.save(path)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("outdir")
    ap.add_argument("--start", type=float, default=0.0); ap.add_argument("--end", type=float, default=None)
    a = ap.parse_args(); out = Path(a.outdir).expanduser(); out.mkdir(parents=True, exist_ok=True)
    trim = ["-ss", str(a.start)] + (["-to", str(a.end)] if a.end else [])
    L = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); (tmp / "f4").mkdir(); (tmp / "f10").mkdir()
        run(["ffmpeg", "-v", "error", *trim, "-i", a.video, "-vf", "fps=4,scale=360:-2", "-q:v", "3", str(tmp / "f4" / "%05d.jpg")])
        run(["ffmpeg", "-v", "error", *trim, "-i", a.video, "-vf", "fps=10,scale=400:-2", "-q:v", "4", str(tmp / "f10" / "%05d.jpg")])
        f4 = sorted((tmp / "f4").glob("*.jpg")); f10 = sorted((tmp / "f10").glob("*.jpg"))
        sheets(f4, 4, out / "sheets")
        # hard cuts + brightness
        prev = None; diffs, luma = [], []
        for f in f10:
            g = np.asarray(Image.open(f).convert("L").resize((100, 180))).astype(float)
            diffs.append(0 if prev is None else np.abs(g - prev).mean()); luma.append(g.mean()); prev = g
        diffs = np.array(diffs); thr = max(12, np.median(diffs) * 4)
        cuts = [round(i / 10, 1) for i, v in enumerate(diffs) if v > thr]
        # face size per 0.1 s
        (tmp / "face.swift").write_text(SWIFT_FACE)
        fo = subprocess.run(["swift", str(tmp / "face.swift"), *map(str, f10)], capture_output=True, text=True).stdout.split("\n")
        fw = [None if (not l or l == "NONE") else float(l.split()[2]) for l in fo[:len(f10)]]
        # audio
        run(["ffmpeg", "-v", "error", "-y", *trim, "-i", a.video, "-map", "0:a:0", "-ar", str(SR), "-ac", "2", str(tmp / "a.wav")])
        x = np.frombuffer(run(["ffmpeg", "-v", "error", "-i", str(tmp / "a.wav"), "-f", "f32le", "-"], text=False).stdout, np.float32).reshape(-1, 2)
        mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2
        m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(tmp / "a.wav"), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        ln = json.loads(m[m.rindex("{"): m.rindex("}") + 1])
        run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "a.wav"), "-ar", "16000", "-ac", "1", str(tmp / "a16.wav")])
        subprocess.run(["whisper-cli", "-m", whisper_model(), "-f", str(tmp / "a16.wav"), "-ml", "1", "-ojf", "-of", str(tmp / "tr"), "-np"],
                       capture_output=True)
        words = []
        try:
            for s in json.load(open(tmp / "tr.json"))["transcription"]:
                for tok in s.get("tokens", []):
                    tx = tok["text"]
                    if tx.startswith("[_"): continue
                    a0, b0 = tok["offsets"]["from"] / 1000, tok["offsets"]["to"] / 1000
                    if words and not tx.startswith(" "): words[-1] = (words[-1][0], b0, words[-1][2] + tx)
                    else: words.append((a0, b0, tx.strip()))
        except Exception:
            pass
        spectrogram(mid, words, out / "spec_mid.png"); spectrogram(side, words, out / "spec_side.png")
        dur = len(mid) / SR
        rms = lambda v: 20 * np.log10(np.sqrt(np.mean(v ** 2)) + 1e-12)
        w100 = int(0.1 * SR); midw = np.array([rms(mid[i:i + w100]) for i in range(0, len(mid) - w100, w100)])
        sidew = np.array([rms(side[i:i + w100]) for i in range(0, len(side) - w100, w100)])
        speech = float(np.percentile(midw, 75)); floor = float(np.percentile(midw, 10))
        onsets = [round(i / 10, 1) for i in range(1, len(sidew)) if sidew[i] > np.median(sidew) + 6 and sidew[i] - sidew[i - 1] > 3]
        # key stills at cuts and side-channel onsets
        (out / "key").mkdir(exist_ok=True)
        for t in sorted(set(cuts[:12] + onsets[:12])):
            run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.start + t + 0.15), "-i", a.video, "-frames:v", "1", "-q:v", "3", str(out / "key" / f"{t:05.1f}.jpg")])
    gaps = [b[0] - a_[1] for a_, b in zip(words, words[1:])]
    L.append(f"# Reference breakdown: {Path(a.video).name}  ({a.start:g}s to {a.end or 'end'}; {dur:.1f} s analysed)\n")
    L.append("## Pace")
    if words:
        L.append(f"- {len(words)} words, {len(words) / dur * 60:.0f} words/min; pauses > 0.3 s: {sum(g > 0.3 for g in gaps)}; longest {max(gaps or [0]):.2f} s")
        L.append("- transcript: " + " ".join(w for _, _, w in words))
    L.append("\n## Sound")
    L.append(f"- loudness {ln['input_i']} LUFS, LRA {ln['input_lra']} LU, true peak {ln['input_tp']} dBTP")
    L.append(f"- mid (voice) typical {speech:.1f} dB, floor between words {floor:.1f} dB -> "
             + ("a continuous bed under the voice" if speech - floor < 22 else "near-silent between words (no bed, or a very quiet one)"))
    L.append(f"- side (music + stereo SFX) median {np.median(sidew):.1f} dB, {speech - np.median(sidew):.1f} dB under the voice")
    L.append(f"- side-channel onsets (likely SFX hits / whooshes): {onsets}")
    L.append("\n## Picture")
    L.append(f"- hard cuts (frame difference): {len(cuts)} -> {cuts}")
    L.append(f"- mean brightness per second (0-255): {' '.join(str(int(np.mean(luma[i:i + 10]))) for i in range(0, len(luma), 10))}")
    fwl = [("  -- " if v is None else f"{v * 100:4.1f}") for v in fw]
    L.append("- face width % of frame per 0.1 s (push-ins = slow rises, settles = drops after a cut, smash = fast rise):")
    for i in range(0, len(fwl), 20): L.append(f"  {i / 10:5.1f}: " + " ".join(fwl[i:i + 20]))
    L.append("\n## Look at\n- sheets/*.jpg (every one), key/*.jpg, spec_side.png (music chords = horizontal lines; whooshes = broadband swells; sub hits = bright low blobs; ticks = regular vertical lines)")
    (out / "summary.md").write_text("\n".join(L) + "\n")
    print(f"wrote {out / 'summary.md'}")


if __name__ == "__main__":
    main()
