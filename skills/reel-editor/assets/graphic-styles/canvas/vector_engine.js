// Vector, the Split Screen's default art style: flat vector graphics instead of drawings, so real photos and videos can be part of the
// picture. The hand-drawn canvas (panel_engine.js, Sketch) stays for when the user asks for the drawn look.
//
// The look: a near-black field with a faint dot grid and a soft red glow; titles in heavy SF Pro with one word in a red pill
// or in New York italic; dark rounded cards with a thin light border; red tags; real video and photos in rounded frames;
// phones with app screens drawn as real UI; glowing red lines, gradient bars, numbered lists with the live row lit.
// Guide: references/vector-style.md. A reel only writes scenes.js (canvas_init.py PROJECT split copies vector.starter.scenes.js and
// points its require at this copy of the skill).
//
//   const { make, p } = require('<this folder>/vector_engine');
//   module.exports = make({ cells: [{ id, at, draw, cut, shift, until (hidden from then: the panel is off screen) }], recap: { at, first, every, names, title }, overlay: [{ from, to, draw }] });   // last line
//
//   node scenes.js sheet 12.5,13.2 out.jpg      stills at those seconds of the cut
//   node scenes.js still 18.0,22.3 out.jpg      up to four big ones
//   node scenes.js check                        ink outside the panel's safe area, words on words, empty starts, still stretches
//                                               (PANEL_H=1240 for the card layout; split_reel.py sets it)
//   node scenes.js render out.mp4 t0 t1         the panel between those seconds (split_reel.py calls this)
//   node vector_engine.js cards names.json dir  the hook's blurred cards (split_reel.py calls this)
//
// Real footage: p.clip('media/x.mp4', { from: 2 }) and p.photo('media/x.jpg'), paths from the project folder. Clips come
// from scripts/stock.py (Mixkit, Stock Video Free License only) or from the speaker's own files. Frames are cut once into
// work/vframes and loaded as they are needed.
const K = require('../kit'); const { clamp, lerp, pr, E, layer } = K;
const { loadImage, GlobalFonts } = require('@napi-rs/canvas');
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
GlobalFonts.registerFromPath('/System/Library/Fonts/SFNS.ttf', 'SFV'); GlobalFonts.registerFromPath('/System/Library/Fonts/NewYorkItalic.ttf', 'NYI');

const PW = 1080, PH = +(process.env.PANEL_H || 764), DB = PH === 764 ? 735 : PH - 250, HY = 248, FPS = 30;
// ---------- the look. Nothing else on this canvas.
const V = { bg: '#050505', dot: 'rgba(255,255,255,.085)', text: '#ffffff', dim: '#8e8e93', faint: 'rgba(255,255,255,.32)',
  red: '#e6202c', redHi: '#ff3d49', redDeep: '#6e0a11', green: '#34d35f', greenHi: '#5cf07f', greenDeep: '#0a4019', yellow: '#ffd60a',
  magenta: '#e23cf7', greenPill: '#24b14b', card0: '#16161a', card1: '#16161a', border: 'rgba(255,255,255,.55)', ui: '#0e0e11', uiRow: '#1b1b20' };
const F = (w, s) => `${w} ${s}px SFV`, SERIF = s => `italic ${s}px NYI`;
const PROJ = require.main ? path.resolve(path.dirname(require.main.filename), '..') : process.cwd();

// ---------- footage: frames cut once, decoded when a frame asks for them (a missing one is drawn on the next pass)
const CACHE = new Map(), NEED = new Set(), LRU = 420;
function img(f) { const im = CACHE.get(f); if (im) { CACHE.delete(f); CACHE.set(f, im); return im; } NEED.add(f); return null; }
async function loadNeeds() { const fs_ = [...NEED]; NEED.clear(); await Promise.all(fs_.map(async f => { try { CACHE.set(f, await loadImage(f)); } catch (e) { CACHE.set(f, null); console.error('cannot load', f); } })); while (CACHE.size > LRU) CACHE.delete(CACHE.keys().next().value); }
function clip(file, o = {}) {
  const src = path.resolve(PROJ, file); if (!fs.existsSync(src)) { console.error(`missing footage: ${file} (a grey box is drawn in its place)`); return { kind: 'none', file: () => null }; }
  const from = o.from || 0, w = o.w || 720, len = o.len || 14, tag = `${path.basename(file, path.extname(file))}_${from}_${w}`, dir = path.join(PROJ, 'work/vframes', tag);
  if (!fs.existsSync(path.join(dir, 'done'))) { fs.mkdirSync(dir, { recursive: true }); execFileSync('ffmpeg', ['-v', 'error', '-y', '-ss', String(from), '-i', src, '-t', String(len), '-vf', `fps=${FPS},scale=${w}:-2`, '-q:v', '3', path.join(dir, '%04d.jpg')]); fs.writeFileSync(path.join(dir, 'done'), ''); }
  const n = fs.readdirSync(dir).filter(f => f.endsWith('.jpg')).length;
  return { kind: 'video', dir, n, speed: o.speed || 1, file: k => path.join(dir, String(clamp(k, 0, n - 1) + 1).padStart(4, '0') + '.jpg') };
}
const photo = file => ({ kind: 'image', file: () => path.resolve(PROJ, file) });
function frameOf(h, t, t0) { if (h.kind === 'none') return null; if (h.kind === 'image') return img(h.file()); const k = Math.max(0, Math.floor((t - t0) * FPS * h.speed)); for (let j = 1; j < 4; j++) if (!CACHE.has(h.file(k + j))) NEED.add(h.file(k + j)); return img(h.file(k)); }

