# Lessons behind the scripts

Things that went wrong while making real reels, and how the scripts avoid them. Read when something looks off or before
changing a script.

## Cutting to the speech

- **whisper.cpp squeezes words into a silent lead-in.** On a clip whose speech started at 1.24 s it put the
  first word at 0.00 s, so captions ran a second early. ingest.py transcribes only the speech span; cut.py
  re-transcribes each finished part, whose first word is within 0.1 s of its start.
- **Energy thresholds drop quiet words.** A soft "do" or a trailing "it" can sit under the silence threshold.
  ingest.py stretches the nearest chunk over any word whisper heard that no chunk covers.
- **Energy chunks can clip a word's tail** ("that's" before a 0.17 s pause). ingest.py merges gaps under
  0.25 s and stretches a chunk up to 0.3 s to the edge of any word it cuts short.
- **A breath can pass for a line in a very quiet room.** The speech threshold sits between the noise floor
  and the speech level; with a -56 dB room a -43 dB rustle cleared it, whisper squeezed "How to get" into
  that silent chunk, and the reel opened on 0.63 s of silence. ingest.py drops any region that never gets within
  18 dB of the clip's speech level. Re-ingest one clip and `cut.py --part` to repair.
- **Full-band energy can't tell hum from speech.** One clip had a -37 dB room (others -50); its hum tail sat at
  -30 to -32 dB, above the clip's -31.5 dB threshold, so 1.2 s of nothing stayed in the reel. In the 300-7600 Hz
  band speech sits 15-45 dB over the floor and that hum only 4-10 dB. speechmap.py judges every frame there.
- **Loudness can't tell a breath from a word.** The breath before "I" sat 23-30 dB under speech, above the
  floor threshold, and the 50 ms gap to the word was filled as part of it. speechmap.py classes frames by shape
  (voiced: most energy below 1 kHz; fricative: centre over 3.5 kHz near speech level; breath: neither) and needs 40 ms
  of voicing per stretch. Checked on 11 takes: every cut was a breath, a click or a pause; the only word sound lost is a
  weak final "t" release after an 80 ms closure (left cut on purpose: reaching across a silence after a word is how
  mouth clicks get back in).
- **whisper stretches a last word over trailing silence or hum.** cover_words only extends over audio with speech-band
  energy, at most 0.15 s.
- **Full-band silence tests also misread quiet word endings as pauses** ("doing better." at -22 dB band level
  read as 0.5 s of silence). Check pauses with the speech map, never a global full-band threshold.
- **Chunk durations must sit on the frame grid.** Cutting audio at exact times and video at whole frames drifts
  apart over 15 cuts. cut.py snaps every segment to 1/30 s and renders video by frame count (`-frames:v`).
- **`-shortest` silently drops frames** when the processed audio comes out a few ms short. mix.py pads the
  audio and sets the duration from the cut instead; qa.py checks the frame count.
- **whisper sometimes drops all punctuation on a long part** (and caption grouping and sentence capitals
  depend on it). cut.py copies punctuation back from the per-clip transcripts by aligning the word sequences;
  caption groups also break on pauses over 0.35 s, so grouping survives either way.

## One long uncut take

- **Whisper over a whole take with retakes invents text.** Across a 6-minute clip with 20 tries at the hook it smeared
  the retakes together and wrote "Step 2" and "Step 3" where the speaker only re-said the hook. Split at pauses (0.45 s)
  and transcribe each utterance alone with padding; the kept take is the last complete one before the next line.
  Script: `scripts/utterances.py`.
- **The speech map keeps dead air when the room noise changes inside one clip** (floor -50 dB early, -45 dB after about
  2:00): it held 1.3 s of tail after the hook. Set those boundaries from the 300-7600 Hz level against the floor around that
  line, not the whole clip's, and cut with `cut.py --as-is`.
- **A final-pass whisper check can drop a line that is there** (30 s windows). Re-transcribe just that window before
  believing a missing word.
