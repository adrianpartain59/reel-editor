# Edit playbook

How to plan a reel that people watch to the end. Read before writing plan.json.

## House rules

Learned by editing real reels and fixing what was wrong with them. The user's own rules in
`~/.config/reel-editor/preferences.md` win wherever they disagree. HARD RULE = the scripts enforce it or QA fails it.

1. **HARD RULE: face first, full frame.** Every reel opens on the face, full frame (`lay: face`), with captions and
   nothing else on screen, for at least 0.8 s. No split, no phone, no title in that window. The face stops the scroll
   and makes the advice feel like it comes from a person. Never open on a mockup. Don't override this for a planned
   hook element: put the element after the first 0.8 s instead.
2. **Show the thing on the word.** When the speaker says "this paywall" / "like this", the overlay lands on that
   word ("this"), not before. Use the word index (`"t": "w6-0.04"`) so the slide-in finishes as they say it.
3. **First showing of each mockup is full-screen** (`fullpw`) and holds long enough to read: at least 1.5 s,
   ideally 2 to 3 s. Later showings of the same screen can be half-screen (`split`).
4. **Don't flicker overlays in and out.** Once a full-screen overlay is up, keep it until its natural exit
   (end of the sentence about it), then let it drop out (`exit`), rather than cutting to the face mid-thought.
5. **Comparisons change one thing.** When two mockups are compared (bad vs good), keep every part except the one
   being compared identical (same footer, same selector, same layout below the body). Otherwise viewers think the other
   differences are part of the advice.
6. **Captions highlight the important words;** punch titles for the one or two words per section that carry the point.
   In `classic`, caption styles vary through the reel; `cinematic` uses one.
7. **SFX audible but under the voice**, and the whole thing at a normal Instagram volume (the mixer does both).
8. **The voice must sound like the original recording.** No mono fold-down, no default denoise, no low-pass.
   Loudness is raised to Instagram level with gain and a light limiter only (qa.py checks the tone).
9. **Several hooks = several reels.** When the user hands over more than one hook, build one complete,
   separate reel per hook (h1, h2, h3), identical except for the hook. Never stitch hooks together and never
   pick one for them; they A/B test them.
10. **A look they like = a style preset.** When they point at a reel, they mean its production style: captions, SFX, shots,
    grade, pacing. Build or reuse a style preset (references/styles/) from a measured breakdown and re-edit a finished
    reel in it for a side-by-side, rather than tweaking one reel by hand.
11. **No decoration: every background and layout must carry content.** No made-up dark set, no bokeh, no empty letterbox. A
    background is only there to show something: the screen being talked about, a profile, a result (`bg` with a `why`).
    A letterbox only with something useful in its bars. Keep the real room otherwise.
12. **Everything animated, everything with a sound, everything intentional, everything varied.** No element appears or
    leaves without moving; every move has a sound; every move answers "why here"; no transition, title animation or
    phone entrance repeats back to back. references/effects.md is the menu; QA checks all four.
13. **HARD RULE: only the sound pack, each sound for its own job.** Sounds come only from the twelve pack categories
    (`assets/sfx/pack.json`), and each has usage rules that `audiomap.py` enforces (table: `references/sfx-library.md`):
    - **Pop = text appearing.** Every title, punch word, text sticker, banner and chat bubble pops, always.
    - **Whoosh = every transition and anything moving in or out.** It is the quiet background sound; use it freely.
    - **Riser = the hook only**, once, building into the payoff. **Shine (the loud ding) = a button visibly clicked
      for the CTA**, once: a `tap` sticker with `"cta": true` on a button on screen. A spoken CTA with nothing being
      clicked gets no ding.
    - **Typing = one key press per letter**, always, on the frame each letter appears (chat pills, typed titles).
      Single keys, rotating; never a typing burst laid over the line.
    - **Everything else only where it obviously belongs:** camera flash on an on-screen flash, flash + shutter on a
      freeze frame, glitch on a glitch effect, low hit on the big reveal (a drop) or a shake, page flip on a screen
      changing state, counting on a number counting, scribble while a note is drawn. Each has a minimum gap and a
      per-reel cap so it never repeats until it grates.
    - **Never altered:** no speeding up, slowing down or cutting a sound short. If it doesn't fit whole, it isn't
      used. Fewer effects beat effects used the wrong way. Scribble picks the file whose length matches the visual.
