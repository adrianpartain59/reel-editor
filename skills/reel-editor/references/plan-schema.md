# plan.json schema (Talking Head)

`PROJECT/plan.json` drives compose.py. The reel is one hook part followed by the body part. Every time is
relative to its own part and is either seconds (`2.4`) or a word reference from `work/timeline.txt`:

| Spec | Means |
|---|---|
| `"w12"` | start of word 12 |
| `"w12e"` | end of word 12 |
| `"w12-0.05"`, `"w12e+0.2"` | with an offset in seconds |

## Top level
```json
{
  "slug": "paywall-tips",                      // output file names: out/<slug>-<variant>.mp4
  "style": "cinematic",                        // the look: cinematic (default) | bright (on request) | your own. See references/looks/
  "seed": 7,                                   // optional: changes the automatic picks (transitions, animations, sound files)
  "style_overrides": {"music": {"level": -17}},  // optional: deep-merged over the preset (any key in assets/styles/<name>.json)
                                               // a downloaded beat instead of the synth pad: {"music": {"bed": "track:mixkit-358", "level": -16, "duck": 3}}
                                               // (references/music-library.md: beats, levels, how drops land on the downbeat)
  "captions": {
    "keywords": ["paywall", "features", "worth"],   // stay highlighted once spoken (lowercase; ? and ! ignored)
    "max_words": {"pop": 3, "box": 4, "serif": 4, "neon": 3, "word": 1}   // optional, words per caption
  },
  "room": true,                                // OPT-IN ONLY, when asked: replace the room behind the speaker (scripts/room.py,
                                               // references/rooms.md). true = the default saved room, or a name
  "outro_comment": "looks so much better",     // the comment typed in the outro chat_pill compose adds when the body has
                                               // none (HARD RULE); false leaves the outro out (only when asked)
  "hooks": {"h1": PART, "h2": PART},           // one PART per hook clip from selects.json
  "body": PART,
  "cover": {"part": "hook", "t": "w3", "rot": -3,          // y optional: default sits just above the head
            "lines": [["YOUR PAYWALL", "cblack", 190, "#FFFFFF"], ["IS WRONG", "cblack", 230, "#FF3B30"]]}
}
```

## PART
```json
{
  "shots": [...],        // layout changes; the first must be at 0 (a face shot is added if missing)
  "sections": [[0, "pop", "#FFE14D"], ["w17", "box", "#7C5CFF"], ["w40", null]],   // caption style from that time; null = no captions
  "punches": [...],
  "stickers": [...],
  "fx": [...],
  "sfx": [["w43-0.06", "scratch", 0]],   // extra cues: [time, name, extra dB]; overlay/punch/sticker cues are automatic
  "auto_sfx": true,                       // false turns automatic cues off for this part
  "fix": {"w3": "asks", "w9": ""},         // correct a misheard word's caption text ("" hides it); timing refs unchanged
  "drops": ["w59"],                        // music drops (styles with a bed): low end cuts out before, impact lands on it
  "risers": [{"id": "riser_01", "t0": 0, "peak": "w9-0.04", "db": 2}],   // a library riser under the voice, peaking on a
                                           // word (usually the hook's payoff); mixed like the bed, so cues on top don't cut it.
                                           // Pair it with a drop on the same time so the swell lands on an impact.
  "cap_breaks": ["w12", "w20"],            // start a new caption group at these words (groups also break on pauses > 0.35 s)
  "cover": {...}                           // hooks only: this variant's own cover, overriding the top-level one
}
```

## Shots
Common keys: `t` (start), `lay`, `capy` (caption centre y override), `bounce` (zoom kick at the cut, style
default: 0.045 Bright, 0 Cinematic), `sfx: false` (no automatic cue), `drop: true` (a music drop on this cut:
the bed's low end cuts out for 0.5 s before it, then suck + impact land on it), `captions: true` (show captions
on an overlay shot even when the style hides them), `tr` (the transition INTO this shot: a name, `"cut"`, or
`{"name": ..., "d": ..., "dir": ...}`; omitted = the style default, `auto` in cinematic; every name and option
in references/effects.md), `bg` (face shots: a contextual background behind the cut-out speaker, see below).

