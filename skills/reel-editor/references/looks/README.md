# Looks

A look is a Talking Head's whole picture and sound in one preset: grade, caption style, camera motion, how phones are
shown, transitions and variety pools, the automatic sound table, the music bed and the mix. The plan picks one with `"style": "<name>"`;
everything else in the plan (shots, stickers, titles) works in any look. The plan's key is called `style`.

| look | `style` in plan.json | in short | guide |
|---|---|---|---|
| **Cinematic** (default) | `cinematic` | real room with a contrasty grade, wide white building captions, a varied transition on most cuts, 3D dark phones, neon titles with varied animations, spotlight dims, backgrounds only when they show content, a music bed with drops | [cinematic.md](cinematic.md) |
| **Bright** | `bright` (`classic` is its file) | real room, bright, varied caption styles, bouncy cuts, light SFX, no music. Only on request | the edit playbook |

Files: `assets/styles/<name>.json` (machine defaults, deep-merged over `classic.json`) and `references/looks/<name>.md`
(what it's after, the measurements, how to plan for it). `plan.style_overrides` tweaks one reel.

## Adding a look from a reference reel ("make it look like this")

1. Get the reference as a file (a screen recording is fine). Find where the reel itself starts and ends.
2. `python3 scripts/analyze_ref.py VIDEO OUTDIR --start S --end E` (about 20 s). Read `summary.md`, then
   **look at every contact sheet** and the side spectrogram. Write down, with times: caption font/size/
   position/colour/animation, titles, shot types and how often something new appears, zoom behaviour (face
   width curve), transitions, overlays, colour grade and brightness, the music bed (present? how far under the
   voice? drops?), every SFX type (whoosh, sub hit, tick, glitch...) and loudness/compression.
3. Separate what the skill already does from what's new. New things become plan features (a layout, sticker,
   fx, transition, title animation or sound category) usable in any look; the JSON only sets defaults.
   Learn the techniques, not the set dressing: if the reference was filmed in a dark studio, take the grade and the
   lighting feel to the user's real room; never invent a background.
4. Write `assets/styles/<name>.json` (start from the closest existing one) and `references/looks/<name>.md`
   (a technique table: reference measurement -> how the skill does it, plus a planning recipe). Keep a copy in
   `~/.config/reel-editor/looks/`: a plugin update replaces the skill's folder.
5. Re-edit a finished reel in the new look and put it next to the reference (same moments side by side) before
   calling it done. Say plainly what still differs (footage, set, clothing, licensed music).

Never copy the reference's footage, music, logo, fonts that aren't on the Mac, or graphics: learn the
techniques and apply them to the user's own takes, system fonts and this skill's sounds.
