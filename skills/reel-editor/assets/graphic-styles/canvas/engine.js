// The hand-drawn canvas: every step of a reel is a scene in one big drawn world, a dotted road
// winds through them and the camera flies along it. This file owns the world: cells, road, camera, map zoom-out, motion blur.
// A reel only writes scenes.js (copy starter.scenes.js; roadmap.scenes.js is a finished ten-step reel).
//
//   const { make, h } = require('<skill>/assets/graphic-styles/canvas/engine');
//   module.exports = make({ dur, stops: [...], views, ... });   // last line: make() also gives the file its command line
//
//   node scenes.js sheet 1.2,3.4 out.jpg        small stills at those seconds, to see the timing
//   node scenes.js still 4.1,9.3 out.jpg        up to four big ones, to see overlaps and loose labels
//   node scenes.js render out.mp4 [from] [to]   the whole body (or frames from-to), 1080x1920, 30 fps, no sound
//   node scenes.js check [canvas_reel.json]     ink outside the safe area, stretches where nothing new is drawn, scenes that start late or look empty
//   node scenes.js info                         flights and cues as JSON (canvas_sound.py reads it)
const K = require('../kit'); const { W, H, clamp, lerp, pr, E, hash, line, ell, rectP, spline, Sk, words, txt } = K;
const fs = require('fs'), path = require('path');

// ---------- the look. Nothing else is allowed on this canvas.
const C = { bg: '#121212', ink: '#e9e9e9', text: '#f2f2f2', grey: '#adb5bd', dim: '#777777', dim2: '#8a8a8a',
  yellow: '#ffd43b', green: '#69db7c', greenText: '#b2f2bb', red: '#ff6b6b', redLine: '#ff8787', blue: '#74c0fc', violet: '#e599f7', orange: '#ffa94d' };
const FILL = { yellow: 'rgba(255,212,59,.30)', green: 'rgba(105,219,124,.28)', red: 'rgba(255,107,107,.24)', blue: 'rgba(116,192,252,.25)', grey: 'rgba(173,181,189,.20)', violet: 'rgba(229,153,247,.25)' };
const FONT = 'ShanB';                                   // Shantell Sans ExtraBold, for every word and number
const CW = 1320, CH = 1560;                             // one cell of the world; a scene draws in 0..1080 x 0..1720 of its own cell

