# How to draw the hand-drawn canvas

One of the four graphic styles (`graphic-styles.md`) and the only one with a full engine. Code: `assets/graphic-styles/canvas/`
(`engine.js` draws the world, `starter.scenes.js` to copy with `canvas_init.py PROJECT roadmap`, `roadmap.scenes.js` a finished ten-step reel). A reel writes only `scenes.js`.
Look at `assets/examples/canvas-roadmap/sheet.jpg` before drawing: that is the bar.

## The look

- **Ground** #121212 with a faint 60 px dot grid. Nothing else behind the drawing.
- **Line**: every stroke is drawn twice, slightly off, with a small wobble (`pen: rough`). It draws itself on and then holds still: no boil, no shake.
- **Type**: Shantell Sans ExtraBold for every word and number, lower case, written on left to right as it is said.
- **Colour has a job.** Yellow: the step tag and the one thing to remember. Green: our way, the winner, money. Red: wrong, crossed out, stop. Blue:
  a neutral second thing. Grey: the loser, the old way, "instead of". Violet: the thing to skip. White for the rest. Two accents in a scene, three at most.
- **Boxes** are hatched inside in their line's colour at 20 to 30%.

| Thing | Size |
|---|---|
| headline | 88 to 116 px, top at y 366 to 384, 2 to 6 words |
| words in a box | 78 to 128 px (two lines at 88 in a 230 px box) |
| labels, notes | 46 to 72 px; nothing under 40 |
| the number of the scene | 168 to 200 px |
| box and shape lines | 7 to 8 px; small detail 5 to 6 |
| arrow that carries the idea | 13 to 15 px, head 54 to 66; connecting arrows 7 to 9 |
| crosses | 16 to 18 px over the thing, 9 over an icon |

## The frame

