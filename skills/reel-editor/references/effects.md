# Effects library

Everything the compositor can do to the picture, with the sound each move makes. Read this before planning a
reel in the cinematic style, then pick moves on purpose: each one should answer "what does the viewer get from
this here?".

## The four rules

| Rule | What the skill does about it |
|---|---|
| **Everything is animated.** Nothing pops on or off cold. | Every title, sticker, phone and background has an in and an out animation; captions build word by word with the newest word popping in; face shots always push in. |
| **Everything has a sound.** | Every visual event gets a cue from the style's sound table (`auto_sfx`), from the sound pack (`references/sfx-library.md`). `events.json` lists every visual event; QA warns on any that moves in silence unless the plan set `sfx: false`. |
| **Everything is intentional.** | No decoration. A background (`bg`) must show content and carry a `why`; a letterbox must have content in its bars; compose refuses the plan otherwise. Pick transitions and title animations for what the moment is (table below). |
| **Everything varies.** | Transitions, title animations, phone entrances and background entrances rotate through the style's pools when the plan leaves them open (never one of the last 3-4); sound files rotate (`sfx_lib.Picker`: never the same file twice in a row, avoids repeats within 8 s). QA warns on the same transition twice in a row or the same title / phone animation three times running. |

## Transitions (shot key `tr`)

`"tr": "whip"`, or `{"name": "whip", "d": 0.3, "dir": "r"}`, on the shot being cut TO. `"tr": "cut"` is a hard
cut. Left out, the style decides: cinematic uses `"auto"`, which picks from the pool for the context
(`face>face`, `face>overlay`, `overlay>face`, `overlay>overlay`, plus `:drop` pools for shots with `drop` or
`smash`), never one of the last 4, and always a hard cut next to a shot shorter than 0.9 s (two transitions
half a second apart read as noise). The window is centred on the cut. A transition replaces the outgoing
shot's exit animation. Both sides render from the same source frame, so it mixes two framings of one moment.

| name | length | sound (cycled) | energy | look | use for |
|---|---|---|---|---|---|
| `cut` | - | - | 0 | hard cut | zoom cuts between face framings, when the dim / title is already the move |
| `whip` | 0.30 | swish, whoosh | 2 | both shots slide with heavy motion blur; `dir` l/r/u/d | any change of subject |
| `slide` | 0.36 | swipe, swish | 1 | push: new shot pushes the old off; `dir` | face to phone, phone to phone |
| `zoom_in` | 0.36 | whoosh_heavy, whoosh | 3 | punch into the old shot with radial blur, land zoomed on the new | reveals, "here's the thing" |
| `zoom_out` | 0.42 | reverse, whoosh | 2 | old shot pulls away into the distance | phone back to face, endings |
| `flash` | 0.24 | impact, shimmer | 3 | white flash with an exposure bloom | reveals, drops |
| `shutter` | 0.32 | shutter | 2 | camera blades close and open with a flash | a screen being shown as proof, "look at this" |
| `glitch` | 0.30 | glitch | 3 | corruption bursts, slices of each shot bleed into the other | warnings, mistakes, the loop |
| `spin` | 0.34 | whoosh, swish | 3 | rotational whip with zoom and blur | rare high-energy beat |
| `wipe` | 0.34 | swish, swipe | 1 | soft linear wipe with a glowing edge; `dir` | lists, before/after |
| `iris` | 0.40 | whoosh, pop | 2 | circle opens from the face (`cx`, `cy`) with a glowing ring | focusing on one thing |
| `blur` | 0.36 | whoosh | 1 | defocus out, refocus in | calm beats, time skips |
| `dip` | 0.32 | reverse | 1 | dip to black | section breaks |
| `light_leak` | 0.50 | shimmer, whoosh | 1 | warm film leak washes across | story, emotion |
| `pixelate` | 0.30 | glitch, tick | 2 | mosaic out and back | digital topics, censor-style reveals |
| `tv_off` | 0.40 | stop, switch | 2 | old-TV switch-off to a line, back on | "stop doing X", endings |
| `rgb_split` | 0.26 | glitch, swish | 2 | chromatic split peaking at the cut | punchy face to face |
| `strobe` | 0.30 | impact, glitch | 3 | fast flashes alternating both shots | drops, rarely |
| `luma` | 0.45 | shimmer | 1 | new shot burns in through its brightest parts | different content only (on the same face it looks like a double exposure) |
| `impact` | 0.30 | impact | 3 | hard cut landing with flash, shake, zoom punch | drops, punchlines |
| `card` | 0.45 | swipe, whoosh | 2 | old shot shrinks to a card and falls away | face to phone, story beats |
| `stretch` | 0.36 | swish, pop | 2 | elastic: old snaps up, new drops in and squashes | playful beats |