// ---------- small things
const rr = (c, x, y, w, h, r) => { c.beginPath(); c.roundRect(x, y, w, h, r); };
// a thing arriving: fades in, grows from s0 with a small overshoot, around (cx, cy). Call inside save/restore
function arrive(c, t, t0, cx, cy, d = .32, s0 = .86, dy = 0) { const u = pr(t, t0, t0 + d); if (u <= 0) return 0; const k = lerp(s0, 1, E.back(u, 1.3)); c.globalAlpha *= E.out(Math.min(1, u * 1.7)); c.translate(cx, cy + dy * (1 - E.out(u))); c.scale(k, k); c.translate(-cx, -cy); return u; }
function glowStroke(c, col, w, glow = 22, a = .85) { c.save(); c.shadowColor = col; c.shadowBlur = glow; c.globalAlpha *= a; c.strokeStyle = col; c.lineWidth = w; c.stroke(); c.restore(); c.strokeStyle = col; c.lineWidth = w; c.stroke(); }
const textW = (c, s, font, ls = 0) => { c.font = font; c.letterSpacing = ls + 'px'; const w = c.measureText(s).width; c.letterSpacing = '0px'; return w; };
function text(c, s, x, y, font, col = V.text, o = {}) { c.font = font; c.fillStyle = col; c.textAlign = o.align || 'center'; c.textBaseline = 'middle'; c.letterSpacing = (o.ls || 0) + 'px'; if (o.blur) c.filter = `blur(${o.blur}px)`; c.fillText(s, x, y); c.filter = 'none'; c.letterSpacing = '0px'; }

