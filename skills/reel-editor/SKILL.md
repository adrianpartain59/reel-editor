---
name: reel-editor
description: Turns raw talking-head phone takes into a finished, high-retention Instagram Reel, TikTok or YouTube Short in one of three formats, Drawn Roadmap (the default, a number counting up in the hook, then a hand-drawn canvas with one drawing per step), Talking Head (word-synced captions, app mockups and screen recordings on the word, titles, transitions, sound effects, music) and Split Screen (drawn canvas over the face). Cuts to the speech, sets loudness, makes hook variants, cover, post copy and QA. Use it whenever someone drops in clips and wants a reel, short or TikTok edited ("edit my reel", "here are my takes", "cut this down to where I'm talking", "add captions", "make it engaging", "overlay the app", "draw the steps", "split screen"), sends a reel whose style they like ("make it cinematic", "edit it like this"), or wants a list, roadmap or process drawn, even if they never say "skill". Not for long-form video, AI-generated footage, or designing real app screens.
---

# reel-editor

Edits someone's phone takes into a reel that holds attention: face first, words on screen the moment they are said,
the thing being talked about shown on screen while it is talked about, and something changing every second or two.
Everything runs locally and costs nothing: whisper.cpp for word timings, macOS Vision for face position, headless
Chrome for mockups, Pillow for compositing, a synthesized sound pack, ffmpeg for the rest.

The scripts do the mechanics. Your job is the editor's judgement: which takes to keep, what to show and when, which
words deserve a punch title, and checking the result with your own eyes before anyone else sees it.

## The user's own rules come first

Read `~/.config/reel-editor/preferences.md` before planning, if it exists. Those are this user's rules and they win over
everything in `references/`. When the user corrects how they want reels made, add it there (the date, the rule, and why),
never to this skill's files: an update would overwrite them. If the folder has `rooms/`, those are their saved rooms
(references/rooms.md).

## Formats, looks and art styles

**Format** is the kind of reel:

| Format | What it is | How |
|---|---|---|
| **Drawn Roadmap** (the default) | an edited hook with a number counting up on a graph, then a hand-drawn canvas the camera flies through, one drawing per step, the face cut back in at a few moments, a beat that drops on the number | `references/drawn-roadmap.md`. Its own scripts and no plan.json; steps 1, 2 and 6 below (takes, cut, deliver) are shared. Read that guide and `references/sketch.md` before planning |
| **Talking Head** | the takes with captions, phones, titles, transitions and sound effects | steps 3 to 5 below: plan.json, compose, mix, qa |
| **Split Screen** (not Talking Head's `split` layout) | the face full frame for the hook (text hook, blurred cards popping in), the intro and the outro (follow card); the hand-drawn canvas over the face for the points; captions with the word being said in yellow; almost no effects, no music, no grade | `references/split-screen.md`. Its own scripts (`split_cut.py`, `split_reel.py`, `split_thumb.py`) and no plan.json. Build it end to end without asking |

Pick the format without asking:
1. They name one or describe one ("draw the steps", "split screen", "just captions"): that one.
2. They ask for something only Talking Head does (app screens, phones or recordings shown on the word, titles, transitions, Cinematic or Bright): Talking Head.
3. Otherwise: Drawn Roadmap. It needs at least two points to draw and a number said in the hook. A take without both can't carry it, so make a Talking Head and say why in one line.

**Look** is a Talking Head's grade, captions, motion and sound: **Cinematic** (`"style": "cinematic"`, its default) or **Bright** (`"style": "bright"`, only when
asked). `references/looks/`.

**Art style** is how drawn things look: **Sketch** (the default, and the only one with an engine for a whole reel), **Stick Figures**, **Blueprint** or
**Neon**. One per reel. `references/art-styles.md`.

## Inputs

- **Clips.** Any phone video. Vertical 1080x1920 is ideal; anything else is cover-cropped to 9:16.
- **Which clips are hooks.** Each hook clip becomes its own variant (`h1`, `h2`, ...) sharing one body, so the
  user can A/B hooks. If they don't say, the first clip is the hook.
- **A rough transcript.** It tells you the intended flow, so you can spot retakes, flubs and missing lines.
  If they give none, the transcript from ingest is the flow.

Work in a project folder next to the clips: `<clips folder>/reel-<slug>/` unless the user names another place.
Scripts live in this skill's `scripts/` folder; run them with `python3 <skill>/scripts/<name>.py`.

