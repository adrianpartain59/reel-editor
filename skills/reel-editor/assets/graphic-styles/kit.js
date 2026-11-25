// Shared kit for the art-style mockups: timing, easing, strokes, hand jitter, word-synced type, props.
// Every style draws the same 14.8 s (step 1, step 4, step 10's creators) with the same voice, so only the style changes.
const { createCanvas, GlobalFonts, loadImage, Path2D } = require('@napi-rs/canvas');
const fs = require('fs'), path = require('path');
const W = 1080, H = 1920;

// ---------- fonts
const FD = path.join(__dirname, 'node_modules/@fontsource');
function reg(pkg, weight, name) {
  const d = path.join(FD, pkg, 'files'); const f = `${pkg}-latin-${weight}-normal.woff2`;
  if (fs.existsSync(path.join(d, f))) GlobalFonts.registerFromPath(path.join(d, f), name);
  else console.error('font missing', pkg, weight);
}
[['permanent-marker', 400, 'Marker'], ['league-gothic', 400, 'League'], ['space-mono', 700, 'MonoB'], ['space-mono', 400, 'Mono'], ['rajdhani', 700, 'RajB'], ['shantell-sans', 800, 'ShanB']].forEach(a => reg(...a));

// ---------- time: the spoken words, on the sample's clock
const T = { step1: .08, w1: .75, w2: 1.13, w3: 1.81, w4: 2.25, you: 2.71, pal: 3.24, pair: 3.76,
  s2: 4.49, four: 4.75, dont: 5.01, wrong: 5.46, wrongEnd: 5.97, right1: 6.10, right2: 6.36, opt1: 7.2, opt2: 7.39, no: 7.77, no2: 7.96, no3: 8.33,
  s3: 8.73, a: 8.91, aTop: 9.64, aTop2: 10.26, only: 10.75, aDays: 11.37, aDays2: 11.68, b: 12.0, bTop: 12.88, bTop2: 13.23, bMade: 13.59, bDays: 13.87, bDays2: 14.16, end: 14.8 };

const clamp = (v, a = 0, b = 1) => v < a ? a : v > b ? b : v;
const lerp = (a, b, u) => a + (b - a) * u;
const pr = (t, a, b) => clamp((t - a) / (b - a));
const E = { out: u => 1 - (1 - u) ** 3, in: u => u ** 3, io: u => u < .5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2,
  back: (u, s = 1.7) => { if (u <= 0) return 0; if (u >= 1) return 1; u -= 1; return 1 + (s + 1) * u ** 3 + s * u ** 2; },
  elastic: u => u <= 0 ? 0 : u >= 1 ? 1 : 2 ** (-10 * u) * Math.sin((u * 10 - .75) * (2 * Math.PI) / 3) + 1,
  bounce: u => { const n = 7.5625, d = 2.75; if (u < 1 / d) return n * u * u; if (u < 2 / d) return n * (u -= 1.5 / d) * u + .75; if (u < 2.5 / d) return n * (u -= 2.25 / d) * u + .9375; return n * (u -= 2.625 / d) * u + .984375; } };
function rng(seed) { let s = (seed * 2654435761) >>> 0 || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; }
const hash = (a, b = 0) => { const x = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return x - Math.floor(x); };

// ---------- geometry -> point lists
const line = (x1, y1, x2, y2, n = 14) => Array.from({ length: n + 1 }, (_, i) => [lerp(x1, x2, i / n), lerp(y1, y2, i / n)]);
const ell = (cx, cy, rx, ry = rx, a0 = -Math.PI / 2, a1 = 1.5 * Math.PI, n = 40) => Array.from({ length: n + 1 }, (_, i) => { const a = lerp(a0, a1, i / n); return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]; });
const rectP = (x, y, w, h, r = 0) => { if (!r) return [...line(x, y, x + w, y), ...line(x + w, y, x + w, y + h), ...line(x + w, y + h, x, y + h), ...line(x, y + h, x, y)];
  const q = Math.PI / 2; return [...line(x + r, y, x + w - r, y, 8), ...ell(x + w - r, y + r, r, r, -q, 0, 8), ...line(x + w, y + r, x + w, y + h - r, 8), ...ell(x + w - r, y + h - r, r, r, 0, q, 8), ...line(x + w - r, y + h, x + r, y + h, 8), ...ell(x + r, y + h - r, r, r, q, 2 * q, 8), ...line(x, y + h - r, x, y + r, 8), ...ell(x + r, y + r, r, r, 2 * q, 3 * q, 8)]; };
