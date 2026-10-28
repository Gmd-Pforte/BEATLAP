// Browser-Regressionstests für die echten Instrumente (Playwright + Chromium).
// Aufruf:  node tests/real-instruments.browser.mjs   (vorher einmal: npm i playwright && npx playwright install chromium)
// Startet einen kleinen Webserver auf dem Repo-Ordner und prüft:
//   1. Offline direkt nach der Installation: Verzeichnis + Sampler kommen aus dem Service-Worker-Cache
//   2. Verzeichnis blockiert: gespeichertes Projekt behält „fluteReal“ (Ersatzklang), danach online wieder echt
//   3. Varianten (Round-Robin) hängen nicht vom Startzeitpunkt ab: Live = Export
//   4. Fallback bei fehlenden Flöten-Samples, Speicherbedarf der dekodierten Samples
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
// require() statt import, damit auch eine global installierte Playwright-Version gefunden wird (NODE_PATH)
const { chromium } = createRequire(import.meta.url)('playwright');

const ROOT = new URL('..', import.meta.url).pathname;
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.md': 'text/markdown' };
const server = createServer(async (req, res) => {
  try {
    const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^(\.\.[/\\])+/, '');
    const file = join(ROOT, path.endsWith('/') ? path + 'index.html' : path);
    const body = await readFile(file);
    res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' }); res.end(body);
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(ok => server.listen(0, '127.0.0.1', ok));
const BASE = `http://localhost:${server.address().port}/index.html`;
const results = [];
const check = async (name, fn) => { await fn(); results.push(name); console.log('  ✓ ' + name); };

const browser = await chromium.launch();
const _newContext = browser.newContext.bind(browser);
// Externe Server (Schriften, CDN) im Test abschalten: Ergebnis soll nur vom Repo abhängen
browser.newContext = async (o) => { const c = await _newContext(o); await c.route(u => !u.hostname.startsWith('localhost'), r => r.abort()); c.setDefaultTimeout(20000); return c; };
try {
  await check('Offline direkt nach der Installation: Verzeichnis und Sampler aus dem Cache', async () => {
    const ctx = await browser.newContext(); const page = await ctx.newPage();
    await page.goto(BASE);
    // Beatlab registriert den Service Worker nur unter https (GitHub Pages); im Test über localhost manuell
    await page.evaluate(async () => { await navigator.serviceWorker.register('./sw.js'); await navigator.serviceWorker.ready; });
    await page.reload(); await page.waitForFunction(() => !!navigator.serviceWorker.controller);
    await ctx.setOffline(true);
    await page.reload();
    const r = await page.evaluate(() => ({ reg: (window.PSRealInstruments || []).map(x => x.id), sampler: !!window.PSSampler }));
    assert.ok(r.sampler, 'sampler.js fehlt offline');
    assert.ok(r.reg.includes('grandReal') && r.reg.includes('fluteReal'), 'Verzeichnis fehlt offline: ' + JSON.stringify(r.reg));
    await ctx.close();
  });

  await check('Verzeichnis fehlt: Projekt behält „fluteReal“, keine Fehler, Anzeige „nicht verfügbar“; danach online wieder echt', async () => {
    const ctx = await browser.newContext(); const page = await ctx.newPage();
    await page.goto(BASE);
    // Projekt mit echter Flöte speichern (gleicher Weg wie die App: localStorage beatlab.v2)
    await page.evaluate(() => { [...document.querySelectorAll('button')].find(x => x.textContent.trim().startsWith('Boom Bap')).click(); }); // speichert ein Projekt
    await page.evaluate(() => { const p = JSON.parse(localStorage.getItem('beatlab.v2') || 'null'); if (!p) throw Error('kein Projekt');
      p.params.lead.snd = 'fluteReal'; localStorage.setItem('beatlab.v2', JSON.stringify(p)); });
    await page.route('**/samples/real/index.js', r => r.abort());
    const errors = []; page.on('pageerror', e => errors.push(String(e)));
    await page.reload(); await page.waitForTimeout(500);
    const off = await page.evaluate(() => ({ reg: (window.PSRealInstruments || []).length, snd: JSON.parse(localStorage.getItem('beatlab.v2')).params.lead.snd,
      label: [...document.querySelectorAll('.pad small')].map(x => x.textContent) }));
    assert.equal(off.reg, 0, 'Test-Aufbau: Verzeichnis sollte blockiert sein');
    assert.equal(off.snd, 'fluteReal', 'Projekt-Einstellung wurde überschrieben');
    assert.deepEqual(errors, [], 'JavaScript-Fehler: ' + errors.join(' | '));
    assert.ok(off.label.some(x => /nicht verfügbar/.test(x)), 'Melodie-Pad zeigt nicht „nicht verfügbar“: ' + JSON.stringify(off.label));
    await page.unroute('**/samples/real/index.js');
    await page.reload(); await page.waitForTimeout(300);
    const on = await page.evaluate(() => ({ snd: JSON.parse(localStorage.getItem('beatlab.v2')).params.lead.snd, ok: window.PSSampler.supports('fluteReal') }));
    assert.equal(on.snd, 'fluteReal'); assert.ok(on.ok);
    await ctx.close();
  });

  await check('Varianten unabhängig vom Startzeitpunkt (Live = Export)', async () => {
    const ctx = await browser.newContext(); const page = await ctx.newPage(); await page.goto(BASE);
    const same = await page.evaluate(async () => {
      await PSSampler.load('fluteReal');
      // 8 kurze A4-Noten (Staccato mit 2 Varianten), einmal ab 0 s, einmal ab 3,7 s (wie Live mit anderer Startzeit)
      async function render(t0) { const oc = new OfflineAudioContext(1, 44100 * (t0 + 3), 44100), st = {};
        for (let i = 0; i < 8; i++) PSSampler.play(oc, oc.destination, 'fluteReal', 440, t0 + i * 0.3, 0.12, 0.25, st);
        const d = (await oc.startRendering()).getChannelData(0); return d.slice(Math.round(t0 * 44100), Math.round((t0 + 2.6) * 44100)); }
      const a = await render(0), b = await render(3.7); let diff = 0, e = 0;
      for (let i = 0; i < a.length; i++) { diff = Math.max(diff, Math.abs(a[i] - b[i])); e = Math.max(e, Math.abs(a[i])); }
      return { diff, e };
    });
    assert.ok(same.e > 0.01, 'stumm');
    assert.ok(same.diff < 1e-3, 'Varianten hängen vom Startzeitpunkt ab, max. Abweichung ' + same.diff);
    await ctx.close();
  });

  await check('Fehlende Flöten-Samples: Ersatzklang, Export nicht stumm; Speicherbedarf gemeldet', async () => {
    const ctx = await browser.newContext(); const page = await ctx.newPage();
    await page.route('**/samples/real/flute/*.mp3', r => r.abort());
    await page.goto(BASE);
    const r = await page.evaluate(async () => {
      const failed = await PSSampler.ensure(['fluteReal']);
      const oc = new OfflineAudioContext(1, 44100, 44100);
      const played = PSSampler.play(oc, oc.destination, 'fluteReal', 440, 0, 0.5, 0.25, {});
      return { failed, played, status: PSSampler.status('fluteReal') };
    });
    assert.deepEqual(r.failed, ['fluteReal']); assert.equal(r.played, false, 'darf nicht spielen, sonst kein Ersatzklang'); assert.equal(r.status, 'error');
    await ctx.close();
    const ctx2 = await browser.newContext(); const p2 = await ctx2.newPage(); await p2.goto(BASE);
    const mem = await p2.evaluate(async () => { const out = {};
      for (const id of ['grandReal', 'fluteReal']) { await PSSampler.load(id); out[id] = [PSSampler.decodedMB(id)]; }
      await PSSampler.ensure(['grandReal', 'fluteReal'], true);
      for (const id of ['grandReal', 'fluteReal']) out[id].push(PSSampler.decodedMB(id)); return out; });
    console.log('    Speicher dekodiert (Wiedergabe → Export mit allen Stufen): ' + Object.entries(mem).map(([k, [a, b]]) => `${k} ${a.toFixed(1)} → ${b.toFixed(1)} MB`).join(', '));
    assert.ok(mem.grandReal[0] < mem.grandReal[1], 'Stufen werden nicht einzeln geladen');
    await ctx2.close();
  });
} finally {
  await browser.close(); server.close();
}
console.log(`\n${results.length} Browser-Prüfungen bestanden.`);
