#!/usr/bin/env python3
"""Person masks for styles that relight the background (cinematic). macOS Vision, accurate quality.

  segment.py PROJECT                 every part the plan uses (hooks + body); skips parts already done
  segment.py PROJECT --part body     one part; --force to redo

Writes work/parts/<part>/mask.mp4: 540x960 grey, white = person, frame-aligned with base.mp4. Masks are
smoothed over time (a 1-2-1 blur across neighbouring frames) so hair edges do not shimmer. compose.py runs this
automatically when the style needs it and a mask is missing or older than base.mp4.
About 30-60 ms a frame on Apple silicon: a 60 s reel takes 1-2 minutes, once.
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from common import load, run, die, FPS

MW, MH = 540, 960
SWIFT = r'''
import Vision
import AppKit
import CoreImage
let args = Array(CommandLine.arguments.dropFirst())
let outDir = args[0]
let ctx = CIContext()
let req = VNGeneratePersonSegmentationRequest()
req.qualityLevel = .accurate
req.outputPixelFormat = kCVPixelFormatType_OneComponent8
for path in args.dropFirst() {
  autoreleasepool {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("NONE \(path)"); return }
    do { try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req]) } catch { print("ERR \(path)"); return }
    guard let pb = req.results?.first?.pixelBuffer else { print("NONE \(path)"); return }
    let url = URL(fileURLWithPath: outDir).appendingPathComponent((path as NSString).lastPathComponent.replacingOccurrences(of: ".jpg", with: ".png"))
    try? ctx.writePNGRepresentation(of: CIImage(cvPixelBuffer: pb), to: url, format: .L8, colorSpace: CGColorSpaceCreateDeviceGray())
    print("OK")
  }
}
'''


def segment_part(d, force=False):
    base, out = d / "base.mp4", d / "mask.mp4"
    if not base.exists(): die(f"{base} missing (run cut.py)")
    if out.exists() and out.stat().st_mtime >= base.stat().st_mtime and not force:
        print(f"{d.name}: mask up to date"); return out
    n = load(d / "segs.json")["frames"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); (tmp / "in").mkdir(); (tmp / "m").mkdir()
        run(["ffmpeg", "-v", "error", "-y", "-i", str(base), "-vf", f"scale={MW}:{MH}", "-q:v", "3", str(tmp / "in" / "%05d.jpg")])
        files = sorted((tmp / "in").glob("*.jpg"))
        (tmp / "seg.swift").write_text(SWIFT)
        print(f"{d.name}: segmenting {len(files)} frames ...", flush=True)
        for i in range(0, len(files), 400):        # chunks keep argv short and memory flat
            r = subprocess.run(["swift", str(tmp / "seg.swift"), str(tmp / "m"), *map(str, files[i:i + 400])],
                               capture_output=True, text=True)
            if r.returncode != 0: die(f"swift segmentation failed: {r.stderr[-800:]}")
        def read(i):
            f = tmp / "m" / f"{i + 1:05d}.png"
            return np.asarray(Image.open(f).convert("L").resize((MW, MH), Image.BILINEAR), np.float32) if f.exists() else None
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{MW}x{MH}",
                              "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(out)],
                             stdin=subprocess.PIPE)
        prev = cur = None; missing = 0
        for i in range(n + 1):                    # 1-2-1 temporal blur, streaming: only three masks in memory
            nxt = read(i) if i < n else None
            if i < n and nxt is None: missing += 1; nxt = cur if cur is not None else np.zeros((MH, MW), np.float32)
            if cur is not None:
                a = prev if prev is not None else cur; b = nxt if nxt is not None else cur
                p.stdin.write(np.clip(0.25 * a + 0.5 * cur + 0.25 * b, 0, 255).astype(np.uint8).tobytes())
            prev, cur = cur, nxt
        p.stdin.close(); p.wait()
        if missing: print(f"{d.name}: {missing} frames had no mask (reused the previous one)")
    print(f"{d.name}: wrote {out}"); return out


def parts_in_plan(proj):
    plan = load(proj / "plan.json")
    return [f"hook-{k}" for k in plan.get("hooks", {})] + ["body"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--part"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); proj = Path(a.project).expanduser().resolve()
    for name in ([a.part] if a.part else parts_in_plan(proj)):
        segment_part(proj / "work" / "parts" / name, a.force)


if __name__ == "__main__":
    main()
