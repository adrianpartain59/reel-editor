// Split Screen's top half: the hand-drawn canvas redrawn wide and short (1080 x 764), the face is under it.
// One cell per beat in a row, a dotted road between them, the camera flies along it. A reel only writes scenes.js
// (canvas_init.py PROJECT split copies split.starter.scenes.js). Guide: references/split-screen.md.
//
//   const { make, p } = require('<skill>/assets/graphic-styles/canvas/panel_engine');
//   module.exports = make({ cells: [{ id, n, at, draw }], recap: { at, first, names } });   // last line
//
//   node scenes.js sheet 12.5,13.2 out.jpg      stills at those seconds of the cut
//   node scenes.js still 18.0,22.3 out.jpg      up to four big ones
//   node scenes.js check                        ink outside the panel's safe area, empty starts, stretches with nothing new
//   node scenes.js render out.mp4 t0 t1         the panel between those seconds (split_reel.py calls this)
//   node panel_engine.js cards names.json dir   the hook's blurred cards (split_reel.py calls this)
const { h } = require('./engine'); const { C, FILL, FONT, K, mk, hatch, box, write, tag, pop, label, face, line, ell, spline, txt, pr, E, lerp, clamp } = h;
const fs = require('fs'), path = require('path'), PW = 1080, PH = 764, CW = 1260, HY = 248, Z0 = .965;
const COL = [C.green, C.yellow, C.violet, C.orange, C.blue, C.red, C.grey];                             // the hook cards and the recap, in order

// ---------- pieces (coordinates in a cell: x 34 to 1040, the header row at y 248, the drawing between y 325 and 715)
// the #n pill and the line beside it, written on as it is said; shrinks to fit one line. n = null: no pill, the line starts at the left edge
function head(c, t, n, tn, ws) { if (n !== null) tag(c, '#' + n, 122, HY, t, tn, C.yellow, 152); const x = n === null ? 48 : 226, max = n === null ? 970 : 780; let size = 94; c.font = `${size}px "${FONT}"`; const w = ws.reduce((a, q) => a + c.measureText(q[0]).width, 0) + size * .28 * (ws.length - 1); if (w > max) size = Math.floor(size * max / w); write(c, ws, x, HY - size * .5, size, t, { align: 'left', maxW: 4000 }); }
// a pill as wide as its words
const pill = (c, s, x, y, t, t0, col = C.yellow) => { c.font = `50px "${FONT}"`; tag(c, s, x, y, t, t0, col, Math.max(130, c.measureText(s).width + 76)); };
// how wide words are at a size, for placing labels: p.wide(c, 'fixed bedtime', 52)
const wide = (c, s, size) => { c.font = `${size}px "${FONT}"`; return c.measureText(s).width; };
const brackets = (S, x, y, r, t0, o) => { const L = r * .5; for (const [a, b] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) S().path([...line(x + a * r, y + b * (r - L), x + a * r, y + b * r, 6), ...line(x + a * r, y + b * r, x + a * (r - L), y + b * r, 6)], t0, t0 + .22, o); };   // camera corners round a thing
const tick = (S, x, y, s, t0, o) => S().path([...line(x - s, y, x - s * .25, y + s * .75, 6), ...line(x - s * .25, y + s * .75, x + s, y - s * .8, 8)], t0, t0 + .18, o);
function star(c, x, y, r, u, col) { if (u <= 0) return; c.save(); c.translate(x, y); c.scale(u, u); c.fillStyle = col; c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, q = i % 2 ? r * .45 : r; c[i ? 'lineTo' : 'moveTo'](Math.cos(a) * q, Math.sin(a) * q); } c.closePath(); c.fill(); c.restore(); }
// a bar growing off baseline y; val lands on top (leave it out for the loser)
const bar = (c, S, x, y, w, hh, t, t0, col, fill, val, size = 100) => { const u = E.back(pr(t, t0, t0 + .42), 1.1); if (u <= 0) return; hatch(c, x + 4, y - hh * u, w - 8, hh * u, fill, 1, x); S().rect(x, y - hh * u, w, hh * u, t0, t0 + .14, { c: col, w: 8 }); if (val) { const z = lerp(1.7, 1, E.out(pr(t, t0, t0 + .25))); c.save(); c.translate(x + w / 2, y - hh * u - size * .6); c.scale(z, z); txt(c, val, 0, 0, FONT, size, col, 'center', pr(t, t0 + .05, t0 + .2)); c.restore(); } };
// a number counting up and landing; fmt(v) makes the text
const count = (c, v, x, y, size, t, t0, t1, col, fmt) => { if (t > t0) pop(c, x, y, E.back(pr(t, t0, t0 + .25)), () => txt(c, (fmt || (n => n.toLocaleString('en-US')))(Math.round(v * E.out(pr(t, t0, t1)))), 0, 0, FONT, size, col)); };
// a ready-made app icon (rounded square) popping in; on = lit in colour
const icon = (c, x, y, s, t, t0, col, fn) => pop(c, x + s / 2, y + s / 2, E.back(pr(t, t0, t0 + .24)), () => { c.save(); c.translate(-x - s / 2, -y - s / 2); const k = mk(c, 99); k.rect(x, y, s, s, -1, -1, { c: col, w: 8, r: s * .24 }); if (fn) fn(k); c.restore(); });
const p = { ...h, head, pill, wide, brackets, tick, star, bar, count, icon, COL, PW, PH };