// ---------- pieces (x, y in the panel: 1080 wide, the title row at y 248, the picture between y 320 and DB)
// The title: heavy white words, typed out when the cell starts. A word's options: red (on a red pill), pill: 'green' (on a green
// pill, for good news), serif (New York italic), dim, green. o.n = 1 puts '#1' in a red pill first (at o.nt, or with the first word). o: { y, size, max, under: t (a red underline draws on) }
function title(c, t, ws, o = {}) {
  if (o.n) ws = [['#' + o.n, o.nt ?? ws[0][1], { red: true }], ...ws];
  // The title is the picture's headline and types out at once from the cell's start: one word hanging at the top of the screen while the speaker
  // gets to the next reads as broken. A word's own time is used only outside a cell (an overlay) or with o.spoken
  const t0 = o.at ?? (o.spoken || CUR.at === undefined ? null : CUR.at + .1); if (t0 !== null) ws = ws.map(([w, , q], i) => [w, t0 + i * .06, q]);                               // a point's number in a red pill before its words
  const y = o.y || HY; let s = o.size || 74;
  const font = (q, z) => q.serif ? SERIF(z * 1.2) : F(800, z), ls = (q, z) => q.serif ? 0 : -z * .028;
  const widths = z => ws.map(([w, , q = {}]) => textW(c, w, font(q, z), ls(q, z)) + (q.red || q.pill ? z * .46 : 0));
  let W = widths(s), gap = s * .27, tot = W.reduce((a, b) => a + b, 0) + gap * (ws.length - 1); const max = o.max || 990;
  if (tot > max) { s *= max / tot; W = widths(s); gap = s * .27; tot = W.reduce((a, b) => a + b, 0) + gap * (ws.length - 1); }
  let x = (o.x ?? 540) - tot / 2; const x0 = x;
  ws.forEach(([w, t0, q = {}], i) => { const u = pr(t, t0 - .06, t0 + .16); if (u > 0) { c.save(); c.globalAlpha *= E.out(u); const dy = (1 - E.out(u)) * 14;
    if (q.red || q.pill) { const k = E.back(pr(t, t0 - .02, t0 + .22), 1.4), gp = q.pill === 'green'; c.translate(x + W[i] / 2, y); c.scale(k, k); c.translate(-x - W[i] / 2, -y); rr(c, x, y - s * .66, W[i], s * 1.26, s * .14); c.fillStyle = gp ? V.greenPill : V.red; c.fill(); }
    text(c, w, x + (q.red || q.pill ? s * .23 : 0), y + dy + (q.serif ? s * .04 : 0), font(q, s), q.dim ? V.dim : q.green ? V.greenHi : V.text, { align: 'left', ls: ls(q, s) }); c.restore(); }
    x += W[i] + gap; });
  if (o.under) { const u = E.out(pr(t, o.under, o.under + .35)); if (u > 0) { c.beginPath(); c.moveTo(x0, y + s * .7); c.lineTo(x0 + tot * u, y + s * .7); c.lineCap = 'round'; c.strokeStyle = V.red; c.lineWidth = 5; c.stroke(); } }
  return { x0, x1: x0 + tot, size: s };
}
// a dark rounded card with a thin light border. o: { r, title, ts (title size), glow: red glow, border, fill: [top, bottom] }
function card(c, x, y, w, h, t, t0, o = {}) {
  c.save(); if (!arrive(c, t, t0, x + w / 2, y + h / 2, .32, .9, 18)) { c.restore(); return 0; }
  const r = o.r ?? 30; rr(c, x, y, w, h, r); c.save(); if (o.glow) { c.shadowColor = 'rgba(255,255,255,.22)'; c.shadowBlur = 34; } c.fillStyle = o.fill || V.card0; c.fill(); c.restore();
  c.lineWidth = 2.5; c.strokeStyle = o.border || V.border; c.stroke();
  if (o.title) text(c, o.title, x + (o.tx ?? 38), y + (o.ty ?? 64), F(800, o.ts || 52), V.text, { align: 'left', ls: -(o.ts || 52) * .025 });
  c.restore(); return 1;
}
// a label. kind: red (default, white on a red pill), white (black on white, a callout), outline (white on black, white border), dark
// o: { size, kind, point: 'down' | 'up' (a small pointer under or over it), w (fixed width), d (arrive time) }
function tag(c, s, x, y, t, t0, o = {}) {
  const z = o.size || 44, kind = o.kind || 'red', tw = textW(c, s, F(800, z), -z * .02), w = o.w || tw + z * .95, h = z * 1.48;
  c.save(); const u = pr(t, t0, t0 + (o.d || .26)); if (u <= 0) { c.restore(); return w; } const k = lerp(.55, 1, E.back(u, 1.6)); c.globalAlpha *= E.out(Math.min(1, u * 2)); c.translate(x, y); c.scale(k, k); c.translate(-x, -y);
  rr(c, x - w / 2, y - h / 2, w, h, o.r ?? h * .22);
  if (kind === 'red') { c.fillStyle = V.red; c.fill(); }
  else if (kind === 'white') { c.fillStyle = '#f5f5f5'; c.fill(); }
  else if (kind === 'green') { c.fillStyle = V.greenPill; c.fill(); }
  else { c.fillStyle = kind === 'dark' ? 'rgba(38,38,42,.96)' : '#0a0a0a'; c.fill(); c.lineWidth = kind === 'dark' ? 1.5 : 2.5; c.strokeStyle = kind === 'dark' ? 'rgba(255,255,255,.28)' : 'rgba(255,255,255,.9)'; c.stroke(); }
  if (o.point) { const d = o.point === 'down' ? 1 : -1, py = y + d * h / 2; c.beginPath(); c.moveTo(x - z * .3, py - d * 1); c.lineTo(x, py + d * z * .34); c.lineTo(x + z * .3, py - d * 1); c.fillStyle = kind === 'white' ? '#f5f5f5' : kind === 'red' ? V.red : kind === 'green' ? V.greenPill : '#0a0a0a'; c.fill(); }
  text(c, s, x, y + 1, F(800, z), kind === 'white' ? '#0a0a0a' : V.text, { ls: -z * .02 }); c.restore(); return w;
}
// real footage in a rounded frame. h = p.clip(...) or p.photo(...). o: { r, fx, fy (focus 0..1), kb (zoom-out seconds), rot (deg),
// grey: t (turns grey and dark from then), tint: 'red', border: false, glow, label: 'text' (a tag over the top edge), d }
function media(c, h, x, y, w, hh, t, t0, o = {}) {
  c.save(); if (!arrive(c, t, t0, x + w / 2, y + hh / 2, o.d || .34, .88, 26)) { c.restore(); return; }
  if (o.rot) { c.translate(x + w / 2, y + hh / 2); c.rotate(o.rot * Math.PI / 180); c.translate(-x - w / 2, -y - hh / 2); }
  const r = o.r ?? 26; rr(c, x, y, w, hh, r); c.save(); c.shadowColor = `rgba(255,255,255,${o.glow ? .26 : .14})`; c.shadowBlur = o.glow ? 40 : 28; c.fillStyle = '#101012'; c.fill(); c.restore();
  const im = frameOf(h, t, t0); c.save(); rr(c, x, y, w, hh, r); c.clip();
  if (im) { const z = lerp(1.1, 1, E.out(pr(t, t0, t0 + (o.kb || 7)))), s = Math.max(w / im.width, hh / im.height) * z, dw = im.width * s, dh = im.height * s, fx = o.fx ?? .5, fy = o.fy ?? .5;
    const dx = x + (w - dw) * fx, dy = y + (hh - dh) * fy; const g = o.grey !== undefined ? E.out(pr(t, o.grey, o.grey + .35)) : 0;
    if (g < 1) c.drawImage(im, dx, dy, dw, dh); if (g > 0) { c.globalAlpha = g; c.filter = 'grayscale(1) brightness(0.45)'; c.drawImage(im, dx, dy, dw, dh); c.filter = 'none'; c.globalAlpha = 1; }
    if (o.tint === 'red') { c.fillStyle = 'rgba(200,16,30,.35)'; c.fillRect(x, y, w, hh); } }
  c.restore();
  if (o.border !== false) { rr(c, x, y, w, hh, r); c.lineWidth = 2.5; c.strokeStyle = 'rgba(255,255,255,.8)'; c.stroke(); }
  c.restore(); if (o.label) { const z = o.ls || 40; tag(c, o.label, x + w / 2, y - z * .74 - 20, t, o.lt ?? t0 + .12, { size: z, kind: o.lk || 'red' }); }   // clear of the edge: text right on a clip's edge is hard to read
}
// raw footage cover-fit into a rectangle, no frame (inside a phone's screen, say)
function footage(c, h, x, y, w, hh, t, t0, o = {}) { const im = frameOf(h, t, t0); if (!im) return; const sc = Math.max(w / im.width, hh / im.height) * (o.z || 1), dw = im.width * sc, dh = im.height * sc; c.drawImage(im, x + (w - dw) * (o.fx ?? .5), y + (hh - dh) * (o.fy ?? .5), dw, dh); }
// where a phone's screen sits (the same numbers phone() uses), to draw on top of a screen from outside it
const screenOf = (cx, cy, h) => { const w = h * .485, b = w * .045, s = { x: cx - w / 2 + b, y: cy - h / 2 + b, w: w - 2 * b, h: h - 2 * b }; s.k = s.w / 290; return s; };
// an iPhone holding a screen; scr(c, s) draws the app in screen space: s = { x, y, w, h, k (1 = a 290 pt screen), t }
// o: { grey: t (dims from then), lit: t (dim until then), glow, rot, label: 'text' (a tag over the top edge), lk (its kind) }
function phone(c, cx, cy, h, t, t0, scr, o = {}) {
  const w = h * .485, x = cx - w / 2, y = cy - h / 2; c.save(); if (!arrive(c, t, t0, cx, cy, .36, .9, 34)) { c.restore(); return; }
  if (o.rot) { c.translate(cx, cy); c.rotate(o.rot * Math.PI / 180); c.translate(-cx, -cy); }
  rr(c, x, y, w, h, w * .17); c.save(); c.shadowColor = `rgba(255,255,255,${o.glow ? .3 : .16})`; c.shadowBlur = o.glow ? 44 : 30; c.fillStyle = '#060607'; c.fill(); c.restore();   // a subtle white glow round the outline
  c.lineWidth = w * .02; c.strokeStyle = '#55555b'; c.stroke();
  const b = w * .045, s = { x: x + b, y: y + b, w: w - 2 * b, h: h - 2 * b, t }; s.k = s.w / 290;                 // type a size up from a real phone, so it reads in a reel
  c.save(); rr(c, s.x, s.y, s.w, s.h, w * .13); c.clip(); c.fillStyle = V.ui; c.fillRect(s.x, s.y, s.w, s.h); if (scr) scr(c, s); ui.status(c, s);
  const g = Math.max(o.grey !== undefined ? E.out(pr(t, o.grey, o.grey + .35)) : 0, o.lit !== undefined ? 1 - E.out(pr(t, o.lit, o.lit + .3)) : 0); if (g > 0) { c.fillStyle = `rgba(5,5,5,${.64 * g})`; c.fillRect(s.x, s.y, s.w, s.h); }
  c.restore(); rr(c, cx - w * .15, s.y + s.h * .016, w * .3, s.h * .042, s.h * .021); c.fillStyle = '#000'; c.fill(); c.restore();
  if (o.label) { const z = o.ls || 38; tag(c, o.label, cx, y - z * .74 - 20, t, o.lt ?? t0 + .12, { size: z, kind: o.lk || 'red' }); }
}
// app screens, drawn as real UI on a dark app (a made-up app, never a real one). Sizes are in points of a 390 pt wide screen.
const ui = {
  status(c, s) { const k = s.k; text(c, '9:41', s.x + 46 * k, s.y + 26 * k, F(600, 15 * k), V.text); for (let i = 0; i < 4; i++) { c.fillStyle = V.text; c.fillRect(s.x + s.w - 86 * k + i * 6 * k, s.y + (30 - i * 3) * k, 4 * k, (4 + i * 3) * k); } rr(c, s.x + s.w - 54 * k, s.y + 20 * k, 26 * k, 13 * k, 4 * k); c.lineWidth = 1.2 * k; c.strokeStyle = V.text; c.stroke(); c.fillStyle = V.text; c.fillRect(s.x + s.w - 52 * k, s.y + 22 * k, 19 * k, 9 * k); },
  // the onboarding's progress bar: u = 0..1
  bar(c, s, u) { const k = s.k; rr(c, s.x + 24 * k, s.y + 62 * k, s.w - 48 * k, 6 * k, 3 * k); c.fillStyle = 'rgba(255,255,255,.14)'; c.fill(); rr(c, s.x + 24 * k, s.y + 62 * k, Math.max(6 * k, (s.w - 48 * k) * u), 6 * k, 3 * k); c.fillStyle = V.text; c.fill(); },
  h(c, s, str, y, size = 32, col = V.text) { str.split('\n').forEach((l, i) => text(c, l, s.x + 24 * s.k, s.y + (y + i * size * 1.15) * s.k, F(800, size * s.k), col, { align: 'left', ls: -size * s.k * .02 })); },
  p(c, s, str, y, size = 17, col = V.dim) { text(c, str, s.x + 24 * s.k, s.y + y * s.k, F(500, size * s.k), col, { align: 'left' }); },
  // an answer row; on = 0..1 (picked), em = a small emoji-free glyph drawn left: 'dot'
  row(c, s, str, y, on = 0, o = {}) { const k = s.k, x = s.x + 24 * k, w = s.w - 48 * k, h = (o.h || 60) * k; rr(c, x, s.y + y * k, w, h, 16 * k); c.fillStyle = V.uiRow; c.fill(); if (on > 0) { c.save(); c.globalAlpha = on; c.fillStyle = '#f2f2f2'; c.fill(); c.restore(); }
    c.lineWidth = 1.5 * k; c.strokeStyle = on > .5 ? '#f2f2f2' : 'rgba(255,255,255,.12)'; c.stroke(); text(c, str, x + 20 * k, s.y + y * k + h / 2, F(700, (o.size || 19) * k), on > .5 ? '#0a0a0a' : V.text, { align: 'left' });
    if (on > .5) { c.beginPath(); c.arc(x + w - 26 * k, s.y + y * k + h / 2, 11 * k, 0, 7); c.fillStyle = '#0a0a0a'; c.fill(); c.beginPath(); c.moveTo(x + w - 31 * k, s.y + y * k + h / 2); c.lineTo(x + w - 27 * k, s.y + y * k + h / 2 + 4 * k); c.lineTo(x + w - 20 * k, s.y + y * k + h / 2 - 4 * k); c.lineWidth = 2.2 * k; c.strokeStyle = '#fff'; c.stroke(); } },
  btn(c, s, str = 'Continue', u = 1) { const k = s.k; rr(c, s.x + 24 * k, s.y + s.h - 96 * k, s.w - 48 * k, 56 * k, 28 * k); c.fillStyle = u > .5 ? '#f2f2f2' : 'rgba(255,255,255,.18)'; c.fill(); text(c, str, s.x + s.w / 2, s.y + s.h - 68 * k, F(700, 18 * k), u > .5 ? '#0a0a0a' : 'rgba(255,255,255,.5)'); },
};
// a glowing line through points, drawn on from t0 to t1; o: { c, w, dots: [index...], glow }
function curve(c, pts, t, t0, t1, o = {}) { const P = K.spline(pts, 14), u = E.io(pr(t, t0, t1)); if (u <= 0) return; const n = Math.max(2, Math.ceil(P.length * u));
  c.save(); c.beginPath(); P.slice(0, n).forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); c.lineCap = 'round'; c.lineJoin = 'round'; glowStroke(c, o.c || V.red, o.w || 6, o.glow ?? 14, .6); c.restore();
  (o.dots || []).forEach(i => { const at = t0 + (t1 - t0) * (i / (pts.length - 1)); dot(c, pts[i][0], pts[i][1], t, at, o.dr || 11); }); }
