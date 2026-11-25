// A ten-step roadmap reel about walking more, as the worked example (the words are invented). Times are seconds on the body's clock, taken from
// work/body_words.json (seg_words.py): every drawing lands on the word that names it. Copy the idea, not the drawings.
const { make, h } = require('./engine');
const { C, FILL, FONT: F, K, mk, hatch, box, write, tag, pop, play, face, line, ell, spline, txt, pr, E, lerp, clamp, hash } = h;

const draw = {
  1(c, t, sk) {
    box(c, sk, 100, 420, 390, 230, .68, C.grey, FILL.grey); write(c, [['boring', .73], ['\n'], ['route', 1.15]], 295, 440, 88, t, { maxW: 380 }); sk.arrow(line(510, 535, 610, 535), 1.5, 1.75, { w: 7 });
    box(c, sk, 630, 420, 380, 230, 1.78, C.green, FILL.green); write(c, [['right', 1.82, { c: C.greenText }], ['\n'], ['outside', 2.19, { c: C.greenText }]], 820, 446, 78, t, { maxW: 380 });
    sk.line(150, 1170, 150, 740, 1.85, 2.0, { w: 7 }); sk.line(150, 1170, 970, 1170, 1.9, 2.1, { w: 7 }); sk.arrow(spline([[165, 1150], [380, 1112], [580, 1020], [740, 890], [900, 720]]), 2.0, 2.62, { c: C.green, w: 14, head: 60 });
    for (const [x, s, t0, col, f, z] of [[300, 'me', 2.73, C.yellow, FILL.yellow, 74], [700, '1 other', 3.06, C.grey, FILL.grey, 60]]) { const u = pr(t, t0, t0 + .3); c.save(); c.beginPath(); c.arc(x, 1370, 120, 0, 7); c.clip(); hatch(c, x - 120, 1250, 240, 240, f, u, x); c.restore(); sk.circ(x, 1370, 122, t0, t0 + .32, { c: col, w: 8 }); txt(c, s, x, 1374, F, z, C.text, 'center', pr(t, t0 + .12, t0 + .28)); }
  },
  2(c, t, sk) {
    write(c, [['one', 5.18, { c: C.yellow }], ['podcast', 5.39, { c: C.yellow }], ['\n'], ['just', 5.92], ['for', 6.72], ['walks', 6.83, { c: C.greenText }]], 540, 376, 100, t);
    for (const [x, y, k] of [[70, 780, 0], [70, 1000, 1], [850, 780, 2], [850, 1000, 3]]) { sk.rect(x, y, 160, 150, 4.86 + k * .06, 5.05 + k * .06, { c: C.dim, w: 5, r: 18 }); sk.line(x + 30, y + 55, x + 130, y + 55, 5.0, 5.1, { c: C.dim, w: 5 }); sk.line(x + 30, y + 95, x + 100, y + 95, 5.05, 5.15, { c: C.dim, w: 5 }); sk.cross(x + 80, y + 75, 66, 5.55 + k * .08, { c: C.red, w: 9 }); }
    sk.phone(540, 950, 380, 600, 4.82, 5.15, { w: 8 }); box(c, sk, 400, 810, 280, 250, 5.35, C.yellow, FILL.yellow); play(sk, 535, 935, 74, 5.55, { c: C.yellow, w: 10 });
    h.hearts(c, 540, 820, t, 6.83);
    sk.arrow(spline([[540, 1265], [525, 1300], [540, 1350]]), 8.0, 8.35, { c: C.grey, w: 7 }); write(c, [['for', 8.28]], 345, 1378, 70, t); tag(c, 'step 6', 560, 1418, t, 8.62, C.yellow, 250);
  },
  3(c, t, sk) {
    write(c, [['make', 10.02], ['it', 10.31], ['about', 10.84]], 540, 376, 96, t); box(c, sk, 100, 520, 880, 400, 11.1, C.green, FILL.green); for (const [r, k] of [[150, 0], [98, 1], [46, 2]]) sk.circ(320, 720, r, 11.2 + k * .07, 11.42 + k * .07, { c: C.green, w: 8 }); sk.arrow(line(560, 560, 340, 706), 11.5, 11.68, { c: C.yellow, w: 12, head: 54 }); write(c, [['the', 11.14], ['\n'], ['streak', 11.46]], 740, 620, 118, t, { maxW: 480 });
    write(c, [['instead', 11.70, { c: C.grey }], ['of', 12.12, { c: C.grey }]], 540, 946, 66, t); box(c, sk, 100, 1040, 800, 340, 12.2, C.grey, FILL.grey); for (let k = 0; k < 4; k++) { sk.rect(160, 1090 + k * 66, 40, 40, 12.28 + k * .04, 12.38 + k * .04, { c: C.grey, w: 5, r: 8 }); sk.line(225, 1112 + k * 66, 400 - (k % 2) * 50, 1112 + k * 66, 12.32 + k * .04, 12.42 + k * .04, { c: C.grey, w: 6 }); } write(c, [['the', 12.5], ['\n'], ['miles', 12.72]], 660, 1096, 112, t, { maxW: 420 }); sk.cross(500, 1210, 190, 12.82, { c: C.red, w: 16 });
  },
  4(c, t, sk) {
    box(c, sk, 140, 420, 800, 230, 15.8, C.redLine, FILL.red); write(c, [['later', 15.84]], 540, 466, 128, t); sk.cross(540, 535, 165, 16.28, { c: C.red, w: 16 }); sk.arrow(line(540, 680, 540, 800), 16.5, 16.7, { w: 8 });
    box(c, sk, 100, 830, 880, 250, 16.6, C.green, FILL.green); write(c, [['same', 16.63], ['time', 16.85]], 540, 896, 112, t); sk.arrow(spline([[330, 1100], [300, 1165], [290, 1225]]), 17.3, 17.5, { w: 8 }); box(c, sk, 90, 1245, 400, 200, 17.48, C.blue, FILL.blue); write(c, [['rest', 17.5], ['day', 17.72]], 290, 1308, 70, t, { maxW: 390 });
    sk.arrow(spline([[700, 1100], [710, 1165], [712, 1225]]), 18.0, 18.2, { w: 8 }); box(c, sk, 520, 1245, 380, 200, 18.2, C.redLine, FILL.red); write(c, [['no', 18.2], ['zero', 18.3], ['days', 18.4]], 710, 1318, 50, t, { maxW: 380 });
  },
  5(c, t, sk) {
    write(c, [['start', 19.9], ['in', 20.24], ['minutes', 20.41, { c: C.greenText }]], 540, 384, 100, t);
    sk.path(line(110, 620, 970, 620), 19.5, 20.0, { c: C.dim, w: 6 }); for (let k = 0; k < 13; k++) sk.line(110 + k * 71.6, 604, 110 + k * 71.6, 636, 19.6 + k * .02, 19.7 + k * .02, { c: C.dim, w: 5 }); txt(c, 'buying gear', 690, 566, F, 54, C.dim2, 'center', pr(t, 19.8, 20.0)); sk.line(480, 590, 960, 545, 20.62, 20.8, { c: C.red, w: 10 }); sk.line(480, 548, 960, 592, 20.72, 20.9, { c: C.red, w: 10 });
    sk.arrow(line(110, 700, 380, 700), 20.5, 20.75, { c: C.green, w: 20, head: 66 }); txt(c, 'go', 450, 702, F, 64, C.greenText, 'center', pr(t, 20.7, 20.85));
    h.count(c, 5000, 480, 910, 200, t, 21.5, 22.1, C.greenText, v => v.toLocaleString('en-US'));
    const n = pr(t, 21.6, 22.6) * 12; for (let i = 0; i < 12; i++) { const x = 110 + (i % 4) * 196, y = 1060 + Math.floor(i / 4) * 112; sk.rect(x, y, 172, 92, 21.3 + i * .012, 21.45 + i * .012, { c: C.dim2, w: 5, r: 16 }); if (n > i) { c.save(); c.globalAlpha *= clamp(n - i); c.fillStyle = 'rgba(105,219,124,.85)'; c.beginPath(); c.roundRect(x + 8, y + 8, 156, 76, 12); c.fill(); c.restore(); txt(c, String(i + 1), x + 86, y + 50, F, 46, C.bg, 'center', clamp(n - i)); } } write(c, [['12', 22.22, { c: C.yellow }], ['days', 22.61, { c: C.yellow }]], 470, 1398, 84, t);
  },
  6(c, t, sk) {
    write(c, [['100', 26.9, { c: C.yellow }], ['short', 27.42], ['walks', 27.71]], 540, 384, 88, t, { maxW: 1040 }); h.dots(c, 100, 10, 243, 552, 66, 25, t, 26.9, 28.15, 28.2, 29.1);
    sk.arrow(spline([[330, 1300], [340, 1260], [400, 1210]]), 28.3, 28.55, { c: C.yellow, w: 8 }); box(c, sk, 130, 1310, 360, 180, 28.4, C.yellow, FILL.yellow); write(c, [['that', 28.45], ['\n'], ['podcast', 28.7]], 310, 1322, 68, t, { maxW: 340 }); tag(c, 'from step 2', 705, 1400, t, 28.85, C.yellow, 350);
  },
  7(c, t, sk) {
    write(c, [['each', 32.26], ['gets', 32.4], ['a', 32.7], ['ticket', 32.76, { c: C.yellow }]], 540, 376, 100, t); face(c, sk, 230, 660, 120, 32.2, t > 34.8 ? 'happy' : 'flat', { w: 8, c: t > 34.8 ? C.yellow : C.ink }); sk.arrow(line(380, 660, 480, 660), 32.6, 32.78, { w: 8 });
    sk.rect(510, 570, 470, 180, 32.7, 32.95, { c: C.yellow, w: 8, r: 30 }); for (let k = 0; k < 8; k++) sk.line(620, 586 + k * 20, 620, 596 + k * 20, 32.85, 32.95, { c: C.yellow, w: 6 }); write(c, [['COFFEE', 32.8, { c: C.yellow }]], 800, 628, 60, t, { maxW: 400 });
    h.slice(c, sk, 320, 1100, 205, .2, 33.05, [800, 960]); write(c, [['of', 33.69], ['them', 33.81], ['\n'], ['win', 34.13]], 785, 1050, 84, t, { maxW: 380 });
    sk.arrow(spline([[330, 860], [290, 850], [245, 800]]), 34.3, 34.6, { c: C.yellow, w: 9 }); for (let k = 0; k < 3; k++) { const q = (t - 34.6 - k * .22) / .6; if (q > 0 && q < 1) { const p = spline([[430, 930], [330, 850], [235, 690]]); const [x, y] = p[Math.floor(q * (p.length - 1))]; c.fillStyle = C.yellow; c.beginPath(); c.arc(x, y, 32, 0, 7); c.fill(); txt(c, '+', x, y + 2, F, 44, C.bg); } } write(c, [['you', 34.57], ['want', 34.76, { c: C.greenText }], ['to', 34.95], ['go', 35.04, { c: C.greenText }]], 470, 1370, 84, t, { maxW: 860 });
  },
  8(c, t, sk) {
    write(c, [['routes', 36.17], ['that', 36.37], ['look', 36.63], ['\n'], ['like', 36.89], ['normal', 37.15, { c: C.greenText }], ['errands', 37.55, { c: C.greenText }]], 540, 372, 84, t);
    const px = 760, qx = 290; sk.phone(px, 960, 370, 640, 36.6, 36.95, { w: 8, c: t > 37.6 ? C.green : C.ink }); for (let k = 0; k < 4; k++) { sk.rect(px - 135, 760 + k * 115, 56, 56, 37.0 + k * .08, 37.15 + k * .08, { w: 7, r: 12 }); sk.line(px - 50, 790 + k * 115, px + 130 - (k % 2) * 50, 790 + k * 115, 37.05 + k * .08, 37.2 + k * .08, { w: 8 }); } if (t > 37.6) sk.path([[px - 80, 1360], [px - 35, 1405], [px + 60, 1310]], 37.62, 37.85, { c: C.green, w: 20 });
    sk.phone(qx, 960, 370, 640, 38.0, 38.3, { w: 8, c: t > 39.42 ? C.redLine : C.ink }); c.save(); c.beginPath(); c.roundRect(qx - 176, 690, 352, 580, 40); c.clip(); const sc = E.io(pr(t, 38.55, 39.15)) * 620 + E.io(pr(t, 39.25, 39.8)) * 620; for (let k = 0; k < 3; k++) { const oy = k * 620 - sc; if (t < 38.2 || oy < -640 || oy > 640) continue; const s2 = mk(c, t); c.save(); c.translate(0, oy); s2.rect(qx - 140, 730, 280, 290, 38.2, 38.4, { c: C.violet, w: 7, r: 24 }); hatch(c, qx - 136, 734, 272, 282, FILL.violet, pr(t, 38.25, 38.45), k + 3); c.fillStyle = C.yellow; c.beginPath(); c.roundRect(qx - 130, 745, 100, 60, 14); c.fill(); txt(c, 'GYM', qx - 80, 777, F, 40, C.bg); c.fillStyle = C.violet; c.beginPath(); c.roundRect(qx - 110, 1070, 220, 84, 42); c.fill(); txt(c, 'SIGN UP', qx, 1113, F, 40, C.bg); c.restore(); } c.restore();
    if (t > 38.55) sk.arrow(line(qx + 250 - 20, 1150, qx + 230, 860), 38.6, 38.85, { c: C.grey, w: 9, head: 50 }); sk.cross(qx, 960, 190, 39.42, { c: C.red, w: 18 }); write(c, [['skip', 38.57, { c: C.grey }], ['past', 38.75, { c: C.grey }]], 290, 1318, 72, t, { maxW: 480 });
  },
  9(c, t, sk) {
    write(c, [['sore', 40.89, { c: C.yellow }], ['legs', 41.07], ['\n'], ['before', 41.62], ['strong', 42.07, { c: C.greenText }]], 540, 376, 92, t, { maxW: 1040 }); sk.line(110, 960, 980, 960, 40.6, 40.85, { w: 7, c: C.dim2 }); txt(c, 'now', 66, 915, F, 46, C.dim2, 'center', pr(t, 40.7, 40.9));
    const dip = spline([[130, 960], [260, 1060], [400, 1200], [540, 1180], [650, 1060], [716, 960]]); const u = pr(t, 40.9, 41.7); if (u > 0) { c.save(); const p = K.part(dip, u), e = p[p.length - 1]; K.trace(c, [...p, [e[0], 960]]); c.closePath(); c.clip(); hatch(c, 110, 940, 640, 300, FILL.red, 1, 8); c.restore(); } sk.path(dip, 40.9, 41.7, { c: C.redLine, w: 13 }); sk.arrow(spline([[716, 960], [790, 860], [850, 740], [930, 610]]), 42.07, 42.6, { c: C.green, w: 15, head: 62 }); const d = E.back(pr(t, 41.9, 42.1)); pop(c, 716, 960, d, () => { c.fillStyle = C.green; c.beginPath(); c.arc(0, 0, 24, 0, 7); c.fill(); });
    sk.arrow(spline([[250, 1380], [290, 1320], [370, 1250]]), 41.2, 41.45, { c: C.yellow, w: 9 }); write(c, [['sore', 41.1, { c: C.yellow }], ['here', 41.2, { c: C.yellow }]], 260, 1390, 80, t, { maxW: 420 });
  },
  10(c, t, sk) {
    write(c, [['judge', 45.0], ['by', 46.05], ['streak', 46.19, { c: C.greenText }]], 540, 366, 100, t); write(c, [['instead', 46.68, { c: C.grey }], ['of', 47.19, { c: C.grey }], ['speed', 47.33, { c: C.grey }]], 540, 490, 72, t); sk.line(640, 530, 880, 520, 47.55, 47.7, { c: C.red, w: 12 }); const go = 1 - E.in(pr(t, 47.6, 47.8)); if (go > 0) { c.save(); c.globalAlpha *= go; c.translate(540, 960); c.scale(.85 + .15 * go, .85 + .15 * go); c.translate(-540, -960); sk.phone(540, 960, 300, 500, 45.3, 45.6, { w: 8 }); sk.circ(540, 950, 84, 45.6, 45.8, { w: 9 }); sk.arrow(line(700, 900, 760, 870), 46.1, 46.25, { c: C.green, w: 8 }); pop(c, 870, 850, E.back(pr(t, 46.19, 46.45), 2.4), () => { c.fillStyle = C.green; c.beginPath(); c.arc(0, 0, 92, 0, 7); c.fill(); txt(c, '60', 0, 6, F, 104, C.bg); }); sk.arrow(line(380, 900, 320, 870), 46.65, 46.8, { c: C.grey, w: 8 }); sk.circ(205, 850, 86, 46.7, 46.95, { c: C.grey, w: 8 }); sk.line(205, 850, 250, 800, 46.9, 47.0, { c: C.grey, w: 8 }); sk.cross(205, 850, 96, 47.4, { c: C.red, w: 14 }); c.restore(); }
    sk.line(70, 1400, 960, 1400, 47.7, 47.95, { w: 8 });
    for (const [x, nm, t0] of [[90, 'friend A', 47.81], [540, 'friend B', 50.96]]) txt(c, nm, x + 185, 1462, F, 62, C.ink, 'center', pr(t, t0, t0 + .2));
    h.bar(c, 90, 1400, 176, 600, t, 48.47, '9K', C.blue, FILL.blue); h.bar(c, 286, 1400, 176, 40, t, 50.35, '4d', C.grey, FILL.grey);          // every bar lands on the word that says it
    h.bar(c, 540, 1400, 176, 200, t, 51.46, '3K', C.blue, FILL.blue); h.bar(c, 736, 1400, 176, 520, t, 52.82, '60d', C.green, FILL.green, true);
  },
  // most people roll down the road and stop at the barrier; one goes through once it lifts
  T(c, t, sk, { map }) { h.barrier(c, t, 25.16, 25.95); if (!map) write(c, [['most', 24.5], ['new', 24.72], ['walkers', 24.95], ['\n'], ['stop', 25.2, { c: C.red }], ['here', 25.3, { c: C.red }]], 470, 1120, 106, t, { maxW: 900 }); },
  F(c, t) { h.flag(c, t, 53.25); },
};