| lay | keys |
|---|---|
| `face` | `z` zoom (1.0 to 1.6, centred on the detected face), `push` slow push-in (Bright: fraction over the shot, 0.03; Cinematic: per second, 0.03), `settle` (true or an amount like 0.16: the cut lands that much tighter and eases out over ~1.1 s; the reveal move), `smash: true` (zooms in from 0.62x in 0.24 s with motion blur), `bg` (below) |
| `letterbox` | 16:9 window of the face with content in the bars: `top` / `bottom` each `{"title": [[text, colour, size], ...], "label", "accent", "frame"}` or `{"img": mockup}` (at least one is required: an empty letterbox is refused), `z`, `bh` window height (608), `cy` window centre (900). The bars close in; captions go in a free bar |
| `phone3d` | a mockup floating in 3D over the shot's own blurred, dimmed frame, drifting. `img`, `swaps`, `enter` (0.45), `exit`, `enter_anim` rise / side / far / drop / flip, `exit_anim` sink / side / far / flip (both rotate when left out), `yaw` [from, to] degrees ([14, 5]), `pitch` ([7, 3]), `ph` phone height px (1380), `cy` centre y (980), `dx`, `push` (0.04), `glow` backdrop glow RGB. In Cinematic every `fullpw` renders as `phone3d` |
| `split` | `img` mockup name (PNG in mock/ without .png), `pw` phone width px (660), `focus` fraction of the phone height to centre in the visible safe area (0 = top, 0.72 = price selector on paywalls) or `[from, to]` to scroll during the shot, `py` raw `[from, to]` panel y instead of focus, `enter` slide-up seconds, `exit` drop-out seconds at the end, `zf` face zoom in the top half, `swaps` `[[t, img], ...]` change the mockup mid-shot (highlights), `swap_sfx: false` silences the swap clicks when a riser carries a fast montage of swaps |
| `fullpw` | `img`, `enter` (0.3), `exit` (0.28, recommended), `swaps`, `bubble: true` adds the face in a circle, `push` |
| `video` | screen recording inside the phone frame: `src` (path, relative to the project or absolute), `src_in` seconds, `speed`, `enter`, `exit`, `bubble`. Needs mock/frame.png |
| `broll` | full-screen footage: `src`, `src_in`, `speed`, `bubble` (default true: face circle top right) |

### Contextual background (`bg`, face shots)
`{"mock": name | "img": path, "why": "what it shows the viewer", "dim": 0.42, "blur": 0, "sat": 0.85, "focus": 0.5,
"scroll": 0, "push": 0.05, "in": "fade|zoom|slide|drop", "enter": 0.4, "exit": 0.3}`. The speaker is cut out
(Vision mask) in front of it. `why` is required and the image must be content (a screen, a profile, a result):
no decorative sets. Consecutive shots with the same `bg` keep it.

## Punches
```json
{"t0": "w12-0.02", "t1": "w14", "lines": [["TERRIBLE", "cblack", 250, "#FF3B30"], ["STRATEGY", "black", 84, "#FFFFFF"]],
 "rot": -5, "x": 540, "y": null, "sfx": "thud", "keep_captions": false}
```
Line = `[text, font, size, colour]`. Fonts: `cblack` (SF Compressed Black: huge words), `cheavy`, `black`,
`heavy`, `bold`, `xblack` (expanded), `serif`. Captions pause while a punch is up unless `keep_captions`.
`y` defaults per layout (1330 face, 960 split, 380 full-screen). `sfx` defaults to `thud`; `false` for none.
In looks with neon titles (Cinematic) punches render as neon titles and take `anim` / `out` like a glow_title.

## Stickers
All have `t0`, `t1`, optional `sfx` (name or false), `hold_out: true` to skip the exit shrink. Position is
screen pixels (`x`, `y`) or, with `"space": "phone"`, fractions of the phone mockup on screen (`px`, `py`),
which follow the phone as it moves; skipped when no phone is on screen.

