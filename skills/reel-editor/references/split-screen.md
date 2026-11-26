# Split Screen (the default format)

The user hands over the full video and asks for a reel, or says "split screen". Build it end to end and send the finished reel. Ask nothing
first: every choice below has a default. Not to be confused with `split`, a half-phone layout in a Talking Head's plan.json.

**The graphics are in the Vector art style** (`vector-style.md`): dark cards, red tags, glowing lines, and real footage and phones in the
picture. The hand-drawn canvas ("Drawing the panel (Sketch)" below) is for when the user asks for the drawn look. `split_reel.py` reads which
engine a reel's scenes.js uses; nothing else changes.

## The edit, part by part

| Part | What is on screen | When |
|---|---|---|
| First 0.2 s | the whole frame snaps out from 1.35x, blurred | always |
| Hook | **split screen from the first frame** (`split.hook_out`, below): the speaker's footage in the card, the Instagram text hook over the top of the graphics (black bold on white, caps, two lines at most), and under it the hook's pictures, one focus at a time, changing every 1.5 to 3 s with the words. A list named in the hook is a numbered list in the panel, rows not reached blurred (`p.list`), not the cards beside the face | from 0 to the end of the hook line |
| Intro | full frame, captions only, while the speaker says who they are and names their app; its App Store page pops in above the head with one pop sound. No intro: the split runs on | from the first sound of the name to the end of that claim, about 2.5 s |
| Points | split screen again, **card layout** (below): the graphics over the top 65%, the footage in a rounded card at the bottom, 740 wide, no cut-out. The footage shrinks into the card as the canvas slides down | starts about 0.35 s before the first point |
| Recap | the same names, now readable, as a numbered list on the canvas, each row lit in turn | on the sentence after the last point ("pick one of these") |
| Outro | full frame again. The follow card drops in on top; the button is tapped on the word "follow" and turns to "Following"; a yellow line appears when the speaker says what they're making | card in 0.15 s before "remember to follow" |
| Captions | all the way through. White SF Pro Semibold, one line, two to five words, the word being said in yellow. Full shots: under the chin. Split: just above the head, over the card. They fade across the move | every word |
| Sound | the voice; the default bed under it from the first frame, once downloaded (Musinova's "Minimal IDM Ambient Electronic": 13 dB under the speech, measured above 150 Hz, dipping 2.5 dB while the speaker talks, fading out on the last frame; `music-library.md`, "Curious underscore"); one pop on the App Store page. No other effects | -12 LUFS |
| Picture | raw. No grade | |

Everything in that table is fixed in the scripts. A reel changes the words, the times, the pictures and the names.

## Steps

`S=<this skill>/scripts`, project `<clips folder>/reel-<slug>/`. Cutting takes 2 to 4 minutes and a render 2 to 8: run both in the background.

1. **Takes.** `python3 $S/ingest.py PROJECT --body RAW --slug name`, then `python3 $S/utterances.py PROJECT RAW`. The kept take of each line is the last
   complete one before the speaker moves on; one clean take is every utterance in order. If the user has a script, it gives the order and the on-screen
   text. Write `selects.json`: `{"hooks": {}, "body": [["b1", in, out], ...]}`, one entry per kept utterance in speaking
   order, about 0.08 s of room each side. A scripted line that was never said stays out; say so.
2. **Cut.** `python3 $S/split_cut.py PROJECT`. It cuts every pause, tightens every clip to the word, times the words and lists the edges. The last line must
   start "every clip starts on the word, no stray clicks". A FIX line: set that clip's in or out by hand (the raw second of the first sound, minus 0.04) and run it
   with `--as-is`. A CHECK line is a word whisper heard in the raw take and lost in the cut: put it back with `add` (step 4). A long clean take can come out as 40 clips; that's right.
3. **Set up.** `python3 $S/canvas_init.py PROJECT split` writes `split_reel.json` and `canvas/scenes.js` from the Vector starter (and installs the drawing
   library the first time); `canvas_init.py PROJECT split sketch` starts from the drawn canvas instead. Always start from these, never from another reel's
   files: its `times`, `shots`, `cap_y` and `store` would silently carry over. Fill split_reel.json (below), caps `[]` for now.
4. **Captions.** `python3 $S/split_reel.py PROJECT words`, then `draft`: paste into `caps` and fix the breaks by hand. A line is a thought ("This is like
   a timer", not "This is like a / timer but for"). `fix`, `join` and `add` repair what whisper misheard or lost. `caps` lists the lines with their widths and how long they show.
5. **Footage, then draw.** Pick the real clips (`vector-style.md`, "Real footage": `stock.py search` in the background, then `get` once the user knows
   what will be downloaded). One cell per point, two when the point has two ideas (below). `PANEL_H=1240 node canvas/scenes.js sheet 12.7,13.6,... work/sheet.jpg`
   as you go, then `check`, then a `still` of every finished cell.
6. **App Store page**, when the speaker names their app: `python3 $S/split_reel.py PROJECT store APP_ID` fetches today's name, icon and rating. The id is the number in
   the app's App Store link.
7. **Preview.** `python3 $S/split_reel.py PROJECT check` until it prints OK (a `note` is something to look at, not to fix), then `preview` at the first second, every pop, both moves, one per cell, the tap
   and the last frame. Look at it.
8. **Render.** `python3 $S/split_reel.py PROJECT render` in the background. It prints frames, loudness, the music it used (or how to get the default bed)
   and any line whisper can't hear, and writes `work/final_sheet.jpg`: look at every still.
9. **Thumbnail and caption.** `split_thumb.py PROJECT candidates`, pick a face, set `thumb`, `make`, look at `work/thumb/check.jpg`. Caption by
   `captions.md` in `out/post.md`.
10. **Deliver.** Send the phone copy (under 30 MB) and the thumbnail, give the full file's path, the caption in the message, what you could not
    check (you can't hear it), any line the user's data doesn't support, whether the music bed is in it, the stock clips used (`media/credits.json`),
    and anything you left out. Never publish.

## Several hooks, one body

One project per hook, each with the hook as its first clip and the same body clips after it. Cut all of them with the same body selects (`--as-is`), so
every body frame is identical; then write one clean body word list and give it to every version, shifted by the hook's length, and draw the scenes once
in a file that takes that length (`module.exports = OFF => make({...})`, each cell `at: at + OFF, shift: -OFF`). Same text hook, cards and captions in
all of them, so only the spoken hook is tested. One thumbnail. **For Instagram trial reels that is too alike**: Instagram can limit a trial that repeats
content already shared, and does not say how much has to differ. Give each version its own text hook, cover and, when there is one, a different take of
the next line, and post one a day.

## The card layout

`"layout": {"kind": "card"}` (the starter has it): in the split the footage sits in a rounded card at the bottom, inset from the sides, and the graphics
get the rest of the height, so they can be bigger and easier to read.

- Defaults: `top` 1200 (the card's top edge: the card is 37.5% of the screen), `inset` 170 (740 wide), `r` 46, `z` 0.72 (the footage's scale, the least
  that still fills that width), `over` -34 (the hair stays just inside the card), `cutout` false. A head poking out of the frame distracts and takes up room.
- The other card look: `"inset": 60, "z": 0.9, "over": 70, "cutout": true`, a wider card with the head cut out over its top edge. The cut-out is
  `segment.py`'s person mask (made once per cut, about 3 minutes for 95 s), through the same camera as the footage, kept only inside an ellipse round the
  head from the face track and no higher than the hair should reach (Vision can mark a ceiling light touching the hair as person; the head shape
  separates it). It roughly doubles the render time.
- **The canvas is 1080 x 1240** (`PANEL_H`, set by `split_reel.py`; both engines export `PH` and `DB`). The picture runs down to `DB` 990; the caption
  sits under it, above the head. `check` warns at these edges.
- `"layout"` left out is the seam layout: a 764-high canvas on top and the face under it, the caption on the seam.

## Opening in the split (the default)

The hook gets as much movement as possible, and the face comes in once the speaker starts on who they are and their app. Set `split.hook_out` to the
moment the hook line ends (just before "If you're new here", say): the reel opens in the split, goes full frame for the intro (App Store page as
before) and comes back to the split at `split.in`. With no intro, set `hook_out` at or after `split.in` and the split runs on from the first frame.
A reel without `hook_out` opens on the full face (`check` notes it). Then:
- The text hook stays Instagram's own white box (edit-playbook rule 33, never the graphics' type). It sits over the top of the panel from frame 0
  (y 186 to 466 for two lines), so the hook's pictures go below it, y 500 to 990, with no titles of their own. The snap-out zooms the whole frame.
- Movement, but one focus at a time (edit-playbook rule 34): one phone going through the app, then one bar chart, then a comparison on a scale; never
  all of them at once.
- The first body cell after the full-frame stretch takes `cut: true` (no push: it is already there when the panel slides back in).

## What to decide from the take

| Choice | Default |
|---|---|
| Text hook | the script's on-screen text for the hook; otherwise the spoken hook cut to 4 to 7 words. Caps, two lines of similar width. Black on white; `hook.style: "black"` for white on black |
| Cards (face-first hook only, a reel without `hook_out`; in the split opening a list is a numbered list in the panel) | when: the line that says how many there are. Blank boxes before the speaker has said what they are read as a mistake. What: the points in order, two words each where you can (`["meal", "planning"]`), 3 to 7 of them. No list in the video: the two to five things it covers. One idea only: `"cards": []` and `face_x` 540 (the starter's) |
| `hook.end`, `hook.out` | the last word of the hook's end; 0.25 s before it |
| `split.hook_out` | the end of the hook line (above) |
| `split.in` | 0.35 s before the sentence that opens the first point. Up to about 8 s of full-frame talking before it (who they are, why listen). Longer than that: open the split earlier and draw what is said in cells with no number |
| `split.out` | 0.23 s before the outro's first sentence, which starts on a clip of its own. The outro is the last full sentences, at least 2.5 s of them |
| Recap | from the first sentence after the last point that is about all of them ("pick one of these"). If there is none, the last 1.5 to 2.5 s before `split.out`. Advice with its own content after the last point gets its own unnumbered cell first |
| App Store page | the speaker's own app, the first time they name it, only while the shot is full frame. `in` = the first sound of the name (check the waveform, whisper is up to 0.3 s off), `out` = the end of the claim. Never a subtitle or screenshots. Other apps get no page |
| Follow card | `name` is the display name to show. `in` 0.15 s before "remember to follow", `tap` on "follow", `line` = what they're making next in three or four words, `line_at` on those words. No "follow" in the take: show it over the last sentences, 2.2 s or more before the end, `tap` 0.75 s after `in`, no `line` |
| Music | the default bed (`music-library.md`); `"music": false` when the user wants to add a sound in the app instead |
| Thumbnail words | the same idea as the text hook: on top the count in yellow and the thing in white, two to four words; under the chin the rest of the phrase |
| Numbers on the canvas | the ones said, nothing else |

## split_reel.json

Times are seconds of the cut. Everything not listed is fixed.

| key | what it is |
|---|---|
| `slug`, `scenes` | output name; the scenes file (`canvas/scenes.js`) |
| `layout` | `{"kind": "card"}` plus any of `top`, `inset`, `r`, `z`, `over`, `cutout` (above). Left out: the seam layout |
| `hook` | `end`, `out`, `text` (list of lines), `style` (`"black"` for white on black), `cards` (list of one- or two-line names), `first` 0.86, `every` 0.18, `cards_out` (when they leave; left out, with the text), `face_x` (445 puts the face left of the cards; 540 without cards). For cards on a later line set `first` to the second of the count word and `cards_out` to 0.35 s before `split.in`; the shot they sit in moves the face left, the hook stays centred |
| `split` | `hook_out` (the end of the hook line: the reel opens in the split and goes full frame for the intro), `in`, `out` |
| `store` | `app` (App Store id), `in`, `out`, `name` (only to shorten the listed name). Leave the key out for none. Its pop is automatic |
| `follow` | `in`, `tap`, `name`, `line`, `line_at`, `photo` (second to take the avatar from) |
| `music` | left out: the default bed if downloaded, none if not. `false`: none. `{"file": "media/music.mp3", "start": 0, "level": -13, "duck": 2.5, "pocket": -4, "fade_out": 1.5}`: a file in the project (or `"lib:<name>.mp3"` in `~/.cache/reel-editor/music`), from `start` seconds, `level` dB under the speech (both measured above 150 Hz, what a phone plays), `duck` dB lower while the speaker talks, `pocket` dB at 2.4 kHz where the consonants are. It loops if the reel outlasts it |
| `caps` | every word said, once, in order, as a list of lines |
| `fix` | `{"Notion": "notion", "2": "number two"}`: a heard word and what shows (one may become two) |
| `join` | `[["life", "hacking", "lifehacking"], ["It", "costs", "costs"]]`: a run of heard words and, last, the one that shows |
| `add` | `[["So", 77.18]]`: a word whisper lost, and its second of the cut |
| `times` | `{"w188": 47.43}` moves one word's highlight (numbers from `words`) |
| `pops` | seconds for the pop sound; left out, the App Store page's `in` |
| `shots`, `cap_y`, `room` | by hand only: `[t0, t1, zoom0, zoom1, face_x]` per full shot; `[[from, y], ...]`; `"room": false`. Left out, zooms and caption heights come from the face, and a shot framed too close for the cards or the thing above the head is moved down and left with the empty wall stretched to fill (`check` says so; look at it) |
| `thumb` | `t`, `top` (`[["3 HABITS", "yellow"], ["THAT STICK", "white"]]`), `bottom` |

## Drawing the panel (Sketch)

For a reel in the Vector style, `vector-style.md` has the look, the frame and the pieces. What follows is the hand-drawn canvas
(`canvas_init.py PROJECT split sketch`). The look, colours and what-to-draw table in `sketch.md` all hold. The frame is different: drawn in cells,
1080 x 1240 in the card layout, 1080 x 764 in the seam layout.

- **Header row** (`head`): the yellow #n pill and the point in two to five words, written on as it is said, one key word in colour. It shrinks to fit.
- **Drawing**, card layout: from y 340 to `DB` 990, labels at y 950, phones about 260 x 520, bars off a baseline at y 880, figures about 460 tall.
  Seam layout: between y 325 and 715, labels at y 684 to 702. Both: x 40 to 1030. Fill it edge to edge, left to right in the order it is said: two
  or three pictures with an arrow between them, each about 220 to 400 wide. The starter's cells are sized for the seam layout: make them taller for the card.
- **Sizes** (seam layout; scale up for the card): labels 42 to 62, the number of the scene 96 to 118, words in a box 56 to 92, phone 224 x 376 with
  line 8, bars 120 to 136 wide off a baseline at y 648 to 694, box lines 7, a cross 17 with half-width 124 to 150, the arrow that carries the idea 15
  with head 54, connecting arrows 10 with head 38 to 40.
- **Time**: the first ink lands by the point's first word; something new at least every 1.5 s; a shape 0.1 s before its word, a written word on it. A cell lasts 3 to
  6 s, so a long point gets two, three or more cells with the same #n, one idea each.
- **Cells**: `{ id, at, draw }`, `at` = the beat's first word. The camera flies from 0.1 s before it to 0.36 s after; `fly: [t0, t1]` to start it earlier when there
  is a breath before the sentence, `shift` to move a whole scene after a recut. `recap: { at, first, names }` is drawn for you (short names: they shrink to fit).
  `head(c, t, null, ...)` is a header with no number.
- **Pieces** on `p`: `head, box, card, write, label, pill, bar, count, icon, star, tick, brackets, face, hatch, pop` plus the pen `S()`: `line, rect, circ, path, arrow,
  cross, phone, fig`. Call `S()` fresh for every shape, so shapes don't wobble when a new one starts. `pill` is as wide as its words; `p.wide(c, 'fixed bedtime', 52)`
  measures a label (about 0.55 x size per letter), so two labels side by side don't collide.
- Same mistakes as the canvas: words over an edge, a label under a line, a number run into its neighbour, a half-empty panel. `check` finds edges, gaps, long cells and words
  on words; only a `still` shows words over a line or a box.

## Where this differs from the edit playbook

- Rule 1 (face first, full frame; nothing but face and captions for 0.8 s): the reel opens in the split, the face in the card under the hook's
  pictures, with the text hook there from the first frame. Without `hook_out` it opens on the face and the cards wait for 0.86 s.
- Rules 12, 13 and 21 (a sound on every move, the riser): no effects except the App Store pop.
- Rule 15 (a beat): the curious underscore instead, once downloaded. `"music": false` for none; never add a trending sound on top of it in the app.
- Rule 23 (the CC pass): raw picture.
- Rule 26 (captions at the top): under the chin on full shots, just above the head over the card in the split.
- Rule 29 (the typed comment outro): the follow card replaces it.
- Still in force: the snap-out, head tracking, the slow push, no breaths or mouth sounds, only the parts with talking, the safe area, rules 33
  (the text hook is Instagram's own text) and 34 (signal over noise).

## Mistakes already made once

- **A mouth click as the start of a clip.** The speech map kept it because the room tone after it read as a voice. `split_cut.py` fixes the start and flags clicks; its
  last line is the proof. A clip can also open on silence with no click, which is the same fix.
- **Word times up to 0.3 s off**, at clip starts and mid-sentence. `split_cut.py` times words by whisper's DTW alignment and puts every clip's first word on the
  sound (within 0.1 s of the waveform on a test reel). Use `times` for the odd one left.
- **Copying another reel's settings**: its `times`, `shots` and App Store page ride along unseen. Start from the starter files.
- **A take framed too close**: the cards land on an ear and hair in the text hook, and panning can't help at zoom 1.00. The builder makes room.
- **Captions sliding over the face** when the screen splits: they fade.
- **The follow card and the captions in the same place.** The card is at the top; keep it there.
- **A zoom that pushes hair into the text hook or a card.** `check` measures it.
- **A number misspoken in the only take.** It can be rebuilt from the speaker's own words in the same take: cut picture and sound together so the lips
  match, put every join in the silence before a hard consonant (k, b, t), take a word no longer than its vowel (0.1 s too much of the next word changes
  what is heard), and run two whisper models on the result. Tell the user the line is rebuilt and ask them to listen. Short clips transcribe as
  "Okay." or "Thank you.", so fix the word list by hand.
- **A shoulder cut off by the frame** drew a straight white line on the thumbnail. `thumb_split.js` fades it now.
- **A story with no numbered points**: every cell gets `n: null` and its own header, a cell per sentence or two, and the wrap-up line becomes the recap
  with `every` set so each name lands on its part of the sentence. `check` asks for a recap, so a story reel needs one too.
- **One clip lopsided, left only.** A hand or a collar over one phone mic in the raw take: that clip's left-right gap jumped and the mics stopped
  matching. `check` notes any clip whose balance or match is off from the rest of the take. Listen to it, then write that clip's louder channel on both
  sides of `work/parts/body/voice.wav` (keep the original), EQ-matched and level-matched to the clips around it, and re-run only the audio
  (`import split_reel as S; S.setup(PROJECT); S.audio()`): the video doesn't change. One channel alone loses bass against a stereo pair (6 to 9 dB under
  125 Hz), so the EQ step isn't optional: match the clip's long-term spectrum to its neighbours and check it against the final mix.
- **A lamp in the thumbnail.** Vision marked a ceiling light above the head as part of the person, and the white edge drew round it as a floating
  blob. `split_thumb.py` keeps only the part of the mask joined to the face.
- **A music bed measured full band** sat 21 dB under the voice on a phone speaker and couldn't be heard. Beds are levelled above 150 Hz now.
- **Awkward caption breaks** from automatic grouping. Always set the lines by hand.
