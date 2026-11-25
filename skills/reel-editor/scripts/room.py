#!/usr/bin/env python3
"""Replace the room behind the speaker with another one, no green screen. OPT-IN ONLY: runs when plan.json has "room".

  room.py PROJECT                 every part the plan uses; skips parts already done with the same settings
  room.py PROJECT --part body     one part; --force to redo
  room.py PROJECT --still body:120  one composited frame as a JPG (to check a plate before a full run)

plan.json:  "room": true          the default room (~/.config/reel-editor/rooms/default.jpg)
            "room": "loft"        a saved room by name (~/.config/reel-editor/rooms/loft.jpg)
            "room": {"plate": NAME | path, "blur": 6, "wrap": 0.5, "match": 0.5, "track": true}   (blur 0 = sharp room)

Writes work/parts/<part>/room.mp4 (frame-aligned with base.mp4); compose.py reads it instead of base.mp4 when the
plan has a room. Per frame:
  matte    Vision person segmentation (keeps real hair texture) + Vision subject lift limited to near the person
           (catches motion-blurred hands the person model drops), 1-2-1 smoothed over time, refined against the
           frame itself with a guided filter so curls and fingertips stay sharp
  edges    the old room's colour is pulled out of the edge pixels (decontamination)
  plate    exposure matched half-way to the old room, so the speaker doesn't look pasted on; defocused by default ("blur",
           6 px, the polished portrait look; "blur": 0 keeps the room sharp like a phone would)
  wrap     the plate's light bleeds onto the silhouette ("wrap")
  track    handheld sway is copied onto the plate: background motion measured by phase correlation with the speaker
           masked out, smoothed, reset at every cut (each segment can be a different take)
  grain    one grain over everything
What sells it is light, not the matte: the plate must have the footage's light (time of day, colour, direction).
See references/rooms.md for making plates.
"""
import argparse, hashlib, json, os, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from common import load, save, run, die, W, H, FPS

SKILL = Path(__file__).resolve().parent.parent
ROOMS = Path.home() / ".config" / "reel-editor" / "rooms"
BLUR_DEFAULT = 6.0   # px of defocus on the room (the portrait look); "blur": 0 for sharp
CACHE = Path.home() / ".cache" / "reel-editor"
MATTE_SWIFT = r'''
import Vision
import AppKit
import CoreImage
// matte MODE OUTDIR frame...   MODE = fg (subject lift) | person (person segmentation, accurate)
let args = Array(CommandLine.arguments.dropFirst())
let mode = args[0]; let outDir = args[1]
let ctx = CIContext()
for path in args.dropFirst(2) {
  autoreleasepool {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("NONE \(path)"); return }
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    var out: CIImage? = nil
    do {
      if mode == "fg" {
        let req = VNGenerateForegroundInstanceMaskRequest()
        try handler.perform([req])
        if let obs = req.results?.first {
          out = CIImage(cvPixelBuffer: try obs.generateScaledMaskForImage(forInstances: obs.allInstances, from: handler))
        }
      } else {
        let req = VNGeneratePersonSegmentationRequest(); req.qualityLevel = .accurate
        req.outputPixelFormat = kCVPixelFormatType_OneComponent8
        try handler.perform([req])
        if let pb = req.results?.first?.pixelBuffer { out = CIImage(cvPixelBuffer: pb) }
      }
    } catch { print("ERR \(path)"); return }
    guard let o = out else { print("NONE \(path)"); return }
    let url = URL(fileURLWithPath: outDir).appendingPathComponent(((path as NSString).lastPathComponent as NSString).deletingPathExtension + ".png")
    try? ctx.writePNGRepresentation(of: o, to: url, format: .L8, colorSpace: CGColorSpaceCreateDeviceGray())
    print("OK")
  }
}
'''


