// Line styles: stick figures on black, neon sign.
const K = require('./kit'); const { W, H, T, clamp, lerp, pr, E, rng, hash, line, ell, rectP, spline, Sk, words, txt, cached, noiseTex, pens, money } = K;

// ---------- one storyboard, drawn by any pen. g = {sk opts, ink, hi, bad, good, dim, head, label, reveal, w}
function brick(sk, x, y, w, h, rows, t0, t1, o) { const bh = h / rows; for (let r = 0; r < rows; r++) { const a = t0 + (t1 - t0) * (rows - 1 - r) / rows, b = a + (t1 - t0) / rows; sk.line(x, y + r * bh, x + w, y + r * bh, a, b, o); const n = 4, bw = w / n; for (let k = 0; k <= n; k++) { const xx = x + k * bw + (r % 2 ? bw / 2 : 0); if (xx > x + w - 8 || xx < x + 8) continue; sk.line(xx, y + r * bh, xx, y + (r + 1) * bh, b - .04, b + .06, o); } } sk.line(x, y + h, x + w, y + h, t0, t0 + .1, o); sk.line(x, y, x, y + h, t0, t1, o); sk.line(x + w, y, x + w, y + h, t0, t1, o); }
function coins(sk, cx, base, n, r, t0, t1, o) { for (let i = 0; i < n; i++) { const a = lerp(t0, t1, i / n), u = pr(sk.t, a, a + .13); if (u <= 0) continue; const y = base - i * r * .25 - (1 - E.bounce(u)) * 70; sk.ell(cx, y, r, r * .34, -1, -1, { ...o, amp: 1 }); sk.line(cx - r, y, cx - r, y + r * .25, -1, -1, { ...o, amp: .6 }); sk.line(cx + r, y, cx + r, y + r * .25, -1, -1, { ...o, amp: .6 }); sk.path(ell(cx, y + r * .25, r, r * .34, 0, Math.PI, 18), -1, -1, { ...o, amp: 1 }); } }
function play(sk, x, y, s, t0, t1, o) { sk.path([...line(x - s * .5, y - s * .6, x + s * .6, y, 6), ...line(x + s * .6, y, x - s * .5, y + s * .6, 6), ...line(x - s * .5, y + s * .6, x - s * .5, y - s * .6, 6)], t0, t1, o); }
function lock(sk, x, y, s, t0, t1, o) { sk.rect(x - s * .5, y - s * .1, s, s * .8, t0, t1, { r: s * .12, ...o }); sk.path(ell(x, y - s * .1, s * .32, s * .42, Math.PI, 2 * Math.PI, 18), t0, t1, o); sk.circ(x, y + s * .26, s * .08, t1, t1 + .1, o); }

