#!/usr/bin/env python3
"""Head tracking: where the face is in every moment of a part, so the camera can follow it.

  track.py PART_DIR            write PART_DIR/track.json (no-op when it is newer than base.mp4)

Samples base.mp4 at RATE fps, finds the face in each sample with macOS Vision (the same detector ingest uses), fills
gaps, and smooths the path inside each cut (never across one: a jump cut is a new camera position) so the camera
glides after the head instead of jittering with it. compose.py reads it through Reel.anchor().

track.json: {"rate": 10, "smooth_s": SIGMA, "segs": [[t0, t1, [[t, cx, cy, fh], ...]], ...]} in output pixels
(1080x1920) on the part's own timeline.
"""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from common import W, H, run, load, save

RATE = 10            # samples a second
SIGMA = 0.45         # seconds of Gaussian smoothing: follows a lean, ignores a nod
SW, SH = 360, 640    # sample size for the detector

SWIFT = r'''
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
  guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("NONE"); continue }
  let req = VNDetectFaceRectanglesRequest()
  try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
  let faces = (req.results ?? []).sorted { $0.boundingBox.width > $1.boundingBox.width }
  if let f = faces.first { let b = f.boundingBox; print("\(b.midX) \(1 - b.midY) \(b.height)") } else { print("NONE") }
}
'''


def detect(base, dur):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        run(["ffmpeg", "-v", "error", "-i", str(base), "-vf", f"fps={RATE},scale={SW}:{SH}", str(tmp / "f%05d.png")])
        paths = sorted(str(p) for p in tmp.glob("f*.png"))
        (tmp / "t.swift").write_text(SWIFT)
        out = subprocess.run(["swift", str(tmp / "t.swift"), *paths], capture_output=True, text=True, timeout=900).stdout.split("\n")
    vals = []
    for i, line in enumerate(l for l in out if l):
        t = (i + 0.5) / RATE
        if line == "NONE": vals.append((t, None)); continue
        cx, cy, fh = map(float, line.split()); vals.append((t, (cx * W, cy * H, fh * H)))
    return vals


def smooth(samples):
    """Fill gaps by interpolation, then a Gaussian of SIGMA seconds (edges reflect, so a cut's ends don't drift)."""
    ts = np.array([t for t, _ in samples]); ok = np.array([v is not None for _, v in samples])
    if ok.sum() == 0: return []
    cols = []
    for k in range(3):
        y = np.array([v[k] if v else np.nan for _, v in samples])
        y = np.interp(ts, ts[ok], y[ok])
        r = max(1, int(SIGMA * RATE * 3)); g = np.exp(-0.5 * (np.arange(-r, r + 1) / (SIGMA * RATE)) ** 2); g /= g.sum()
        cols.append(np.convolve(np.pad(y, r, mode="reflect"), g, mode="valid"))
    return [[round(float(t), 3), round(float(a), 1), round(float(b), 1), round(float(c), 1)] for t, a, b, c in zip(ts, *cols)]


def track_part(d):
    d = Path(d); base, out = d / "base.mp4", d / "track.json"
    if out.exists() and out.stat().st_mtime > base.stat().st_mtime: return load(out)
    segs = load(d / "segs.json")
    vals = detect(base, segs["duration"])
    js = {"rate": RATE, "smooth_s": SIGMA, "found": round(sum(v is not None for _, v in vals) / max(1, len(vals)), 3), "segs": []}
    for s in segs["segs"]:
        inside = [(t, v) for t, v in vals if s["t0"] <= t < s["t1"]]
        if not inside: inside = [((s["t0"] + s["t1"]) / 2, (s["ax"], s["ay"] , s["fh"]) if s.get("fh") else None)]
        # no face seen in the whole segment: hold the position ingest found for its clip, so every reader has a path to follow
        js["segs"].append([s["t0"], s["t1"], smooth(inside) or [[round((s["t0"] + s["t1"]) / 2, 3), s["ax"], s["ay"], s["fh"] or 300.0]]])
    save(out, js)
    print(f"{d.name}: head track, face found in {js['found'] * 100:.0f}% of {len(vals)} samples")
    return js


if __name__ == "__main__":
    for p in sys.argv[1:]: track_part(p)