// ---------- one reel
function make(R) {
  const cells = R.cells.map(q => ({ ...q })); if (R.recap) cells.push({ id: 'recap', at: R.recap.at, fly: R.recap.fly, draw: recap(R.recap) });
  const FL = cells.slice(1).map((q, i) => [...(q.fly || [q.at - .10, q.at + .36]), i, i + 1]);              // after the last word of the scene before, which is cut tight to it
  function recap(r) { const n = r.names.length, gap = Math.min(108, 540 / n), y0 = 462 - gap * (n - 1) / 2; return (c, t) => { c.font = `${78 * gap / 108}px "${FONT}"`; const w = Math.max(...r.names.map(s => c.measureText(s).width)), k = gap / 108 * Math.min(1, 752 / w); r.names.forEach((s, i) => { const y = y0 + i * gap, a = r.first + i * (r.every || .17); pop(c, 196, y, E.back(pr(t, a, a + .24)), () => { c.fillStyle = COL[i % COL.length]; c.beginPath(); c.arc(0, 0, 44 * k, 0, 7); c.fill(); txt(c, String(i + 1), 0, 4 * k, FONT, 58 * k, C.bg); }); write(c, [[s, a + .05]], 276, y - 41 * k, 78 * k, t, { align: 'left', maxW: 4000 }); }); }; }
  const drift = (t, s) => Z0 * (1 + .005 * Math.max(0, Math.min(6, t - s)));                            // a touch under full size so the labels clear the caption on the seam
  function cam(t) { let cur = 0, s0 = cells[0].at - .4; for (const [a, b, f, g] of FL) { if (t >= b) { cur = g; s0 = b; continue; } if (t >= a) { const u = E.io(pr(t, a, b)), zA = drift(a, s0); return [lerp(f * CW + 540, g * CW + 540, u), Math.exp(lerp(Math.log(zA), Math.log(Z0), u)) * (1 - Math.sin(u * Math.PI) * .2)]; } break; } return [cur * CW + 540, drift(t, s0)]; }
  const where = t => FL.reduce((k, f) => t >= f[1] ? f[3] : k, 0), left = k => { const f = FL.find(q => q[2] === k); return f ? f[0] : 1e9; };
  const drawCell = (c, i, t) => { const q = cells[i], tt = t + (q.shift || 0); q.draw(c, tt, () => mk(c, tt), p); };   // shift: after a recut, move a whole scene instead of retyping its times
  function world(c, t) { const [x, z] = cam(t); c.save(); c.translate(540, PH / 2 - 10); c.scale(z, z); c.translate(-x, -PH / 2); const hw = 560 / z + 80, vh = PH / 2 / z + 80;
    c.fillStyle = 'rgba(255,255,255,.075)'; for (let a = Math.floor((x - hw) / 60) * 60; a < x + hw; a += 60) for (let b = Math.floor((PH / 2 - vh) / 60) * 60; b < PH / 2 + vh; b += 60) c.fillRect(a, b, 4, 4);
    c.fillStyle = '#9a9a9a'; FL.forEach(([a, b, f]) => { const u = pr(t, a - .15, b - .12), x0 = f * CW + 1096, x1 = (f + 1) * CW - 70; for (let q = x0; q < x0 + (x1 - x0) * u; q += 36) { c.beginPath(); c.arc(q, HY, 7, 0, 7); c.fill(); } });
    cells.forEach((q, i) => { const ox = i * CW; if (Math.abs(ox + 540 - x) > hw + 560 || t < q.at - .6) return; c.save(); c.translate(ox, 0); drawCell(c, i, t); c.restore(); }); c.restore(); }
  let layer; function frame(c, t) { c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.fillStyle = C.bg; c.fillRect(0, 0, PW, PH); const a = cam(t), b = cam(t - 1 / 30), sp = Math.abs(a[0] - b[0]) * a[1] + Math.abs(Math.log(a[1] / b[1])) * 500; if (sp < 26) return world(c, t);
    const k = Math.max(4, Math.min(14, Math.ceil(sp / 9))), [o, x] = layer || (layer = K.layer(PW, PH)); for (let i = 0; i < k; i++) { x.globalAlpha = 1; x.fillStyle = C.bg; x.fillRect(0, 0, PW, PH); world(x, t - (i / k) * (.55 / 30)); c.globalAlpha = 1 / (i + 1); c.drawImage(o, 0, 0); } c.globalAlpha = 1; }   // real motion blur on every flight
  const api = { frame, cells, flights: FL, where, left, drawCell };
  setImmediate(() => { if (require.main && require.main.exports === api) cli(api).catch(e => { console.error(e); process.exit(1); }); }); return api; }