// ---------- pieces a scene is made of (x, y in the scene's own 1080-wide screen; t = seconds on the body's clock)
const mk = (c, t) => new Sk(c, t, { pen: 'rough', w: 6, ink: C.ink, amp: 1.6, step: 9 });
function hatch(c, x, y, w, hh, col, u, seed = 1, gap = 17) { if (u <= 0) return; c.save(); c.beginPath(); c.rect(x, y, w, hh); c.clip(); c.strokeStyle = col; c.lineWidth = 4; c.lineCap = 'round'; const n = Math.ceil((w + hh) / gap); c.beginPath(); for (let i = 0; i < n * u; i++) { const q = x + i * gap - hh, j = (hash(i, seed) - .5) * 8; c.moveTo(q + j, y + hh); c.lineTo(q + hh + j, y); } c.stroke(); c.restore(); }
// a hatched box drawing itself on at t0: line and fill are the same colour (C.green + FILL.green)
function box(c, sk, x, y, w, hh, t0, col, fill, o = {}) { hatch(c, x + 5, y + 5, w - 10, hh - 10, fill, pr(sk.t, t0 + .08, t0 + .42), x + y); sk.rect(x, y, w, hh, t0, t0 + .28, { c: col, w: o.w || 7, r: o.r ?? 26 }); }
// words written on as they are said: [['text', time, {c, size}], ['\n'], ...]. y is the top of the first line
const write = (c, ws, x, y, size, t, o = {}) => words(c, ws, x, y, { font: FONT, size, color: C.text, reveal: 'write', maxW: o.maxW || 960, lh: 1.12, align: o.align, sp: .28 }, t);
// the two pieces most scenes start from; both shrink their words to fit, so a long word can't run out of its box
const KIND = { green: [C.green, FILL.green, C.greenText], red: [C.redLine, FILL.red, C.text], blue: [C.blue, FILL.blue, C.text], yellow: [C.yellow, FILL.yellow, C.text], grey: [C.grey, FILL.grey, C.text], violet: [C.violet, FILL.violet, C.text] };
function fit(c, ws, size, maxW) { const lines = [[]]; ws.forEach(w => w[0] === '\n' ? lines.push([]) : lines[lines.length - 1].push(w)); const wide = Math.max(...lines.map(l => { c.font = `${size}px "${FONT}"`; return l.reduce((a, w) => a + c.measureText(w[0]).width, 0) + size * .28 * Math.max(0, l.length - 1); })); return [wide > maxW ? Math.floor(size * maxW / wide) : size, lines.length]; }
// the scene's line: 2 to 6 words at the top, each written on as it is said. Returns the y under it
const headline = (c, ws, t, o = {}) => { const [size, n] = fit(c, ws, o.size || 104, 940); write(c, ws, 540, o.y || 372, size, t, { maxW: 2000 }); return (o.y || 372) + n * size * 1.12; };
// a hatched box with its words centred: kind = green | red | blue | yellow | grey | violet
function card(c, sk, x, y, w, hh, t0, kind, ws, size = 100) { const [l, f, tc] = KIND[kind], [z, n] = fit(c, ws, size, w - 56); box(c, sk, x, y, w, hh, t0, l, f); write(c, ws.map(q => q[0] === '\n' ? q : [q[0], q[1], { c: tc, ...q[2] }]), x + w / 2, y + (hh - n * z * 1.12) / 2 + 2, z, sk.t, { maxW: 2000 }); }
// a yellow pill popping in (the step badge, or "from step 2")
const tag = (c, s, x, y, t, t0, col = C.yellow, w = 240) => { const u = E.back(pr(t, t0, t0 + .25)); if (u <= 0) return; c.save(); c.translate(x, y); c.scale(u, u); c.fillStyle = col; c.beginPath(); c.roundRect(-w / 2, -44, w, 88, 44); c.fill(); txt(c, s, 0, 4, FONT, 50, C.bg); c.restore(); };
const pop = (c, x, y, u, fn) => { if (u <= 0) return; c.save(); c.translate(x, y); c.scale(u, u); fn(); c.restore(); };
// a number or word landing at t0 with an overshoot
const land = (c, s, x, y, size, t, t0, col = C.green) => pop(c, x, y, E.back(pr(t, t0, t0 + .25)), () => txt(c, s, 0, 0, FONT, size, col));
// a number counting up between t0 and t1 (say the sound "counting" with it)
const count = (c, v, x, y, size, t, t0, t1, col = C.green, fmt = K.money) => { if (t > t0 - .15) pop(c, x, y, E.back(pr(t, t0 - .15, t0 + .1)), () => txt(c, fmt(Math.round(v * E.out(pr(t, t0, t1)))), 0, 0, FONT, size, col)); };
const label = (c, s, x, y, size, t, t0, col = C.text, al = 'center') => txt(c, s, x, y, FONT, size, col, al, pr(t, t0, t0 + .18));
const play = (sk, x, y, s, t0, o) => sk.path([...line(x - s * .5, y - s * .6, x + s * .65, y, 6), ...line(x + s * .65, y, x - s * .5, y + s * .6, 6), ...line(x - s * .5, y + s * .6, x - s * .5, y - s * .6, 6)], t0, t0 + .18, o);
const face = (c, sk, x, y, r, t0, mood, o = {}) => { sk.circ(x, y, r, t0, t0 + .28, o); const e = r * .34; sk.line(x - e, y - e * .5, x - e, y + e * .05, t0 + .2, t0 + .28, o); sk.line(x + e, y - e * .5, x + e, y + e * .05, t0 + .2, t0 + .28, o); sk.path(mood === 'flat' ? line(x - e, y + r * .36, x + e, y + r * .36, 6) : mood === 'sad' ? ell(x, y + r * .62, r * .42, r * .3, Math.PI * 1.15, Math.PI * 1.85, 12) : ell(x, y + r * .12, r * .45, r * .38, Math.PI * .12, Math.PI * .88, 12), t0 + .24, t0 + .34, o); };
// hearts rising off something people love
const hearts = (c, x, y, t, t0, n = 12, spread = 560, col = C.red) => { for (let i = 0; i < n; i++) { const a = t0 + i * .085; if (t < a) continue; const q = pr(t, a, a + 1.0); if (q >= 1) continue; const s = 26 + hash(i, 7) * 22, hx = x + (hash(i, 4) - .5) * spread * (.4 + q), hy = y - q * 260 - hash(i, 2) * 60; c.save(); c.globalAlpha = Math.sin(q * Math.PI); c.translate(hx, hy); c.rotate((hash(i, 1) - .5) * .6); c.scale(s / 30, s / 30); c.fillStyle = col; c.beginPath(); c.moveTo(0, 26); c.bezierCurveTo(-44, -6, -26, -38, 0, -16); c.bezierCurveTo(26, -38, 44, -6, 0, 26); c.fill(); c.restore(); } };
// one bar of a chart growing from baseline y, its value landing on top; big = the winner
function bar(c, x, y, w, hh, t, t0, val, col, fill, big = false) { const u = E.back(pr(t, t0, t0 + .42), 1.1); if (u <= 0) return; hatch(c, x + 4, y - hh * u, w - 8, hh * u, fill, 1, x); mk(c, t).rect(x, y - hh * u, w, hh * u, t0, t0 + .14, { c: col, w: 8 }); const z = big ? lerp(1.7, 1, E.out(pr(t, t0, t0 + .25))) : 1; c.save(); c.translate(x + w / 2, y - hh * u - (big ? 74 : 54)); c.scale(z, z); txt(c, val, 0, 0, FONT, big ? 122 : 80, big ? C.green : C.text, 'center', pr(t, t0 + .05, t0 + .2)); c.restore(); }
// n dots in a grid, drawn between t0 and t1; lit (yellow, with a play mark) between l0 and l1
function dots(c, n, cols, x, y, gap, r, t, t0, t1, l0, l1) { const k1 = E.io(pr(t, t0, t1)) * n, on = l0 ? pr(t, l0, l1) * n : 0, ord = dots[n] || (dots[n] = [...Array(n).keys()].sort((a, b) => hash(a, 9) - hash(b, 9))); c.save(); c.lineWidth = 5; for (let k = 0; k < n; k++) { const i = ord[k], u = E.back(clamp((k1 - k) / 6)); if (u <= 0) continue; const px = x + (i % cols) * gap, py = y + Math.floor(i / cols) * gap, lit = on > k; c.save(); c.translate(px, py); c.scale(u, u); c.strokeStyle = lit ? C.yellow : C.ink; c.fillStyle = lit ? 'rgba(255,212,59,.22)' : 'rgba(255,255,255,.05)'; c.beginPath(); c.arc(0, 0, r, 0, 7); c.fill(); c.stroke(); if (lit) { c.fillStyle = C.yellow; c.beginPath(); c.moveTo(-r * .28, -r * .44); c.lineTo(r * .48, 0); c.lineTo(-r * .28, r * .44); c.fill(); } c.restore(); } c.restore(); }
// a pie with one slice pulled out in yellow
function slice(c, sk, cx, cy, r, share, t0, txtAt) { const t = sk.t, u = pr(t, t0 + .05, t0 + .35), out = E.back(pr(t, t0 + .35, t0 + .6)) * r * .25, a0 = -Math.PI / 2, a1 = a0 + Math.PI * 2 * share, am = (a0 + a1) / 2; sk.path(ell(cx, cy, r, r, a1, a0 + Math.PI * 2), t0, t0 + .35, { c: C.grey, w: 8 }); if (u > 0) { c.save(); c.beginPath(); c.moveTo(cx, cy); c.arc(cx, cy, r, a1, a0 + Math.PI * 2); c.closePath(); c.clip(); hatch(c, cx - r, cy - r, r * 2, r * 2, FILL.grey, u, 5); c.restore(); sk.line(cx, cy, cx, cy - r, t0 + .15, t0 + .3, { c: C.grey, w: 7 }); sk.line(cx, cy, cx + Math.cos(a1) * r, cy + Math.sin(a1) * r, t0 + .15, t0 + .3, { c: C.grey, w: 7 }); }
  if (t > t0 + .27) { c.save(); c.translate(Math.cos(am) * out, Math.sin(am) * out); c.fillStyle = 'rgba(255,212,59,.92)'; c.beginPath(); c.moveTo(cx, cy); c.arc(cx, cy, r, a0, a1); c.closePath(); c.globalAlpha *= pr(t, t0 + .27, t0 + .37); c.fill(); c.restore(); if (txtAt) pop(c, txtAt[0], txtAt[1], E.back(pr(t, t0 + .3, t0 + .55)), () => txt(c, Math.round(share * 100) + '%', 0, 0, FONT, 168, C.yellow)); } }