const dot = (c, x, y, t, t0, r = 11, col = '#fff') => { const u = E.back(pr(t, t0, t0 + .2), 2); if (u <= 0) return; c.save(); c.beginPath(); c.arc(x, y, r * u, 0, 7); c.shadowColor = 'rgba(255,255,255,.8)'; c.shadowBlur = 16; c.fillStyle = col; c.fill(); c.restore(); };
// thin white lines: axes (an L), connectors (elbows), arrows. All draw on.
function axes(c, x0, y0, x1, y1, t, t0, o = {}) { const u = E.out(pr(t, t0, t0 + .4)); if (u <= 0) return; c.save(); c.beginPath(); c.moveTo(x0, y1 - (y1 - y0) * u); c.lineTo(x0, y1); c.lineTo(x0 + (x1 - x0) * u, y1); c.lineCap = 'round'; glowStroke(c, 'rgba(255,255,255,.92)', o.w || 3.5, 12, .5); c.restore();
  (o.ticks || []).forEach(([s, y], i) => { if (u > .5) text(c, s, x0 - 22, y, F(600, 20), V.dim, { align: 'right' }); }); }
function lines(c, pts, t, t0, t1, o = {}) { const u = E.io(pr(t, t0, t1)); if (u <= 0) return; let L = 0; const seg = []; for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); L += d; }
  let left = L * u; c.save(); c.beginPath(); c.moveTo(...pts[0]); let end = pts[0], ang = 0; for (let i = 1; i < pts.length && left > 0; i++) { const f = Math.min(1, left / seg[i - 1]); end = [lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)]; ang = Math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0]); c.lineTo(...end); left -= seg[i - 1]; }
  c.lineCap = 'round'; c.lineJoin = 'round'; glowStroke(c, o.c || 'rgba(255,255,255,.9)', o.w || 3, o.glow ?? 10, .5);
  if (o.head && u > .05) { const hz = o.head; c.beginPath(); c.moveTo(end[0] + Math.cos(ang) * hz * .2, end[1] + Math.sin(ang) * hz * .2); c.lineTo(end[0] - Math.cos(ang - .5) * hz, end[1] - Math.sin(ang - .5) * hz); c.lineTo(end[0] - Math.cos(ang + .5) * hz, end[1] - Math.sin(ang + .5) * hz); c.closePath(); c.fillStyle = o.c || 'rgba(255,255,255,.9)'; c.fill(); } c.restore(); }
