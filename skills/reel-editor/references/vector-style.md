# Vector (the Split Screen's default art style)

Flat vector graphics instead of drawings, so real photos and videos can be part of the picture: dark cards, red tags, glowing lines, phones with a
made-up app, stock footage in rounded frames. It is the top half of a Split Screen unless the user asks for the drawn look (Sketch, `sketch.md`
and "Drawing the panel" in `split-screen.md`).

Engine: `assets/graphic-styles/canvas/vector_engine.js`. `canvas_init.py PROJECT split` starts a reel from `vector.starter.scenes.js` next to it.
`split_reel.py` works out which engine a reel uses from its scenes.js, so nothing else changes in the pipeline.

## Signal over noise (HARD RULE)

There has to be one thing that is clearly the main focus of every picture. If there isn't, that's a problem: too much at once stresses the
viewer's eyes. Each rule below fixes a real mistake:
- **One main thing per picture.** A phone, or a chart, or a clip; a second thing only when it is the same idea's other half (before and
  after) and arrives after the first. If you can't say in three words what the viewer should look at, cut until you can.
- **Nothing too brief to read.** Two boxes that appear for a split second can't be read. Words stay up at least 0.8 s or don't go up
  (`check` flags anything shorter).
- **No label that repeats the caption or the obvious.** "Steps" over a phone counting steps, "every morning" while the speaker says it,
  "a better habit" over a phone: cut. A label earns its place only if the picture is unclear without it.