A scene draws in its own 1080 x 1720 screen; the engine moves the camera. The tag ("step 3") is at y 300 and is drawn for you. Keep words and shapes inside
x 40-1040, y 220-1500, and nothing that must be read right of x 900 below y 1150 (Instagram's buttons). Put the headline at the top, one
drawing between y 500 and 1300, and at most one payoff line at y 1370 to 1410. Below y 1500 stays empty.
The camera pushes in 0.85% a second on every scene, so leave 20 px spare at the edges.

**Fill it.** Every scene of the worked example runs from x 40-110 to x 970-1020, ends between y 1408 and 1496, and leaves no empty band over 90 px (one of 176). 8 to 22% of the frame
is ink. A phone is 370 to 420 wide, a box 800 to 880 wide and 200 to 250 tall, a bar 176 to 220 wide. A thin scene with small labels floating around it is the usual failure: make the
one picture big and drop the labels.

## One scene = one idea, drawn on the words

1. Write the step's line down with its word times. Underline the two or three words that can be seen.
2. Start the picture while the speaker says "step three": the phone, the axes, the empty boxes. The first ink is within 0.9 s of the step's first word, usually 0.2 to 0.7.
3. Choose the picture that makes the point without sound: a thing crossed out and its replacement, a curve, two bars, a grid filling up, a slice of a pie.
4. Give every element the time of the word that names it, minus 0.05 to 0.1 s for a shape (so it is there as it is said) and exactly on it for a
   written word. The winner lands last.
5. Something new at least every 1.5 s (`check` reports longer gaps). If the talking runs past the drawing, that is where a face moment or a camera move belongs.
6. Fewer words than are said. The headline is the step in 2 to 6 words; the drawing carries the rest. Never write the headline's words again in a box under it, and don't caption parts of a picture ("people", "film").

| What is said | Draw |
|---|---|
| don't do A, do B | A in a red box, a red cross on the next word, an arrow, B in a green box (step 4) |
| A instead of B | A large and green with its picture, "instead of", B grey and crossed (step 3) |
| growing / going up | axes and one thick green arrow; a dip below the line in red that comes back for "it gets harder first" (steps 1, 9) |
| one thing out of many | a phone with the one thing in yellow, the others as small grey boxes crossed one after another (step 2) |
| do it fast | a timeline with the long way struck out and a short thick arrow, then the number counting up (step 5) |
| a hundred of them | `dots` filling in, then lighting up (step 6) |
| a share of something | `slice`, the number popping beside it (step 7) |
| X looks like Y | two phones side by side, one ticked, one crossed; the feed inside scrolls (step 8) |
| this beat that | `bar` pairs landing on each number said, the winner's value bigger and green; push the camera to each (`moves`), back for the winner, a shake and a hit on it (step 10) |
| most people stop here | `barrier`, as an extra stop on the road with `corner: true` |
| the end | `flag` as the finish, and the pull-back over the whole road |

Link scenes when the speaker links steps: step 2 ends with "for (step 6)", step 6 answers with "from step 2" in a tag.

## Look at every finished scene big

`sheet` shows timing; it hides mistakes. For each step run `node canvas/scenes.js still <last moment before the flight or face moment> work/still.jpg` and look for:
- a label or number under a line, a cross or another shape. Crosses go over words on purpose (step 4); a cross over a number the viewer needs to read is a mistake;
- a label that runs into the thing beside it;
- something off-centre in its box, or sticking out of it;
- a leftover: a picture from the first half of the step that means nothing once the second half is drawn.

Times inside a flight are blurred on purpose; `node canvas/scenes.js info` lists the flights. A step may begin as a face moment ends: its flight happens under the face.

## The pieces (`const { make, h } = require(engine)`)

`c` is the canvas, `t` the second, `sk` a pen that draws on. Every `sk` call takes `(…, t0, t1, {c, w, r})` and draws between t0 and t1.

- `h.headline(c, [['pick', .37], ['one', .6, {c: C.yellow}], ['\n'], ...], t)` the step's line; shrinks to fit
- `h.card(c, sk, x, y, w, h, t0, 'green', [['same', 16.6], ['time', 16.9]], 112)` a hatched box with centred words; kinds green, red, blue, yellow, grey, violet
- `h.write(c, words, x, yTop, size, t, {maxW, align})` words anywhere; `h.label(c, 'mine', x, y, size, t, t0)` fades in; `h.land(c, '20%', x, y, size, t, t0)` pops
- `h.count(c, 10000, x, y, 200, t, t0, t1)` counts up, for 100 and over (a 3 just lands) (add `counting: [t0]` to the stop's cues); last argument formats it, default $1,234
- `h.bar(c, x, baseline, w, height, t, t0, '9K', C.blue, FILL.blue, big)`, `h.dots(c, n, cols, x, y, gap, r, t, t0, t1, lit0, lit1)`, `h.slice(c, sk, cx, cy, r, .2, t0, [x, y])`
- `h.hearts(c, x, y, t, t0)`, `h.face(c, sk, x, y, r, t0, 'happy' | 'flat' | 'sad')`, `h.play(sk, x, y, size, t0, {c, w})`, `h.tag(c, 'step 6', x, y, t, t0, C.yellow, w)`
- `h.barrier(c, t, slam, lift)`, `h.flag(c, t, t0)`, `h.box(c, sk, x, y, w, h, t0, C.green, FILL.green)` an empty hatched box, `h.hatch`, `h.pop`
- `sk.line(x1, y1, x2, y2, …)`, `sk.rect(x, y, w, h, …)`, `sk.circ(x, y, r, …)`, `sk.path(points, …)`, `sk.arrow(h.line(…) or h.spline([[x, y], …]), t0, t1, {c, w, head})`, `sk.cross(x, y, half, t0, {c, w})` (`half` = half its width: 130 to 190 over a box, 66 over an icon),
  `sk.phone(cx, cy, w, h, t0, t1, {w})`, `sk.fig(x, footY, height, {la, ra, ll, rl, lb, rb, lean, face: 'happy' | 'flat' | 'sad'}, t0, t1, {c, w})` a stick person (arm, leg and elbow angles in degrees from straight down, at least 400 tall)
- `K.money`, `pr(t, a, b)` (0 to 1 between two times), `E.out | io | back` (easings), `lerp`, `clamp`

## The reel around the scenes

`make({ dur, stops, views, flights, shakes, hits, cues })`:

- `stops`: in road order, three to a row, snaking (row 1 left to right, row 2 right to left). A step: `{ id: 4, at: 15.13, map: ['same', 'time'], draw, cues }`. `at` is
  its first word; `map` is the two short lines shown when the camera pulls back; `label` replaces "step 4"; `moves: [[t0, t1, dx, dy, zoom], ...]` moves the
  camera inside the scene. An extra stop (`extra: true`) has no tag; `corner: true` sends the road straight down through it, `finish: true` shows `map[0]` in green on
  the map, `road: [t0, t1]` says when the road reaches it.
- `flights`: `[t0, t1, from, to, dip]`. Leave it out and one is made per step, 0.32 s before its first word to 0.45 s after. Write them out when you want a
  pull-back: fly to a view and on (`[23.2, 23.95, 5, 'HALF', 0], [24.4, 25.05, 'HALF', 'T', 0]`). `dip` is how far it zooms out on the way: .36 sideways, .3 down a row, 0 to or from a view.
- `views`: `{ HALF: { rows: [0, 1], title: 'SETUP', at: [23.75, 24.4] }, ALL: { rows: [0, 3] } }`. Two pull-backs in a 60 s reel: the halfway turn and the end. Every finished
  scene fades to its number and two lines.
- `shakes`: `[t, px, seconds]`, `hits`: `[[t]]` (a 5% camera jump). Only on a slam or the payoff number; twice a reel at most.
- `cues` (on a stop or on the reel): `pop: [t]` as each main drawing lands (2 or 3 a scene), `scribble: [[t, seconds]]` on big crosses (4 a reel at most), `counting: [t]` under a counting
  number, `low_hit: [[t, dB]]` on the slam (-9) and the payoff (-12). Whooshes are made from the flights and the face cuts.

## Mistakes already made once

- A pull-back that pans and zooms on the same easing swings past its subject; the engine pans in step with the zoom, so don't animate the camera by hand.
- Typed text with key sounds doesn't suit the canvas: write it on.
- A scene drawn all at once and then held reads as a slide. Spread the drawing over the step's words.
- The finished scenes must disappear on the map, or their detail turns to noise at that size.
- An empty screen with only the step tag for a second, a small drawing in the middle third, a box that says the headline again. `check` measures the first two.
- Words that cross a box's edge: use `card` or `headline`, which shrink to fit, and look at a still after the last word of the step.
