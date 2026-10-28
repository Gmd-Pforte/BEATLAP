/* PS Beatlab Sampler 1.0 (Claude)
 * Spielt echte, mehrschichtige Instrumenten-Samples (zuerst: „Flügel (echt)“, Salamander Grand Piano).
 * - Lädt erst bei Bedarf (lazy), AudioBuffer werden einmal dekodiert und für Live-Wiedergabe
 *   UND Offline-WAV-Export geteilt (AudioBuffer sind nicht an einen AudioContext gebunden).
 * - Nächster Grundton, höchstens maxShift Halbtöne gepitcht, Anschlagstärke wählt die Dynamikstufe.
 * - Ist ein Instrument (noch) nicht geladen, gibt play() false zurück → Beatlab nutzt den Synth-Fallback.
 */
(function (root) {
  'use strict';

  const BASE = './samples/real/';
  const INSTRUMENTS = { grandReal: 'piano' };   // Beatlab-Instrument-ID → Ordner

  const state = {};   // id → { status: 'idle'|'loading'|'ready'|'error', manifest, layers, promise, error }

  function decoderContext() {
    const C = root.OfflineAudioContext || root.webkitOfflineAudioContext;
    return new C(2, 1, 44100);
  }

  // MP3/AAC-Encoder setzen etwas Stille vor den Ton. Wir suchen den echten Anschlag beim Laden.
  function onsetOf(buf) {
    const d = buf.getChannelData(0), n = Math.min(d.length, Math.floor(buf.sampleRate * 0.15));
    let peak = 0;
    for (let i = 0; i < d.length; i++) { const a = Math.abs(d[i]); if (a > peak) peak = a; }
    const th = Math.max(0.0005, peak * 0.02);
    for (let i = 0; i < n; i++) if (Math.abs(d[i]) > th) return Math.max(0, i - Math.floor(buf.sampleRate * 0.002)) / buf.sampleRate;
    return 0;
  }

  async function fetchBuffer(dec, url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Sample fehlt: ' + url + ' (HTTP ' + res.status + ')');
    const ab = await res.arrayBuffer();
    return await new Promise((ok, fail) => {
      const p = dec.decodeAudioData(ab, ok, fail);
      if (p && p.then) p.then(ok, fail);
    });
  }

  async function loadInstrument(id) {
    const dir = BASE + INSTRUMENTS[id] + '/';
    const res = await fetch(dir + 'manifest.json');
    if (!res.ok) throw new Error('Manifest fehlt (HTTP ' + res.status + ')');
    const manifest = await res.json();
    if (manifest.format !== 'beatlab-sampler-1') throw new Error('Unbekanntes Sampler-Format');
    const dec = decoderContext();
    const layers = [];
    // Mittlere Dynamikstufe zuerst, dann die anderen – parallel, aber begrenzt
    const order = [...manifest.layers].sort((a, b) => (a.name === 'mf' ? -1 : b.name === 'mf' ? 1 : 0));
    for (const layer of order) {
      const notes = [];
      const jobs = layer.notes.map(n => async () => {
        const buffer = await fetchBuffer(dec, dir + encodeURIComponent(n.file));
        notes.push({ midi: n.midi, tune: n.tune || 0, buffer, offset: onsetOf(buffer) });
      });
      const queue = jobs.slice();
      await Promise.all(Array.from({ length: 6 }, async () => { while (queue.length) await queue.shift()(); }));
      notes.sort((a, b) => a.midi - b.midi);
      layers.push({ name: layer.name, velMax: layer.velMax, notes });
    }
    layers.sort((a, b) => a.velMax - b.velMax);
    return { manifest, layers };
  }

  function load(id) {
    if (!INSTRUMENTS[id]) return Promise.reject(new Error('Kein Sampler-Instrument: ' + id));
    const s = state[id] || (state[id] = { status: 'idle' });
    if (s.status === 'ready') return Promise.resolve(s);
    if (s.status === 'loading') return s.promise;
    s.status = 'loading';
    s.promise = loadInstrument(id).then(r => {
      Object.assign(s, r, { status: 'ready', error: null });
      try { root.dispatchEvent(new CustomEvent('ps-sampler', { detail: { id, status: 'ready' } })); } catch (e) {}
      return s;
    }, err => {
      s.status = 'error'; s.error = err;
      try { root.dispatchEvent(new CustomEvent('ps-sampler', { detail: { id, status: 'error', error: err } })); } catch (e) {}
      throw err;
    });
    return s.promise;
  }

  function nearest(notes, midi) {
    let best = notes[0];
    for (const n of notes) if (Math.abs(n.midi - midi) < Math.abs(best.midi - midi)) best = n;
    return best;
  }

  /* v: Beatlab-Lautstärke (typisch 0,1–0,45). Wird auf 0–1 normiert für die Dynamikstufe. */
  function play(ctx, out, id, freq, t, dur, v) {
    const s = state[id];
    if (!s || s.status !== 'ready') { if (!s || s.status === 'idle') load(id).catch(() => {}); return false; }
    const midi = 69 + 12 * Math.log2(freq / 440);
    const vel = Math.max(0, Math.min(1.2, v / 0.3));
    const layer = s.layers.find(l => vel <= l.velMax) || s.layers[s.layers.length - 1];
    const n = nearest(layer.notes, midi);
    const src = ctx.createBufferSource();
    src.buffer = n.buffer;
    src.detune.value = (midi - n.midi) * 100 + n.tune;   // SFZ „tune“: Korrektur in Cent, positiv = höher
    const g = ctx.createGain();
    const level = Math.min(0.8, v * 1.25) * Math.pow(10, (s.manifest.gainDb || 0) / 20);
    const rel = s.manifest.release || 0.35;
    const rate = Math.pow(2, src.detune.value / 1200);
    const natural = (n.buffer.duration - n.offset) / rate;          // Ende des Samples (mit Ausblendung)
    const end = Math.min(t + Math.max(dur, 0.05) + rel, t + natural);
    g.gain.setValueAtTime(level, t);
    g.gain.setValueAtTime(level, Math.max(t, end - rel));
    g.gain.setTargetAtTime(0.0001, Math.max(t, end - rel), rel / 4);  // Dämpfer: weich abklingen
    src.connect(g); g.connect(out);
    src.start(t, n.offset);
    src.stop(end + 0.05);
    return true;
  }

  root.PSSampler = {
    supports: id => !!INSTRUMENTS[id],
    status: id => (state[id] && state[id].status) || 'idle',
    error: id => state[id] && state[id].error,
    manifest: id => state[id] && state[id].manifest,
    load,
    ensure: async ids => {
      const wanted = [...new Set(ids)].filter(id => INSTRUMENTS[id]);
      const results = await Promise.allSettled(wanted.map(load));
      return wanted.filter((id, i) => results[i].status === 'rejected');   // fehlgeschlagene IDs
    },
    play
  };
})(window);
