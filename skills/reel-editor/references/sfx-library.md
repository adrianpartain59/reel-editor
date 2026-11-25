# Sound effects: the pack and its rules

A reel uses the sound pack and nothing else: twelve categories, each with one job. The files are synthesized by `scripts/sfx_pack.py`
(no samples, nothing to license), so they can be shared. `assets/sfx/pack.json` holds what each sound is for, its level against the voice and
when it's allowed; `audiomap.py` enforces it and `qa.py` checks it. `sfx_lib.py audition --out FILE.m4a` plays the whole pack with each id read out.

| Sound | Category | Offset (dB vs voice) | When it plays | Limits |
|---|---|---|---|---|
| Counting | `counting` | -14 | only a number counting up on screen | max 2, 4 s apart |
| Glitch | `glitch` | -8 | only on a glitch, RGB split or invert effect | max 3, 5 s apart |
| Cinematic Whoosh | `whoosh` | -9 | the background sound: every transition and every phone, overlay or background moving in or out. Quiet, so it may repeat freely and play under other sounds | background |
| Metallic Riser | `riser` | -9 | only in the hook, once, building into the hook's payoff | hook only, max 1 |
| Low Hit | `low_hit` | -3 | the big reveal (a drop) and a screen shake | max 4, 5 s apart |
| Camera Flash | `flash` | -8 | only on an on-screen white flash (fx flash) | max 2, 10 s apart |
| Camera Flash & Shutter | `flash_shutter` | -8 | only on a freeze frame / screenshot moment (fx freeze) | max 2, 10 s apart |
| Page Flip | `page_flip` | -10 | a mockup changing state (a swap); other swaps stay silent | max 8, 2.5 s apart |
| Shine | `shine` | -10 | the loud ding: only when a button is visibly clicked for the call to action (a `tap` sticker with `"cta": true`). Never on a spoken CTA with nothing clicked on screen | cta only, max 1 |
| Pop | `pop` | -9 | every piece of on-screen text appearing (titles, punch words, text stickers, banners, chat bubbles) gets it, always; small pop-ins (emoji, icons, check marks, taps) only when no text pop is near | 0.6 s apart |
| Key presses | `key` | -15 | computer typing: one key press per letter, on the frame each letter appears (chat pills, typed titles), always. Rotates through 12 keys | one per letter, overlap each other only |
| Scribble | `scribble` | -12 | only while a hand-drawn note, circle, arrow or underline is being drawn; the file is the one whose length matches the draw | max 4, 2 s apart |

The rules live in `pack.json` (`rules`: `events` the sound may serve, `must` events that always get it, `where`,
`min_gap`, `max`, `background`, `fit`), are copied into `library.json` by `sfx_pack.py`, and are enforced in
`audiomap.schedule`: cues claim time in priority order (the CTA ding on a clicked button, then must-have text pops and typing, then the rest), a sound
plays whole or not at all, and the loud part of one foreground sound never overlaps another's (the tail may ring
under the next; whooshes and the hook riser play under everything). QA fails a reel that breaks a rule.

Style tables (`assets/styles/*.json` `sfx`) say which sound an event asks for; a key left empty (`spotlight`, `fx:bw`)
is silent on purpose. Every transition asks for the whoosh (`tr`). Older category names still resolve: `sfx_lib.LEGACY` maps
them to one of the twelve.

No sound is sped up, slowed down or trimmed.

## Using your own sounds

Put your recording over the file it replaces (`assets/sfx/lib/<cat>/<cat>_01.wav`, 48 kHz stereo 16-bit, starting within 5 ms of its first transient) and run
`python3 scripts/sfx_pack.py --measure`, which re-reads lengths and sync points. More files in a category rotate automatically. Check the licence of anything you
download: most free sound libraries allow use in your videos but not handing the files on, so keep them out of anything you publish. When cutting sounds out of a longer recording, send
the user a labelled audition of anything look-alike before wiring it into rules: labels on a timeline can be a clip off.
