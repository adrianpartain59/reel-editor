#!/usr/bin/env python3
"""Set up the graphics half of a reel: copy the starter settings and scenes into the project, pointing at this copy of the skill.

  canvas_init.py PROJECT [split]        Split Screen (the default format) in the Vector art style: split_reel.json + canvas/scenes.js
  canvas_init.py PROJECT split sketch   Split Screen with the hand-drawn canvas (Sketch) instead
  canvas_init.py PROJECT roadmap        Drawn Roadmap: canvas_reel.json + canvas/scenes.js
  canvas_init.py PROJECT --relink       point an existing canvas/scenes.js at this copy of the skill (after a plugin update)

Existing files are kept. Runs `npm install` for the drawing library and fonts the first time.
"""
import re, shutil, subprocess, sys
from pathlib import Path
from common import ASSETS, die

GS = ASSETS / "graphic-styles"
REQ = re.compile(r"""require\((['"])[^'"]*?(vector_engine|panel_engine|engine)\1\)""")


def link(text): return REQ.sub(lambda m: f"require({str(GS / 'canvas' / m.group(2))!r})", text)


def ensure_node():
    if not shutil.which("node"): die("node not on PATH (brew install node)")
    if not (GS / "node_modules").exists():
        print("installing the drawing library and fonts (once)..."); r = subprocess.run(["npm", "install", "--silent", "--no-fund", "--no-audit"], cwd=GS)
        if r.returncode: die(f"npm install failed in {GS}")


def main():
    kind = sys.argv[2] if len(sys.argv) > 2 else "split"; look = sys.argv[3] if len(sys.argv) > 3 else "vector"
    if len(sys.argv) not in (2, 3, 4) or sys.argv[1].startswith("-") or kind not in ("roadmap", "split", "--relink") or look not in ("vector", "sketch") or (len(sys.argv) == 4 and kind != "split"): die(__doc__)
    proj = Path(sys.argv[1]).expanduser().resolve(); sc = proj / "canvas/scenes.js"; ensure_node()
    if kind == "--relink":
        if not sc.exists(): die(f"{sc} missing")
        sc.write_text(link(sc.read_text())); print(f"{sc} now uses {GS / 'canvas'}"); return
    js, starter = {"roadmap": ("canvas_reel.json", "starter.scenes.js"), "split": ("split_reel.json", "vector.starter.scenes.js" if look == "vector" else "split.starter.scenes.js")}[kind]
    src = ASSETS / "examples" / ("canvas_reel.starter.json" if kind == "roadmap" else "split_reel.starter.json")
    (proj / "canvas").mkdir(parents=True, exist_ok=True)
    for dst, text in ((proj / js, src.read_text()), (sc, link((GS / "canvas" / starter).read_text()))):
        if dst.exists(): print(f"{dst} exists, left as is")
        else: dst.write_text(text); print(f"wrote {dst}")


if __name__ == "__main__":
    main()
