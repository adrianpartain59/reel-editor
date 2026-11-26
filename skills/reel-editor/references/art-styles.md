# Art styles

One per reel.

**Vector is the Split Screen's default** (`vector-style.md`, engine `assets/graphic-styles/canvas/vector_engine.js`): flat graphics on near-black,
heavy titles with one word on a red or green pill, dark cards, charts, numbered lists, phones with a made-up app and real stock footage
(`scripts/stock.py`). Signal over noise: one main thing per picture, no gradients (edit-playbook rule 34).

The four drawn styles below are for when a reel needs drawn art over it or in place of the face. **Sketch has an engine**
(`assets/graphic-styles/canvas/`): use that, not the sample scenes. `sketch.md` is how to draw in it, `drawn-roadmap.md` and `split-screen.md`
("Drawing the panel (Sketch)") are the reels around it.

The other three: code in `assets/graphic-styles/` (`npm i` once, then `node render.js list`, `sheet <id>` for stills, `film <id>` for a moving sample).
The scenes there are three steps of the ten-step example; copy them as the pattern and write new scenes for a new reel. `kit.js`
has the pens, word-synced type and figures.

| id | Name | Ground | Lines and colors | Text | Motion |
|---|---|---|---|---|---|
| `stick` | **Stick Figures** (on black) | #000 | White marker 15 px, one accent #FFD400, red #FF4B3E for wrong, grey #8D8D8D for the loser | Permanent Marker, words pop in as said | Line boil at 8 fps, figures act (jump, cheer, sulk), the new scene drops in with overshoot |
| `sketch` | **Sketch** (the Drawn Roadmap's) | #121212, faint dot grid | Doubled rough lines 6 px, hatched boxes: green #69DB7C, red #FF8787, blue #74C0FC, yellow step tag #FFD43B | Shantell Sans ExtraBold, written on | Boxes and arrows draw on; the camera flies along an arrow to the next step, zooming out on the way |
| `blueprint` | **Blueprint** | #143F9E, 36/180 px grid | White technical lines 4 px, yellow #FFD34D, red #FF6B5E stamps, measurement arrows | League Gothic headline typed on, Space Mono labels, footer caption + FIG. number | Lines and dimensions draw from the center, stamp lands |
| `neon` | **Neon** | #05060B, faint brick, pink and blue haze | Glowing tubes with a white core: cyan #39C6FF, pink #FF4FD8, green #4DFF9D, violet #8A7DFF, red #FF3B4E | Rajdhani Bold with a glow | Tubes draw on, the sign flickers, scene changes flicker for 0.3 s |

Rules that hold in all four: text and art stay inside x 40-1040, y 220-1500 (nothing right of x 900 below y 1150);
the thing said is drawn on the word that names it; few words, numbers big; the winner gets the accent and the loser goes
grey. The hook stays the speaker's face.

Which to reach for: Sketch for steps, systems and roadmaps; Blueprint for frameworks and numbers; Stick Figures for people
and choices; Neon for a short, punchy list.

The art runs most of the body and the face comes back for first-hand proof and blunt calls, never at every step; text is written on, not typed,
so there are no key sounds. A longer reel in Stick Figures, Blueprint or Neon reuses canvas_body.py and canvas_sound.py: render the art to `work/canvas.mp4`, 1080x1920 at 30 fps, as long
as the body.
