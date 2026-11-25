# The split screen reel

The user hands over the full video and says "split screen style". Build it end to end and send the finished reel. Ask nothing
first: every choice below has a default. Not to be confused with `split`, a layout in the standard reel's plan.json.

## The edit, part by part

| Part | What is on screen | When |
|---|---|---|
| First 0.2 s | the face snaps out from 1.35x, blurred | always |
| Hook | the face full frame. Text hook on top from the first frame: black bold on white, caps, two lines at most. Beside the face, one card per point pops in, 0.18 s apart, the number sharp and the name blurred | cards from 0.86 s, all in by 2 s; text and cards leave together 0.25 s before the hook ends |
| Intro | the face full frame, captions only. When the speaker names their app, its App Store page pops in above the head with one pop sound | from the first sound of the name to the end of that claim, about 2.5 s |
| Points | split screen: the drawn canvas on top, the face under it. The canvas slides down while the footage slides down with it, so the face never cuts | starts about 0.35 s before the words "number one" |
| Recap | the same names, now readable, pop in one by one on the canvas | on the sentence after the last point ("pick one of these") |
| Outro | full frame again. The follow card drops in on top; the button is tapped on the word "follow" and turns to "Following"; a yellow line appears when the speaker says what they're making | card in 0.15 s before "remember to follow" |
| Captions | all the way through. White SF Pro Semibold, one line, two to five words, the word being said in yellow. Full shots: under the chin. Split: on the seam. They fade across the move | every word |
| Sound | the voice, and one pop on the App Store page. No other effects, no music | -12 LUFS |
| Picture | raw. No grade | |

Everything in that table is fixed in the scripts. A reel changes the words, the times, the drawings and the names.

## Steps

`S=<this skill>/scripts`, project `<clips folder>/reel-<slug>/`. Cutting takes 2 to 4 minutes and a render 2 to 6: run both in the background.

1. **Takes.** `python3 $S/ingest.py PROJECT --body RAW --slug name`, then `python3 $S/utterances.py PROJECT RAW`. The kept take of each line is the last
   complete one before the speaker moves on; one clean take is every utterance in order. If the user has a script, it gives the order and the on-screen
   text. Write `selects.json`: `{"hooks": {}, "body": [["b1", in, out], ...]}`, one entry per kept utterance in speaking
   order, about 0.08 s of room each side. A scripted line that was never said stays out; say so.
2. **Cut.** `python3 $S/split_cut.py PROJECT`. It cuts every pause, tightens every clip to the word, times the words and lists the edges. The last line must
   start "every clip starts on the word, no stray clicks". A FIX line: set that clip's in or out by hand (the raw second of the first sound, minus 0.04) and run it
   with `--as-is`. A CHECK line is a word whisper heard in the raw take and lost in the cut: put it back with `add` (step 4). A long clean take can come out as 40 clips; that's right.
3. **Set up.** `python3 $S/canvas_init.py PROJECT split` writes `split_reel.json` and `canvas/scenes.js` (and installs the drawing library the first time).
   Always start from these, never from another reel's files: its `times`, `shots`, `cap_y` and `store` would silently carry over.
   Fill split_reel.json (below), caps `[]` for now.