## Workflow

### 1. Ingest
```
python3 scripts/ingest.py PROJECT --hook HOOK1.MOV [--hook HOOK2.MOV] --body B1.MOV B2.MOV ... --slug short-name
```
Body clips go in speaking order. File names from an iPhone (IMG_0001, IMG_0002 ...) are recording order, which is
usually speaking order, but confirm against the transcript. Ingest takes about 10 s per clip.

Then read `work/transcript.txt` and look at `work/clips.jpg` (the red dot is where the face was found).

### 2. Choose the takes (`selects.json`)
`selects.json` lists every speech chunk as `[clip, in, out]` in source seconds, already stripped of breaths and
silence. Compare the chunk text with the user's transcript and edit the list:
- Repeated line (a retake): keep the last complete, clean take, drop the others. People re-record because the
  earlier one was wrong.
- False starts, "wait, let me redo that", off-script asides: drop them.
- A chunk that starts or ends mid-word: nudge its `in`/`out` by 0.05 to 0.15 s.
- A line recorded later that belongs earlier (a pickup): move its chunk to where it belongs, and say you did.
- Missing line from the script: tell the user rather than inventing around it.

If nothing needs changing, leave it alone. One long take with many retakes: `scripts/utterances.py` first. Then cut:
```
python3 scripts/cut.py PROJECT
```
This renders each part (every hook and the body) at 30 fps with the CC pass (per-clip white balance, a gentle S-curve and a subtle look; `"cc": false` in plan.json turns it off), re-transcribes it and writes
`work/timeline.txt`: every word with an index (`w12`). You reference those indices in the plan, so timings land
on the word itself and survive small re-cuts. Name hook variants in `selects.json` (`"namefirst"` rather than
`"h1"`) before cutting: the names become the output file names.

### 3. Plan the edit (Talking Head)
This is where the reel is made. Read `references/edit-playbook.md` first: it holds the house rules and the pacing,
hook, caption, overlay and sound rules. The ones that matter most: open on the face, full frame; the camera always
moving, subtly; sound effects only from the pack; everything animated, everything with a sound, everything intentional
(no decorative backgrounds or empty layouts), everything varied. Then:

0. **The look is Cinematic**, the default when plan.json has no `"style"`. Read `references/looks/cinematic.md`
   and `references/effects.md` before planning, and match the density of the worked example
   (`assets/examples/cinematic-plan.json`, its timeline is `cinematic-timeline.txt`). **Bright** is the plainer look: only
   when the user asks for it. If the user points at a reel they want to look like, follow "Adding a look from a
   reference reel" in the looks README: `scripts/analyze_ref.py` measures the reference, then you write the preset.
0b. **Drawn art over a Talking Head** uses one art style (`references/art-styles.md`).

1. **Mockups.** Decide what the viewer needs to *see* for each claim (a paywall, an onboarding step, a
   notification, a before/after). Start from the library: `python3 scripts/mockups.py --init PROJECT`, edit
   `PROJECT/mock/screens.html` (fictional brand, copy that fits the topic, new screens if none fit), then render
   every variant you need, plus `frame` if you overlay screen recordings:
   `python3 scripts/mockups.py PROJECT/mock/screens.html PROJECT/mock paywall-features "paywall-features&hl=3" ...`
   Look at `mock/_sheet.jpg`. Details in `references/mockups.md`.
2. **Write `PROJECT/plan.json`.** Shots (layouts and zooms), caption sections, punch titles, stickers, fx and
   extra sfx, per part. Schema and every option: `references/plan-schema.md`. A complete worked example in
   Bright: `assets/examples/paywall-plan.json` (its timeline is `paywall-timeline.txt`); in
   Cinematic: `assets/examples/cinematic-plan.json`.
   Sound effects for every visual event are added automatically from the look's table; add only the extra
   ones. In Cinematic, transitions, title animations and phone entrances are picked automatically
   when left out; pick them yourself where the moment calls for a specific one (references/effects.md).

**Room replacement (opt-in only).** Only when the user asks for it in this reel: add `"room"` to plan.json
(references/rooms.md). Never add it by default.