Options: `dir` (whip, slide, wipe; auto-alternates), `cx`/`cy` (zoom_in, zoom_out, iris; default the face on
screen), `color` (flash, wipe, iris, dip), `amp` (glitch, rgb_split), `block` (pixelate), `sgn` (spin, card).
Energy 3 on the 3-4 biggest moments only; mostly 1-2. Catalog stills: `assets/examples/fx-transitions-*.jpg`.

## Titles: `glow_title`, cinematic `text` stickers, punches

`anim` (in), `out`, `d_in` (seconds, default per anim), `shine` (light sweep after landing, default on),
`spotlight` (see below). Left open, cinematic rotates through its `variety.title_in` / `title_out` pools; a
title followed immediately by another gets `out: "cut"`. Coloured lines are lit neon (whitened core in a
three-layer bloom); white lines get a shadow and a faint accent bloom.

| anim | look | sound |
|---|---|---|
| `flicker` | neon flicker-on, label typed on | neon buzz |
| `pop` | scale overshoot from 55% | pop |
| `type` | typed on letter by letter, in place | a key click per letter |
| `scramble` | random characters resolve into the words | glitch, then a tick per letter |
| `slide` | slides in from the side with motion blur | swish |
| `drop` | falls from above, lands with a shake | impact on landing |
| `stamp` | slams down from 2.4x with a shake | stamp on landing |
| `blur` | comes into focus from a big soft blur | whoosh |
| `reveal` | wiped on left to right behind a glowing edge | swish, shimmer on landing |
| `zoom` | flies in from far away | whoosh, impact on landing |
| `glitch` | glitches into place | glitch |
| `rise` | rises 60 px while fading in | shimmer |

Out: `fade`, `pop`, `slide`, `blur`, `glitch`, `flicker`, `drop`, `cut`.
Fit the move to the words: warnings `glitch` / `scramble`; the fix or the rule `stamp`; a list `slide` /
`drop` / `scramble` / `stamp` (vary within the list, end on the heaviest); the CTA `type`; curiosity `reveal`.

## Phones (`phone3d`, and `fullpw` in the cinematic style)

`enter_anim`: `rise` (rises turning to camera), `side` (swings in), `far` (flies in from the distance), `drop`
(falls and bounces), `flip` (turns from edge-on). `exit_anim`: `sink`, `side`, `far`, `flip`. Sounds by mode
(`phone_in:<mode>` / `phone_out:<mode>` in the style). Left open, they rotate.

## Contextual backgrounds (`bg` on a face shot)

The speaker is cut out (macOS Vision person mask, `segment.py`) and placed in front of something the viewer
needs to see: the screen being talked about, the profile, the result. Never a decorative set.

```json
{"t": "w177", "lay": "face", "z": 1.1,
 "bg": {"mock": "plan_full_dark", "why": "the plan screen being talked about",
        "dim": 0.42, "focus": 0.35, "scroll": 140, "in": "zoom"}}
```

