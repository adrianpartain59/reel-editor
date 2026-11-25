// Copy to PROJECT/canvas/scenes.js and draw your own steps. Every time is seconds on the body's clock, from work/body_words.json
// (seg_words.py). Guide: references/sketch.md. A finished ten-step reel: roadmap.scenes.js, next to the engine.
const { make, h } = require('./engine');
const { C, FILL, K, headline, card, box, write, tag, label, land, count, play, face, hearts, bar, dots, slice, line, ell, spline, txt, pr, E, lerp, clamp } = h;

const draw = {
  // the phone starts drawing on "step one", so the frame is never empty; the one thing in yellow, the rest crossed one by one
  1(c, t, sk) {
    sk.phone(540, 900, 420, 720, .10, .55, { w: 8 }); headline(c, [['pick', .50], ['one', .70, { c: C.yellow }], ['song', .95, { c: C.yellow }]], t);
    for (const [x, y, k] of [[60, 640, 0], [60, 880, 1], [860, 640, 2], [860, 880, 3]]) { sk.rect(x, y, 160, 160, .3 + k * .06, .5 + k * .06, { c: C.dim, w: 5, r: 18 }); sk.cross(x + 80, y + 80, 66, 1.9 + k * .08, { c: C.red, w: 9 }); }
    box(c, sk, 385, 720, 310, 300, 1.0, C.yellow, FILL.yellow); play(sk, 535, 870, 84, 1.2, { c: C.yellow, w: 10 }); hearts(c, 540, 720, t, 2.6);
    sk.arrow(spline([[540, 1275], [530, 1315], [540, 1350]]), 2.7, 2.9, { c: C.grey, w: 7 }); write(c, [['the', 2.75], ['one', 2.9], ['you', 3.05], ['love', 3.2, { c: C.yellow }]], 480, 1372, 84, t);
  },
  // two bars, each on the number as it is said; the winner last, bigger and green
  2(c, t, sk) {
    sk.line(70, 1400, 960, 1400, 4.3, 4.6, { w: 8 }); headline(c, [['count', 4.6], ['the', 4.8], ['days', 5.0, { c: C.greenText }]], t); write(c, [['instead', 5.3, { c: C.grey }], ['of', 5.5, { c: C.grey }], ['the', 5.6, { c: C.grey }], ['minutes', 5.8, { c: C.grey }]], 540, 496, 68, t);
    label(c, 'minutes', 270, 1462, 62, t, 5.6, C.grey); label(c, 'days', 690, 1462, 62, t, 6.3);
    bar(c, 160, 1400, 220, 330, t, 5.9, '10', C.grey, FILL.grey); bar(c, 580, 1400, 220, 600, t, 6.5, '60', C.green, FILL.green, true);
  },
  // three days filling in, then the verdict
  3(c, t, sk) {
    for (let k = 0; k < 3; k++) { const x = 90 + k * 305; sk.rect(x, 560, 280, 280, 8.3 + k * .1, 8.55 + k * .1, { c: C.grey, w: 7, r: 30 }); h.hatch(c, x + 8, 568, 264, 264, FILL.yellow, pr(t, 9.1 + k * .15, 9.3 + k * .15), k + 1); label(c, String(k + 1), x + 140, 712, 150, t, 9.1 + k * .15); }
    headline(c, [['3', 9.1, { c: C.yellow }], ['days', 9.3, { c: C.yellow }], ['in a', 9.45], ['row', 9.55]], t); sk.arrow(line(540, 870, 540, 990), 9.6, 9.8, { w: 8 });
    card(c, sk, 100, 1020, 860, 220, 9.7, 'red', [['skip', 9.72], ['one', 9.85]], 120); sk.cross(540, 1130, 150, 10.1, { c: C.red, w: 16 }); card(c, sk, 160, 1280, 700, 190, 10.2, 'green', [['keep', 10.22], ['going', 10.32]], 92);
  },
  F(c, t) { h.flag(c, t, 11.0); },
};

module.exports = make({
  dur: 13.0,                                              // the body's exact length (work/parts/body/segs.json "duration")
  stops: [                                                // order along the road, three to a row, snaking. at = first word of the step
    { id: 1, at: 0, map: ['one', 'song'], draw: draw[1], cues: { pop: [1.0, 2.75], scribble: [[1.90, .4]] } },
    { id: 2, at: 4.3, map: ['count', 'days'], draw: draw[2], cues: { pop: [5.9, 6.5] } },
    { id: 3, at: 8.3, map: ['3 days', 'in a row'], draw: draw[3], cues: { pop: [9.1, 9.7], scribble: [[10.1, .26]] } },
    { id: 'F', extra: true, finish: true, at: 10.9, map: ['100'], draw: draw.F },
  ],
  views: { ALL: { rows: [0, 1] } },                       // the last pull-back: the whole road, then the finish. {} for none
  flights: [[3.98, 4.75, 1, 2, .36], [7.98, 8.75, 2, 3, .36], [10.84, 11.5, 3, 'ALL', 0]],      // leave out and they are made from "at" (no pull-backs then)
  shakes: [], hits: [],
});
