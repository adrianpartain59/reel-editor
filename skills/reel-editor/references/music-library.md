# Music library (downloaded beats)

Instrumental beats for the music bed. A trap beat is the cinematic default (`"bed": "trap"`, picked per reel from `TRAP_POOL` in
scripts/common.py). The files are not in this repository, because Mixkit's licence doesn't allow handing them on inside a tool. Get your own copies once:

```
python3 scripts/music_lib.py fetch
```

That downloads 10 tracks (33 MB) from mixkit.co into `~/.cache/reel-editor/music`. Read the licence below first and tell the user what will be downloaded. Until then a cinematic reel plays the
synthesized `dark_pad` and says so; nothing fails.

## Using one

```json
"style_overrides": {"music": {"bed": "track:mixkit-358"}}   // level -14.5 and duck 3 come from the style
```

| key | default | what it does |
|---|---|---|
| `bed` | style's (`trap`) | `track:<id>` for a beat from `assets/music/library.json`; `dark_pad` for the synthesized pad; `null` for none |
| `level` | -14.5 (style) | dB under the voice's speech level. A beat is measured on what a phone plays (above 150 Hz), because the 808 sub holds most of a trap beat's energy (59-85% under 120 Hz across the 10 beats here) and a phone speaker plays none of it. At this level the voice stays 14-31 dB clear in every band from 150 Hz to 9.6 kHz (measured on a test reel) |
| `duck` | 2.5 (style 3) | extra dB down while the speaker talks |
| `pocket` | -4 | dB at 2.4 kHz (an octave-wide dip where consonants live) |
| `sub` | -3 | dB low shelf under 90 Hz, so the 808 is felt on headphones without pumping the master |
| `drop_len` | 0.5 | seconds of silence before each drop |

What `music.track()` does with it:
- **Hook:** it starts early enough that the track's own lead-in into its full section lands on the first drop
  (the hook payoff), so the beat "drops" with the reveal.
- **Drops** (shots with `drop`/`smash`): the beat stops for `drop_len` (40 ms fade) and comes back on a downbeat exactly at the drop, so the impact
  lands on the "1". Each return jumps to the next downbeat after where the beat would have been, so the track keeps moving forward.
- **Loop:** if the reel outlasts the track's steady section, it loops by whole 4-bar phrases.
- **Untrusted grid** (`grid_conf` < 2): the beat keeps running and only its low end cuts out before a drop.

Hear options under the reel's own voice before choosing:
`python3 scripts/music_lib.py audition PROJECT --variant h1 --ids mixkit-358,mixkit-403 --secs 18`
(writes `~/Downloads/reel-music-audition.m4a`, each beat's name read out first).

## The library: measured trap, not tagged trap

"Trap" means hi-hat patterns with rolls (bursts of 32nds and triplets) over an 808 bassline that rings and slides. A site's trap category and mood tags don't
guarantee that: one track in the category, tagged Hip Hop, has zero hi-hat rolls. So every beat here was measured (`music_lib.trap_measures`) across all 85 tracks in Mixkit's category, and the
top scorers checked by eye on hi-hat and 808 spectrograms. In the library: `hat_rolls` >= 3.5 per 10 s and a real 808 (`sub_share` >= 0.34 with slides).

| id | title | rolls / 10 s | 808 (sub share, slides / min) | notes |
|---|---|---|---|---|
| `mixkit-358` | House Party (Arulo) | 6.3 | 0.79, 15 | varied hats with rolls, a ringing 808 with slides, the cleanest grid of the set (31.7). Its full section starts on a drop out of a breakdown, which lands on the reel's hook payoff |
| `mixkit-403` | G Eazy NBA type (Arulo) | 6.4 | 0.80, 3.5 | long hat rolls, steady 81 s (no loop), fewer slides |
| `mixkit-235` | Try Me (Arulo) | 5.7 | 0.80, 10.9 | confident, serious; grid not trusted (1.1), so drops keep it running |
| `mixkit-369` | Need for speed (Arulo) | 4.4 | 0.47, 20.9 | serious, determined; the most 808 slides of the four; a little more in the voice band |
| `mixkit-426` | Kid's Pop (Arulo) | 6.7 | 0.80, 6.0 | |
| `mixkit-262` | Praise the Lord (Arulo) | 6.0 | 0.49, 10.9 | busy 808 |
| `mixkit-449` | I'm Working (Arulo) | 7.9 | 0.34, 31.4 | most rolls, lighter 808 that slides a lot |
| `mixkit-410` | Lil Pump Type (Arulo) | 4.4 | 0.85, 11.4 | |
| `mixkit-446` | Find Me (Arulo) | 3.6 | 0.56, 19.8 | futuristic |
| `mixkit-299` | Lil Sky Beats (Arulo) | 3.8 | 0.48, 32.1 | reflective, many 808 slides |

Vary the beat across reels. `music_lib.py list` prints the measures. No lyrics or producer tags: whisper (large-v3-turbo) on all 10 returned only the filler it loops on
instrumentals ("Bye.", "Thank you.", "so"). Real words would come out varied.

Adding beats: add an entry to `library.json` (id `mixkit-<n>`, title, artist, url
`https://assets.mixkit.co/music/<n>/<n>.mp3`, licence fields, tags), then `music_lib.py fetch` downloads it and
measures its grid and trap measures. Keep it only if it measures as trap and the spectrogram agrees. Check the grid before trusting it:
`grid_conf` >= 2 and the hats or 808 should start on the downbeat. Any file you have the rights to works the same way: put it in `~/.cache/reel-editor/music` under the entry's id.

## Licence

Mixkit Stock Music Free License, read in November 2026 at https://mixkit.co/license/#musicFree (read it yourself before relying on this summary): free for commercial and
non-commercial projects, no attribution.
- Allowed: social media video posts, online marketing ads, podcasts, YouTube.
- Not allowed: CDs/DVDs, TV and radio broadcast, video games; remixing a track or putting it in a music-only
  track; claiming it as your own; registering it with Content ID or any rights-management service.
- The files can't be handed on inside a tool or template, which is why they aren't here.

A baked-in beat replaces adding a trending sound in the app. Do one or the other, never both.