// a bar growing off baseline y. col: red, green, grey. o: { val (text on top), vt (when the value lands), size }
function bar(c, x, y, w, h, t, t0, col = 'red', o = {}) { const u = E.out(pr(t, t0, t0 + .5)); if (u <= 0) return; const hh = h * u, top = { red: V.redHi, green: V.greenHi, grey: '#6a6a70' }[col], bot = { red: '#3a050a', green: '#062a10', grey: '#1a1a1d' }[col];
  c.save(); rr(c, x, y - hh, w, hh, [10, 10, 0, 0]); c.fillStyle = { red: V.red, green: V.greenPill, grey: '#3a3a40' }[col]; c.fill(); c.restore();
  if (o.val) { const v = pr(t, o.vt ?? t0 + .35, (o.vt ?? t0 + .35) + .22); if (v > 0) { c.save(); c.globalAlpha *= E.out(v); text(c, o.val, x + w / 2, y - hh - (o.size || 64) * .62 - (1 - E.out(v)) * 14, F(800, o.size || 64), col === 'grey' ? V.dim : V.text, { ls: -1 }); c.restore(); } } }
// a progress card like "Skill 2/10": label, a fraction and a glowing red pill filling from a to b between t1 and t2
function meter(c, x, y, w, t, t0, label, a, b, t1, t2, max = 10, o = {}) { const h = o.h || 150; if (!card(c, x, y, w, h, t, t0)) return; const v = lerp(a, b, E.io(pr(t, t1, t2))), col = o.col || 'red';
  c.save(); arrive(c, t, t0, x + w / 2, y + h / 2, .32, .9, 18); text(c, label, x + 36, y + 52, F(800, 50), V.text, { align: 'left', ls: -1 }); text(c, `${Math.round(v)}/${max}`, x + w - 36, y + 56, F(700, 30), V.text, { align: 'right' });
  rr(c, x + 36, y + 96, w - 72, 26, 13); c.fillStyle = 'rgba(255,255,255,.08)'; c.fill(); rr(c, x + 36, y + 96, Math.max(26, (w - 72) * v / max), 26, 13); c.fillStyle = col === 'red' ? V.red : V.green; c.fill(); c.restore(); }
// a numbered list; rows: [{ n: '01', s: 'text', at }]; the row whose time has come is lit (dark bar, red edge), rows not reached are blurred
function list(c, rows, x, y, w, t, t0, o = {}) { const gap = o.gap || 116, z = o.size || 46; rows.forEach((r, i) => { const yy = y + i * gap, u = pr(t, t0 + i * .07, t0 + i * .07 + .3); if (u <= 0) return; c.save(); c.globalAlpha *= E.out(u);
  const live = t >= r.at && (i === rows.length - 1 || t < rows[i + 1].at || o.keep), done = t >= r.at, hl = E.out(pr(t, r.at, r.at + .25));
  if (live && hl > 0) { rr(c, x, yy - 46, w * (.6 + .4 * hl), 92, 10); c.fillStyle = 'rgba(52,52,58,.92)'; c.fill(); rr(c, x, yy - 46, 12, 92, [10, 0, 0, 10]); c.save(); c.shadowColor = V.red; c.shadowBlur = 20; c.fillStyle = V.red; c.fill(); c.restore(); }
  text(c, r.n, x + 44, yy, F(800, z), V.text, { align: 'left' }); text(c, r.s, x + 44 + z * 2, yy, F(800, z * .78), done ? V.text : 'rgba(255,255,255,.7)', { align: 'left', blur: done ? 0 : 9, ls: -.5 }); c.restore(); }); }
