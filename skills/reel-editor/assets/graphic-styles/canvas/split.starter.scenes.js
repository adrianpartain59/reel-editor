// Copy to PROJECT/canvas/scenes.js and draw your own cells. Every time is seconds of the cut (split_reel.py PROJECT words). Guide:
// references/split-screen-reel.md.
const { make, p } = require('./panel_engine');
const { C, FILL, K, mk, hatch, box, card, write, tag, pop, label, face, line, spline, txt, pr, E, lerp, head, brackets, tick, star, bar, count, icon } = p;

const draw = {
  // "number one is a fixed bedtime, not whenever" : the wrong one crossed, an arrow, the right one
  '1'(c, t, S) {
    head(c, t, 1, 4.1, [['fixed', 4.5], ['bedtime', 4.8, { c: C.yellow }]]);                    // pill on "number one", each word on its word
    box(c, S(), 60, 360, 400, 320, 4.2, C.grey, FILL.grey); write(c, [['whenever', 5.6]], 260, 490, 66, t, { maxW: 2000 }); S().cross(260, 520, 140, 5.9, { c: C.red, w: 17 });
    S().arrow(line(490, 520, 580, 520), 6.1, 6.3, { c: C.grey, w: 10, head: 40 });
    card(c, S(), 610, 360, 410, 320, 6.2, 'green', [['fixed', 6.4], ['\n'], ['bedtime', 6.6]], 92);
  },
  // "number two, you get twice the energy" : a short bar, then the winner
  '2'(c, t, S) {
    head(c, t, 2, 8.2, [['2x', 8.7, { c: C.green }], ['the', 9.0], ['energy', 9.1]]);
    S().line(60, 694, 470, 694, 8.4, 8.7, { w: 8 }); bar(c, S, 100, 694, 122, 120, t, 8.8, C.grey, FILL.grey); bar(c, S, 290, 694, 136, 240, t, 9.2, C.green, FILL.green, '2x', 112);
    S().phone(640, 515, 224, 370, 9.3, 9.7, { w: 8 }); label(c, 'your day', 640, 520, 42, t, 9.8); count(c, 8, 898, 450, 100, t, 10.0, 10.6, C.green, v => v + ' h'); label(c, 'a night', 898, 550, 60, t, 10.6);
  },
};

module.exports = make({
  cells: [                                                                                     // at = the first word of the beat. The camera flies in from 0.24 s before it to 0.22 s after
    { id: '1', n: 1, at: 4.1, draw: draw['1'] },                                               // fly: [t0, t1] to set a flight by hand; shift: seconds to move a whole scene after a recut
    { id: '2', n: 2, at: 8.4, draw: draw['2'] },
  ],
  recap: { at: 11.6, first: 11.8, names: ['fixed bedtime', '2x the energy'] },                // the whole list, readable, as the speaker wraps up
});
