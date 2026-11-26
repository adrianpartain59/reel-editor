# Drawn Roadmap

Made when the user asks for drawn steps or a roadmap (the default format is the Split Screen, `split-screen.md`).

A talking-head list video ("I walked a million steps, here's the ten-step roadmap") made of an edited hook, a hand-drawn canvas that runs most
of the body, and the face cut back in at a few moments. It needs at least two points to draw (a numbered list, roadmap, framework or process is
ideal) and a number said in the hook; a take without both can't carry it, so say so and make a Split Screen. The art style is Sketch (`sketch.md`). `canvas-reel-schema.md` documents
`canvas_reel.json`.

It replaces compose.py, mix.py, build.py and qa.py for the whole reel: there is no plan.json. ingest, cut and track are shared. The scripts need
`PROJECT/canvas_reel.json`, `PROJECT/canvas/scenes.js` and, from cut.py, `work/parts/hook-<variant>/` and `work/parts/body/`.

**Look at the worked example first:** `assets/examples/canvas-roadmap/sheet.jpg` (its drawn scenes), drawn by `assets/graphic-styles/canvas/roadmap.scenes.js`
from the words in `body_words.json`, with the settings in `canvas_reel.json`.

## The shape to match

| Part | Length | What happens |
|---|---|---|
| Hook | 8.0 s | Full-frame face, captions only for the first 1.1 s. A dark card pops up: the number squiggles low, then takes off to its final value on the word that claims it, landing at 3.1 s with a green hit, then the line under it. The face moves left while the line climbs on the right. A second card: "10-STEP ROADMAP" and ten markers lighting in a row. Ends on the untouched full frame |
| Canvas | 83% of the body | One drawn world, one cell per step, a dotted road between them. 4 to 6 s a step. Pulls back to the whole map at the halfway turn and at the end |
| Face moments | 6 in 57 s, 0.9 to 2.1 s each | First-hand proof ("this kept me going"), blunt calls ("no zero days"), the turn ("now momentum"), the outro. Never one per step |
| Outro | last 2 s | The canvas shrinks to a card, the face, the typed comment ("doing step 2 tonight") |
| Sound | whole reel | Nothing but the count-up under the hook; the beat drops on the landing, stops when the barrier slams, returns on the turn |

Whole reel 64.7 s, 210 spoken words in the body.