// a red VS badge; a red cross; a green tick; a red spotlight ring; a number counting up
function vs(c, x, y, t, t0, r = 54) { c.save(); const u = E.back(pr(t, t0, t0 + .25), 1.8); if (u <= 0) { c.restore(); return; } c.translate(x, y); c.scale(u, u); c.beginPath(); c.arc(0, 0, r, 0, 7); c.shadowColor = V.red; c.shadowBlur = 34; c.fillStyle = V.red; c.fill(); c.shadowBlur = 0; c.lineWidth = 3; c.strokeStyle = 'rgba(255,255,255,.9)'; c.stroke(); text(c, 'VS', 0, 2, F(900, r * .8), V.text); c.restore(); }
function cross(c, x, y, r, t, t0, o = {}) { [[-1, -1, 1, 1], [1, -1, -1, 1]].forEach(([a, b, d, e], i) => { const u = E.out(pr(t, t0 + i * .1, t0 + i * .1 + .14)); if (u <= 0) return; c.save(); c.beginPath(); c.moveTo(x + a * r, y + b * r); c.lineTo(x + lerp(a, d, u) * r, y + lerp(b, e, u) * r); c.lineCap = 'round'; glowStroke(c, V.red, o.w || 16, 26); c.restore(); }); }
function tick(c, x, y, r, t, t0) { const u = E.back(pr(t, t0, t0 + .24), 1.8); if (u <= 0) return; c.save(); c.translate(x, y); c.scale(u, u); c.beginPath(); c.arc(0, 0, r, 0, 7); c.shadowColor = V.green; c.shadowBlur = 26; c.fillStyle = V.green; c.fill(); c.shadowBlur = 0; c.beginPath(); c.moveTo(-r * .42, 0); c.lineTo(-r * .1, r * .32); c.lineTo(r * .45, -r * .34); c.lineWidth = r * .2; c.lineCap = 'round'; c.lineJoin = 'round'; c.strokeStyle = '#fff'; c.stroke(); c.restore(); }
function spot(c, x, y, r, t, t0) { const u = E.back(pr(t, t0, t0 + .3), 1.4); if (u <= 0) return; c.save(); c.beginPath(); c.arc(x, y, r * u, 0, 7); c.fillStyle = 'rgba(210,18,30,.32)'; c.fill(); c.lineWidth = 3; c.shadowColor = V.red; c.shadowBlur = 30; c.strokeStyle = 'rgba(255,70,80,.95)'; c.stroke(); c.restore(); }
function count(c, v, x, y, size, t, t0, t1, o = {}) { const u = pr(t, t0, t0 + .2); if (u <= 0) return; const n = v * E.out(pr(t, t0, t1)); c.save(); c.globalAlpha *= E.out(u); text(c, (o.fmt || (q => Math.round(q).toLocaleString('en-US')))(n), x, y, F(800, size), o.col || V.text, { ls: -size * .03, align: o.align || 'center' }); c.restore(); }
// a handwritten note in the serif italic, with a hand-drawn arrow toward (ax, ay)
function note(c, s, x, y, t, t0, o = {}) { const u = pr(t, t0, t0 + .25); if (u <= 0) return; c.save(); c.globalAlpha *= E.out(u); text(c, s, x, y, SERIF(o.size || 50), o.col || V.text, { align: o.align || 'center' }); c.restore(); if (o.to) lines(c, [[x + (o.fx || 0), y + 34], ...o.to], t, t0 + .1, t0 + .4, { c: o.col || V.text, w: 2.5, head: 16, glow: 0 }); }
// plain words, landing like the title's
function words(c, s, x, y, t, t0, o = {}) { const u = pr(t, t0 - .04, t0 + .18); if (u <= 0) return; c.save(); c.globalAlpha *= E.out(u); text(c, s, x, y + (1 - E.out(u)) * 12, o.serif ? SERIF(o.size || 50) : F(o.w || 800, o.size || 50), o.col || V.text, { align: o.align || 'center', ls: o.serif ? 0 : -(o.size || 50) * .025 }); c.restore(); }
const fade = (c, t, t0, d = .25) => { c.globalAlpha *= 1 - E.out(pr(t, t0, t0 + d)); return c.globalAlpha > .01; };   // inside save/restore: fade a thing out from t0

const CUR = {};                                                           // the cell being drawn: { at }
const p = { footage, screenOf, V, F, SERIF, PW, PH, DB, HY, FPS, pr, E, lerp, clamp, rr, arrive, text, textW, title, card, tag, media, phone, ui, curve, dot, axes, lines, bar, meter, list, vs, cross, tick, spot, count, note, words, fade, clip, photo };

// ---------- the field behind everything (fixed, the scenes move over it)
let FIELD; function field() { if (FIELD) return FIELD; const [k, x] = layer(PW, PH); x.fillStyle = V.bg; x.fillRect(0, 0, PW, PH); x.fillStyle = V.dot; for (let a = 9; a < PW; a += 24) for (let b = 9; b < PH; b += 24) x.fillRect(a, b, 2.2, 2.2);
  return FIELD = k; }                                                     // flat: no red wash, no vignette, no gradients