4. **Captions.** `python3 $S/split_reel.py PROJECT words`, then `draft`: paste into `caps` and fix the breaks by hand. A line is a thought ("This is like
   a timer", not "This is like a / timer but for"). `fix`, `join` and `add` repair what whisper misheard or lost. `caps` lists the lines with their widths and how long they show.
5. **Draw.** One cell per point, two when the point has two ideas (below). `node canvas/scenes.js sheet 12.7,13.6,... work/sheet.jpg` as you go, then
   `check`, then a `still` of every finished cell.
6. **App Store page**, when the speaker names their app: `python3 $S/split_reel.py PROJECT store APP_ID` fetches today's name, icon and rating. The id is the number in
   the app's App Store link.
7. **Preview.** `python3 $S/split_reel.py PROJECT check` until it prints OK (a `note` is something to look at, not to fix), then `preview` at the first second, every pop, both moves, one per cell, the tap
   and the last frame. Look at it.
8. **Render.** `python3 $S/split_reel.py PROJECT render` in the background. It prints frames, loudness and any line whisper can't hear, and writes
   `work/final_sheet.jpg`: look at every still.
9. **Thumbnail and caption.** `split_thumb.py PROJECT candidates`, pick a face, set `thumb`, `make`, look at `work/thumb/check.jpg`. Caption by
   `captions.md` in `out/post.md`.
10. **Deliver.** Send the phone copy and the thumbnail, give the full file's path, the caption in the message, what you could not
    check (you can't hear it), any line the user's data doesn't support, and anything you left out. Never publish.

## What to decide from the take

| Choice | Default |
|---|---|
| Text hook | the script's on-screen text for the hook; otherwise the spoken hook cut to 4 to 7 words. Caps, two lines of similar width |
| Cards | the points in order, two words each where you can (`["meal", "planning"]`), 3 to 7 of them. No list in the video: the two to five things it covers. One idea only: `"cards": []` and `face_x` 540 |
| `hook.end`, `hook.out` | the last word of the hook's end; 0.25 s before it |
| `split.in` | 0.35 s before the sentence that opens the first point. Up to about 8 s of full-frame talking before it (who they are, why listen). Longer than that: open the split earlier and draw what is said in cells with no number |
| `split.out` | 0.23 s before the outro's first sentence, which starts on a clip of its own. The outro is the last full sentences, at least 2.5 s of them |
| Recap | from the first sentence after the last point that is about all of them ("pick one of these"). If there is none, the last 1.5 to 2.5 s before `split.out`. Advice with its own content after the last point gets its own unnumbered cell first |
| App Store page | the speaker's own app, the first time they name it, only while the shot is full frame. `in` = the first sound of the name (check the waveform, whisper is up to 0.3 s off), `out` = the end of the claim. Never a subtitle or screenshots. Other apps get no page |
| Follow card | `name` is the display name to show. `in` 0.15 s before "remember to follow", `tap` on "follow", `line` = what they're making next in three or four words, `line_at` on those words. No "follow" in the take: show it over the last sentences, 2.2 s or more before the end, `tap` 0.75 s after `in`, no `line` |
| Thumbnail words | the same idea as the text hook: on top the count in yellow and the thing in white, two to four words; under the chin the rest of the phrase |
| Numbers on the canvas | the ones said, nothing else |

## split_reel.json

Times are seconds of the cut. Everything not listed is fixed.

| key | what it is |
|---|---|
| `slug`, `scenes` | output name; the scenes file (`canvas/scenes.js`) |
| `hook` | `end`, `out`, `text` (list of lines), `cards` (list of one- or two-line names), `first` 0.86, `every` 0.18, `face_x` 445 (the face left of the cards; 540 without cards) |
| `split` | `in`, `out` |
| `store` | `app` (App Store id), `in`, `out`, `name` (only to shorten the listed name). Leave the key out for none. Its pop is automatic |
| `follow` | `in`, `tap`, `name`, `line`, `line_at`, `photo` (second to take the avatar from) |
| `caps` | every word said, once, in order, as a list of lines |
| `fix` | `{"Notion": "notion", "2": "number two"}`: a heard word and what shows (one may become two) |
| `join` | `[["life", "hacking", "lifehacking"], ["It", "costs", "costs"]]`: a run of heard words and, last, the one that shows |
| `add` | `[["So", 77.18]]`: a word whisper lost, and its second of the cut |
| `times` | `{"w188": 47.43}` moves one word's highlight (numbers from `words`) |
| `shots`, `cap_y`, `room` | by hand only: `[t0, t1, zoom0, zoom1, face_x]` per full shot; `[[from, y], ...]`; `"room": false`. Left out, zooms and caption heights come from the face, and a shot framed too close for the cards or the thing above the head is moved down and left with the empty wall stretched to fill (`check` says so; look at it) |
| `thumb` | `t`, `top` (`[["3 HABITS", "yellow"], ["THAT STICK", "white"]]`), `bottom` |

## Drawing the panel

The look, colours and what-to-draw table in `canvas-style.md` all hold. The frame is different: 1080 x 764, drawn in cells.

- **Header row** (`head`): the yellow #n pill and the point in two to five words, written on as it is said, one key word in colour. It shrinks to fit.
- **Drawing** between y 325 and 715, x 40 to 1030. Fill it edge to edge, left to right in the order it is said: two or three pictures with an arrow between
  them, each about 220 to 400 wide. Labels sit at y 684 to 702.
- **Sizes**: labels 42 to 62, the number of the scene 96 to 118, words in a box 56 to 92, phone 224 x 376 with line 8, bars 120 to 136 wide off a baseline at
  y 648 to 694, box lines 7, a cross 17 with half-width 124 to 150, the arrow that carries the idea 15 with head 54, connecting arrows 10 with head 38 to 40.
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

- Rule 1 (nothing but face and captions for 0.8 s): the text hook is there from the first frame; the cards still wait for 0.86 s.
- Rules 12, 13 and 21 (a sound on every move, the riser): no effects except the App Store pop.
- Rule 15 (a beat): no music. A trending sound can go on in the app.
- Rule 23 (the CC pass): raw picture.
- Rule 26 (captions at the top): under the chin on full shots, on the seam in the split.
- Rule 29 (the typed comment outro): the follow card replaces it.
- Still in force: the snap-out, head tracking, the slow push, no breaths or mouth sounds, only the parts with talking, the safe area.

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
- **Awkward caption breaks** from automatic grouping. Always set the lines by hand.