// apps rolling down the road into a barrier that slams at t0 and lifts at t1 (a "most people stop here" stop, corner: true)
function barrier(c, t, t0, t1, n = 6, by = 980) { const open = E.io(pr(t, t1, t1 + .4)), slam = pr(t, t0, t0 + .14);
  for (let i = 0; i < n; i++) { const u = pr(t, t0 - .86 + i * .13, t0 - .06 + i * .09); if (u <= 0) continue; const d = 300 + E.out(u) * (by - 150 - i * 108 - 300); c.save(); c.translate(540 + (hash(i, 3) - .5) * 26, d); c.rotate((hash(i, 5) - .5) * .25 * u); c.fillStyle = '#1d1d1d'; c.strokeStyle = [C.grey, C.blue, C.violet, C.grey, C.orange, C.blue][i % 6]; c.lineWidth = 7; c.beginPath(); c.roundRect(-46, -46, 92, 92, 26); c.fill(); c.stroke(); c.lineWidth = 5; c.beginPath(); if (i % 2) c.arc(0, 0, 18, 0, 7); else { c.moveTo(-18, -8); c.lineTo(18, -8); c.moveTo(-18, 10); c.lineTo(8, 10); } c.stroke(); c.restore(); }
  if (slam > 0) { const y = lerp(by - 900, by, E.in(slam)), q = t - t0 - .14, sh = q > 0 && q < .2 ? Math.sin(t * 120) * 12 * (1 - q / .2) : 0; c.save(); c.translate(170, y + sh); c.rotate(-open * 1.15); c.save(); c.beginPath(); c.roundRect(0, -56, 740, 112, 18); c.clip(); for (let k = -2; k < 14; k++) { c.fillStyle = k % 2 ? C.yellow : C.bg; c.beginPath(); c.moveTo(k * 70, 60); c.lineTo(k * 70 + 70, 60); c.lineTo(k * 70 + 130, -60); c.lineTo(k * 70 + 60, -60); c.fill(); } c.restore(); c.strokeStyle = C.yellow; c.lineWidth = 8; c.beginPath(); c.roundRect(0, -56, 740, 112, 18); c.stroke(); c.restore(); c.fillStyle = C.ink; c.beginPath(); c.roundRect(120, y - 90, 60, 180, 14); c.fill(); } }