function spline(p, n = 12) { const o = []; for (let i = 0; i < p.length - 1; i++) { const a = p[Math.max(0, i - 1)], b = p[i], c = p[i + 1], d = p[Math.min(p.length - 1, i + 2)];
  for (let k = 0; k < n; k++) { const t = k / n, t2 = t * t, t3 = t2 * t; o.push([0, 1].map(j => .5 * (2 * b[j] + (c[j] - a[j]) * t + (2 * a[j] - 5 * b[j] + 4 * c[j] - d[j]) * t2 + (3 * b[j] - a[j] - 3 * c[j] + d[j]) * t3))); } } o.push(p[p.length - 1]); return o; }
function resample(p, step = 6) { const o = [p[0]]; let acc = 0; for (let i = 1; i < p.length; i++) { let [x0, y0] = p[i - 1], [x1, y1] = p[i]; let d = Math.hypot(x1 - x0, y1 - y0); if (!d) continue; let q = step - acc; while (q <= d) { o.push([lerp(x0, x1, q / d), lerp(y0, y1, q / d)]); q += step; } acc = d - (q - step); } o.push(p[p.length - 1]); return o; }
function jitter(p, amp, seed) { if (!amp) return p; const f1 = .11, f2 = .31; return p.map(([x, y], i) => [x + amp * (Math.sin(i * f1 * 2 + seed * 7.3) * .6 + Math.sin(i * f2 * 2 + seed * 3.1) * .4), y + amp * (Math.sin(i * f1 * 2.1 + seed * 5.9 + 2) * .6 + Math.sin(i * f2 * 1.9 + seed * 2.3) * .4)]); }
const trace = (c, p) => { c.beginPath(); c.moveTo(p[0][0], p[0][1]); for (let i = 1; i < p.length; i++) c.lineTo(p[i][0], p[i][1]); };
const part = (p, u) => u >= 1 ? p : p.slice(0, Math.max(2, Math.ceil(p.length * u)));

