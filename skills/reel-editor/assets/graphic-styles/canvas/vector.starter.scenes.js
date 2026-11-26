// Vector (the Split Screen's default art style): canvas_init.py PROJECT split writes this to PROJECT/canvas/scenes.js. Draw your own cells. Every
// time is seconds of the cut (split_reel.py PROJECT words). Guide: references/vector-style.md (read "Signal over noise" first).
// The reel opens in the split (split.hook_out): the Instagram text hook covers y 186 to 466, so the hook's cells draw from y 500 down and
// have no titles. The speaker goes full frame for the intro; the first cell after it takes cut: true. Body cells: the title at y 248 (it types
// out at once when the cell starts), the picture from y 330 to DB (990). One main thing per picture.
// The panel is 1080 x 1240 in the card layout: split_reel.py sets PANEL_H; on its own, run `PANEL_H=1240 node canvas/scenes.js check`.
const { make, p } = require('./vector_engine');
const { V, F, E, pr, rr, text, title, card, tag, media, phone, ui, curve, axes, lines, bar, list, cross, tick, count, words, fade, clip, photo, footage, screenOf } = p;

// real footage, from the project folder (scripts/stock.py get PROJECT ID NAME, or the speaker's own clips): const M = { a: clip('media/a.mp4') };
// the made-up app: the question and blank answer rows (words only on the row the speaker names)
const ask = (question, n = 3, pick = -1, pickAt = 1e9) => (c, s) => { ui.bar(c, s, .4); ui.h(c, s, question, 112); for (let i = 0; i < n; i++) ui.row(c, s, '', 210 + i * 72, i === pick ? E.out(pr(s.t, pickAt, pickAt + .2)) : 0); ui.btn(c, s, 'Continue', s.t > pickAt); };

const draw = {
  // HOOK (under the text hook, no title). "Most people stop walking in the second week": one bar chart, the drop is the focus
  h1(c, t) {
    axes(c, 190, 520, 890, 930, t, 0);
    bar(c, 280, 930, 210, 380, t, .3, 'grey'); words(c, 'week one', 385, 965, t, .3, { size: 30, w: 700, col: V.dim });
    bar(c, 590, 930, 210, 190, t, 1.4, 'red', { val: '-50%', vt: 1.7 }); words(c, 'week two', 695, 965, t, 1.4, { size: 30, w: 700, col: V.dim });
  },
  // "number one is a set time, not a step goal": one phone. The title reads on its own
  '1'(c, t) {
    title(c, t, [['A', 0], ['set', 0], ['time,', 0], ['not', 0], ['a', 0], ['goal', 0]], { n: 1 });                 // the #1 pill is this title's accent
    phone(c, 540, 660, 620, t, 9.2, ask('When will\nyou walk?', 3, 0, 10.0));
  },
  // "number two, people walk three times as often": one chart; the bar is the point
  '2'(c, t) {
    title(c, t, [['3x', 0, { pill: 'green' }], ['more', 0], ['walks', 0]], { n: 2 });
    axes(c, 190, 380, 890, 920, t, 13.0); bar(c, 280, 920, 210, 92, t, 13.2, 'grey', { val: '1x' }); bar(c, 590, 920, 210, 460, t, 13.8, 'green', { val: '3x' });
  },
};

module.exports = make({
  cells: [{ id: 'h1', at: 0, draw: draw.h1, until: 3.4 }]                                     // until: split.hook_out + 0.4 (the panel is off screen after it)
    .concat([{ id: '1', at: 9.0, cut: true, draw: draw['1'] }])                                // back from the full-frame intro: no push
    .concat([{ id: '2', at: 12.8, draw: draw['2'] }]),                                         // shift: seconds to move a whole cell after a re-cut
  recap: { at: 16.0, first: 16.1, every: .2, names: ['A set time', '3x more walks'] },         // a numbered list, every row lit as the speaker wraps up
});