// the chequered flag at the end of the road
function flag(c, t, t0) { const u = E.back(pr(t, t0 + .1, t0 + .5), 1.4); if (u <= 0) return; mk(c, t).line(420, 1180, 420, 620, t0 + .05, t0 + .25, { w: 14 }); for (let a = 0; a < 5; a++) for (let b = 0; b < 4; b++) { c.fillStyle = (a + b) % 2 ? C.text : '#1c1c1c'; c.globalAlpha = u; c.fillRect(428 + a * 62 * u, 630 + b * 54, 62 * u, 54); } c.globalAlpha = 1; }
const h = { C, FILL, FONT, K, mk, headline, card, hatch, box, write, tag, pop, land, count, label, play, face, hearts, bar, dots, slice, barrier, flag, line, ell, rectP, spline, txt, pr, E, lerp, clamp, hash };

// ---------- one reel
function make(R) {
  const N = Math.round(R.dur * 30), stops = R.stops, ids = stops.map(s => String(s.id)), by = {}; stops.forEach(s => by[String(s.id)] = s);
  const cell = {}; ids.forEach((id, i) => { const r = Math.floor(i / 3), q = i % 3; cell[id] = [r % 2 ? 2 - q : q, r]; });                    // a snake, three across
  const ctr = k => [cell[k][0] * CW + 540, cell[k][1] * CH + 860], badge = k => [cell[k][0] * CW + 540, cell[k][1] * CH + 300];
  const isStep = k => !by[k].extra;

  // ---- map views: { NAME: { rows: [first, last], title, at: [t0, t1] } }; a pull-back over those rows of the map
  const V = {}; for (const [k, v] of Object.entries(R.views || {})) { const n = v.rows[1] - v.rows[0] + 1; V[k] = [CW + 540, (v.rows[0] + v.rows[1]) / 2 * CH + 860 + (v.dy || 0), v.z || Math.min(.245, 1323 / (n * CH))]; }
  const view = k => V[k] || [...ctr(k), 1];

  // ---- flights: from stop to stop, about 0.32 s before the step's first word to 0.45 s after it
  const FL = R.flights ? R.flights.map(f => [f[0], f[1], String(f[2]), String(f[3]), f[4] || 0]) : ids.slice(1).map((k, i) => { const a = ids[i], s = by[k]; return [s.at - .32, s.at + .45, a, k, cell[a][1] === cell[k][1] ? .36 : .3]; });
  const since = k => { let s = 0; for (const f of FL) if (f[3] === k) s = f[1]; return s; };
  const left = k => { for (const f of FL) if (f[2] === k) return f[1]; return 1e9; };
  const drift = (k, t, s) => 1 + .0085 * Math.max(0, Math.min(6, t - s));                                                                     // never still: a slow push in on every scene

  // ---- road: badge to badge; a bulge round the outside where it turns down a row, or straight down through a corner stop
  const ROAD = (() => { const p = [], at = {}, q = Math.PI / 2, arc = (cx, cy, r, a0, a1) => ell(cx, cy, r, r, a0, a1, 14); p.push(badge(ids[0])); at[ids[0]] = 0; let from = badge(ids[0]);
    for (let i = 1; i < ids.length; i++) { const k = ids[i], a = ids[i - 1], [x1, y1] = badge(k), sameRow = cell[a][1] === cell[k][1], dir = cell[k][1] % 2 ? -1 : 1;
      if (sameRow && by[k].corner) { const s = dir < 0 ? -1 : 1; p.push(...line(from[0], from[1], x1 - s * 160, y1, 50), ...(s < 0 ? arc(x1 + 160, y1 + 160, 160, -q, -2 * q) : arc(x1 - 160, y1 + 160, 160, -q, 0))); from = [x1, y1 + 160]; }
      else if (sameRow) { p.push(...line(from[0], from[1], x1, y1, 60)); from = [x1, y1]; }
      else if (by[a].corner) { p.push(...line(from[0], from[1], x1, y1, 60)); from = [x1, y1]; }
      else { const s = cell[a][0] === 2 ? 1 : -1, ux = from[0] + s * 520, y0 = from[1]; p.push(...line(from[0], y0, ux - s * 160, y0, 16), ...(s > 0 ? arc(ux - 160, y0 + 160, 160, -q, 0) : arc(ux + 160, y0 + 160, 160, -q, -2 * q)), ...line(ux, y0 + 160, ux, y1 - 160, 50), ...(s > 0 ? arc(ux - 160, y1 - 160, 160, 0, q) : arc(ux + 160, y1 - 160, 160, 2 * q, q)), ...line(ux - s * 160, y1, x1, y1, 16)); from = [x1, y1]; }
      at[k] = p.length - 1; }
    if (p.length < 2) return { r: p, D: { [ids[0]]: 0 } };
    const r = K.resample(p, 40), D = {}; for (const k of ids) { const [x, y] = p[at[k]]; let best = 0, bd = 1e9; r.forEach(([a, b], i) => { const d = Math.hypot(a - x, b - y); if (d < bd) { bd = d; best = i; } }); D[k] = best; } return { r, D }; })();
  // how much of the road is drawn: it runs ahead of the camera to the next stop
  const RT = [[-1, ids[0]]]; { let cur = ids[0]; const arrive = {}; FL.forEach(f => { if (by[f[3]]) arrive[f[3]] = f; }); for (const k of ids.slice(1)) { const f = arrive[k], o = by[k].road || (f ? [f[0] - .15, f[1] - .22] : [by[k].at - .4, by[k].at + .2]); RT.push([o[0], cur], [o[1], k]); cur = k; } }
  const roadN = t => { for (let i = 0; i < RT.length - 1; i++) if (t < RT[i + 1][0]) { const [a, k0] = RT[i], [b, k1] = RT[i + 1]; return lerp(ROAD.D[k0], ROAD.D[k1], E.io(pr(t, a, b))); } return ROAD.r.length - 1; };

  // ---- camera
  const hitK = t => (R.hits || []).reduce((z, [a]) => z * (t > a ? 1 + .05 * Math.exp(-pr(t, a, a + .36) * 4) : 1), 1);
  function cam(t) { let cur = ids[0], s0 = 0;
    for (const [a, b, f, to, dip] of FL) { if (t >= b) { cur = to; s0 = b; continue; } if (t >= a) { const u = E.io(pr(t, a, b)), A = view(f), B = view(to), zA = A[2] * (V[f] ? 1 : drift(f, a, since(f))), z = Math.exp(lerp(Math.log(zA), Math.log(B[2]), u)) * (1 - Math.sin(u * Math.PI) * dip);
        let m = u; if (V[f] || V[to]) { const k = B[2] / zA; m = Math.abs(k - 1) < .01 ? u : (1 - zA / z) / (1 - zA / B[2]); }                   // a pull-back pans in step with the zoom, so it keeps its subject
        return [lerp(A[0], B[0], m), lerp(A[1], B[1], m), z]; } break; }
    const [x, y, z] = view(cur), mv = by[cur] && by[cur].moves;
    if (mv) { let dx = 0, dy = 0, zz = 1; for (const [a, b, x1, y1, z1] of mv) { if (t >= b) { dx = x1; dy = y1; zz = z1; } else if (t >= a) { const u = E.io(pr(t, a, b)); dx = lerp(dx, x1, u); dy = lerp(dy, y1, u); zz = lerp(zz, z1, u); break; } else break; } return [x + dx, y + dy, zz * (1 + .006 * (t - s0)) * hitK(t)]; }
    return [x, y, z * drift(cur, t, s0) * hitK(t)]; }

  // ---- one frame
  function world(c, t) { const [x, y, z] = cam(t); let sx = 0, sy = 0; for (const [a, amp, d = .22] of R.shakes || []) if (t > a && t < a + d) { const k = amp * (1 - pr(t, a, a + d)); sx = Math.sin(t * 112) * k; sy = Math.cos(t * 96) * k; }
    c.save(); c.translate(540 + sx, 860 + sy); c.scale(z, z); c.translate(-x, -y);
    const hw = 560 / z + 80, up = 880 / z + 80, dn = 1080 / z + 80, far = z < .45, gap = far ? 240 : 60, gs = far ? 12 : 4; c.fillStyle = 'rgba(255,255,255,.075)'; for (let a = Math.floor((x - hw) / gap) * gap; a < x + hw; a += gap) for (let b = Math.floor((y - up) / gap) * gap; b < y + dn; b += gap) c.fillRect(a, b, gs, gs);
    const n = roadN(t); c.fillStyle = far ? '#dcdcdc' : '#9a9a9a'; const rr = far ? 13 : 7; for (let i = 0; i < n; i++) { const [a, b] = ROAD.r[i]; if (a < x - hw || a > x + hw || b < y - up || b > y + dn) continue; c.beginPath(); c.arc(a, b, rr, 0, 7); c.fill(); }
    const lod = clamp((.55 - z) / .22);                                                                                                          // 0 = in a scene, 1 = on the map
    for (const k of ids) { const s = by[k], [cx, cy] = ctr(k); if (Math.abs(cx - x) > hw + 560 || cy - y > dn + 720 || y - cy > up + 760) continue; if (t < s.at - .6) continue; const map = lod > .5 && t > left(k);
      c.save(); c.translate(cx - 540, cy - 860); c.save(); if (lod > 0 && isStep(k)) c.globalAlpha = 1 - lod * .94; s.draw(c, t, mk(c, t), { map }); c.restore();
      if (isStep(k)) { if (lod < 1) { c.save(); c.globalAlpha = 1 - lod; tag(c, s.label || 'step ' + k, 540, 300, t, s.at - .12, C.yellow, s.labelW); c.restore(); }
        if (lod > 0 && t > s.at) { c.save(); c.globalAlpha = lod; c.fillStyle = C.bg; c.beginPath(); c.arc(540, 300, 190, 0, 7); c.fill(); c.fillStyle = C.yellow; c.beginPath(); c.arc(540, 300, 168, 0, 7); c.fill(); txt(c, s.num || k, 540, 312, FONT, 210, C.bg); (s.map || []).forEach((m, i) => { let f = 218; c.font = `${f}px "${FONT}"`; const w = c.measureText(m).width; if (w > 1010) f *= 1010 / w; txt(c, m, 540, 690 + i * 236, FONT, f, C.text); }); c.restore(); } }
      else if (s.map && (s.finish ? lod > 0 : map)) { c.save(); c.globalAlpha = s.finish ? lod * pr(t, s.at + .3, s.at + .55) : lod; if (s.finish) txt(c, s.map[0], 560, 1330, FONT, 340, C.green); else s.map.forEach((m, i) => txt(c, m, 540, 1180 + i * 170, FONT, 170, C.red)); c.restore(); }
      c.restore(); }
    if (far) for (const [k, v] of Object.entries(R.views || {})) if (v.title && v.at) { const u = pr(t, v.at[0], v.at[0] + .25) * (1 - pr(t, v.at[1], v.at[1] + .2)); if (u > 0) txt(c, v.title, CW + 540, v.rows[0] * CH - 330, FONT, 330, C.yellow, 'center', u); }
    c.restore(); }
  let layer; function frame(c, n) { const t = n / 30; c.fillStyle = C.bg; c.fillRect(0, 0, W, H); const a = cam(t), b = cam(t - 1 / 30), sp = Math.hypot(a[0] - b[0], a[1] - b[1]) * a[2] + Math.abs(Math.log(a[2] / b[2])) * 500; if (sp < 26) { world(c, t); return; }
    const k = Math.max(4, Math.min(14, Math.ceil(sp / 9))), [o, x] = layer || (layer = K.layer()); for (let i = 0; i < k; i++) { x.globalAlpha = 1; x.fillStyle = C.bg; x.fillRect(0, 0, W, H); world(x, t - (i / k) * (.55 / 30)); c.globalAlpha = 1 / (i + 1); c.drawImage(o, 0, 0); } c.globalAlpha = 1; }   // real motion blur on every flight

  const where = t => FL.reduce((k, f) => t >= f[1] ? f[3] : k, ids[0]);
  const api = { frame, world, cam, where, by, N, dur: R.dur, flights: FL, stops, ids };
  setImmediate(() => { if (require.main && require.main.exports === api) cli(api, R).catch(e => { console.error(e); process.exit(1); }); });
  return api;
}