// ---------- pens: (ctx, pts, {w, c, seed, a})
const pens = {
  marker(c, p, o) { c.save(); c.globalAlpha *= o.a ?? 1; c.strokeStyle = o.c; c.lineWidth = o.w; c.lineCap = 'round'; c.lineJoin = 'round'; trace(c, p); c.stroke(); c.restore(); },
  pen(c, p, o) { c.save(); c.globalAlpha *= (o.a ?? 1) * .92; c.strokeStyle = o.c; c.lineCap = 'round'; c.lineJoin = 'round'; c.lineWidth = o.w; trace(c, p); c.stroke(); c.globalAlpha *= .45; c.lineWidth = o.w * .6; trace(c, p.map(([x, y], i) => [x + Math.sin(i * .5 + o.seed) * 1.2, y + Math.cos(i * .4 + o.seed) * 1.2])); c.stroke(); c.restore(); },
  chalk(c, p, o) { const r = rng(Math.floor(o.seed * 97) + 3); const q = resample(p, 2.2); c.save(); c.fillStyle = o.c; const A = (o.a ?? 1); c.globalAlpha = A * .34; c.strokeStyle = o.c; c.lineWidth = o.w * .72; c.lineCap = 'round'; c.lineJoin = 'round'; trace(c, p); c.stroke();
    for (const [x, y] of q) { for (let k = 0; k < 5; k++) { const d = (r() + r() - 1) * o.w * .62, e = (r() - .5) * o.w * .5; const z = r() * 2.6 + .7; c.globalAlpha = A * (.35 + r() * .6); c.fillRect(x + d, y + e, z, z); } if (r() < .12) { c.globalAlpha = A * .22; c.fillRect(x + (r() - .5) * o.w * 3.2, y + (r() - .5) * o.w * 3.2, 1.5, 1.5); } } c.restore(); },
  neon(c, p, o) { c.save(); c.lineCap = 'round'; c.lineJoin = 'round'; c.globalCompositeOperation = 'lighter'; const A = o.a ?? 1; c.strokeStyle = o.c; for (const [b, w, a] of [[46, 1.6, .5], [18, 1.15, .75]]) { c.globalAlpha = A * a; c.shadowColor = o.c; c.shadowBlur = b; c.lineWidth = o.w * w; trace(c, p); c.stroke(); } c.shadowBlur = 0; c.globalAlpha = A; c.globalCompositeOperation = 'source-over'; c.strokeStyle = o.core || '#fff'; c.lineWidth = o.w * .5; trace(c, p); c.stroke(); c.restore(); },
  rough(c, p, o) { c.save(); c.strokeStyle = o.c; c.lineWidth = o.w; c.lineCap = 'round'; c.lineJoin = 'round'; c.globalAlpha *= o.a ?? 1; for (const s of [1, 2]) { const q = jitter(p, 2.6, o.seed * 1.7 + s * 4.1); trace(c, q); c.stroke(); c.globalAlpha *= .8; } c.restore(); },
  tech(c, p, o) { c.save(); c.globalAlpha *= o.a ?? 1; c.strokeStyle = o.c; c.lineWidth = o.w; c.lineCap = 'butt'; c.lineJoin = 'miter'; if (o.dash) c.setLineDash(o.dash); trace(c, p); c.stroke(); c.restore(); },
};