function S1(c, t, g) {
  const sk = new Sk(c, t, g.sk); const D = { c: g.dim, w: g.w * .85 }, HI = { c: g.hi }, GO = { c: g.good }; const ty = g.ty || 310;
  txt(c, 'STEP 1', 540, ty - 56, g.label, 58, g.hi, 'center', pr(t, 0, .1));
  words(c, [['Pick', .44], ['a', .7], ['boring', T.w1, { c: g.dim }], ['habit', T.w2], ['\n'], ['that', 1.44], ['adds', T.w3, { c: g.good }], ['up', T.w4, { c: g.good }]], 540, ty, { font: g.head, size: g.hs || 112, color: g.ink, reveal: g.reveal, maxW: 990 }, t);
  sk.line(60, 1440, 1020, 1440, .1, .5);
  // the boring box, asleep
  sk.rect(90, 1190, 290, 250, .62, 1.0, D); sk.line(90, 1190, 150, 1125, .9, 1.0, D); sk.line(150, 1125, 440, 1125, .95, 1.1, D); sk.line(380, 1190, 440, 1125, 1.0, 1.1, D); sk.line(440, 1125, 440, 1378, 1.05, 1.15, D); sk.line(380, 1440, 440, 1378, 1.1, 1.2, D);
  sk.path(ell(185, 1285, 28, 14, 0, Math.PI, 8), 1.05, 1.15, D); sk.path(ell(285, 1285, 28, 14, 0, Math.PI, 8), 1.05, 1.15, D); sk.line(205, 1350, 265, 1350, 1.1, 1.2, D);
  for (let i = 0; i < 3; i++) { const u = pr(t, 1.1 + i * .16, 2.4 + i * .16); if (u > 0 && u < 1) txt(c, 'z', 400 + i * 44 + Math.sin(t * 5 + i) * 10, 1080 - i * 60 - u * 50, g.head, 64 + i * 20, g.dim, 'center', Math.sin(u * Math.PI)); }
  sk.arrow(spline([[250, 1100], [440, 1060], [620, 985], [770, 860], [870, 740], [940, 620]]), T.w3 - .1, T.w4 + .25, { ...GO, w: g.w * 1.7, head: 74 });
  // you and a friend
  const y = 1440 - Math.abs(Math.sin((t - 2.9) * 7)) * 60 * pr(t, 2.9, 3.0) * (1 - pr(t, 3.9, 4.2)); const up = t > 2.9;
  if (t > T.you - .05) sk.fig(615, y, 420, { la: up ? 150 : 25, ra: up ? -150 : -25, lb: -20, rb: 20, face: 'happy' }, T.you - .05, T.you + .35, { ...HI, w: g.w * 1.15 });
  if (t > T.you) txt(c, 'you', 615, 1500, g.label, 60, g.hi, 'center', pr(t, T.you, T.you + .15));
  if (t > T.pal) { sk.fig(870, 1440, 340, { la: 20, ra: -20, face: 'flat' }, T.pal, T.pal + .4, D); txt(c, '1 friend', 870, 1500, g.label, 60, g.dim, 'center', pr(t, T.pal + .2, T.pal + .4)); }
}
function S2(c, t, g) {
  const sk = new Sk(c, t, g.sk); const ty = g.ty || 310;
  txt(c, 'STEP 4', 540, ty - 56, g.label, 58, g.hi, 'center', pr(t, T.s2, T.s2 + .1));
  const out = words(c, [["Don't", T.dont], ['do', 5.3], ['later', T.wrong, { c: g.bad }], ['\n'], ['Same', T.right1, { c: g.good }], ['time', T.right2, { c: g.good }]], 540, ty, { font: g.head, size: g.hs || 112, color: g.ink, reveal: g.reveal, maxW: 1000 }, t);
  const fw = out.items[2]; if (t > 5.9 && fw) sk.line(fw.x - 8, fw.cy + 6, fw.x + fw.w + 8, fw.cy - 8, 5.92, 6.06, { c: g.bad, w: g.w * 1.2 });
  // a big LATER tag, X'd, then it drops off screen
  const sh = t > 5.95 && t < 6.1 ? Math.sin(t * 90) * 14 : 0, fall = E.in(pr(t, 6.12, 6.5)); if (fall < 1) { c.save(); c.translate(540 + sh, 1010 + fall * 1200); c.rotate(fall * 1.1); c.translate(-540, -1010);
    sk.path([...line(150, 1010, 270, 870, 8), ...line(270, 870, 900, 870, 18), ...line(900, 870, 900, 1150, 10), ...line(900, 1150, 270, 1150, 18), ...line(270, 1150, 150, 1010, 8)], T.wrong - .1, T.wrong + .3, { c: g.ink, w: g.w * 1.2 }); sk.circ(258, 1010, 26, T.wrong + .2, T.wrong + .3);
    txt(c, 'LATER', 590, 1018, g.head, 176, g.ink, 'center', pr(t, T.wrong + .1, T.wrong + .25)); sk.cross(540, 1010, 230, 5.9, { c: g.bad, w: g.w * 2.6 }); c.restore(); }
  // the wall goes up, with a lock
  brick(sk, 70, 760, 620, 680, 8, T.right1 + .3, T.right2 + .6, { w: g.w * .9 });
  if (t > T.right2) { c.save(); c.fillStyle = g.paper; c.globalAlpha = pr(t, T.right2 + .15, T.right2 + .25); c.beginPath(); c.arc(380, 915, 118, 0, 7); c.fill(); c.restore(); lock(sk, 380, 900, 150, T.right2 + .2, T.right2 + .6, { c: g.hi, w: g.w * 1.3 }); }
  // the door (a rest day) swings open
  const o = E.io(pr(t, T.opt2 - .1, T.opt2 + .35)); if (t > 7.0) { c.save(); c.fillStyle = g.paper; c.globalAlpha = pr(t, 7.0, 7.1); c.fillRect(250, 1100, 260, 340); c.restore(); sk.rect(250, 1100, 260, 340, 7.0, 7.3, { c: g.good, w: g.w * 1.1 }); const dx = 260 * (1 - o * .74); sk.path([...line(250, 1100, 250 + dx, 1100 - o * 46, 8), ...line(250 + dx, 1100 - o * 46, 250 + dx, 1440 + o * 36, 8), ...line(250 + dx, 1440 + o * 36, 250, 1440, 8)], 7.1, 7.3, { c: g.good, w: g.w * 1.3 }); if (o > 0) for (let i = 0; i < 4; i++) sk.line(390 + i * 10, 1200 + i * 52, 470 - i * 6, 1195 + i * 52, -1, -1, { c: g.good, w: g.w * .8, a: o * .8 }); }
  if (t > T.opt1) { txt(c, 'rest', 860, 1060, g.head, 120, g.good, 'center', pr(t, T.opt1, T.opt1 + .15)); txt(c, 'day', 860, 1170, g.head, 120, g.good, 'center', pr(t, T.opt2, T.opt2 + .15)); sk.arrow(spline([[820, 1240], [760, 1300], [640, 1310], [540, 1290]]), T.opt2, T.opt2 + .3, { c: g.good, head: 54 }); }
  if (t > T.no) { const u = E.out(pr(t, T.no, T.no + .16)); c.save(); c.translate(860, 830); const k = lerp(2, 1, u); c.scale(k, k); txt(c, 'NO ZERO', 0, -42, g.head, g.sb || 72, g.bad, 'center', u); txt(c, 'DAYS', 0, 44, g.head, g.sb || 72, g.bad, 'center', u); c.restore(); sk.rect(710, 730, 300, 200, T.no + .05, T.no + .25, { c: g.bad, w: g.w * 1.1, r: 16 }); }
}
function S3(c, t, g) {
  const sk = new Sk(c, t, g.sk); const ty = g.ty || 310;
  txt(c, 'STEP 10', 540, ty - 56, g.label, 58, g.hi, 'center', pr(t, T.s3, T.s3 + .1));
  words(c, [['Judge', T.s3], ['by', T.s3 + .08], ['streak', T.s3 + .16, { c: g.good }]], 540, ty, { font: g.head, size: g.hs || 112, color: g.ink, reveal: g.reveal, maxW: 1000 }, t);
  for (const [cx, t0, vt, mt, ml, n, win] of [[285, T.a - .1, T.aTop, T.aDays, '4 days', 2, false], [795, T.b, T.bTop, T.bDays, '60 days', 12, true]]) {
    if (t < t0) continue; const o = { c: win && t > mt ? g.hi : g.ink, w: g.w * 1.1 }, won = win && t > mt + .2, yb = 850 - (won ? Math.abs(Math.sin((t - mt) * 9)) * 40 : 0);
    sk.fig(cx - 110, yb, 360, { la: won ? 150 : 30, ra: won ? -140 : -80, rb: -30, face: t > mt + .3 ? (win ? 'happy' : 'sad') : 'flat' }, t0, t0 + .4, o); sk.phone(cx + 90, 720, 150, 250, t0 + .25, t0 + .5, o); sk.circ(cx + 90, 725, 36, t0 + .45, t0 + .6, { c: g.hi });
    if (t > vt) { const v = Math.round((win ? 3 : 9) * E.out(pr(t, vt, vt + .5))); txt(c, v + 'K a day', cx, 935, g.label, 80, g.ink, 'center', pr(t, vt, vt + .1)); }
    if (t > mt - .1) { coins(sk, cx, 1345, n, 112, mt - .1, mt + (win ? .75 : .35), { c: win ? g.good : g.dim, w: g.w * .85 }); const u = pr(t, mt, mt + .2); c.save(); c.translate(cx, 1458); const k = lerp(1.8, 1, E.back(u)); c.scale(k, k); txt(c, ml, 0, 0, g.head, win ? 116 : 92, win ? g.good : g.dim, 'center', u); c.restore(); }
  }
  sk.line(540, 560, 540, 1480, T.b - .2, T.b + .1, { c: g.dim, w: g.w * .6 });
}
const scene = t => t < T.s2 ? [S1, 0] : t < T.s3 ? [S2, T.s2] : [S3, T.s3];