async function cli(A) { const [, , cmd, a, b, d] = process.argv, cv = K.createCanvas(PW, PH), c = cv.getContext('2d');
  if (cmd === 'sheet' || cmd === 'still') { const big = cmd === 'still', ts = a.split(',').map(Number).slice(0, big ? 4 : 99), w = big ? 810 : 540, hh = Math.round(w * PH / PW), cols = Math.min(big ? 2 : 4, ts.length), s = K.createCanvas(w * cols, hh * Math.ceil(ts.length / cols)), x = s.getContext('2d'); ts.forEach((t, i) => { frameTo(A, c, t); x.drawImage(cv, (i % cols) * w, Math.floor(i / cols) * hh, w, hh); x.fillStyle = '#fff'; x.font = '20px "MonoB"'; x.fillText(t.toFixed(2), (i % cols) * w + 8, Math.floor(i / cols) * hh + 22); }); fs.mkdirSync(path.dirname(path.resolve(b || 'sheet.jpg')), { recursive: true }); fs.writeFileSync(b || 'sheet.jpg', s.toBuffer('image/jpeg', 90)); }
  else if (cmd === 'render') { const n0 = Math.round(+b * 30), n1 = Math.round(+d * 30), ff = require('child_process').spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${PW}x${PH}`, '-r', '30', '-i', '-', '-c:v', 'libx264rgb', '-crf', '6', '-preset', 'fast', a], { stdio: ['pipe', 'inherit', 'inherit'] }); for (let n = n0; n < n1; n++) { A.frame(c, n / 30); if (!ff.stdin.write(Buffer.from(c.getImageData(0, 0, PW, PH).data.buffer.slice(0)))) await new Promise(r => ff.stdin.once('drain', r)); } ff.stdin.end(); await new Promise(r => ff.on('close', r)); console.log(n1 - n0, 'panel frames'); }
  else if (cmd === 'check') check(A, c); else if (cmd === 'info') console.log(JSON.stringify({ cells: A.cells.map(q => [q.id, q.at]), flights: A.flights })); else console.log('sheet <t,t> [out] | still <t,t> [out] | check | info | render <out.mp4> <t0> <t1>'); }
const frameTo = (A, c, t) => A.frame(c, t);

// measured on the cell itself, not the camera: what the finished scene covers, when its first ink lands, and how long nothing new is drawn
function check(A, c) { const msgs = []; const snap = (i, t) => { c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.fillStyle = C.bg; c.fillRect(0, 0, PW, PH); A.drawCell(c, i, t); return c.getImageData(0, 0, PW, PH).data; };
  // where every piece of text sits on a finished cell, to find words on top of words
  const texts = (i, t) => { const out = [], fill = c.fillText; c.fillText = function (s, x, y) { const m = c.getTransform(), w = c.measureText(s).width, z = parseFloat(c.font), al = c.textAlign, x0 = al === 'center' ? x - w / 2 : al === 'right' ? x - w : x, mid = c.textBaseline === 'middle'; if (c.globalAlpha > .4 && String(s).trim()) out.push({ s, x0: m.a * x0 + m.e, x1: m.a * (x0 + w) + m.e, y0: m.d * (mid ? y - z * .36 : y - z * .7) + m.f, y1: m.d * (mid ? y + z * .36 : y + z * .12) + m.f }); return fill.apply(c, arguments); }; snap(i, t); c.fillText = fill; return out; };
  const bounds = d => { let x0 = PW, x1 = 0, y0 = PH, y1 = 0, n = 0; for (let y = 0; y < PH; y += 2) for (let x = 0; x < PW; x += 2) { const i = (y * PW + x) * 4; if (Math.max(d[i], d[i + 1], d[i + 2]) > 80) { n++; x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); } } return { x0, x1, y0, y1, n }; };
  A.cells.forEach((q, i) => { if (q.id === 'recap') { const b = bounds(snap(i, q.at + 6)); if (b.x1 > 1046) msgs.push(`recap: a name runs to x ${b.x1}; shorten it`); return; } const end = Math.min(A.left(i), q.at + 12) - .04, b = bounds(snap(i, end)); if (!b.n) return msgs.push(`cell ${q.id}: nothing is drawn`);
    if (b.x0 < 34) msgs.push(`cell ${q.id}: ink at x ${b.x0}, keep it right of 34`); if (b.x1 > 1046) msgs.push(`cell ${q.id}: ink at x ${b.x1}, keep it left of 1040`); if (b.y0 < 190) msgs.push(`cell ${q.id}: ink at y ${b.y0}, nothing above 195 (Instagram's header)`); if (b.y1 > 738) msgs.push(`cell ${q.id}: ink at y ${b.y1}, nothing below 735 (the caption sits on the seam)`);
    if (b.y1 < 600) msgs.push(`cell ${q.id}: the drawing ends at y ${b.y1}; fill down to about 690 to 715`); if (b.x1 < 900) msgs.push(`cell ${q.id}: the drawing ends at x ${b.x1}; use the whole width, to about 980 to 1030`);
    const tx = texts(i, end), seen = new Set(); for (let a = 0; a < tx.length; a++) for (let z = a + 1; z < tx.length; z++) { const A1 = tx[a], B1 = tx[z], ox = Math.min(A1.x1, B1.x1) - Math.max(A1.x0, B1.x0), oy = Math.min(A1.y1, B1.y1) - Math.max(A1.y0, B1.y0), key = A1.s + '|' + B1.s; if (ox > 6 && oy > 8 && !seen.has(key)) { seen.add(key); msgs.push(`cell ${q.id}: "${A1.s}" and "${B1.s}" sit on top of each other`); } }
    const nx = A.left(i) < 1e8 ? A.left(i) : null; if (nx && nx - q.at > 7) msgs.push(`cell ${q.id}: ${(nx - q.at).toFixed(1)} s on one drawing; give the second half its own cell (3 to 6 s each)`);
    let first = null, last = null, still = 0, at = null, sig = null; for (let t = q.at - .4; t < end; t += .1) { const d = snap(i, t), s = bounds(d).n; let diff = 0; if (sig) for (let k = 1; k < d.length; k += 148) diff += (d[k] >> 4) !== sig[(k - 1) / 148]; const now = new Uint8Array(Math.ceil((d.length - 1) / 148)); for (let k = 1, z = 0; k < d.length; k += 148, z++) now[z] = d[k] >> 4; if (first === null && s > 40) first = t; if (first !== null && sig && diff < 2) { if (at === null) at = t - .1; still = Math.max(still, t - at); } else { if (at !== null && t - at > 1.6) msgs.push(`cell ${q.id}: nothing new from ${at.toFixed(1)} to ${t.toFixed(1)} s; draw something on those words`); at = null; } sig = now; }
    if (at !== null && end - at > 1.6) msgs.push(`cell ${q.id}: nothing new from ${at.toFixed(1)} s to its end (${end.toFixed(1)})`); if (first !== null && first - q.at > .5) msgs.push(`cell ${q.id}: empty for ${(first - q.at).toFixed(1)} s after its first word`); });
  console.log(msgs.length ? msgs.map(m => 'WARN ' + m).join('\n') : 'OK every scene is inside the panel, starts on time and keeps moving'); }