// ---------- sketcher: draw-on + boil on top of a pen
class Sk {
  constructor(c, t, o) { this.c = c; this.t = t; this.o = o; this.boil = o.boilFps ? Math.floor(t * o.boilFps) : 0; this.n = 0; }
  path(pts, t0 = -1, t1 = -1, o = {}) { const u = t1 < 0 ? 1 : pr(this.t, t0, t1); if (u <= 0) return this; const id = ++this.n; const st = { w: this.o.w, c: this.o.ink, ...o };
    const seed = id * 1.37 + (this.o.boilAmt ? (this.boil % 3) * 11.1 : 0); let p = resample(pts, this.o.step || 7); p = jitter(p, (o.amp ?? this.o.amp ?? 2), id * 2.3 + (this.boil % 3) * (this.o.boilAmt || 0)); p = part(p, E.out(u));
    if (p.length > 1) (pens[o.pen || this.o.pen])(this.c, p, { ...st, seed }); return this; }
  line(x1, y1, x2, y2, t0, t1, o) { return this.path(line(x1, y1, x2, y2), t0, t1, o); }
  rect(x, y, w, h, t0, t1, o = {}) { return this.path(rectP(x, y, w, h, o.r || 0), t0, t1, o); }
  circ(x, y, r, t0, t1, o) { return this.path(ell(x, y, r), t0, t1, o); }
  ell(x, y, rx, ry, t0, t1, o) { return this.path(ell(x, y, rx, ry), t0, t1, o); }
  cross(x, y, s, t0, o = {}) { this.line(x - s, y - s, x + s, y + s, t0, t0 + .14, o); return this.line(x + s, y - s, x - s, y + s, t0 + .12, t0 + .26, o); }
  arrow(p, t0, t1, o = {}) { this.path(p, t0, t1, o); const [x, y] = p[p.length - 1], [a, b] = p[Math.max(0, p.length - 4)]; const an = Math.atan2(y - b, x - a), L = o.head || 46; this.line(x, y, x - Math.cos(an - .5) * L, y - Math.sin(an - .5) * L, t1 - .02, t1 + .1, o); return this.line(x, y, x - Math.cos(an + .5) * L, y - Math.sin(an + .5) * L, t1 - .02, t1 + .12, o); }
  // stick figure. pose: {la, ra: arm angles, ll, rl: leg angles, lean}; degrees from straight down
  fig(x, y, h, pose = {}, t0 = -1, t1 = -1, o = {}) { const d = a => a * Math.PI / 180, hr = h * .15, hipY = y - h * .42, shY = y - h * .72, lean = (pose.lean || 0) * h; const hx = x + lean, hy = shY - hr * 1.25;
    const A = (pose.la ?? 25), B = (pose.ra ?? -25), L = (pose.ll ?? 14), R = (pose.rl ?? -14), s = t1 > 0 ? (t1 - t0) / 5 : 0, tt = i => t1 > 0 ? [t0 + s * i, t0 + s * (i + 1.3)] : [-1, -1];
    this.circ(hx, hy, hr, ...tt(0), o); this.line(hx, shY - hr * .25, x, hipY, ...tt(1), o); const sx = x + lean * .8, sy = shY + h * .05;
    for (const [a, e] of [[A, pose.lb ?? 10], [B, pose.rb ?? -10]]) { const ex = sx + Math.sin(d(a)) * -h * .17, ey = sy + Math.cos(d(a)) * h * .17; this.path([...line(sx, sy, ex, ey, 6), ...line(ex, ey, ex + Math.sin(d(a + e)) * -h * .17, ey + Math.cos(d(a + e)) * h * .17, 6)], ...tt(2), o); }
    for (const a of [L, R]) this.path([...line(x, hipY, x + Math.sin(d(a)) * -h * .42, y, 8)], ...tt(3), o);
    if (pose.face) { const e = hr * .34; this.line(hx - e, hy - e * .4, hx - e, hy + e * .25, ...tt(4), { ...o, w: (o.w || this.o.w) * .8 }); this.line(hx + e, hy - e * .4, hx + e, hy + e * .25, ...tt(4), { ...o, w: (o.w || this.o.w) * .8 }); const m = pose.face === 'sad' ? ell(hx, hy + hr * .62, hr * .38, hr * .24, Math.PI * 1.15, Math.PI * 1.85, 10) : pose.face === 'flat' ? line(hx - e, hy + hr * .42, hx + e, hy + hr * .42, 5) : ell(hx, hy + hr * .2, hr * .46, hr * .36, Math.PI * .12, Math.PI * .88, 10); this.path(m, ...tt(4), { ...o, w: (o.w || this.o.w) * .8 }); } return this; }
  phone(x, y, w, h, t0, t1, o = {}) { this.rect(x - w / 2, y - h / 2, w, h, t0, t1, { r: w * .16, ...o }); return this.line(x - w * .14, y - h / 2 + h * .07, x + w * .14, y - h / 2 + h * .07, t1 - .05, t1 + .05, o); }
}