def matte_bin():
    """The compiled matte tool (cached; recompiled when the source changes)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(MATTE_SWIFT.encode()).hexdigest()[:10]
    b = CACHE / f"matte-{h}"
    if not b.exists():
        src = CACHE / f"matte-{h}.swift"; src.write_text(MATTE_SWIFT)
        r = subprocess.run(["swiftc", "-O", str(src), "-o", str(b)], capture_output=True, text=True)
        if r.returncode != 0: die(f"could not compile the matte tool: {r.stderr[-600:]}")
    return b


# ------------------------------------------------------------------ image helpers (float32, H x W [x 3])
def box(a, r):
    p = np.pad(a, ((r + 1, r), (r + 1, r)), mode="edge")
    c = p.cumsum(0).cumsum(1)
    return (c[2 * r + 1:, 2 * r + 1:] - c[:-2 * r - 1, 2 * r + 1:] - c[2 * r + 1:, :-2 * r - 1] + c[:-2 * r - 1, :-2 * r - 1]) / (2 * r + 1) ** 2


def rs(a, size):
    return np.asarray(Image.fromarray(a.astype(np.float32)).resize(size, Image.BILINEAR), np.float32)


def blur(a, sigma):
    """~Gaussian blur (three box passes); big sigmas run at quarter size."""
    a3 = a if a.ndim == 3 else a[..., None]; out = []
    k = 4 if sigma > 12 else 1
    for c in range(a3.shape[2]):
        ch = a3[..., c].astype(np.float32)
        if k > 1: ch = rs(ch, (W // k, H // k))
        r = max(1, int(round(sigma / k)))
        for _ in range(3): ch = box(ch, r)
        if k > 1: ch = rs(ch, (W, H))
        out.append(ch)
    o = np.stack(out, -1)
    return o if a.ndim == 3 else o[..., 0]


def guided(I, p, r=8, eps=8e-4, s=2):
    Is, ps = rs(I, (W // s, H // s)), rs(p, (W // s, H // s))
    mI, mp = box(Is, r), box(ps, r)
    a = (box(Is * ps, r) - mI * mp) / (box(Is * Is, r) - mI * mI + eps)
    b = mp - a * mI
    return np.clip(rs(box(a, r), (W, H)) * I + rs(box(b, r), (W, H)), 0, 1)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ settings
def settings(plan, proj):
    rm = plan.get("room")
    if not rm: return None
    if rm is True: rm = {}
    if isinstance(rm, str): rm = {"plate": rm}
    plate = rm.get("plate") or "default"
    if plate and "/" not in plate and not plate.endswith((".jpg", ".png")):     # a saved room by name: "loft"
        named = next((p for d in (proj, ROOMS) for p in (d / f"{plate}.jpg", d / f"{plate}.png") if p.exists()), None)
        if not named: die(f'no saved room "{plate}" in {ROOMS} (have: {", ".join(sorted(p.stem for p in ROOMS.glob("*.*"))) or "none"}); make one with references/rooms.md or give "plate": PATH')
        plate = str(named)
    p = Path(plate).expanduser()
    if not p.is_absolute():
        p = proj / p
    if not p.exists(): die(f"room plate not found: {p}")
    return {"plate": str(p), "blur": float(rm.get("blur", BLUR_DEFAULT)), "wrap": float(rm.get("wrap", 0.5)),
            "match": float(rm.get("match", 0.5)), "track": bool(rm.get("track", True)), "margin": float(rm.get("margin", 1.12))}


def key_of(s):
    st = os.stat(s["plate"])
    return hashlib.sha1(json.dumps({**s, "plate_mtime": st.st_mtime, "plate_size": st.st_size, "v": 1}, sort_keys=True).encode()).hexdigest()


def prep_plate(s):
    """Plate covering the frame at `margin` x size (room for tracking), defocused if asked."""
    im = Image.open(s["plate"]).convert("RGB")
    PW, PH = int(W * s["margin"]), int(H * s["margin"])
    sc = max(PW / im.width, PH / im.height)
    im = im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS)
    x0, y0 = (im.width - PW) // 2, (im.height - PH) // 2
    im = im.crop((x0, y0, x0 + PW, y0 + PH))
    if s["blur"] > 0: im = im.filter(ImageFilter.GaussianBlur(s["blur"]))
    return np.asarray(im, np.float32) / 255


# ------------------------------------------------------------------ camera tracking
def phase_shift(a, b, win):
    A = np.fft.fft2(a * win); B = np.fft.fft2(b * win)
    R = A * np.conj(B); R /= np.abs(R) + 1e-9
    r = np.abs(np.fft.ifft2(R)); y, x = np.unravel_index(r.argmax(), r.shape)
    if y > a.shape[0] // 2: y -= a.shape[0]
    if x > a.shape[1] // 2: x -= a.shape[1]
    return x, y, float(r.max())


def track(frames, masks, segs_frames):
    """Per-frame background offset (dx, dy) in output pixels, relative to each segment's first frame."""
    sw, sh = 270, 480
    win = np.hanning(sh)[:, None] * np.hanning(sw)[None, :]
    g = []
    for f, m in zip(frames, masks):
        im = np.asarray(Image.open(f).convert("L").resize((sw, sh), Image.BILINEAR), np.float32)
        mk = np.asarray(Image.open(m).convert("L").resize((sw, sh), Image.BILINEAR), np.float32) / 255
        mk = np.asarray(Image.fromarray((mk * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)), np.float32) / 255
        bgv = im[mk < 0.5].mean() if (mk < 0.5).any() else im.mean()
        g.append(im * (1 - mk) + bgv * mk - bgv)           # the speaker filled with the room's mean: only the room moves it
    n = len(g); off = np.zeros((n, 2)); starts = set(segs_frames)
    for i in range(1, n):
        if i in starts: continue                             # a cut: new take, start again from 0
        dx, dy, conf = phase_shift(g[i], g[i - 1], win)
        step = np.array([dx, dy], float) if conf > 0.04 and abs(dx) < 20 and abs(dy) < 20 else np.zeros(2)
        off[i] = off[i - 1] + step
    # smooth inside each segment (never across a cut)
    bounds = sorted(starts | {0, n})
    for a, b in zip(bounds, bounds[1:]):
        if b - a < 3: continue
        for c in range(2):
            v = off[a:b, c]; k = np.exp(-0.5 * (np.arange(-6, 7) / 2.5) ** 2); k /= k.sum()
            off[a:b, c] = np.convolve(np.pad(v, 6, mode="edge"), k, mode="valid")
    return off * (W / sw)


