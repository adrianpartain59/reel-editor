// node render.js sheet [id,id]      -> sheets/<id>.jpg (12 stills per style)
// node render.js film id             -> film/<id>.mp4 (14.8 s, 720x1280, silent unless audio/voice.m4a exists)
const K = require('./kit'); const { spawn } = require('child_process'); const fs = require('fs'); const path = require('path');
const all = []; for (const f of fs.readdirSync(__dirname).filter(f => /^s_.*\.js$/.test(f)).sort()) all.push(...require('./' + f).list);
const VOICE = path.join(__dirname, 'audio/voice.m4a');
const FPS = 30, N = Math.round(K.T.end * FPS);
const STILLS = [.3, 1.0, 1.9, 2.5, 3.3, 4.2, 5.2, 5.75, 6.3, 7.1, 7.7, 8.5, 9.2, 10.0, 11.6, 12.4, 13.3, 14.5];
async function draw(st, c, n) { const x = c.getContext('2d'); x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.globalCompositeOperation = 'source-over'; x.shadowBlur = 0; x.filter = 'none'; x.clearRect(0, 0, K.W, K.H); const hold = st.hold ? Math.floor(n / st.hold) * st.hold : n; await st.frame(x, hold / FPS); }
async function sheet(ids) { fs.mkdirSync(path.join(__dirname, 'sheets'), { recursive: true }); for (const st of all.filter(s => !ids || ids.includes(s.id))) { const w = 240, h = 427, cols = 9, rows = 2; const S = K.createCanvas(w * cols, h * rows), sx = S.getContext('2d'); const c = K.createCanvas(K.W, K.H); const t0 = Date.now(); let i = 0;
  if (st.stateful) { const want = new Set(STILLS.map(t => Math.round(t * FPS))); for (let n = 0; n < N; n++) { await draw(st, c, n); if (want.has(n)) { sx.drawImage(c, (i % cols) * w, Math.floor(i / cols) * h, w, h); i++; } } }
  else for (const t of STILLS) { await draw(st, c, Math.round(t * FPS)); sx.drawImage(c, (i % cols) * w, Math.floor(i / cols) * h, w, h); i++; }
  fs.writeFileSync(path.join(__dirname, 'sheets', st.id + '.jpg'), S.toBuffer('image/jpeg', 88)); console.log(st.id, Math.round((Date.now() - t0) / STILLS.length) + 'ms/frame'); } }
async function film(id) { const st = all.find(s => s.id === id); fs.mkdirSync(path.join(__dirname, 'film'), { recursive: true }); const out = path.join(__dirname, 'film', id + '.mp4');
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${K.W}x${K.H}`, '-r', String(FPS), '-i', '-', ...(fs.existsSync(VOICE) ? ['-i', VOICE, '-c:a', 'copy', '-shortest'] : []), '-vf', 'scale=720:1280:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '21', '-preset', 'medium', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const c = K.createCanvas(K.W, K.H); for (let n = 0; n < N; n++) { await draw(st, c, n); const buf = c.data(); if (!ff.stdin.write(Buffer.from(buf))) await new Promise(r => ff.stdin.once('drain', r)); }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); console.log('film', id, (fs.statSync(out).size / 1e6).toFixed(1) + 'MB'); }
(async () => { const [, , cmd, arg] = process.argv; if (cmd === 'sheet') await sheet(arg && arg.split(',')); else if (cmd === 'film') await film(arg); else if (cmd === 'list') console.log(all.map(s => s.id).join(' ')); })().catch(e => { console.error(e); process.exit(1); });
