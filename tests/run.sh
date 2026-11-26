#!/usr/bin/env bash
# End to end on takes with nobody in them: make takes, ingest, cut, mock up, render, mix, QA, then the graphics engines' starters.
#   tests/run.sh            everything (about 4 minutes)   tests/run.sh fast   no full render (about 1 minute)
# Uses $PYTHON (default python3). Leaves its files in tests/out/.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; S="$here/../skills/reel-editor"; PY="${PYTHON:-python3}"; out="$here/out"; mode="${1:-full}"
rm -rf "$out/reel" "$out/road"; mkdir -p "$out"
say_() { printf '\n== %s\n' "$*"; }

say_ "sound pack"; "$PY" "$S/scripts/sfx_lib.py" check
say_ "takes"; [ -f "$out/takes/TAKE_4.mov" ] || "$PY" "$here/make_takes.py" "$out/takes"
T="$out/takes"; P="$out/reel"
say_ "ingest"; "$PY" "$S/scripts/ingest.py" "$P" --hook "$T/HOOK_A.mov" --hook "$T/HOOK_B.mov" --body "$T/TAKE_1.mov" "$T/TAKE_2.mov" "$T/TAKE_3.mov" "$T/TAKE_4.mov" --slug onboarding > "$out/ingest.log"
tail -4 "$out/ingest.log"
"$PY" - "$P" <<'PYIN'
# drop the flub and the apology in TAKE_2: the retake is everything after the last long pause
import json, sys
from pathlib import Path
f = Path(sys.argv[1]) / "selects.json"; s = json.loads(f.read_text()); b2 = [c for c in s["body"] if c[0] == "b2"]
cut = max(((b[1] - a[2], b[1]) for a, b in zip(b2, b2[1:]) if b[1] > 4), default=(0, 0))[1]
assert cut, "TAKE_2's retake was not found"
s["body"] = [c for c in s["body"] if c[0] != "b2" or c[1] >= cut - 0.01]; f.write_text(json.dumps(s, indent=1)); print("kept", len(s["body"]), "body chunks")
PYIN
say_ "cut"; "$PY" "$S/scripts/cut.py" "$P"
grep -qi "sorry" "$P/work/timeline.txt" && { echo "FAIL the flub is still in the cut"; exit 1; } || echo "ok the flub is gone"
say_ "mockups"; "$PY" "$S/scripts/mockups.py" --init "$P"; "$PY" "$S/scripts/mockups.py" "$P/mock/screens.html" "$P/mock" "onboarding-question&step=1&dark=1" "onboarding-question&step=1&sel=1&dark=1" "onboarding-plan&full=1&dark=1" | tail -1
cp "$here/plan.json" "$P/plan.json"
say_ "preview"; "$PY" "$S/scripts/compose.py" "$P" --variant h1 --preview 0.05,0.4,1.5,3.6,6.2,7.4,9.0,11.4,13.2,14.9 | tail -2
if [ "$mode" != fast ]; then say_ "render, mix, QA"; "$PY" "$S/scripts/build.py" "$P" --variant h1; fi
say_ "drawn canvas"; R="$out/road"; mkdir -p "$R/work"; "$PY" "$S/scripts/canvas_init.py" "$R" roadmap; (cd "$R" && node canvas/scenes.js info > work/info.json && node canvas/scenes.js sheet 1.5,3.2,5.6,7.2,9.6,10.4,11.8,12.8 work/sheet.jpg && ls -la work/sheet.jpg)
say_ "split screen, Vector (the default)"; mkdir -p "$R/split/work"; "$PY" "$S/scripts/canvas_init.py" "$R/split" split
(cd "$R/split" && export PANEL_H=1240 && node canvas/scenes.js sheet 1,2.5,9.5,10.6,14.5,16.8 work/sheet.jpg && node canvas/scenes.js check | tee work/check.txt && grep -q '^OK' work/check.txt)
say_ "split screen, Sketch"; mkdir -p "$R/split-sketch/work"; "$PY" "$S/scripts/canvas_init.py" "$R/split-sketch" split sketch
(cd "$R/split-sketch" && node canvas/scenes.js sheet 5,6.2,7.2,9.4,10.8,12.4 work/sheet.jpg && node canvas/scenes.js check | tee work/check.txt && grep -q '^OK' work/check.txt)
say_ "art styles"; (cd "$S/assets/graphic-styles" && node render.js list)
printf '\nall done: %s\n' "$out"