module.exports = make({
  dur: 56.7,                                              // the body's length, from work/parts/body/segs.json
  // order = order along the road, three to a row, snaking. at = the first word of the step. map = its two lines on the map.
  stops: [
    { id: 1, at: 0, map: ['boring', 'route'], draw: draw[1], cues: { pop: [.70, 1.80, 2.75] } },
    { id: 2, at: 4.43, map: ['one', 'podcast'], draw: draw[2], cues: { pop: [5.37, 6.85, 8.64], scribble: [[5.55, .45]] } },
    { id: 3, at: 9.43, map: ['the', 'streak'], draw: draw[3], cues: { pop: [11.14], scribble: [[12.83, .26]] } },
    { id: 4, at: 15.13, map: ['same', 'time'], draw: draw[4], cues: { pop: [15.84, 16.62, 17.5], scribble: [[16.29, .26]] } },
    { id: 5, at: 19.3, map: ['start in', 'minutes'], draw: draw[5], cues: { pop: [20.72], counting: [21.5] } },
    { id: 'T', extra: true, corner: true, at: 24, road: [23.6, 24.4], map: ['most', 'stop here'], draw: draw.T, cues: { low_hit: [[25.29, -9]] } },       // between the two halves
    { id: 6, at: 26.47, map: ['100', 'walks'], draw: draw[6], cues: { pop: [26.92, 28.45] } },
    { id: 7, at: 31.57, map: ['20%', 'win'], draw: draw[7], cues: { pop: [32.74, 33.37] } },
    { id: 8, at: 35.5, map: ['normal', 'errands'], draw: draw[8], cues: { pop: [36.65, 37.64, 38.05], scribble: [[39.43, .26]] } },
    { id: 9, at: 40.37, map: ['sore', 'first'], draw: draw[9], cues: { pop: [40.73, 41.95] } },
    { id: 10, at: 44.47, map: ['streak,', 'not speed'], draw: draw[10], moves: [[47.75, 48.3, -24, 60, 1.055], [50.75, 51.3, 24, 60, 1.055], [52.35, 52.75, 0, 0, 1]], cues: { pop: [45.35, 46.22, 48.49, 50.37, 51.48], low_hit: [[52.84, -12]] } },   // push to each friend, back for the payoff
    { id: 'F', extra: true, finish: true, at: 53.2, road: [53.0, 53.5], map: ['1M'], draw: draw.F },
  ],
  // the two pull-backs: "now that's setup" shows steps 1-5, the end shows the whole road
  views: { HALF: { rows: [0, 1], title: 'SETUP', at: [23.75, 24.4] }, ALL: { rows: [0, 3], dy: -10 } },
  flights: [[4.12, 4.86, 1, 2, .36], [9.08, 9.82, 2, 3, .36], [14.85, 15.62, 3, 4, .3], [19.0, 19.78, 4, 5, .36], [23.2, 23.95, 5, 'HALF', 0], [24.4, 25.05, 'HALF', 'T', 0], [26.15, 26.95, 'T', 6, .3],
    [31.25, 32.0, 6, 7, .36], [35.12, 35.86, 7, 8, .36], [40.16, 40.9, 8, 9, .3], [44.15, 44.92, 9, 10, .36], [53.14, 53.78, 10, 'ALL', 0]],
  shakes: [[25.3, 14, .2], [52.86, 13, .24]],             // [time, px, seconds]: the barrier slam, the 60d landing
  hits: [[52.84]],                                        // the camera jumps 5% on the landing
});