// ---------- 2 stick figures, thick white marker on black, line boil at 8 fps, one accent
const stick = { id: 'stick', name: 'Stick figures on black', frame(c, t) {
  c.fillStyle = '#000'; c.fillRect(0, 0, W, H); const b = Math.floor(t * 8); const g = { sk: { pen: 'marker', w: 15, ink: '#fff', amp: 3.4, boilFps: 8, boilAmt: 1.9 }, w: 15, ink: '#fff', hi: '#ffd400', bad: '#ff4b3e', good: '#ffd400', dim: '#8d8d8d', head: 'Marker', label: 'Marker', reveal: 'pop', paper: '#000', hs: 100, sb: 56 };
  const [f, t0] = scene(t); c.save(); const tr = [T.s2, T.s3].find(s => t >= s && t < s + .28); if (tr) { const u = E.back(pr(t, tr, tr + .28), 1.4); c.translate(0, (1 - u) * 260); } c.translate(Math.sin(b * 2.1) * 1.6, Math.cos(b * 1.7) * 1.6); f(c, t, g); c.restore();
} };

// ---------- 5 neon
const neonBg = () => cached('neon', W, H, x => { x.fillStyle = '#05060b'; x.fillRect(0, 0, W, H); for (const [a, b, r, k] of [[200, 400, 700, 'rgba(255,40,160,.10)'], [900, 1300, 800, 'rgba(30,150,255,.12)']]) { const g = x.createRadialGradient(a, b, 10, a, b, r); g.addColorStop(0, k); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, W, H); } x.strokeStyle = 'rgba(255,255,255,.02)'; x.lineWidth = 2; for (let y = 0; y < H; y += 96) for (let q = (y / 96 % 2) * 110 - 110; q < W; q += 220) x.strokeRect(q, y, 220, 96); });
const neon = { id: 'neon', name: 'Neon sign', frame(c, t) {
  c.drawImage(neonBg(), 0, 0); const fl = hash(Math.floor(t * 24)) > .93 ? .72 : 1; c.save(); c.globalAlpha = fl; const g = { sk: { pen: 'neon', w: 9, ink: '#39c6ff', amp: 0 }, w: 9, ink: '#39c6ff', hi: '#ff4fd8', bad: '#ff3b4e', good: '#4dff9d', dim: '#8a7dff', head: 'RajB', label: 'RajB', reveal: 'none', paper: '#05060b', hs: 112 };
  const [f, t0] = scene(t); const tr = [T.s2, T.s3].find(s => t >= s && t < s + .3); if (tr) c.globalAlpha = fl * (hash(Math.floor(t * 30), 3) > .4 ? 1 : .15);
  c.shadowColor = 'rgba(255,80,200,.9)'; c.shadowBlur = 22; f(c, t, g); c.restore();
} };


module.exports = { list: [stick, neon], brick, coins, play, lock, S1, S2, S3, scene };
