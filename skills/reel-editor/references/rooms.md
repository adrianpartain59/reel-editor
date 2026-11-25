# Replacing the room behind the speaker (no green screen)

**Opt-in only.** Add `"room"` to plan.json only when the user asks for it in that reel. `scripts/room.py` does the work; compose.py
reads `room.mp4` instead of `base.mp4` when the plan has a room, and nothing changes when it doesn't.

```json
"room": true            // the user's default room: ~/.config/reel-editor/rooms/default.jpg
"room": "loft"          // another saved room: ~/.config/reel-editor/rooms/loft.jpg
"room": {"plate": "loft", "blur": 6, "wrap": 0.5, "match": 0.5}   // with settings (blur 6 is the default; 0 = sharp)
```

A room is a 9:16 photo ("plate") of an empty room. Save the ones the user picks in `~/.config/reel-editor/rooms/`; a plate in the project folder works too.

Check a plate on one frame before a full run: `room.py PROJECT --still body:120` (writes room-still-120.jpg in the
part folder). A full run is about 0.3 s a frame with 4 workers (a 70 s reel: ~10 min), once per plate.

## What makes it believable

1. **Light first.** The plate must have the footage's light: time of day, colour and direction. An evening take (warm front light, dim room) sits perfectly in
   evening rooms lit by warm lamps; a bright daytime room gives the composite away. Match a daylight take with a daylight plate.
2. **The camera's angle.** Seated, phone at chest height, angled slightly up so the ceiling shows: say so in the prompt.
3. **An empty foreground.** "phone sitting on a desk" in a prompt draws a desk and a phone into the plate, which
   peek out around the arms. Say "the foreground is completely empty: no desk, no table, no phone".
4. **Blurred by default (`blur: 6`).** It's the polished portrait-mode look. A phone would really keep a room 3 m away nearly sharp, so
   `"blur": 0` is there for the more literal look. Generate plates in sharp focus, so the blur is all ours.
5. **Camera sway is tracked.** Handheld takes sway 75-175 px; room.py measures the old room's motion with the speaker masked
   out and moves the plate the same way (reset at every cut). A still camera (phone on a stand) is the clean case.
   Walking or big angle changes won't hold.
6. **Known weak spot:** very fast hand motion: a faint tint of the old room shows through the motion blur for a few frames.

## Making a plate

Any image model works, or a photo the user took of an empty room. Two takes, and let the user pick. A prompt that has worked, to change only in its last sentence:

> Vertical 9:16 photo of an empty room at night, no people, taken from seated chest height with the camera angled slightly upward so part of the ceiling shows at the
> top: the background behind someone sitting about one metre from the camera. Everything in sharp focus with deep depth of field, like a normal iPhone photo (no
> portrait-mode blur). The foreground is completely empty: no desk, no table, no phone, no objects close to the camera. The room is lit by a mix of warm orange light and
> cool blue light, both clearly visible. Real photo with natural light falloff and soft shadows; not a render, not a showroom, not CGI. Behind: a loft apartment corner
> with wide windows onto a blue-lit night city; a warm pendant light over a dining table near the window.

## Posting a reel with a replaced room

A generated room is "a realistic-looking scene that didn't actually occur": answer **Yes** to YouTube's
AI question and turn on the AI label on Instagram and TikTok. Say so in out/post.md.