14. **The cinematic style is the house style.** Match the worked example's density (`assets/examples/cinematic-plan.json`,
    ~58 s), scaled to length: a transition on most shot changes (20 transitions, 13 kinds; hard cuts only for zoom cuts and
    next to very short shots); a phone on screen for every screen described, each entering differently (7 phones, 5
    entrances), with a tap per state change; 2 backgrounds that show the screen being described; 3 spotlight moments (hook
    payoff, the viewer's doubt with a neon icon, the recap list); 9 neon titles on the thumbnail phrases with 6 different
    animations; 2 handwritten notes; 4 drops; a notification; a glitch into the loop. Tune one reel with `style_overrides`.
15. **A beat under the voice, low.** The cinematic bed is `"trap"`: it resolves per reel (by slug) to one of the measured
    beats with a trusted beat grid (`TRAP_POOL` in scripts/common.py) at -14.5 dB, ducked 3 dB while the speaker talks, so
    the beat varies between reels and drops land on the downbeat. Pin one with `style_overrides.music.bed = "track:<id>"`;
    `music.bed: null` when the user adds a trending sound in the app. Until the beats are downloaded
    (references/music-library.md) a synthesized pad plays. "Trap" means hi-hat rolls and a ringing, sliding 808: pick by
    the measurements, never by a site's genre or mood tag.
16. **Photos the reel needs: ask, or generate.** Don't pull stock from the web on your own initiative. No person, logo or
    readable screen in a generated part, and label the reel as AI where the platform asks.
17. **HARD RULE: only the parts where the speaker is talking.** The speech map (`scripts/speechmap.py`) decides
    every cut from speech-band energy against each clip's own floor; `cut.py` intersects every select with it, cuts
    any pause over 0.20 s down to 0.13 s, and refuses to write a part with a gap over 0.25 s; `qa.py` re-checks
    the finished parts. Never hand-widen a select to get around it.
18. **HARD RULE: no breaths, no mouth sounds.** The speech map classes every 10 ms by shape, not just level: a stretch is
    speech only if it holds 40 ms of voiced sound; "s"/"f" and loud bursts join a word only within 0.15 s of it; a word may
    trail 0.12 s; nothing ever reaches back before a word, where the inhale and the lip smack sit (`--frames` shows the
    class of every frame). Never widen a select to win a sound back.
19. **No sound without a visible cause.** No key clicks unless text visibly types (`type` titles, chat pills); no ticks under
    scrambling titles; no neon buzz (it reads as a siren). When in doubt, leave a moment silent.
20. **App screens in a reel must look like a shipping app.** Every screen full to the tab bar with realistic data, drawn icons,
    a real tab bar and status bar, at the App Store size. The quality bar is in references/mockups.md.
21. **A riser under the hook.** Every hook gets a `risers` entry from 0 s peaking on the hook's payoff word (the reveal or the
    snap to the after), plus a `drop` at the same time so the swell lands on an impact. It plays under the voice the
    whole way; the one-at-a-time rule still governs every other effect.
22. **HARD RULE: the camera always moves, subtly.** No frame is ever a locked-off still. Face shots push in or pull out slowly
    (3% a second; compose alternates in and out when a shot has no `push`), phones drift, backgrounds drift. No shot
    zooms more than about 15% on its own; the big moves (smash, punch zoom, shake) stay for the beats that earn them.
23. **The CC pass stays gentle.** `cut.py` corrects each clip's white balance 70% of the way to neutral (a room keeps a little
    warmth) plus a gentle S-curve and a hint of teal/warm split. Full correction turns white walls grey-green and skin red.