# ------------------------------------------------------------------ one frame
_PLATE = None


def _init(s):
    global _PLATE, _WRAP, _S
    _S = s; _PLATE = prep_plate(s)
    _WRAP = None


def composite(job):
    """job = (index, frame path, [mask paths prev/cur/next for person and fg], (dx, dy), gain or None) -> RGB bytes."""
    global _WRAP
    i, fpath, mp, mf, (dx, dy), gain = job
    s = _S
    I = np.asarray(Image.open(fpath).convert("RGB"), np.float32) / 255
    if I.shape[:2] != (H, W): I = np.asarray(Image.fromarray((I * 255).astype(np.uint8)).resize((W, H)), np.float32) / 255
    gray = I @ np.array([0.299, 0.587, 0.114], np.float32)
    def raw(pp, ff):
        person = np.asarray(Image.open(pp).convert("L").resize((W, H), Image.BILINEAR), np.float32) / 255
        fg = np.asarray(Image.open(ff).convert("L").resize((W, H), Image.BILINEAR), np.float32) / 255
        near = Image.fromarray((person * 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.MaxFilter(11))
        return np.maximum(person, fg * np.asarray(near.resize((W, H), Image.BILINEAR), np.float32) / 255)
    m = 0.6 * raw(mp[1], mf[1]) + 0.2 * raw(mp[0], mf[0]) + 0.2 * raw(mp[2], mf[2])
    al = smoothstep(0.08, 0.92, guided(gray, m))
    # the guided filter may only reshape a thin band along the matte's edge: unconstrained, it grew the person into
    # dark things beside a dark shirt (a drawn figure on a tapestry showed through by the shoulder)
    hard = Image.fromarray(((m > 0.5) * 255).astype(np.uint8)).resize((W // 2, H // 2), Image.BILINEAR)
    # lopsided band at full size: it may GROW only 4 px past Vision's edge (no smearing into dark things in the room)
    # but may TRIM up to 8 px inside it (Vision's edge sometimes sits a few px out on the room)
    outer = np.asarray(hard.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.0)).resize((W, H), Image.BILINEAR), np.float32) / 255
    inner = np.asarray(hard.filter(ImageFilter.MinFilter(9)).filter(ImageFilter.GaussianBlur(1.0)).resize((W, H), Image.BILINEAR), np.float32) / 255
    al = np.maximum(np.minimum(al, outer), inner)
    bgm = (al < 0.05).astype(np.float32)
    old = blur(I * bgm[..., None], 30) / np.maximum(blur(bgm, 30), 1e-3)[..., None]
    edge = (al > 0.02) & (al < 0.98)
    F = I.copy()
    F[edge] = np.clip((I[edge] - (1 - al[edge, None]) * old[edge]) / np.maximum(al[edge, None], 0.15), 0, 1)
    PH, PW = _PLATE.shape[:2]
    x0 = int(round(np.clip((PW - W) / 2 - dx, 0, PW - W))); y0 = int(round(np.clip((PH - H) / 2 - dy, 0, PH - H)))
    B = _PLATE[y0:y0 + H, x0:x0 + W]
    if gain is None:
        ob = I[bgm > 0].mean(0) if bgm.any() else I.mean((0, 1)); pb = B[bgm > 0].mean(0) if bgm.any() else B.mean((0, 1))
        gain = np.clip((ob / np.maximum(pb, 1e-3)) ** s["match"], 0.6, 1.6)
    B = np.clip(B * gain, 0, 1)
    A3 = al[..., None]
    C = F * A3 + B * (1 - A3)
    C = C + blur(B, 22) * (blur(1 - al, 10) * al)[..., None] * s["wrap"]
    C = np.clip(C + np.random.default_rng(i).normal(0, 0.008, (H, W, 1)).astype(np.float32), 0, 1)
    return (C * 255 + 0.5).astype(np.uint8).tobytes(), gain


# ------------------------------------------------------------------ a part
def room_part(d, s, force=False, still=None, workers=4):
    d = Path(d); base, out, meta = d / "base.mp4", d / "room.mp4", d / "room.json"
    if not base.exists(): die(f"{base} missing (run cut.py)")
    k = key_of(s)
    if still is None and out.exists() and meta.exists() and not force:
        m = load(meta)
        if m.get("key") == k and out.stat().st_mtime >= base.stat().st_mtime:
            print(f"{d.name}: room up to date"); return out
    segs = load(d / "segs.json")
    seg_starts = [int(round(x["t0"] * FPS)) for x in segs["segs"]]
    binp = matte_bin()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for sub in ("in", "mp", "mf"): (tmp / sub).mkdir()
        sel = [] if still is None else ["-vf", f"select=eq(n\\,{still})", "-vsync", "0"]
        run(["ffmpeg", "-v", "error", "-y", "-i", str(base), *sel, "-q:v", "2", str(tmp / "in" / "%05d.jpg")])
        files = sorted((tmp / "in").glob("*.jpg"))
        print(f"{d.name}: matting {len(files)} frames ...", flush=True)
        for i in range(0, len(files), 300):
            for mode, sub in (("person", "mp"), ("fg", "mf")):
                r = subprocess.run([str(binp), mode, str(tmp / sub), *map(str, files[i:i + 300])], capture_output=True, text=True)
                if r.returncode != 0: die(f"matte failed: {r.stderr[-600:]}")
        def mpath(sub, j):
            j = min(max(j, 0), len(files) - 1); p = tmp / sub / (files[j].stem + ".png")
            return p if p.exists() else tmp / sub / (files[min(len(files) - 1, j + 1)].stem + ".png")
        offs = track(files, [mpath("mp", j) for j in range(len(files))], seg_starts) if (s["track"] and still is None) \
            else np.zeros((len(files), 2))
        if still is None:
            mx = float(np.abs(offs).max()) if len(offs) else 0.0
            print(f"{d.name}: camera sway up to {mx:.0f} px{' (treated as still)' if mx < 4 else ''}", flush=True)
            if mx < 4: offs[:] = 0
        _init(s)
        first, gain = composite((0, files[0], [mpath("mp", -1), mpath("mp", 0), mpath("mp", 1)],
                                 [mpath("mf", -1), mpath("mf", 0), mpath("mf", 1)], tuple(offs[0]), None))
        if still is not None:
            jp = d / f"room-still-{still}.jpg"
            Image.frombytes("RGB", (W, H), first).save(jp, quality=92); print(f"wrote {jp}"); return jp
        jobs = [(j, files[j], [mpath("mp", j - 1), mpath("mp", j), mpath("mp", j + 1)],
                 [mpath("mf", j - 1), mpath("mf", j), mpath("mf", j + 1)], tuple(offs[j]), gain) for j in range(1, len(files))]
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "14", "-preset", "medium",
                                "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
        enc.stdin.write(first)
        with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(s,)) as ex:
            for n, (buf, _) in enumerate(ex.map(composite, jobs, chunksize=4), 2):
                enc.stdin.write(buf)
                if n % 300 == 0: print(f"{d.name}: frame {n}/{len(files)}", flush=True)
        enc.stdin.close(); enc.wait()
    save(meta, {"key": k, "plate": s["plate"], "frames": len(files)})
    print(f"{d.name}: wrote {out}"); return out


def ensure(proj):
    """compose.py calls this: build room.mp4 for every part when the plan has a room. Returns True when it does."""
    proj = Path(proj); plan = load(proj / "plan.json"); s = settings(plan, proj)
    if not s: return False
    from segment import parts_in_plan
    for name in parts_in_plan(proj): room_part(proj / "work" / "parts" / name, s)
    return True


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--part"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--still"); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(); proj = Path(a.project).expanduser().resolve()
    s = settings(load(proj / "plan.json"), proj)
    if not s: die('no "room" in plan.json: background replacement only runs when the plan asks for it')
    if a.still:
        part, fr = a.still.split(":"); room_part(proj / "work" / "parts" / part, s, still=int(fr)); return
    from segment import parts_in_plan
    for name in ([a.part] if a.part else parts_in_plan(proj)):
        room_part(proj / "work" / "parts" / name, s, force=a.force, workers=a.workers)


if __name__ == "__main__":
    main()