- **Word times from the whole body drift across cuts**: a word was placed 0.76 s early at a jump cut. Transcribe each kept
  segment alone with 0.25 s of lead-in and offset by its `t0` (`scripts/seg_words.py`), and check the first word of a
  visual cut against the level (30 ms steps) before setting it.

## Voice

- **Never fold iPhone audio to mono.** The front-camera stereo comes from two spaced mics whose highs are
  uncorrelated or out of phase (measured: L/R correlation 0.0 at 2-5 kHz, -0.73 at 5-10 kHz), so
  `-ac 1` cancels 5-10 dB of the 4-16 kHz clarity band and the voice sounds muffled and hollow. cut.py and
  mix.py keep the recorded stereo end to end; mono is used only for analysis (speech detection, whisper).
- **Don't run a spectral denoiser by default.** `afftdn=nf=-30` assumed a noise floor far above the real one
  (-38 to -63 dB) and took another 3 dB at 2-4 kHz and 7.6 dB at 12-15 kHz, with watery artifacts. Denoise is
  opt-in (`"audio": {"denoise": true}`) and then set from the measured floor. qa.py compares each reel's
  spectrum with the original takes (audio_check.py) and fails a reel that drifts more than 3 dB above 2 kHz.
- **Limit 1 dB lower than the target true peak.** AAC encoding overshoots about 1 dB, so a -1 dBFS limiter
  produced 0.0 dBTP files; the limiter ceiling is -2 dBFS and loudness is re-measured after limiting.
- **AAC overshoot depends on the mix.** With a trap beat's 808 under the voice the encoder overshot by 1.55 dB, landing at
  -0.45 dBTP (QA fail). `mix.py` measures the encoded file and, only when it is over -1 dBTP, re-masters with the ceiling
  lowered by the excess.
- **Mono-to-stereo in ffmpeg is -3 dB per side.** mix.py measures loudness on the stereo signal.

## Sound effects

- **Drop impacts were silently lost.** A drop schedules its swell and its impact at the same time; a spacing rule dropped the
  impact as a rival. Check `audio_map.json` "dropped" after any change to drops.
- **A riser is not a whoosh.** Hook risers go in the plan's `risers` key and are mixed beside the bed, so cues on top don't
  cut them.
- **SFX levels are calibrated, not hand-set:** each cue's loudest 100 ms is placed a category offset under the
  voice's median 400 ms speech level, so effects never drown the voice or vanish under it.
- **Sub hits need harmonics to exist on a phone.** A 30-60 Hz drop is inaudible on iPhone speakers; the heavy
  hits are saturated asymmetrically (2nd harmonic = an octave up) and carry a separate punch layer at 60-170 Hz.
  mix.py measures SFX above 100 Hz for level, and caps the full-band peak at voice + 4 dB, so the sub adds
  weight on headphones without the hit jumping out of a phone.
- **One moment, one sound per kind.** A tap and a swap land on the same frame; with rotating files they became
  two different clicks 20 ms apart, which sounds like a flam. Cues are de-duplicated by sound kind within
  0.1 s, except keys and ticks, which are meant to be fast (30 ms).
- **Animations inside a rendered `broll` track have no automatic sound.** Add `sfx` cues by hand for each one (swaps,
  phones landing, a pan, a flip, typing) or QA can't see them and they move in silence.
- **A count-up that matches its graph:** drive the line, the number and the pitch from one function of time
  (`countup_hook.py` `value` / `tip_h`, `canvas_sound.py` `taps`), so the sound wobbles with the squiggle and climbs with it.

## Music beds

- **Level a downloaded beat on what a phone plays.** Across 10 measured trap beats the 808 sub (under
  120 Hz) holds 59-85% of the energy (median 78%). Matched to the voice by full-band level, the part a phone
  speaker reproduces (hats, snare, melody) ends up 5-10 dB lower than intended. `mix.music_bus` measures a `track:` bed
  above 150 Hz instead.
- **Bar lines from onsets, downbeat from the kick.** Tempo comes out as 60 or 120 for the same beat (half or
  double time), which doesn't matter for cutting as long as the cut lands on a bar line. The downbeat is the
  one of four beat positions with the strongest kick/808 onsets; when it isn't at least 2x the next one
  (`grid_conf`), drops don't restart the beat.