24. **Every reel opens with the snap-out zoom.** Frame 0 is the face at 1.35x, blurred all over and streaked at the edges; it
    snaps to normal framing in 0.2 s and is sharp by about 0.13 s. On by default (`intro_zoom`, plan-schema.md); camera
    only, captions stay put. A 0.35 s zoom with no blur reads as too slow and too clean.
25. **Head tracking on every face shot, by default.** 0.45 s smoothing and a 1.12x floor, so the face stays put while the room
    moves and there is room to follow.
26. **HARD RULE: the text safe area; captions at the top.** Captions sit just inside the top of the head on face shots
    (following the head track) and in the top band on phones, b-roll and splits. Every caption, title, punch and text
    sticker goes through `paste_text`, which keeps its ink inside x 40-1040, y 220-1500 and out of the like/share column
    (x > 900 below y 1150). Put stickers (counters, icons, cards) where they don't cover the mouth: above the head, to
    the side, or on the chest.
27. **Graphics pop up; they don't take the screen.** An animated chart or graphic is a `clip` sticker (a dark rounded card of
    PNG frames) over the face shot, not a `broll` with the face bubble.
28. **Show the mystery when the speaker teases it.** A hook that holds back the answer shows a skeleton of the thing with a "?"
    on the tease.
29. **HARD RULE: every reel ends on the comment outro.** A `chat_pill` with the speaker's face types a short viewer comment over
    the last line ("looks so much better", "adding this to mine today"); keep it under ~28 characters so it fits the
    pill. compose adds one from plan `"outro_comment"` when a plan has none; QA fails a reel without it.
    `"outro_comment": false` leaves it out, only when the user asks.
30. **Pricing screens stay honest.** Price and period visible, trial terms if there's a trial, a close button. No countdown, no
    "one time offer", no "Try for $0.00".
31. **The voice keeps its air:** a +2.5 dB high shelf from 7.5 kHz is part of the voice chain. The 4:1 compressor holds its gain
    down through the "s" sounds after loud vowels and takes ~2 dB off 8-12 kHz. It lives in `assets/styles/cinematic.json`
    (`mix.voice_chain`); a reel never needs its own override for it.
32. **Room replacement only when asked.** `"room"` in plan.json swaps the room behind the speaker for another one
    (references/rooms.md). Never add it on your own initiative and never suggest it as a default. A reel with a generated
    room gets the AI disclosure when posted.

## The first 3 seconds
- First word within 0.6 s of the first frame (ingest already trims dead air).
- A caption on screen from the first word: most people start with sound off.
- The hook's key word gets a punch title or a sticker (red X on a "terrible", a green check on a "works").
- Optional: a `banner` sticker at the top with the promise of the reel in 3 to 6 words, for the first 2 s.
- With several hook takes, build each as its own variant; describe how they differ when delivering.
- Don't pay off the hook before 3 s. Instagram's skip rate counts swipes in the first 3 s; a before → after that
  completes at 1.75 s closes the gap while the viewer can still swipe for free. Tease it (the first flicker of change),
  land the full reveal at about 3 s.
- One text layer at a time in the first 3 s. A caption plus a glow title on top of a busy screen reads as clutter.

## Pacing
- Something visible changes every 1 to 2.5 s: a cut between zoom levels (`face` shots at z 1.0 / 1.12 / 1.2 /
  1.35 / 1.5), an overlay, a punch, a sticker. qa.py warns over 3 s.
- Cut on word starts, not mid-word: shot times are word indices.
- Zoom in for emphasis and conflict ("but this is WRONG"), zoom out to reset after an overlay.
- Alternate face shots and overlays; never two overlays of the same screen back to back with no face between.
- End within 0.5 s of the last word. No outro card; the last line is the call to action.

## Layouts: which to use when
| Layout | Use when | Notes |
|---|---|---|
| `face` | talking points with no visual, emotion, the hook, the CTA | `z` zoom 1.0-1.5; push-in is automatic |
| `fullpw` | the **first** time a screen appears, or the screen is the point of the sentence | holds >= 1.5 s, `enter` slide-up, `exit` drop-out |
| `split` | a screen the viewer has already seen, highlighting part of it, scrolling it | `focus` = which part of the phone sits in the safe area |
| `video` | the user's own screen recording, played inside the phone frame | needs `mock/frame.png` |
| `broll` | full-screen footage (a dev timelapse, a demo) with the face in a bubble | `src`, `src_in`, `speed` |