| type | keys |
|---|---|
| `red_x` / `check` | `size` (520), position (phone space is typical) |
| `thought` | `text`, `side` l/r, `x`, `y` |
| `review_card` | `lines` (list of quote lines, ~28 chars each), `name`, `src` ("App Store review"), `stars` (5), `x`, `y` |
| `emoji` | `char`, `size` (220), `rot`, `wiggle` (true), position |
| `banner` | `text`, `bg`, `fg`, `size` (56), `x`, `y` (330); slides down |
| `circle` | screen: `x`, `y`, `w`, `h`; phone: `px`, `py`, `pw`, `ph` (fractions); `color`; draws itself on |
| `arrow` | `x1`, `y1`, `x2`, `y2`, `color` |
| `counter` | `from`, `to`, `prefix`, `suffix`, `decimals`, `dur` (0.8), `size`, `color`, `x`, `y` |
| `image` | `path`, `w`, `x`, `y` |
| `clip` | an animated graphic that pops up over the shot: `src` a folder of RGBA PNG frames (played from `t0`, holds the last frame), `fps` (30), `w` (900), `x`, `y` (1150). Pops in with an overshoot, pops out over the last 0.2 s, whoosh in and out; kept inside the text safe area |
| `text` | `lines` (punch-style lines), `rot`, `x`, `y`; like a punch but doesn't pause captions |
| `tap` | glowing touch indicator with a ripple: position (phone space is typical), `size` (96) |
| `glow_title` | neon title card: `lines` `[[text, colour, size(, font)], ...]` (font xblack), `label` small caption above, typed on, `frame: true` neon box around the first coloured line, `accent` glow colour for white lines, `x`, `y` (760), `anim` / `out` / `d_in` / `shine` (references/effects.md: 12 in, 8 out, each with its sound; rotate when left out); auto-fits to 1000 px wide |
| `icon` | neon line icon drawn on: `name` (check, cross, question, warning, trend_up, trend_down, podium, funnel, user, eye, bell, lock, target, heart, phone, clock, arrow_right), `color`, `size` (420), `draw` (0.55), `x`, `y` |
| `hand_note` | handwritten note (Noteworthy Bold) revealed word by word: `text`, `x`, `y`, `size` (66), `reveal` seconds (0.6), `arrow` `[[x0, y0], [x1, y1]]` drawn on (the end point is phone fractions with `space: phone`), `bend` (0.25, negative curves the other way) |
| `notify` | dark lock-screen-style notification that drops in from the top: `app`, `title`, `body`, `color` (icon), `y` (300) |
| `chat_pill` | comment / DM input pill with the speaker's face, text typed letter by letter + caret, send button: `text`, `placeholder`, `y` (1300), `delay` (0.25), `cps` seconds per letter (0.09) |

Any sticker can take `hide_captions: true`: captions pause while it shows (use it when a title says the same words),
and `spotlight: 0.3`: the frame dims to that brightness while it shows and the sticker (plus captions and punch
titles) stays lit.

## fx
| type | keys |
|---|---|
| `flash` | `t`, `d` (0.12), `color`, `strength` (0.85) |
| `shake` | `t`, `d` (0.25), `amp` (16) |
| `rgb` | `t`, `d` (0.25), `amp` (14): chromatic glitch, adds a glitch sound |
| `zoom` | `t`, `d`, `to` (1.15), `x`, `y`: punch-zoom of the whole frame and back |
| `glitch` | `t`, `d` (0.25), `amp` (1.0): authentic digital corruption in bursts (displaced slices with their own RGB split, datamosh blocks from recent frames, pixel stretch, scanline noise, stutter). Put one on the last 0.2 s so the loop back to the hook hides the seam. `glitch_lite` is the old sliced-band look |
| `dip` | `t`, `d`, `strength` (1.0): dip to black and back |
| `spotlight` | `t`, `d` (1.2), `level` (0.3): the frame dims, all text stays lit |
| `freeze` | `t`, `d` (0.7), `scale` (0.8), `rot` (-3): photo snap into a white-bordered print, with a flash |
| `invert` / `bw` / `pulse` | `t`, `d`: negative frame(s) / black and white with text in colour / small zoom pulse |