// ---------- one reel: a cell per beat, pushed in from the right as the next beat starts, a slow push-in while it holds
function make(R) {
  const cells = R.cells.map(q => ({ ...q })); if (R.recap) cells.push({ id: 'recap', at: R.recap.at, draw: recap(R.recap) });
  const TR = [.12, .24];                                                                                     // the push: from 0.12 s before the next beat to 0.24 s after
  function recap(r) { return (c, t) => { title(c, t, r.title || [['The', r.at], [String(r.names.length), r.at + .05, { red: true }], ['moves', r.at + .1]]); const n = r.names.length, gap = Math.min(150, (DB - 360) / n);
    list(c, r.names.map((s, i) => ({ n: String(i + 1).padStart(2, '0'), s, at: r.first + i * (r.every || .2) })), 110, 320 + (DB - 320 - gap * (n - 1)) / 2, 860, t, r.at, { gap, size: 52, keep: true }); }; }
  const drawCell = (c, i, t) => { const q = cells[i], tt = t + (q.shift || 0); CUR.at = q.at + (q.shift || 0); c.save(); q.draw(c, tt, p); c.restore(); CUR.at = undefined; };
  // cut: true = the cell is there from its `at` with no push (the first cell after a stretch of full face, when the panel slides back in)
  const into = (q, t) => q.cut ? (t >= q.at ? 1 : 0) : E.io(pr(t, q.at - TR[0], q.at + TR[1]));
  function world(c, t) { cells.forEach((q, i) => { const nx = cells[i + 1], a0 = q.at - TR[0], u0 = i ? into(q, t) : 1, u1 = nx ? into(nx, t) : 0;
    if (t < a0 || u1 >= 1) return; const dx = (1 - u0) * 300 - u1 * 300, a = Math.min(u0, 1 - u1), z = (1 + .028 * pr(t, q.at, q.at + 9)) * lerp(.96, 1, Math.min(u0, 1)) * lerp(1, .96, u1);
    c.save(); c.globalAlpha = a; c.translate(540 + dx, PH / 2); c.scale(z, z); c.translate(-540, -PH / 2); drawCell(c, i, t); c.restore(); });
    (R.overlay || []).forEach(o => { if (t < o.from - .5 || t > o.to + .4) return; c.save(); c.globalAlpha = 1 - E.out(pr(t, o.to, o.to + .3)); o.draw(c, t, p); c.restore(); }); }   // screen-space layers over the cells (the hook's header)
  let lay; function frame(c, t) { c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.drawImage(field(), 0, 0); const moving = cells.some((q, i) => i && !q.cut && t > q.at - TR[0] && t < q.at + TR[1]);
    if (!moving) return world(c, t); const k = 5, [o, x] = lay || (lay = layer(PW, PH)); for (let i = 0; i < k; i++) { x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.clearRect(0, 0, PW, PH); world(x, t - (i / k) * (.5 / FPS)); c.globalAlpha = 1 / (i + 1); c.drawImage(o, 0, 0); } c.globalAlpha = 1; }   // motion blur on every push
  const api = { frame, cells, flights: cells.slice(1).map((q, i) => [q.at - TR[0], q.at + TR[1], i, i + 1]).filter((f, i) => !cells[i + 1].cut), left: k => cells[k + 1] ? cells[k + 1].at - TR[0] : 1e9, drawCell };
  setImmediate(() => { if (require.main && require.main.exports === api) cli(api).catch(e => { console.error(e); process.exit(1); }); }); return api; }