**Shorter reels.** Keep the order, scale the counts. Under five steps: no halfway pull-back, and the final one only if there is at least a second of talking between the last
step and the outro (`views: {}` is fine). A body under 25 s gets one face moment plus the outro. A hook under 7 s: the number still lands around 3 s, at the end of the claim, and
the title card may hold to the last frame (`title.out` = the hook's length); the canvas then rises over it.

## Steps

1. **Find the kept takes.** Separate clips: ingest them as usual (SKILL.md step 1) and call the hook `main` in `selects.json`. Several hooks are several reels: give each its own name,
   set `hook.variant` and `slug` to match, and re-run `countup_hook.py` and `canvas_sound.py` for each. One long take with retakes: `python3 scripts/ingest.py PROJECT --hook RAW --body RAW --slug name` (the same file twice is
   fine: ids `h1` and `b1`), then `utterances.py PROJECT RAW`. The kept take of a line is the last complete one before the speaker moves to the
   next line. Write `selects.json` (`{"hooks": {"main": [["h1", in, out], ...]}, "body": [["b1", in, out], ...]}`), cutting tight to the words.
   Say which scripted lines were never said; don't invent around them.
2. **Cut.** `cut.py PROJECT` for the usual speech map and grade, or `cut.py PROJECT --as-is` when you set the boundaries by hand (they asked
   for "just cut, unedited", or the room noise changes mid-take and the speech map keeps dead air). Then `seg_words.py PROJECT`:
   word times per segment. Whisper starts the first word of a segment up to 0.2 s early, so check any cut or zoom that lands on one.
3. **Set up.** `canvas_init.py PROJECT roadmap` writes `canvas_reel.json` and `canvas/scenes.js` (and installs the drawing library the first time).
4. **Hook.** Fill `hook` (beats on the spoken words, the value, the label, the title). Leave `zoom`, `face` and `blur` out and list `punch`: they are
   made for you. `countup_hook.py PROJECT preview 0.1,1.0,1.5,2.2,2.8,3.12,3.3,4.0,5.3,6.0,7.0,7.9`, look, fix, `render`.
5. **Canvas.** Draw one scene per step by `sketch.md`. `cd PROJECT && node canvas/scenes.js sheet 1,2.5,... work/sheet.jpg` while you
   draw (two or three stills per step; each is stamped with its time), then `node canvas/scenes.js check canvas_reel.json` and a `still` of every finished scene. Fix every `stop N:` and `nothing new` line. Ink in the
   like/share column or at an edge is a judgement call: a line of art may brush it, words may not.
6. **Face moments.** Fill `faces` and `outro`, then `canvas_body.py PROJECT preview` at every in + 0.1, in + 0.5 and out + 0.1. `render`.
7. **Sound.** `canvas_sound.py PROJECT --keys mixkit-358 mixkit-403 mixkit-369` gives each beat's `shift`; put one in `beat` and run
   `canvas_sound.py PROJECT`. It writes the reel, the phone copy and a still every 1.5 s, and prints loudness, frame count and how
   far the beat's first hit is from the landing. "Effects within 6 dB of the voice" at a slam, a landing or a counting number is expected; anywhere else, move the cue off the word.
   Vary the beat from reel to reel. For a choice, render three with `--beat` and let the user pick by ear. The beats have to be downloaded first
   (`music-library.md`); without them the reel has no beat.
   (`Truncating packet of size ...` while the canvas renders is ffmpeg reading the pipe; the frame count line is the check.)
8. **Thumbnail.** `canvas_thumb.py PROJECT candidates`, pick a frame (eyes fully open, mouth mid-word, no blur), then `make --t 4.4 --from '0' --to '1M' --title
   'THE 10-STEP ROADMAP'`.
9. **Check, with your own eyes:** the still sheet, every face cut in and out, every flight. Re-transcribe the final file and compare it with the
   script; whisper can drop a line that is there, so re-run just that window before believing it. Say you can't hear the result.
10. **Deliver.** Phone copy, full file, thumbnail, `out/post.md` (`captions.md`) and, for a Short, `out/youtube-short.md` (title, description
    with the numbered steps, tags, and the AI question answered honestly). Upload the full file, not the phone copy. Never publish without a yes.

## Where the face comes back

Pick the moments from the transcript before drawing anything. A moment qualifies when the line is worth more from the speaker's mouth than from a drawing:
- **proof** they lived ("this kept me going", "I did"): enters `down`, accent green or yellow, `punch` on the number;
- **a blunt call** ("no zero days"): enters `cut`, tight (`z0` 1.45 to 1.6), red for a no;
- **a turn** ("now momentum"): `cut`, then the canvas rises back (`back: "up"`);
- **a second thought** under a drawing ("you're sore because it's working"): `through`;
- **the outro**: `shrink`, with the typed comment.

Aim for one every 8 to 12 s, 15 to 20% of the body, never two in a row and never as a step begins (the step's drawing needs its first word).
The canvas comes back `left` or `right` in the direction it left off; the flight to the next step hides under the face moment.

## Rules for this format

- Captions on the face only. The canvas writes its own words, so a caption over it says everything twice.
- Text on the canvas is written on, not typed: no key sounds there. Key sounds belong to the typed comment.
- The big number lands on its word, the count-up's pitch follows the line, and nothing but the count-up plays before the landing.
- The squiggle is for effect. Never present it as real data, and never put a fake dashboard around it.
- Numbers on screen are the ones said. No invented figures to fill a chart.
- Send the first complete set of mockups rough; polish only what the user picks.

## Where this differs from the edit playbook

The playbook's rules hold except these: the canvas takes the whole screen (rule 27 says graphics pop up); there are no b-roll phones, neon titles, transitions
or caption styles in the body; the count-up taps and the ding are outside the pack (`assets/sfx/countup`). Still in force: face first and full frame, the
snap-out, head tracking, no breaths, the safe area, the typed comment outro, -12 LUFS.
