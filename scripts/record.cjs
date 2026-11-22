// Frame-perfect video (or one still) of a card: the engine's ?rec mode draws frame t on demand, so every frame lands exactly on time.
// It plays a fixed 16 s show: the card builds, tilts, pulls its layers apart, shows them, and closes again.
// usage: node record.cjs <cards-dir> <name> <out.mp4|out.png> [w=1080] [h=1350] [fps=30] [t0=0] [t1=16]
//   env: DPR=2 (draw at 2x, scale down: sharper), Q="pose=0,20&flat" (extra page options), STILL=6 (one PNG at t=6 s)
// needs: npm i playwright && npx playwright install chromium (setup.sh --record), and ffmpeg for video
const { chromium } = require('playwright'), http = require('http'), fs = require('fs'), path = require('path'), os = require('os'), { execFileSync } = require('child_process');
const [ROOTARG, NAME, OUT, W = '1080', H = '1350', FPS = '30', T0 = '0', T1 = '16'] = process.argv.slice(2);
if (!OUT) { console.log('usage: node record.cjs <cards-dir> <name> <out.mp4|out.png> [w h fps t0 t1]'); process.exit(1); }
const ROOT = path.resolve(ROOTARG);
const MIME = { '.html': 'text/html', '.webp': 'image/webp', '.png': 'image/png', '.js': 'text/javascript', '.jpg': 'image/jpeg', '.json': 'application/json', '.mp4': 'video/mp4' };
const srv = http.createServer((q, r) => {
  const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end(); }
  const body = fs.readFileSync(f), type = MIME[path.extname(f)] || 'application/octet-stream', m = /bytes=(\d+)-(\d*)/.exec(q.headers.range || '');
  if (m) { const a = +m[1], b = m[2] ? +m[2] : body.length - 1;   // range requests: the card's videos need them to seek
    r.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${a}-${b}/${body.length}`, 'Accept-Ranges': 'bytes', 'Content-Length': b - a + 1 }); return r.end(body.subarray(a, b + 1)); }
  r.writeHead(200, { 'Content-Type': type, 'Accept-Ranges': 'bytes' }); r.end(body);
}).listen(0);
(async () => { try {
  const port = srv.address().port, args = ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])];
  let b; try { b = await chromium.launch({ channel: 'chrome', headless: true, args }); } catch { b = await chromium.launch({ headless: true, args }); }
  const p = await b.newPage({ viewport: { width: +W, height: +H }, deviceScaleFactor: +(process.env.DPR || 1) });
  p.on('pageerror', e => console.log('PAGEERROR', e.message));
  p.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
  p.on('requestfailed', r => console.log('FAILED', r.url()));
  p.on('response', r => { if (r.status() >= 400) console.log('HTTP', r.status(), r.url()); });
  await p.goto(`http://127.0.0.1:${port}/card.html?c=${encodeURIComponent(NAME)}&rec${process.env.Q ? '&' + process.env.Q : ''}`, { waitUntil: 'load' });
  await p.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
  if (process.env.STILL) {
    await p.evaluate(t => window.__frame(t), +process.env.STILL); await p.screenshot({ path: OUT });
    await b.close(); srv.close(); return console.log('wrote', OUT);
  }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'holocard-')), n = Math.round((+T1 - +T0) * +FPS), t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await p.evaluate(t => window.__frame(t), +T0 + i / +FPS);
    await p.screenshot({ path: path.join(tmp, `f${String(i).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 95 });
    if (i % 60 === 0) console.log(`frame ${i}/${n}  ${((Date.now() - t0) / (i + 1)).toFixed(0)} ms/frame`);
  }
  await b.close(); srv.close();
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-framerate', FPS, '-i', path.join(tmp, 'f%05d.jpg'), '-vf', `scale=${W}:${H}:flags=lanczos`,
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'slow', '-movflags', '+faststart', OUT]);
  fs.rmSync(tmp, { recursive: true }); console.log('wrote', OUT, n, 'frames');
} catch (e) { console.log('ERROR', e.message); process.exit(1); } })();
