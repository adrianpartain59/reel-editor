#!/usr/bin/env python3
"""Render mockup screens to transparent phone PNGs (1260x2640, iPhone frame, 3x).

  mockups.py HTML OUTDIR VARIANT [VARIANT ...]      e.g.  mockups.py mock/screens.html mock paywall-features paywall-features&hl=3
  mockups.py --init PROJECT_DIR                      copy the screen library into PROJECT/mock/screens.html

Output names: the variant with & and = turned into _ (paywall-features&hl=3 -> paywall-features_hl_3.png).
Reference the PNG (without .png) as "img" in plan.json. Always render "frame" too if you overlay screen recordings.
"""
import shutil, subprocess, sys, tempfile, time
from pathlib import Path
from PIL import Image
from common import CHROME, ASSETS, die


def name_for(variant): return variant.replace("&", "_").replace("=", "_")


def render(html, outdir, variant):
    out = Path(outdir) / f"{name_for(variant)}.png"
    if out.exists(): out.unlink()
    err = ""
    with tempfile.TemporaryDirectory() as prof:
        # Chrome sometimes exits non-zero on teardown after writing the file, or hangs there and never exits
        # (renders can hang past 90 s while a cut runs), so judge by the file, not the exit
        try:
            r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                                f"--user-data-dir={prof}", "--default-background-color=00000000",
                                "--force-device-scale-factor=3", "--window-size=420,880", f"--screenshot={out}",
                                f"file://{Path(html).resolve()}#{variant}"], capture_output=True, text=True, timeout=30)
            err = r.stderr
        except subprocess.TimeoutExpired as e:
            err = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    if not out.exists(): die(f"chrome did not write {out}: {err[-800:]}")
    im = Image.open(out)
    if im.size != (1260, 2640): die(f"{out}: unexpected size {im.size}")
    return out


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--init":
        dst = Path(sys.argv[2]).expanduser() / "mock"; dst.mkdir(parents=True, exist_ok=True)
        if (dst / "screens.html").exists(): print(f"{dst/'screens.html'} exists, left as is")
        else: shutil.copy(ASSETS / "mockups" / "screens.html", dst / "screens.html"); print(f"copied to {dst/'screens.html'}")
        return
    if len(sys.argv) < 4: die(__doc__)
    html, outdir = sys.argv[1], Path(sys.argv[2]); outdir.mkdir(parents=True, exist_ok=True)
    for v in sys.argv[3:]:
        print(render(html, outdir, v))
    # contact sheet for a quick look
    pngs = [Image.open(outdir / f"{name_for(v)}.png") for v in sys.argv[3:]]
    sheet = Image.new("RGBA", (len(pngs) * 330, 690), (40, 40, 40, 255))
    for i, p in enumerate(pngs): sheet.alpha_composite(p.resize((315, 660)), (i * 330 + 8, 15))
    sheet.convert("RGB").save(outdir / "_sheet.jpg", quality=85)
    print(f"sheet: {outdir/'_sheet.jpg'}")


if __name__ == "__main__":
    main()