## Caption styles
`pop`, `box`, `serif`, `neon`, `word` (Bright), and `cine`: SF Expanded Black caps, white with a slight
metallic falloff and a soft shadow, keywords in the section accent with a glow, built word by word (only the
words said so far show, re-centred), placed just inside the top of the head on face shots (head-tracked) and in the top band on every other layout
(HARD RULE, playbook rule 26). Max words per group comes from
the style (4).

## Automatic sound cues
Set by the style's `sfx` table (`assets/styles/<name>.json`: event -> `[[sound, dt, extra dB], ...]`). A sound
is `"cat:a|b"`, a category of the sound pack cycling a -> b on each use (references/sfx-library.md); files rotate so none
repeats back to back. Older names still work: they resolve to a pack category.
Every event the style's table names gets its sound: transitions, phone entrances and exits, swaps and taps, titles by animation
(a key per typed letter), hand notes, notifications, the chat pill, counters, icons, freezes, background entrances, drops. Plus the music bed.
`events.json` lists every visual event (`visual`) and whether it got a sound; qa.py warns on silent ones.

### Sound rules in the plan
- `{"type": "tap", ..., "cta": true}`: a button visibly clicked for the call to action. The only place the loud ding
  (shine) plays. There is no part-level `cta` key; compose stops with an error if a plan still has one.
- Sounds follow per-sound rules (`references/sfx-library.md`); a plan's own `sfx` entries are checked against them too.

### CC (colour correction), read by cut.py
- On by default. Per source clip: white balance from the clip's own neutral midtones, 70% of the way to neutral (a
  room keeps some warmth), a gentle S-curve, a hint of teal shadows / warm highlights, saturation 1.06, sharpen,
  vignette. Gains are cached in `work/cc.json`.
- `"cc": false` turns it off (back to the old light grade); `"cc": {"wb": 0.5}` corrects less, `1.0` fully.
- It's baked into the cut, so changing it means re-running `cut.py` (word timings stay the same: same audio).

### Intro zoom
- ON BY DEFAULT for every hook. `"intro_zoom": false`
  turns it off for one hook; `"intro_zoom": {"from": 1.35, "d": 0.2}` overrides the defaults: the reel opens on the face zoomed
  in to `from` and snaps out to the shot's own zoom over `d` seconds, with a zoom blur that streaks the edges
  (`zoom_blur` 0.14), a soft blur over the whole frame at the start (`blur` 7 px) and an extra edge-only blur
  (`edge_blur` 18 px), all fading out with the zoom. Camera only; captions stay put. 0.35 s
  without blur looks too slow and too clean.
- Trying it on a finished reel without a full render: `compose.py PROJECT --variant V --range 0:K --out head.mp4`
  (K = the first keyframe frame after `d`; `ffprobe -skip_frame nokey`), copy the rest of `work/out/V/video.mp4` from
  that keyframe, concat both with `-c copy`, then `mix.py` and `qa.py`. Took ~5 s for 42 frames.

### Head tracking
- On by default: `track.py` samples each part at 10 fps, finds the face with macOS Vision, fills gaps and smooths the
  path (0.45 s Gaussian) inside each cut, never across one. `Reel.anchor()` reads it, so face shots, captions that
  avoid the face and the chat-pill avatar all follow the head. Cached in `work/parts/<part>/track.json` (~20 s for a
  70 s reel, redone only when `base.mp4` changes).
- Face shots get at least `motion.track_zoom` (1.12) so the frame has room to follow; at 1.12 the face's on-screen
  wobble dropped from ~15-22 px to ~0-3 px on a test reel. A face near the edge of the source can only be
  followed partway (the crop never leaves the frame).
- `"track": false` at the top of plan.json turns it off.