- **Every picture stands alone.** Without the voice it still says something: the title is a phrase that reads ("The walk matters, not the
  steps" over a park path; "Out the door" over someone tying their shoes), never a run of fragments ("walk", "not the steps", "the door"). The
  title types out at once when the cell starts; it doesn't wait for the spoken words.
- **Show a comparison as a measure.** "Twice as often" is a scale with 1x and 2x under rows of screens, not the words.
- **App screens: the question and blank answer rows.** No text in the rows, no fake content, except the one option the speaker names, which
  grows out of the list with its words. Screens with no question (rows of screens on a scale) are blank.
- **No gradients, no colour wash.** Gradients make it look machine-made. Flat fills everywhere; the only soft edge allowed is a subtle glow
  round a thing (phones and clips get a faint white one). No red glow behind the pictures.
- **Labels clear of the edge.** A tag over a clip or phone sits about 20 px above its edge, never on it.
- **The text hook is Instagram's own text** (edit-playbook rule 33), even when the reel opens on graphics: the white box over the panel, the
  hook's pictures below it (y 500 to 990).

## The look (nothing else on this canvas)

| Thing | How |
|---|---|
| Field | flat near-black `#050505` and a faint dot grid every 24 px; no glow, no vignette. Fixed: the scenes move over it |
| Title | heavy SF Pro (800), white, centred at y 248, typed out at once when the cell starts (a word's time is ignored inside a cell). One word per title gets the accent: a red pill (`{ red: true }`), a green pill for good news (`{ pill: 'green' }`), or New York italic (`{ serif: true }`). Supporting words can be `{ dim: true }` |
| Cards | flat dark rounded rectangles (`#16161a`), a thin light border; `{ glow: true }` adds a subtle white glow for the one that matters |
| Tags | flat: red with white bold text (default), white with black text (a callout, `point: 'up' / 'down'`), green (good news), dark (a neutral label). Used rarely (see above); `label` puts one 20 px above a clip or phone |
| Real footage | in a rounded frame with a white border, a faint white glow and a slow zoom-out. `{ grey: t }` turns it grey and dark from then (what failed). `p.footage` draws a clip with no frame, inside a phone's screen say |
| Phones | an iPhone (flat grey frame, faint white glow) with a made-up app as dark UI: progress bar, the question, blank answer rows, a white Continue button. `p.screenOf` gives the screen's place, to draw over it from outside |
| Lines | thin white, with a soft glow: axes, arrows, connectors. Data lines are red and glow, with white dots on the points |
| Bars | flat: red (the problem), green (the result), grey (before) |
| Lists | `01 02 03` rows; the live row sits on a dark bar with a red edge, rows not reached yet are blurred |
| Marks | red cross (glowing), green tick, red VS badge, red spotlight ring, a handwritten note in New York italic with an arrow |
| Motion | every piece arrives (fades in, grows from 0.86 with a small overshoot) on the word it belongs to. Between cells the next one pushes in from the right with motion blur; a cell holds with a slow push-in |

Colours are fixed: red `#e6202c`, green `#24b14b` (pills and bars), white, greys. The made-up app's own icons may use other colours, small.
Fonts are macOS system fonts (SF Pro, New York italic).

## Real footage

The point of the style. Something real on screen in most cells: a person doing the thing the speaker describes, a place that stands for the
idea (a path for "the way", a summit for "the goal"), the speaker's own clips, or app screens. Where nothing real fits, a chart or a phone.

- **Where it comes from:** `scripts/stock.py search PROJECT "term" ...` lists Mixkit clips under the Stock Video Free License only and
  writes a sheet of thumbnails per term (`media/_search/<term>.jpg`); `stock.py get PROJECT ID NAME` checks the licence again and downloads
  the 720p clip to `media/NAME.mp4`, recorded in `media/credits.json`. Mixkit's FAQ: Free License videos can be used in commercial projects,
  social media marketing included, no attribution needed; Restricted License videos are personal-only, so the script refuses them. Most
  Mixkit clips are Restricted: search broad words ("running", "mountain", "phone") to find Free ones. Read the licence yourself and tell the
  user what will be downloaded before running `get`.
- **Searches are paced** (Mixkit answers 429 to bursts). A round of eight terms takes several minutes: run it in the background and draw
  meanwhile.
- Unsplash answers scripts with a bot check: never get round it. Pexels and Pixabay refuse scripts.
- **In scenes.js:** `const M = { why: clip('media/why.mp4', { from: 2 }) }`, then `media(c, M.why, x, y, w, h, t, t0, { label: 'why walk?' })`.
  A clip plays from `from` when the piece arrives; frames are cut once into `work/vframes`. A missing file draws a grey box and warns.
- A still: `stock.py still PROJECT NAME 3.2` writes `media/NAME.jpg`, used with `photo('media/NAME.jpg')`.
- Never a real company's app, logo or screens. The phones show a made-up app.

## The frame (card layout)

Panel 1080 x 1240 (`PANEL_H`, set by `split_reel.py`; run `PANEL_H=1240 node canvas/scenes.js check` on its own). Title row at y 248 (nothing
above 195, Instagram's header). The picture runs from y 330 to `DB` (990); the caption sits under it, above the speaker's head. Use the whole
width (x 40 to 1040). Typical pieces: a phone 540 to 620 tall centred at y 650; footage 420 to 940 wide, 400 to 590 tall; a chart's baseline at
y 900 to 930 with its labels under it.

## Cells, layers and the hook

A cell is `{ id, at, draw }`; `shift` moves a whole cell's times after a re-cut (it draws at `t + shift`); `cut: true` makes it appear at `at` with
no push; `until` hides it from then (the panel is off screen). `overlay: [{ from, to, draw }]` draws in screen space over every cell, fading at
`to`. When the reel opens in the split (`split-screen.md`, "Opening in the split"), the hook's cells come first, at 0. `recap: { at, first, every,
names, title }` is drawn for you as a numbered list.

## Checks

`PANEL_H=1240 node scenes.js check` (also run by `split_reel.py check`, which sets the height): anything outside the panel, a picture that ends
high, words on words, words up too briefly to read, a cell that starts empty or holds still for more than 2.5 s, a cell over 7.5 s. Then `sheet`
at the beats, and a final look at the rendered frames.

## Mistakes already made once

- **A font weight napi-rs doesn't parse** (650): the text came out as a giant glyph across the phone. Use 400, 500, 600, 700, 800, 900.
- **An invented number on screen** ("Months 3/6" for "a few months"): numbers come only from what the speaker says.
- **A spotlight bigger than its card** washed the whole cell red. Keep the ring just round the thing.
- **A tag repeating the title** under the picture says nothing new; tag something the title doesn't.
- **A first version that broke every rule at the top**: a hook with a phone, three boxes, two labels and a tag at once; boxes that flashed
  for a few frames across a cut; labels on the top edges of phones; option rows full of tiny words; a red glow behind every picture and gradients
  on every fill; titles that held one word for seconds while the speaker talked. The rules at the top of this guide are the fixes.
- **The ground beside the card was the drawn canvas's grey** (`#121212`), a visible seam under the near-black field: `split_reel.py` now paints
  `#050505` there when the reel uses this engine.
- **The phone copy came out at 44 MB** (real footage compresses less than drawings): `split_reel.py` now sizes its bitrate to stay under 30 MB.