// ---------- command line of a scenes file
async function cli(A, R) { const [, file, cmd, a, b, d] = process.argv, dir = process.cwd(), c = K.createCanvas(W, H), x = c.getContext('2d'); const draw = n => { x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; A.frame(x, n); };
  if (cmd === 'still') { const ts = a.split(',').map(Number).slice(0, 4), s = K.createCanvas(648 * ts.length, 1152), sx = s.getContext('2d'); ts.forEach((t, i) => { draw(Math.min(A.N - 1, Math.round(t * 30))); sx.drawImage(c, i * 648, 0, 648, 1152); sx.fillStyle = '#fff'; sx.font = '24px "MonoB"'; sx.fillText(t.toFixed(2), i * 648 + 10, 28); }); fs.writeFileSync(path.resolve(dir, b || 'still.jpg'), s.toBuffer('image/jpeg', 92)); }
  else if (cmd === 'sheet') { const ts = a.split(',').map(Number), w = 270, hh = 480, cols = Math.min(8, ts.length), rows = Math.ceil(ts.length / cols), s = K.createCanvas(w * cols, hh * rows), sx = s.getContext('2d'); ts.forEach((t, i) => { draw(Math.min(A.N - 1, Math.round(t * 30))); sx.drawImage(c, (i % cols) * w, Math.floor(i / cols) * hh, w, hh); sx.fillStyle = '#fff'; sx.font = '18px "MonoB"'; sx.fillText(t.toFixed(2), (i % cols) * w + 8, Math.floor(i / cols) * hh + 22); }); fs.writeFileSync(path.resolve(dir, b || 'sheet.jpg'), s.toBuffer('image/jpeg', 88)); }
  else if (cmd === 'render') { const ff = require('child_process').spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '1080x1920', '-r', '30', '-i', '-', '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-crf', '10', '-preset', 'fast', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', path.resolve(dir, a)], { stdio: ['pipe', 'inherit', 'inherit'] }); const n1 = d ? +d : A.N; for (let n = b ? +b : 0; n < n1; n++) { draw(n); if (!ff.stdin.write(Buffer.from(c.data()))) await new Promise(r => ff.stdin.once('drain', r)); } ff.stdin.end(); await new Promise(r => ff.on('close', r)); }
  else if (cmd === 'info') console.log(JSON.stringify({ dur: A.dur, frames: A.N, flights: A.flights, cues: A.stops.reduce((o, s) => { for (const [k, v] of Object.entries(s.cues || {})) (o[k] = o[k] || []).push(...v); return o; }, { ...(R.cues || {}) }) }));
  else if (cmd === 'check') check(A, R, x);
  else console.log('sheet <t,t,...> [out.jpg] | still <t,t,...> [out.jpg] | render <out.mp4> [from] [to] | check | info'); }

// measured on real frames: ink outside the safe area while the camera is parked, and stretches where nothing new is drawn
const STILL_MAX = 1.5, LATE = .95, LOW = 1380, GAP = 180, THIN = 7.5;   // measured on a finished reel: nothing new for 1.4 s at most, first ink 0.2 to 0.93 s into a step, lowest ink y 1408 to 1496, empty bands to 176 px, 8 to 22% ink
function check(A, R, x) { const rj = process.argv[3], faces = rj ? JSON.parse(fs.readFileSync(path.resolve(rj))).faces || [] : [], hid = t => faces.some(f => t > f.in && t < f.out + .25), parked = t => !A.flights.some(f => t > f[0] - .05 && t < f[1] + .1); const areas = {}, still = []; let last = null, key = '', since = 0, idle = false;
  const ink = (d, x0, y0, x1, y1) => { let n = 0; for (let yy = y0; yy < y1; yy += 4) for (let xx = x0; xx < x1; xx += 4) { const i = (yy * W + xx) * 4; if (Math.max(d[i], d[i + 1], d[i + 2]) > 168) n++; } return n; };      // the road's grey dots don't count
  const end = t => { if (idle && t - since > STILL_MAX) still.push([since, t, key]); idle = false; };
  for (let n = 0; n < A.N; n += 6) { const t = n / 30, k = A.where(t); if (!parked(t) || hid(t) || !A.by[k]) { end(t); last = null; continue; } x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; A.frame(x, n); let d = x.getImageData(0, 0, W, H).data;
    for (const [nm, ...r] of [['top (above y 214)', 0, 0, W, 214], ['bottom (below y 1506)', 0, 1506, W, H], ['left (x < 34)', 0, 340, 34, 1506], ['right (x > 1046)', 1046, 340, W, 1506], ['like/share column (x > 906 below y 1156)', 906, 1156, W, 1506]]) if (ink(d, ...r) > 40) { const q = `${nm} in stop ${k}`; (areas[q] = areas[q] || []).push(t); }
    x.fillStyle = C.bg; x.fillRect(0, 0, W, H); A.by[k].draw(x, t, mk(x, t), { map: false }); d = x.getImageData(0, 0, W, H).data; const sig = new Uint8Array(360 * 640); for (let yy = 0; yy < 640; yy++) for (let xx = 0; xx < 360; xx++) sig[yy * 360 + xx] = d[((yy * 3) * W + xx * 3) * 4 + 1] >> 4; let q = 0; if (last && key === k) for (let i = 0; i < sig.length; i++) q += sig[i] !== last[i];
    if (last && key === k && q < 25) { if (!idle) { idle = true; since = t - .2; } } else end(t); last = sig; key = k; } end(A.N / 30);
  const thin = []; for (const st of A.stops) { if (st.extra) continue; const k = String(st.id), f = A.flights.find(q => q[2] === k); let end = f ? f[0] : A.N / 30; for (const q of faces) if (q.in < end && q.out > end - .6) end = Math.min(end, q.in);
    const at = t => { x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.fillStyle = C.bg; x.fillRect(0, 0, W, H); st.draw(x, t, mk(x, t), { map: false }); const d = x.getImageData(0, 0, W, H).data, ys = []; let n = 0; for (let yy = 340; yy < 1620; yy += 4) { let q = 0; for (let xx = 0; xx < W; xx += 4) { const i = (yy * W + xx) * 4; if (Math.max(d[i], d[i + 1], d[i + 2]) > 70) q++; } if (q > 2) ys.push(yy); n += q; } return { n, ys }; };
    let first = null; for (let t = st.at - .3; t < end && first === null; t += 1 / 30) if (at(t).n > 60) first = t; if (first === null) { thin.push(`stop ${k}: nothing is drawn`); continue; } if (first - st.at > LATE) thin.push(`stop ${k}: empty for ${(first - st.at).toFixed(1)} s after the step starts; draw the frame of the picture while the speaker says "step ${k}"`);
    const e = at(end - .05); let gap = 0, g = 0; e.ys.forEach((v, i) => { if (i && v - e.ys[i - 1] > gap) { gap = v - e.ys[i - 1]; g = e.ys[i - 1]; } }); const low = e.ys[e.ys.length - 1]; if (low < LOW) thin.push(`stop ${k}: the finished scene ends at y ${low}; fill down to about 1400 to 1490`); if (gap > GAP) thin.push(`stop ${k}: an empty band of ${gap} px at y ${g}`); const pc = e.n / (1280 * W / 16) * 100; if (pc < THIN) thin.push(`stop ${k}: only ${pc.toFixed(1)}% of the frame is drawn (approved scenes 8 to 22%); make the picture bigger`); }
  const runs = ts => { const o = []; ts.forEach(t => { if (o.length && t - o[o.length - 1][1] < .45) o[o.length - 1][1] = t; else o.push([t, t]); }); return o.map(([p, q]) => `${p.toFixed(1)}-${q.toFixed(1)}`).join(', '); };
  for (const [nm, ts] of Object.entries(areas)) console.log(`WARN bright ink in the ${nm} at ${runs(ts)} s`); for (const [s, e, k] of still) console.log(`WARN nothing new is drawn in stop ${k} for ${(e - s).toFixed(1)} s (${s.toFixed(1)}-${e.toFixed(1)}): draw something on those words or put a face moment there`); thin.forEach(m => console.log('WARN ' + m)); if (!Object.keys(areas).length && !still.length && !thin.length) console.log('OK safe area clear, scenes full, something new at least every ' + STILL_MAX + ' s'); }

module.exports = { make, h, K };
