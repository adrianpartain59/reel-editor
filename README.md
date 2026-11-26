# reel-editor



https://github.com/user-attachments/assets/f22f6d04-c352-481f-9c6f-5d3ca7e3079f




A Claude Code skill that edits raw talking-head phone takes into finished Instagram Reels, TikToks and YouTube Shorts.

Drop in your clips and say "edit my reel". Claude picks the takes, plans the edit and checks its own frames; the scripts
do the cutting, captions, motion, sound and quality checks. Everything runs on your Mac and costs nothing.

![Four drawn scenes from a Drawn Roadmap](docs/roadmap.jpg)

*Four scenes from a Drawn Roadmap. The default format is the Split Screen (below).*

## What it does

1. **Cuts to the speech.** Finds where you're actually talking (not room hum, breaths or lip smacks), drops flubs and
   retakes, and refuses to leave a pause over a quarter of a second.
2. **Captions every word as you say it**, above your face and clear of Instagram's buttons.
3. **Shows what you're talking about on the word you say it:** vector graphics with real stock footage, app screens
   rendered as phones, your own screen recordings, b-roll, handwritten notes, neon titles and icons.
4. **Keeps it moving:** head tracking, slow pushes, 22 transitions, 12 title animations, none repeating back to back.
5. **Does the sound:** your voice kept as recorded in stereo, effects that each have one job, a beat that drops on the
   reveal, mastered to -12 LUFS.
6. **Makes one reel per hook** so you can test them, plus a cover, the caption and a phone-sized copy.
7. **Checks itself:** frame count, loudness, dead air, pacing, silent moves, repeated effects, and the voice against the
   original recording.

## Formats

Say the name of the one you want. If you don't, you get a Split Screen.

| Format | What you get | Say |
|---|---|---|
| **Split Screen** (default) | Graphics above your face from the first frame, under an Instagram-style text hook: dark cards, charts, phones with a made-up app and real stock footage, one clear focus at a time, landing on your words. Your face goes full frame for your intro and the outro (a follow card), your footage sits in a rounded card for the points, the word you're saying is highlighted, and a soft electronic bed runs underneath | "edit my reel", "make it a Split Screen" |
| **Drawn Roadmap** | A number counts up on a graph in the hook, then a hand-drawn canvas the camera flies across, one drawing per step, landing on your words, with your face cut back in for the lines that need it | "draw the steps", "make it a roadmap" |
| **Talking Head** | Your takes with captions, app screens as 3D phones, titles, transitions and sound effects | "make it a Talking Head", "show the app when I say it" |

![A Talking Head: captions, a spotlit title, a phone with a tap on it, a plan screen, the typed comment at the end](docs/standard.jpg)

*A Talking Head, from the test reel in this repo. The speaker is drawn, so nobody's face is in it.*

### Looks for a Talking Head

| Look | What you get |
|---|---|
| **Cinematic** (default) | Contrasty grade, glowing titles, 3D phones, a transition on most cuts, a beat that drops on the reveal |
| **Bright** | Your room bright and natural, bouncy cuts, mixed caption styles, no music |

### Art styles for the graphics

**Vector** is the Split Screen's: flat graphics on near-black, heavy titles with one word on a red or green pill, dark cards, bar charts,
numbered lists, phones with a made-up app (the question and blank answer rows) and real stock footage in rounded frames. No gradients,
one main thing per picture. Free stock clips come from Mixkit (Stock Video Free License only) through `scripts/stock.py`.

The drawn styles:

| **Sketch** | **Blueprint** | **Neon** | **Stick Figures** |
|---|---|---|---|
| Hand-drawn on dark | White technical lines on blue | Glowing tubes on black | White marker on black |

![The four drawn art styles moving, left to right: Sketch, Blueprint, Neon, Stick Figures](docs/styles.gif)

Sketch draws whole reels (the Drawn Roadmap, and a Split Screen when you ask for the drawn look). The other three come with sample
scenes to build on.

## Install

```bash
claude plugin marketplace add adrianpartain59/reel-editor
claude plugin install reel-editor@reel-editor
```

Or copy `skills/reel-editor/` into `~/.claude/skills/`.