// draw, and draw again once the footage it asked for is loaded
async function ready(fn) { fn(); for (let i = 0; i < 4 && NEED.size; i++) { await loadNeeds(); fn(); } }
async function cli(A) { const [, , cmd, a, b, d] = process.argv, cv = K.createCanvas(PW, PH), c = cv.getContext('2d');
  if (cmd === 'sheet' || cmd === 'still') { const big = cmd === 'still', ts = a.split(',').map(Number).slice(0, big ? 4 : 99), w = big ? 810 : 540, hh = Math.round(w * PH / PW), cols = Math.min(big ? 2 : 4, ts.length), s = K.createCanvas(w * cols, hh * Math.ceil(ts.length / cols)), x = s.getContext('2d');
    for (const [i, t] of ts.entries()) { await ready(() => A.frame(c, t)); x.drawImage(cv, (i % cols) * w, Math.floor(i / cols) * hh, w, hh); x.fillStyle = '#ffd60a'; x.font = '600 22px SFV'; x.textAlign = 'left'; x.fillText(t.toFixed(2), (i % cols) * w + 10, Math.floor(i / cols) * hh + 26); }
    const out = b || path.join(PROJ, 'work', cmd + '.jpg'); fs.writeFileSync(out, s.toBuffer('image/jpeg', 88)); console.log(out); }
  else if (cmd === 'render') { const n0 = Math.round(+b * FPS), n1 = Math.round(+d * FPS), ff = require('child_process').spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${PW}x${PH}`, '-r', String(FPS), '-i', '-', '-c:v', 'libx264rgb', '-crf', '6', '-preset', 'fast', a], { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let n = n0; n < n1; n++) { await ready(() => A.frame(c, n / FPS)); const buf = c.getImageData(0, 0, PW, PH).data; if (!ff.stdin.write(Buffer.from(buf.buffer))) await new Promise(r => ff.stdin.once('drain', r)); } ff.stdin.end(); await new Promise(r => ff.on('close', r)); }
  else if (cmd === 'check') await check(A, c); else if (cmd === 'info') console.log(JSON.stringify({ cells: A.cells.map(q => [q.id, q.at]), flights: A.flights })); else console.log('sheet <t,t> [out] | still <t,t> [out] | check | info | render <out.mp4> <t0> <t1>'); }

// measured on the cell itself: what the finished scene covers, words on words, when its first thing lands, how long nothing changes
async function check(A, c) { const msgs = []; const snap = async (i, t) => { await ready(() => { c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.fillStyle = '#000'; c.fillRect(0, 0, PW, PH); A.drawCell(c, i, t); }); return c.getImageData(0, 0, PW, PH).data; };
  const texts = async (i, t) => { const out = [], fill = c.fillText; c.fillText = function (s, x, y) { const m = c.getTransform(), w = c.measureText(s).width, z = parseFloat(c.font.replace(/^(italic )?\d+ /, '')), al = c.textAlign, x0 = al === 'center' ? x - w / 2 : al === 'right' ? x - w : x; if (c.globalAlpha > .4 && String(s).trim() && z > 12) out.push({ s, x0: m.a * x0 + m.e, x1: m.a * (x0 + w) + m.e, y0: m.d * (y - z * .4) + m.f, y1: m.d * (y + z * .4) + m.f }); return fill.apply(this, arguments); }; await snap(i, t); c.fillText = fill; return out; };
  const bounds = d => { let x0 = PW, x1 = 0, y0 = PH, y1 = 0, n = 0; for (let y = 0; y < PH; y += 2) for (let x = 0; x < PW; x += 2) { const i = (y * PW + x) * 4; if (Math.max(d[i], d[i + 1], d[i + 2]) > 60) { n++; x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); } } return { x0, x1, y0, y1, n }; };
  for (const [i, q] of A.cells.entries()) { const end = Math.min(A.left(i), q.until ?? 1e9, q.at + 12) - .04, b = bounds(await snap(i, end)); if (!b.n) { msgs.push(`cell ${q.id}: nothing is drawn`); continue; }
    if (b.x0 < 30) msgs.push(`cell ${q.id}: something at x ${b.x0}, keep it right of 34`); if (b.x1 > 1050) msgs.push(`cell ${q.id}: something at x ${b.x1}, keep it left of 1046`); if (b.y0 < 190) msgs.push(`cell ${q.id}: something at y ${b.y0}, nothing above 195 (Instagram's header)`); if (b.y1 > DB + 6) msgs.push(`cell ${q.id}: something at y ${b.y1}, nothing below ${DB} (the caption sits under the picture)`);
    if (q.id === 'recap') continue;                                                                       // the recap holds once every row is lit
    if (b.y1 < DB - 150) msgs.push(`cell ${q.id}: the picture ends at y ${b.y1}; fill down to about ${DB - 40}`);
    const tx = await texts(i, end), seen = new Set(); for (let a = 0; a < tx.length; a++) for (let z = a + 1; z < tx.length; z++) { const A1 = tx[a], B1 = tx[z], ox = Math.min(A1.x1, B1.x1) - Math.max(A1.x0, B1.x0), oy = Math.min(A1.y1, B1.y1) - Math.max(A1.y0, B1.y0), key = A1.s + '|' + B1.s; if (ox > 6 && oy > 8 && !seen.has(key)) { seen.add(key); msgs.push(`cell ${q.id}: "${A1.s}" and "${B1.s}" sit on each other`); } }
    const nx = A.left(i) < 1e8 ? A.left(i) : null; if (nx && Math.min(nx, q.until ?? 1e9) - q.at > 7.5) msgs.push(`cell ${q.id}: ${(nx - q.at).toFixed(1)} s on one picture; give the second half its own cell (3 to 6 s each)`);
    // words up too briefly to read: two boxes that appear for a split second can't be read, so they are noise
    const seen2 = new Map(), ft = c.fillText; c.fillText = function (str, x, y) { const z = parseFloat(c.font.replace(/^(italic )?\d+ /, '')) * c.getTransform().a; if (c.globalAlpha > .5 && String(str).trim().length > 1 && z >= 22) seen2.set(str, (seen2.get(str) || 0) + 1); return ft.apply(this, arguments); };
    let first = null, at = null, sig = null; for (let t = q.at - .3; t < end; t += .1) { const d = await snap(i, t), s = bounds(d).n; const now = new Uint8Array(Math.ceil(d.length / 4 / 37)); for (let k = 0, z = 0; k < d.length; k += 148, z++) now[z] = d[k + 1] >> 3; let diff = 0; if (sig) for (let z = 0; z < now.length; z++) diff += now[z] !== sig[z];
      if (first === null && s > 400) first = t; if (sig && diff > now.length * .004) at = null; else if (at === null) at = t; sig = now; }
    c.fillText = ft; for (const [str, n] of seen2) if (n < 8 && ![...seen2.keys()].some(o => o !== str && String(o).startsWith(str))) msgs.push(`cell ${q.id}: "${str}" is up for only ${(n / 10).toFixed(1)} s, too short to read; hold it or cut it`);
    if (at !== null && end - at > 2.5) msgs.push(`cell ${q.id}: nothing moves from ${at.toFixed(1)} s to its end (${end.toFixed(1)})`); if (first !== null && first - q.at > .5) msgs.push(`cell ${q.id}: empty for ${(first - q.at).toFixed(1)} s after its first word`); }
  console.log(msgs.length ? msgs.map(m => 'WARN ' + m).join('\n') : 'OK every scene is inside the panel, starts on time and keeps moving'); }

// ---------- the hook's cards: a dark card with a red #n tag, and the name on its own layer (split_reel.py blurs it)
function cards(names, dir) { fs.mkdirSync(dir, { recursive: true }); const W0 = 292, H0 = 132; names.forEach((nm, i) => { for (const part of ['card', 'name']) { const k = K.createCanvas((W0 + 40) * 2, (H0 + 40) * 2), x = k.getContext('2d'); x.scale(2, 2); x.translate(20, 20);
  if (part === 'card') { card(x, 3, 3, W0 - 6, H0 - 6, 9, 0, { r: 24 }); tag(x, '#' + (i + 1), 62, H0 / 2, 9, 0, { size: 36 }); }
  else nm.forEach((s, j) => { let z = 40; const w = textW(x, s, F(800, z)); if (w > 170) z = z * 170 / w; text(x, s, 190, H0 / 2 + (nm.length > 1 ? -22 + j * 46 : 2), F(800, z), V.text); });
  fs.writeFileSync(path.join(dir, `${part}${i + 1}.png`), k.toBuffer('image/png')); } }); }
if (require.main === module && process.argv[2] === 'cards') cards(JSON.parse(fs.readFileSync(process.argv[3])), process.argv[4]);

module.exports = { make, p };