`mock` (a mockup's screen, no phone frame) or `img` (any image, e.g. a screenshot of the user's real profile:
ask for it), `why` (required), `dim` (0.42), `blur` (0), `sat` (0.85), `focus` (0-1, which part of the image
is centred), `scroll` px over the shot (the image drifts, so it is never still), `push` (0.05), `in` fade /
zoom / slide / drop, `enter` (0.4), `exit` (0.3). Consecutive shots with the same `bg` keep it without
re-entering. A soft dark halo separates the speaker from it. Sound: `bg_in` (swipe / whoosh).

## Spotlight (the room dims, the text stays lit)

On any sticker: `"spotlight": 0.3` (the brightness the frame dims to; `true` = 0.3). While it shows, the
picture and every other sticker dim and desaturate; that sticker, punch titles and captions stay at full
brightness. As fx: `{"t": "w220", "type": "spotlight", "d": 4.4, "level": 0.35}` dims for `d` seconds and
keeps all text lit (titles, counters, notes, icons, captions). Sound: `spotlight` (a light switch). Use it for
the 2-3 moments that should feel like a reveal: the hook payoff, the viewer's doubt, the recap list.

## Neon icons (`icon` sticker)

A line icon that draws itself on with a neon glow, then breathes. `name`, `color`, `size` (420), `draw`
seconds (0.55), `x`, `y`, `spotlight`. Names: check, cross, question, warning, trend_up, trend_down, podium,
funnel, user, eye, bell, lock, target, heart, phone, clock, arrow_right. Sound: neon buzz, shimmer when drawn.

## fx

| type | keys | look | sound |
|---|---|---|---|
| `glitch` | `t`, `d` (0.25), `amp` (1.0) | authentic corruption in bursts: displaced slices with their own RGB split, datamosh blocks from the last frames, pixel-stretch bands, scanline noise, an occasional stutter back to an older frame | glitch |
| `glitch_lite` | `t`, `d`, `amp` | the old sliced-band glitch | glitch |
| `flash` | `t`, `d` (0.12), `color`, `strength` | flash frame | impact / shimmer |
| `shake` | `t`, `d` (0.25), `amp` (16) | camera shake | impact |
| `rgb` | `t`, `d`, `amp` (14) | chromatic split | glitch |
| `zoom` / `pulse` | `t`, `d`, `to` (1.15 / 1.07), `x`, `y` | punch-zoom of the whole frame and back | whoosh / impact |
| `invert` | `t`, `d` (0.07) | a negative frame or two | glitch |
| `bw` | `t`, `d` | picture goes black and white, text stays in colour | switch |
| `freeze` | `t`, `d` (0.7), `scale` (0.8), `rot` (-3) | photo snap: the frame freezes into a white-bordered print with a flash | shutter |
| `dip` | `t`, `d`, `strength` | dip to black and back | reverse |
| `spotlight` | `t`, `d` (1.2), `level` (0.3) | see above | switch |

## Letterbox

Only with content in the bars: `top` and/or `bottom`, each `{"title": [[text, colour, size], ...], "label":
..., "accent": ..., "frame": true}` or `{"img": mockup}`. The bars close in from the full frame. Compose refuses
an empty letterbox.

## Sounds

Every cue goes through the audio map (`scripts/audiomap.py`, playbook rules 13 and 19): whole or not at all, one
foreground sound at a time, at most 3 per second. Read `work/out/<v>/audio_map.txt` after a
mix: it lists, every 0.25 s, whether the speaker is talking and which effect is audible.

Style tables map an event to `[[spec, dt, dB], ...]`. `"cat:pop|shine"` is a pack category, cycling
pop -> shine on each use of that event. Sounds line up their `sync` point (a click's transient, a whoosh's peak, a
riser's end) with the event time. The "sound" columns above name the feel of each move; older names there (swish, impact,
shimmer ...) resolve to one of the twelve pack sounds. The pack and its rules: `references/sfx-library.md`.
