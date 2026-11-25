# Style: cinematic

**The house style**, the default when a plan names no style. `"style": "cinematic"` in plan.json. Its techniques were measured
on a 39 s reel with 5.6M views (`analyze_ref.py`), then reworked: no decorative backgrounds or empty layouts, many more
transitions, everything animated, sounded, intentional and varied. The aim is the feel, not a copy: no one else's footage, music,
fonts or graphics; the user's own takes, system fonts and sounds synthesized here.

Read `references/effects.md` first: every transition, title animation, background and effect, with its sound.

## What makes it feel expensive

| Technique | Reference measurement | How the skill does it |
|---|---|---|
| Grade | dark, contrasty, nothing clips | the real room, never replaced: whole-frame contrast, a touch of warmth, highlight roll-off (the white shirt keeps detail), light vignette and grain |
| Context behind the speaker | the speaker's own profile, dimmed, behind them while they talk about it | `bg` on a face shot: the speaker cut out (Vision mask) in front of the screen being discussed, drifting slowly; must carry content and a `why` |
| Spotlight | the scene dims around a neon icon / title, which stays bright | sticker `spotlight` or fx `spotlight`: picture and other stickers dim and desaturate, text stays lit, light-switch sound |
| Captions | 1-4 words, heavy wide caps, white, soft shadow, centred; phrases build word by word | caption style `cine`: SF Expanded Black, metallic falloff, newest word pops in, keywords lit neon in the accent |
| Titles | neon thumbnail-style cards: small typed label, big glowing coloured line, neon frame | `glow_title` with a three-layer bloom and hot core, a light sweep after landing, 12 in-animations and 8 outs, each with its own sound |
| Constant motion | face always moving: push-in ~3%/s; reveals land ~15% tight and settle; CTA smash-zoom | motion `push_mode: per_second`, shot `settle`, shot `smash` |
| Transitions | few hard cuts; whooshes on all 9 transitions | 22 transitions; `auto` picks one per shot change from a pool that fits the context and never repeats the last 4 |
| UI as motion graphics | half the reel has no face: dark UI in 3D space, taps, toggles, counters | `fullpw` renders as `phone3d` with dark mockups (`&dark=1`), 5 entrances / 4 exits that rotate, `tap` stickers, `swaps` |
| Annotations | handwritten note + drawn arrow; neon line icon drawn on | `hand_note`; `icon` (17 neon line icons) |
| CTA | comment pill with the keyword typed in; push notification | `chat_pill`, `notify` |
| Loop | RGB datamosh glitch from the last frame back into the hook | fx `glitch` on the last 0.2 s (authentic: bursts, datamosh blocks, stutter) |
| Music bed | dark ambient chords + sub, ~12-15 dB under the voice, drops before reveals | default: a trap beat (`music.bed: trap`, one of 4 measured beats per reel), 14.5 dB under the voice, ducks 3 dB under speech; `dark_pad` on request; `drop` shots cut its low end and land a reverse swell + impact; or a downloaded trap beat per reel (`music.bed: "track:<id>"`, references/music-library.md) cut before each drop and back on the downbeat |
| Sound design | heavy, crisp, stereo, different on every move | the sound pack (references/sfx-library.md): twelve sounds, each with its own job and limits |
| Master | -12.2 LUFS, LRA 1.7 LU | voice: high-pass 80, -1.5 dB at 250 Hz, 4:1 compression, +1.5 dB at 5 kHz, +2.5 dB shelf from 7.5 kHz (the compressor dulls the top end ~2 dB); master -12 LUFS |
| Pace | 207 words/min, pauses cut | ingest/cut already remove silences; keep selects tight |

## Planning a cinematic reel

1. **Hook (first 3-4 s).** Face first (>= 0.8 s) with building captions, then the visual of the promise (a
   phone with taps on the fields as they are named), then a `drop` back to the face with `settle` and a
   `glow_title` of the payoff phrase with `spotlight` (`hide_captions`, and `fix` the same words to "").
2. **Rhythm.** Alternate face beats (building captions, a title, a `smash`, a background) with phone beats
   (2.5-4.5 s each, a `tap` per state change). Something new every 1-2 s.
3. **Every beat has a reason.** Before adding a move, name what the viewer gets from it. Show the screen
   being talked about (phone or `bg`); dim the room for the 2-3 moments that should land; a letterbox only with
   something in its bars; no decoration.
4. **Transitions.** Let `auto` vary them, then override where the moment calls for one: `shutter` when a
   screen is shown as proof, `glitch` on a warning, `impact`/`flash` on drops, `tv_off` on "stop doing X",
   `cut` where the dim or the title is already the move. Read the chosen list in `events.json`
   (`transitions`) after the first preview and fix anything that doesn't fit the words.
5. **Drops.** 3-4 per minute, on the biggest reveals only.
6. **Titles** for the 4-6 phrases you'd put in a thumbnail. Colours: red #FF3434 warnings, green #2FE38A the
   fix, yellow #FFD23F curiosity, white for the second line. Chest height (y ~1390 for a selfie close-up).
   Pick the animation for the words (effects.md); vary it through a list and end on the heaviest.
7. **Backgrounds** (`bg`) when the speaker talks about a screen without the phone on screen: the question being
   described, the result, their profile (ask for a real screenshot). 1-3 per reel.
8. **CTA**: `smash` into the face + a typed title or `chat_pill`, and a `glitch` on the final 0.2 s.
9. **Hand notes and icons** sparingly (1-2 each per reel): the viewer's inner voice, the viewer's doubt.

Worked example: `assets/examples/cinematic-plan.json` (its words: `cinematic-timeline.txt`).

## Requirements and costs
- Rendering is ~2x classic (transitions render two shots, titles bloom): about 5-7 min for a 60 s reel.
- `segment.py` (Vision person masks, ~2 min for a 60 s reel, once) runs only when a shot has a `bg`.
- Footage: one person, face and shoulders in frame. Posters or drawn figures on the wall get half-confidence
  in the mask; `grade.mask_lo` (0.66) drops them. Raise it if one still shows behind a `bg`.

## Tuning (style_overrides)
`grade.subject_contrast` (1.08), `grade.vignette` (0.38), `transitions.default` (`"cut"` to only use the ones
you name), `transitions.pools`, `variety.*` pools, `captions.size` (84), `captions.accent`, `motion.push`,
`music.level` (-15 dB under the voice), `music.bed: null` for no bed (e.g. when adding a trending sound in the
app). A synthetic dark set (`grade.segment: true` with bg_dark/bokeh keys) still exists but only on the
user's explicit request: it replaces their room with a made-up one.
