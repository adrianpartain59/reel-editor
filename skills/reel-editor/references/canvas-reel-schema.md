# canvas_reel.json

One file drives countup_hook.py, canvas_body.py and canvas_sound.py. Worked example: `assets/examples/canvas-roadmap/canvas_reel.json`.
Hook times are seconds from the start of the hook; everything else is seconds from the start of the body. Word times: `work/hook-main_words.json`, `work/body_words.json`.

```json
{ "slug": "walking-roadmap", "part": "body", "scenes": "canvas/scenes.js", "hook": {...}, "faces": [...], "outro": {...}, "beat": {...} }
```

## hook

| key | what it is |
|---|---|
| `variant` | the hook's name in selects.json (`main`) |
| `beats` | `card_in` (card pops up, 0.15 to 0.2 s before the number is named; never before 0.8 s, the face comes first), `start` (the number starts moving), `surge` (the line takes off), `land` (the final number: on the end of the word that finishes the claim, about 3 s), `card_out` |
| `value`, `prefix`, `suffix`, `label` | the final number; text put before and after it (both empty unless you set them, so dollars need `"prefix": "$"`); the small label over it ("Steps walked") |
| `under` | the line under the landed number, word by word: `[["in", 3.14], ["one", 3.26], ["summer", 3.54, 1]]` (1 = green) |
| `punch` | times of the big words: the camera steps in on each (number, "steps", "walked"). The landing and the title words step in on their own |
| `title` | the second card: `in` (0.02 s before its first word, or the card sits empty), `out` (0.4 s before the hook ends, or exactly the hook's length to hold it to the end), `words` (`["10-STEP", 5.22, 1]`, 1 = green), `count` (markers), `from`, `to` (when they light up). Leave `title` out for none |
| `caps` | caption groups, only where no card says it: `["I STARTED WALKING", "AND I'M DROPPING", "TO *WALKING*"]`. `*word*` is the green accent, `_` joins words that show together. One flat list of strings, each word found in what whisper heard (number words and digits match each other). If it stops with "is not said", whisper misheard it: write that group out as `[start, end, [["I", 0.0], ["STARTED", 0.23]]]` |
| `zoom`, `face`, `blur` | by hand, only to fine-tune: `[t0, t1, zoom0, zoom1, "out" \| "io" \| "back" \| "lin" \| "in"]`, `[t, x, y]` of the face on screen, times of the zoom blur |
| `countup` | `taps` (default), `arcade`, `charge` |

## faces, outro

`{"in": 13.07, "out": 15.13, "enter": "down", "back": "right", "accent": "green", "punch": [14.02], "caps": ["THIS KEPT ME", "GOING", "ALMOST *FOREVER*"], "why": "proof"}`

- `in` and `out` sit on word or cut boundaries. `enter`: `down`, `cut`, `through`, `shrink`. `back`: `left`, `right`, `up`, or none on the last one.
- `punch`: the word the camera steps in on. `z0`: how tight it starts (1.28; 1.5 for a cut). `accent`: green, yellow, red. `zoom` by hand if needed.
- `outro`: `{"t0": 54.86, "text": "doing step 2 tonight"}`, a viewer's comment under about 28 characters typed into the pill, inside the last face moment.

## beat

`{"track": "mixkit-358", "shift": 1, "stop": 25.29, "back": 25.79}`. Drops on the hook's `land`. `stop` and `back` cut it and bring it back on a downbeat (the
barrier slam and the word after it); leave both out to let it run. `shift` moves the count-up and the ding by semitones so they sit in the beat's key (`canvas_sound.py --keys`). `level`
-16, `duck` 3, `nudge` (seconds) is measured when left out. Only tracks whose `grid_conf` is 2 or more can stop and return cleanly (`music-library.md`).