- **Whisper is no vocal detector on music.** On instrumentals large-v3-turbo outputs "Thank you.", "so" or
  "*music*" on a loop. Real lyrics or a producer tag show up as varied words.
- **A genre tag doesn't make a beat trap; measure it.** `music_lib.trap_measures`: hi-hat onsets in 6-15 kHz (adaptive
  threshold, 25 ms minimum gap), a roll = 3+ gaps under 80 ms in a row; 808 = median sub share of 28-130 Hz per 50 ms frame,
  slides = the sub's pitch moving 2+ semitones within 200 ms while it rings. Then look at the spectrograms: crisp
  hat ticks in clusters and long sub notes that bend.

## Picture

- **Homebrew ffmpeg has no drawtext or libass**, so captions and titles are drawn with Pillow and composited
  frame by frame. That also makes per-word animation easy.
- **Headless Chrome may exit non-zero after writing the screenshot** (teardown watchdog), or hang there and
  never exit. mockups.py judges success by the file, with a throwaway profile per render, and treats a 30 s timeout as
  "check the file".
- **"On by default" silently meant off.** compose turned `intro_zoom: true` into `{}`, and every reader tested `if iz`, so the
  default never ran. A default must be a non-empty value (`compose.INTRO_DEFAULT`), and a fix like this is checked on a
  real frame.
- **Face position comes from macOS Vision** (`VNDetectFaceRectanglesRequest` via a small swift script), median
  of three frames per clip. Zooms aim slightly above the face centre (the eyes).
- **White captions vanish on a white shirt.** compose.py measures the background under each caption and adds
  a dark backing when it is bright.
- **Phone copies over 30 MB don't reach the phone.** A fixed 5 Mbit/s cap made 58 s reels 32 MB; mix.py
  sizes the bitrate from the duration.
- **Instagram's UI covers the bottom ~380 px.** Defaults keep text between y 220 and 1500.
- **Vision's person mask also picks up people-like things on the wall.** A tapestry with a drawn figure behind
  the shoulder came back at 0.53-0.71 confidence while the person is ~1.0 with hard edges, and showed through
  as a lit patch. compose.py runs the mask through a smoothstep from `grade.mask_lo` 0.66 to 0.96.
- **A smash zoom must never ask for less than the full frame.** Starting at 0.62x of a 1.3x shot is below 1.0
  and PIL refuses a crop box larger than the image; the smash starts at max(1.0, z * 0.62) and view_crop clamps.
- **A screen recording of a reel starts wherever the loop was.** analyze_ref.py takes --start/--end so the measurements
  cover the reel only.
- **Two transitions half a second apart read as noise.** With a transition on every cut, a 0.5 s face shot
  between two phones got two transitions back to back. `auto` hard-cuts next to any shot shorter than
  `transitions.min_shot` (0.9 s).
- **Transitions render both shots from the same source frame.** No second video read is needed: a transition
  mixes two framings (zoom, layout) of the same moment, which also keeps lip sync exact through it.
- **A white neon icon needs a stronger bloom than a coloured one** to read as lit on a dimmed frame (g 1.3,
  stroke size/20); at the title defaults it looked like a thin white line.

## Layered builds and long screen time

- **A thing built up layer by layer needs its own b-roll track.** The mockup library shows one phone; a reel
  that builds a whole set of screens (reorder, phones, background, photo, headlines) has no layout for it. What works: a project
  script renders one full-length 1080x1920 track with every animation timed from `work/parts/body/words.json`, and
  every `broll` shot reads it at its own start (`src_in` == the shot's `t`), so face cuts drop in anywhere and
  the animations stay on their words. Generate plan.json from a script so `t` and `src_in` can't drift apart.
- **Two consecutive broll shots from one track can't transition visibly**: both sides render the same frame.
  Change scenes inside the track, or use separate files.
- **The cinematic style hides captions on overlay shots.** In a reel that is mostly screen, that removes the
  captions from most of it; set `captions: true` on those shots and keep the content above y 1300 so the captions
  sit under it.