It needs a Mac (it uses Apple's Vision framework and system fonts) with:

```bash
brew install ffmpeg whisper-cpp node
python3 -m pip install pillow numpy
xcode-select --install
mkdir -p ~/.cache/whisper.cpp && curl -L -o ~/.cache/whisper.cpp/ggml-large-v3-turbo.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
```

and Google Chrome for the app mockups. Node draws the Split Screen and the Drawn Roadmap. The whisper model is 1.6 GB; a smaller one works
with less exact word timings (`REEL_WHISPER_MODEL` points at any ggml file). Ask Claude to "check the reel-editor setup",
or run `python3 skills/reel-editor/scripts/doctor.py`, to see what's missing.

## Use

> Edit my reel. HOOK_A.mov and HOOK_B.mov are two hooks, TAKE_1 to TAKE_4 are the body. Here's the script: ...

> Show the onboarding screen when I say "like this", and hold it longer

> Here's the full take, edit my reel

> Here's a ten-step list I recorded, draw the steps

> I like how this reel is edited, make mine look like that (screen recording attached)

A 40 s Talking Head takes about 5 minutes to render.

## Your own rules

Tell Claude how you want your reels and it keeps your rules in `~/.config/reel-editor/preferences.md`. They win over the
skill's defaults and survive updates. Your own looks go in `~/.config/reel-editor/looks/` and rooms for background
replacement in `~/.config/reel-editor/rooms/`.

## Sound and music

The sound effects are synthesized by `scripts/sfx_pack.py`, so there is nothing to license. You can put your own recordings
over them ([how](skills/reel-editor/references/sfx-library.md)).

No music is in this repository: the licences let you use the tracks in your videos but not hand the files on.

**The Split Screen's bed** is "Minimal IDM Ambient Electronic" by Musinova on Pixabay (Pixabay Content License: commercial use,
no credit). Pixabay doesn't allow scripted downloads, so get it yourself once: open
[its page](https://pixabay.com/music/upbeat-minimal-idm-ambient-electronic-373348/) in your browser, read the licence, download the MP3
and save it as `~/.cache/reel-editor/music/pixabay-373348.mp3`. Every Split Screen then has it under the voice, levelled for a phone
speaker. Without it a Split Screen renders with no music and says how to get it; `"music": false` in `split_reel.json` turns it off.

**The beats** for a Talking Head and a Drawn Roadmap come from Mixkit: `python3 scripts/music_lib.py fetch` downloads your own copies
(33 MB). Until then a Talking Head plays a synthesized pad and a Drawn Roadmap has no beat.

## Scripts

All of them also work without Claude.

| Script | Does |
|---|---|
| `ingest.py`, `utterances.py` | Finds the speech, transcribes it with word timings, finds the face |
| `cut.py`, `speechmap.py` | Cuts the takes to the speech, white balance, gentle grade |
| `mockups.py` | App screens as transparent phones, from one HTML file |
| `compose.py`, `fx.py` | Renders a Talking Head from `plan.json`, or stills of any moment |
| `mix.py`, `audiomap.py`, `sfx_pack.py`, `music.py` | Voice, effects, beat, master |
| `qa.py`, `audio_check.py` | The checks |
| `countup_hook.py`, `canvas_body.py`, `canvas_sound.py` | Drawn Roadmap |
| `split_cut.py`, `split_reel.py`, `split_thumb.py` | Split Screen |
| `stock.py` | Finds free stock video on Mixkit (Free License only) and downloads the clips you pick, with their credits |
| `analyze_ref.py` | Measures a reference reel: pacing, zooms, loudness, caption sheets |
| `room.py` | Replaces the room behind you, no green screen |

## Test it

```bash
tests/run.sh
```

Makes takes of a drawn speaker with a macOS voice (one has a flub in it), edits them into a reel, runs the checks and
draws the starter scenes. About 4 minutes.

## Good to know

- Built for vertical talking-head video of one person, face and shoulders in frame, in English.
- Claude can't hear. Sound is checked by measurement only, so listen before you post.
- The app mockups are for fictional apps. Don't put a real company's name or a made-up review of a real product on them.
- Macs only: fonts, face finding and person masks come from macOS.

MIT licensed. The drawings use [@napi-rs/canvas](https://github.com/Brooooooklyn/canvas) (MIT) and open-licence
Google fonts, installed from npm.