// ---------- type: word-synced, stable layout. ws = [[text, time, {c, size}]]; '\n' forces a break
function layout(c, ws, font, size, maxW, lh = 1.08, sp = .26) { const lines = [[]]; let lw = 0; for (const w of ws) { if (w[0] === '\n') { lines.push([]); lw = 0; continue; } const s = (w[2] && w[2].size || 1) * size; c.font = `${s}px "${w[2] && w[2].font || font}"`; const m = c.measureText(w[0]).width; const gap = lines[lines.length - 1].length ? s * sp : 0; if (lw + gap + m > maxW && lines[lines.length - 1].length) { lines.push([]); lw = 0; } lines[lines.length - 1].push({ txt: w[0], t: w[1], o: w[2] || {}, w: m, s }); lw += (lines[lines.length - 1].length > 1 ? s * sp : 0) + m; } return lines; }
function words(c, ws, x, y, o, t) { const { font, size, color = '#fff', maxW = 900, align = 'center', lh = 1.08, reveal = 'pop', sp = .26, draw } = o; const lines = layout(c, ws, font, size, maxW, lh, sp); let yy = y; const out = [];
  for (const ln of lines) { const ms = Math.max(...ln.map(w => w.s)); const tot = ln.reduce((a, w, i) => a + w.w + (i ? w.s * sp : 0), 0); let xx = align === 'center' ? x - tot / 2 : align === 'right' ? x - tot : x; for (const w of ln) { out.push({ ...w, x: xx, y: yy + ms * .8, cx: xx + w.w / 2, cy: yy + ms * .45 }); xx += w.w + w.s * sp; } yy += ms * lh; }
  for (const w of out) { const age = t - w.t; if (age < 0) continue; c.save(); c.font = `${w.s}px "${w.o.font || font}"`; c.fillStyle = w.o.c || color; c.textBaseline = 'alphabetic';
    if (draw) { draw(c, w, age); c.restore(); continue; }
    if (reveal === 'write') { const d = .05 * w.txt.length + .08, u = clamp(age / d); c.beginPath(); c.rect(w.x - 20, w.y - w.s * 1.2, (w.w + 40) * u, w.s * 1.8); c.clip(); c.fillText(w.txt, w.x, w.y); }
    else if (reveal === 'pop') { const u = clamp(age / .2), k = lerp(.4, 1, E.back(u, 2.2)); c.globalAlpha *= clamp(age / .06); c.translate(w.cx, w.cy); c.scale(k, k); c.translate(-w.cx, -w.cy); c.fillText(w.txt, w.x, w.y); }
    else if (reveal === 'stamp') { const u = clamp(age / .14), k = lerp(1.9, 1, E.out(u)); c.globalAlpha *= clamp(age / .07); c.translate(w.cx, w.cy); c.scale(k, k); c.translate(-w.cx, -w.cy); c.fillText(w.txt, w.x, w.y); }
    else if (reveal === 'rise') { const u = E.out(clamp(age / .28)); c.beginPath(); c.rect(w.x - 10, w.y - w.s * 1.05, w.w + 20, w.s * 1.35); c.clip(); c.fillText(w.txt, w.x, w.y + (1 - u) * w.s * 1.1); }
    else if (reveal === 'type') { const n = Math.floor(age / .035) + 1; c.fillText(w.txt.slice(0, n), w.x, w.y); }
    else c.fillText(w.txt, w.x, w.y); c.restore(); } return { lines, bottom: yy, items: out }; }
function txt(c, s, x, y, font, size, color, align = 'center', a = 1) { c.save(); c.globalAlpha *= a; c.font = `${size}px "${font}"`; c.fillStyle = color; c.textAlign = align; c.textBaseline = 'middle'; c.fillText(s, x, y); c.restore(); }

// ---------- misc
const layer = (w = W, h = H) => { const k = createCanvas(w, h); return [k, k.getContext('2d')]; };
const cache = {}; function cached(key, w, h, fn) { if (!cache[key]) { const [k, x] = layer(w, h); fn(x, k); cache[key] = k; } return cache[key]; }
function noiseTex(key, w, h, a, seed, mono = 0, dark = false) { return cached(key, w, h, x => { const d = x.createImageData(w, h), r = rng(seed); for (let i = 0; i < w * h; i++) { const v = dark ? 0 : r() * 255; d.data[i * 4] = d.data[i * 4 + 1] = d.data[i * 4 + 2] = v; d.data[i * 4 + 3] = r() * a; } x.putImageData(d, 0, 0); }); }
const money = v => '$' + Math.round(v).toLocaleString('en-US');

module.exports = { W, H, T, clamp, lerp, pr, E, rng, hash, line, ell, rectP, spline, resample, jitter, trace, part, pens, Sk, layout, words, txt, layer, cached, noiseTex, money, createCanvas, loadImage, Path2D, fs, path };