// ---------- the hook's cards: a hatched, coloured box with a sharp #n, and the name on its own layer (split_reel.py blurs it)
function cards(names, dir) { fs.mkdirSync(dir, { recursive: true }); const W0 = 292, H0 = 132; names.forEach((nm, i) => { for (const part of ['card', 'name']) { const k = K.createCanvas((W0 + 40) * 2, (H0 + 40) * 2), x = k.getContext('2d'), col = COL[i % COL.length]; x.scale(2, 2); x.translate(20, 20); if (part === 'card') { x.fillStyle = 'rgba(18,18,18,.94)'; x.beginPath(); x.roundRect(3, 3, W0 - 6, H0 - 6, 26); x.fill(); x.save(); x.beginPath(); x.roundRect(5, 5, W0 - 10, H0 - 10, 24); x.clip(); hatch(x, 4, 4, W0 - 8, H0 - 8, col + '2e', 1, i + 2); x.restore(); mk(x, 99).rect(4, 4, W0 - 8, H0 - 8, -1, -1, { c: col, w: 7, r: 26 }); txt(x, '#' + (i + 1), 58, H0 / 2 + 3, FONT, 48, col); } else nm.forEach((s, j) => { let z = 42; x.font = `${z}px "${FONT}"`; const w = x.measureText(s).width; if (w > 176) z = z * 176 / w; txt(x, s, 190, H0 / 2 + (nm.length > 1 ? -22 + j * 46 : 2), FONT, z, '#f2f2f2'); }); fs.writeFileSync(path.join(dir, `${part}${i + 1}.png`), k.toBuffer('image/png')); } }); }
if (require.main === module && process.argv[2] === 'cards') cards(JSON.parse(fs.readFileSync(process.argv[3])), process.argv[4]);

module.exports = { make, p };