## Captions
Styles: `pop` (white caps, black outline, active word in the accent colour), `box` (black on white pills, active
word in a coloured chip), `serif` (italic serif, for quotes, reviews, inner voice), `neon` (glow), `word`
(one huge word at a time, for fast lists or a dramatic line), `cine` (the cinematic default). In classic, change style at
section breaks of the script (problem → why → fix → proof → CTA), roughly every 5 to 10 s. Accent colours carry meaning: red
for the wrong way, green for the right way, yellow/purple neutral.
- `keywords` in plan.json stay highlighted once said: the nouns and verdicts of the topic.
- Turn captions off (`null` section) while thought bubbles or a review card show the same words.
- Positions are automatic per layout and inside the safe zone; override with `capy` on a shot only if a caption covers the
  mouth or the important part of a mockup.
- On a bright background (a white shirt, a white wall) non-box captions get a dark rounded backing
  automatically. Still prefer `pop` and `box` over `serif`/`neon` for long stretches on a white shirt.
- Whisper mishears sometimes ("If you're onboarding, ask" for "If your onboarding asks"). Read the timeline
  against the user's script and correct captions with the part's `fix` map; never leave a wrong word on screen.

## Punch titles
One or two words, huge, tilted 3 to 6 degrees, with a smaller line under them if the sentence needs it. Use
them for the verdict words: TERRIBLE, WRONG, $20, DO THIS INSTEAD, MILES BETTER, 3X. At most one every 4 to 5 s,
or they stop meaning anything. Red for bad, green for good, white for neutral.

## Stickers and fx (what fits which moment)
| Moment | Sticker / fx |
|---|---|
| Calling something bad | `red_x` on the mockup (`space: phone`), `fx: shake` or `rgb` glitch |
| Calling something good | `check`, `fx: flash` |
| Viewer's inner voice / objections | `thought` bubbles, stacked left/right, captions off |
| Social proof | `review_card` (stars fill one by one) |
| A number | `counter` (counts up), or a punch title |
| Pointing at part of a screen | `circle` (draws itself) or `arrow`, in `space: phone` |
| Emotion / tone | `emoji` (🤔 doubt, 🔥 works, 💸 money, 🚀 growth, ❌, ✅), wiggles by default |
| Reveal | `fx: flash` at the start of the reveal + `zoom` |

## Sound
Automatic: every event that the style's `sfx` table names gets its pack sound (references/sfx-library.md). Add by hand only
moments the plan can't infer, such as animations inside a rendered `broll` track. Don't stack cues within 0.1 s.

## Instagram safe zones (1080x1920)
The app draws over the video: top bar to about y 200, username/caption/audio from about y 1540 down, the
like/comment/share column at the right edge from about y 1150 down. compose enforces the text safe area
(rule 26) by moving or shrinking any text that would cross it, so a custom `y` can't put words under the app's UI. Still
place things deliberately: a title moved by the clamp may land somewhere you didn't plan.

## Mockups in the story
- Make the mockup match what is said, word for word: if they say "the features they're going to get", the
  features list is on screen; if they say "$20", the $19.99 price is circled or outlined.
- Use highlight variants (`&hl=3`) to walk through a list as it is spoken.
- Show the bad version and the good version with the same chrome (rule 5).
- If the user has real screen recordings or timelapses, prefer them (`video` / `broll`) for "here's what we
  built" moments; mockups are for illustrating advice.

## Common mistakes
- Overlay before the word that introduces it: the viewer sees it without knowing why.
- A caption sitting on the mouth in a tight zoom (move it with `capy` or zoom less).
- Highlighting every word: keywords lose meaning; 1 to 2 per sentence.
- Long full-screen overlay with nothing moving: add a `circle`/`arrow` or a highlight swap halfway.
- Forgetting that word indices shift after a re-cut.