### 4. Preview, then look (Talking Head)
```
python3 scripts/compose.py PROJECT --variant h1 --preview 0.3,1.2,2.5,...
```
Pick 15 to 25 times that land on the beats you planned (the first second, each overlay, each punch, each sticker,
the last line). Open `work/out/h1/sheet.jpg` and check it like a viewer would: is the face clear in the first
frame, is every caption readable and not covering the mouth, does each mockup show the part being talked about,
is anything under the Instagram UI (bottom ~380 px, top ~200 px, right edge low down)? Then read
`work/out/h1/events.json`: `transitions` and `anims` (what was picked for each cut and title: does each fit its
words?) and `visual` (anything with `sound: false` moves in silence). Fix the plan and preview again. This loop
is cheap (seconds); a full render is not.

### 5. Build and QA (Talking Head)
```
python3 scripts/build.py PROJECT            # every hook variant; --variant h1 for one
```
Composites every frame (a plan with a contextual `bg` runs `segment.py` first: macOS Vision person masks,
about 2 minutes for a 60 s reel, once), mixes voice, SFX and the look's music bed (the voice kept as recorded in
stereo, SFX and bed calibrated against it, mastered to -12 LUFS, about -1.3 dBTP), writes `out/<slug>-<variant>.mp4`, a phone copy under 30 MB, a cover image if the plan has one,
and runs `qa.py`. A FAIL must be fixed before delivery. A WARN is a judgement call: fix it or say why not.
About 1 to 2 minutes per variant for a 40 s reel in Bright, 4 to 6 in Cinematic. Then look at `out/<slug>-<variant>-sheet.jpg` (one still
every 1.5 s) as the last visual check.

### 6. Deliver
- Send the phone copy (it fits mobile delivery) and give the full-quality path.
- With several hooks, say what differs between the variants and which you'd post first and why.
- Write `out/post.md` by `references/captions.md`: line 1 the plain search phrase, a numbered recap of the steps, one ask
  (a send ask by default), 3-5 hashtags, 30-90 words and under 500 characters, plus the cover path.
- Say what you could not check: you cannot hear the audio, so say the sound is level-checked by measurement only.
  `scripts/sfx_lib.py audition CAT --out file.m4a` makes a spoken catalogue of the sounds for the user to veto by ear.
- Note anything the user should do in the app: choose the cover frame, add a trending sound at 5 to 10% if they want
  music from the app instead (then render with no bed; a trending sound on top of a bed clashes).
- A specific beat: pick from the library (`references/music-library.md`, free-licence beats with measured bar lines), set it with
  `style_overrides.music.bed: "track:<id>"`, and send `music_lib.py audition` so the user can hear alternatives
  under their own voice. Re-running `mix.py` alone is enough when only the music changed (no re-render).

If only the audio needs redoing (a mix fix, a new SFX cue), skip the video: `cut.py PROJECT --audio-only`
(when the source audio handling changed), then `mix.py` and `qa.py` per variant.

### Revisions
Most notes ("show the paywall when I say 'this'", "hold it longer", "make it full-screen", "louder") are
plan.json changes: edit, preview the affected seconds, rebuild. Only a change to which takes are used needs
`cut.py` again; after a re-cut, re-read `timeline.txt`, because word indices after the change shift.
A correction about how they want every reel made goes in `~/.config/reel-editor/preferences.md`.

## Guardrails
- **Fictional apps on mockups**, never a real company's name, logo or look. A fake review on a fictional app is
  an illustration; on a real brand it is a fake review.
- **Compliant paywalls only:** price and billing period visible, trial terms stated if there is a trial, no
  fake countdowns or hidden close buttons. A reel showing a dark pattern invites "scam" replies.
- **Claims:** if the script states something as fact that the user's own data doesn't support, say so once,
  then edit what they recorded. It's their call.
- **Never publish or post.** Deliver files; the user posts. Never play audio or video on their machine unasked.
- **Reference reels are for technique.** Never copy their footage, music, logos or graphics.

## Requirements
macOS with Google Chrome, `ffmpeg`, `whisper-cli` (whisper-cpp) and a ggml model (found automatically, or set
`REEL_WHISPER_MODEL`), Python 3.9+ with Pillow and numpy, Xcode command-line tools for `swift` (face detection and,
for contextual backgrounds, person segmentation; without it, framing falls back to the frame centre), and Node 18+ for
Drawn Roadmap and Split Screen. If something is missing, run `python3 scripts/doctor.py`, which says what and how to get it. The sounds are synthesized
(`scripts/sfx_pack.py`). Fonts are macOS system fonts (SF Pro, New York, Apple Color Emoji). Technical gotchas behind the
scripts' design: `references/lessons.md`.
